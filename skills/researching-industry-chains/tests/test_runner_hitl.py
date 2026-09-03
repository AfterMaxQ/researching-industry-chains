"""Runner HITL 状态字段和终态派生测试。"""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from industry_chain_skills.dataset import DatasetService
from industry_chain_skills.runner import RunnerService, refresh_topic_status
from industry_chain_skills.storage import RunnerStore


NOW = datetime(2026, 9, 3, tzinfo=timezone.utc)


def hitl_topic(
    *,
    status: str = "in_progress",
    auto_phase_finished: bool,
    source_groups: list[dict] | None = None,
    review_status: str | None = None,
) -> dict:
    """创建终态派生所需的最小主题。"""
    reviews = [] if review_status is None else [{"status": review_status}]
    return {
        "status": status,
        "auto_phase_finished": auto_phase_finished,
        "source_groups": source_groups or [],
        "review_items": reviews,
    }


class RunnerHitlTests(unittest.TestCase):
    """验证所有主题创建入口和状态推导。"""

    def test_runner_create_initializes_hitl_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = RunnerStore(Path(tmpdir))
            service = RunnerService(store, clock=lambda: NOW)

            created = service.create("锡膏审核", topic="锡膏")
            state = store.read(created["runner_id"])

        topic = state["topics"][0]
        self.assertFalse(topic["auto_phase_finished"])
        self.assertEqual([], topic["review_items"])

    def test_dataset_topic_insert_initializes_hitl_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = RunnerStore(Path(tmpdir))
            runner = RunnerService(store, clock=lambda: NOW)
            created = runner.create("主题维护", topic="锡膏")
            dataset = DatasetService(store, clock=lambda: NOW)

            inserted = dataset.insert(
                created["runner_id"],
                "topic",
                {"主题": "焊料", "path": ["焊料"], "aliases": []},
                None,
                None,
                None,
                None,
            )

        self.assertFalse(inserted["auto_phase_finished"])
        self.assertEqual([], inserted["review_items"])

    def test_dataset_topic_replace_preserves_hitl_process_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = RunnerStore(Path(tmpdir))
            runner = RunnerService(store, clock=lambda: NOW)
            created = runner.create("主题维护", topic="锡膏")
            runner_id = created["runner_id"]
            topic_id = store.read(runner_id)["topics"][0]["node_id"]
            review = {"review_item_id": "review_1", "status": "pending_review"}

            def prepare(state: dict) -> None:
                current = state["topics"][0]
                current["status"] = "awaiting_review"
                current["auto_phase_finished"] = True
                current["review_items"] = [review]

            store.mutate_state(runner_id, prepare)
            dataset = DatasetService(store, clock=lambda: NOW)

            replaced = dataset.replace(
                runner_id,
                "topic",
                topic_id,
                {"主题": "电子焊料", "path": ["电子焊料"], "aliases": []},
                None,
            )

        self.assertTrue(replaced["auto_phase_finished"])
        self.assertEqual([review], replaced["review_items"])

    def test_finished_topic_with_open_review_awaits_review(self) -> None:
        topic = hitl_topic(
            auto_phase_finished=True,
            review_status="pending_review",
        )
        self.assertEqual("awaiting_review", refresh_topic_status(topic))
        self.assertEqual("awaiting_review", topic["status"])

    def test_finished_topic_with_source_and_no_open_review_completes(self) -> None:
        topic = hitl_topic(
            status="awaiting_review",
            auto_phase_finished=True,
            source_groups=[{"source_group_id": "source_1"}],
            review_status="approved",
        )
        self.assertEqual("completed", refresh_topic_status(topic))

    def test_finished_topic_without_source_or_open_review_has_no_source(self) -> None:
        topic = hitl_topic(
            status="awaiting_review",
            auto_phase_finished=True,
            review_status="rejected",
        )
        self.assertEqual("no_qualified_source", refresh_topic_status(topic))

    def test_unfinished_topic_keeps_its_current_status(self) -> None:
        topic = hitl_topic(
            auto_phase_finished=False,
            review_status="pending_review",
        )
        self.assertEqual("in_progress", refresh_topic_status(topic))


if __name__ == "__main__":
    unittest.main()
