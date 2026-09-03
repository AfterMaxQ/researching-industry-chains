"""Human review 状态机和原子正式写入测试。"""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from industry_chain_skills.errors import ClientError
from industry_chain_skills.review import ReviewService
from industry_chain_skills.runner import RunnerService
from industry_chain_skills.storage import RunnerStore


NOW = datetime(2026, 9, 3, tzinfo=timezone.utc)
STAMP = NOW.isoformat()


def review_result() -> dict:
    """创建带来源级和企业 occurrence 不确定性的完整 review。"""
    return {
        "outcome": "review",
        "source": {"name": "示例研究院", "url": "https://example.com/report"},
        "description": "部分企业归属仍需确认。",
        "chain": [
            {
                "name": "上游",
                "children": [
                    {
                        "name": "锡粉",
                        "companies": ["甲公司"],
                        "uncertainties": [
                            {
                                "company": "甲公司",
                                "message": "连接关系不清楚。",
                                "evidence": [
                                    {
                                        "locator": "PDF 第 17 页图 5",
                                        "description": "企业名称位于锡粉节点附近。",
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
        "uncertainties": [{"message": "需要确认来源是否遍历完整。"}],
    }


class ReviewServiceTests(unittest.TestCase):
    """验证 review_item 始终是同一个轻量审核对象。"""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.store = RunnerStore(Path(self.tempdir.name))
        runner = RunnerService(self.store, clock=lambda: NOW)
        created = runner.create("锡膏审核", topic="锡膏")
        self.runner_id = created["runner_id"]
        self.service = ReviewService(
            self.store,
            clock=lambda: NOW,
            review_id_factory=lambda: "review_test",
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def create_review(self, auto_phase_finished: bool = False) -> dict:
        """在真实 Runner 事务中创建一条审核。"""
        def mutation(state: dict) -> dict:
            topic = state["topics"][0]
            topic["auto_phase_finished"] = auto_phase_finished
            if auto_phase_finished:
                topic["status"] = "awaiting_review"
            return self.service.create_in_state(topic, review_result(), STAMP)

        return self.store.mutate_state(self.runner_id, mutation)

    def test_create_in_state_builds_lightweight_review_item(self) -> None:
        review = self.create_review()

        self.assertEqual("review_test", review["review_item_id"])
        self.assertEqual("pending_review", review["status"])
        self.assertEqual(1, review["version"])
        self.assertIsNone(review["agent_claim"])
        self.assertEqual(review_result()["uncertainties"], review["uncertainties"])
        self.assertNotIn("outcome", review)
        self.assertNotIn("draft_records", review)
        self.assertNotIn("draft_tree", review)
        self.assertEqual("review_created", review["events"][0]["type"])

    def test_approve_rejects_stale_version(self) -> None:
        review = self.create_review(auto_phase_finished=True)

        with self.assertRaises(ClientError) as error:
            self.service.approve(
                self.runner_id,
                review["review_item_id"],
                2,
                "最终来源说明",
                review["chain"],
            )

        self.assertEqual("REVIEW_VERSION_CONFLICT", error.exception.code)
        state = self.store.read(self.runner_id)
        self.assertEqual("pending_review", state["topics"][0]["review_items"][0]["status"])

    def test_empty_chain_cannot_be_approved(self) -> None:
        review = self.create_review(auto_phase_finished=True)

        with self.assertRaises(ClientError) as error:
            self.service.approve(
                self.runner_id,
                review["review_item_id"],
                1,
                "最终来源说明",
                [],
            )

        self.assertEqual("REVIEW_EMPTY_CHAIN", error.exception.code)

    def test_approve_strips_uncertainties_and_atomically_writes_formal_group(self) -> None:
        review = self.create_review(auto_phase_finished=True)

        result = self.service.approve(
            self.runner_id,
            review["review_item_id"],
            1,
            "最终来源说明",
            review["chain"],
        )

        self.assertEqual("approved", result["review"]["status"])
        self.assertEqual(2, result["review"]["version"])
        self.assertNotIn(
            "uncertainties",
            result["review"]["chain"][0]["children"][0],
        )
        records = [row["record"] for row in result["source_group"]["rows"]]
        self.assertEqual(["上游", "上游"], [row["分类1"] for row in records])
        self.assertEqual(["", "锡粉"], [row["分类2"] for row in records])
        self.assertEqual("最终来源说明", records[0]["备注"])
        state = self.store.read(self.runner_id)
        self.assertEqual("completed", state["topics"][0]["status"])

    def test_approve_rejects_unknown_tree_fields_without_partial_write(self) -> None:
        review = self.create_review(auto_phase_finished=True)
        invalid_chain = review["chain"]
        invalid_chain[0]["unexpected"] = "不能静默丢弃"

        with self.assertRaises(ClientError) as error:
            self.service.approve(
                self.runner_id,
                review["review_item_id"],
                1,
                "最终来源说明",
                invalid_chain,
            )

        self.assertEqual("TREE_NODE_INVALID", error.exception.code)
        state = self.store.read(self.runner_id)
        topic = state["topics"][0]
        self.assertEqual([], topic["source_groups"])
        self.assertEqual("pending_review", topic["review_items"][0]["status"])

    def test_return_to_agent_is_allowed_once_per_version(self) -> None:
        review = self.create_review(auto_phase_finished=True)

        returned = self.service.return_to_agent(
            self.runner_id,
            review["review_item_id"],
            1,
        )
        self.assertEqual("returned_to_agent", returned["status"])
        self.assertEqual(2, returned["version"])

        with self.assertRaises(ClientError) as error:
            self.service.return_to_agent(
                self.runner_id,
                review["review_item_id"],
                2,
            )
        self.assertEqual("REVIEW_ACTION_NOT_ALLOWED", error.exception.code)

    def test_reject_closes_last_review_without_writing_a_source(self) -> None:
        review = self.create_review(auto_phase_finished=True)

        rejected = self.service.reject(
            self.runner_id,
            review["review_item_id"],
            1,
        )

        self.assertEqual("rejected", rejected["status"])
        state = self.store.read(self.runner_id)
        topic = state["topics"][0]
        self.assertEqual("no_qualified_source", topic["status"])
        self.assertEqual([], topic["source_groups"])


if __name__ == "__main__":
    unittest.main()
