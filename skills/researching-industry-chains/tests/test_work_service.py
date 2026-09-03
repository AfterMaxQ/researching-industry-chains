"""统一 WorkService 调度、租约和自动阶段结束测试。"""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from industry_chain_skills.errors import ClientError
from industry_chain_skills.review import ReviewService
from industry_chain_skills.runner import RunnerService
from industry_chain_skills.storage import RunnerStore
from industry_chain_skills.work import WorkService


NOW = datetime(2026, 9, 3, tzinfo=timezone.utc)


def review_result() -> dict:
    """创建最小合法 review SourceResult。"""
    return {
        "outcome": "review",
        "source": {"name": "示例研究院", "url": "https://example.com/review"},
        "description": "来源结构仍需确认。",
        "chain": [{"name": "上游"}],
        "uncertainties": [{"message": "需要确认结构是否完整。"}],
    }


class WorkServiceTests(unittest.TestCase):
    """验证 topic 和 review 使用同一领取入口。"""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.store = RunnerStore(Path(self.tempdir.name))
        self.now = NOW
        runner = RunnerService(self.store, clock=lambda: self.now)
        created = runner.create("统一调度", topic="锡膏")
        self.runner_id = created["runner_id"]
        self.tokens = iter(["token-1", "token-2", "token-3", "token-4"])
        self.work = WorkService(
            self.store,
            clock=lambda: self.now,
            token_factory=lambda: next(self.tokens),
        )
        self.review = ReviewService(
            self.store,
            clock=lambda: self.now,
            review_id_factory=lambda: "review_test",
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def create_review(self) -> dict:
        """在首个主题下创建待审来源。"""
        return self.store.mutate_state(
            self.runner_id,
            lambda state: self.review.create_in_state(
                state["topics"][0],
                review_result(),
                self.now.isoformat(),
            ),
        )

    def test_returned_review_is_claimed_before_pending_topic(self) -> None:
        review = self.create_review()
        self.review.return_to_agent(self.runner_id, review["review_item_id"], 1)

        claimed = self.work.claim_next(self.runner_id, "Codex")

        self.assertEqual("review", claimed["work_type"])
        self.assertEqual("review_test", claimed["work_id"])
        self.assertEqual("token-1", claimed["claim_token"])
        self.assertEqual("锡膏", claimed["topic"]["主题"])
        self.assertEqual(review_result()["source"], claimed["review"]["source"])
        state = self.store.read(self.runner_id)
        stored = state["topics"][0]["review_items"][0]
        self.assertEqual("in_agent", stored["status"])
        self.assertEqual("Codex", stored["agent_claim"]["worker_label"])
        self.assertEqual("review_claimed", stored["events"][-1]["type"])

    def test_expired_review_claim_is_recovered_before_pending_topic(self) -> None:
        review = self.create_review()
        self.review.return_to_agent(self.runner_id, review["review_item_id"], 1)
        first = self.work.claim_next(self.runner_id)
        self.now += timedelta(hours=2)

        recovered = self.work.claim_next(self.runner_id)

        self.assertEqual("review", recovered["work_type"])
        self.assertEqual(first["work_id"], recovered["work_id"])
        self.assertNotEqual(first["claim_token"], recovered["claim_token"])

    def test_pending_topic_is_claimed_when_no_review_work_exists(self) -> None:
        claimed = self.work.claim_next(self.runner_id, "Claude")

        self.assertEqual("topic", claimed["work_type"])
        self.assertEqual("node_0001", claimed["work_id"])
        self.assertIsNone(claimed["review"])
        self.assertEqual("Claude", claimed["worker_label"])

    def test_topic_done_with_open_review_becomes_awaiting_review(self) -> None:
        claimed = self.work.claim_next(self.runner_id)
        self.create_review()

        result = self.work.done(
            self.runner_id,
            claimed["work_id"],
            claimed["claim_token"],
        )

        self.assertEqual("awaiting_review", result["topic"]["status"])
        state = self.store.read(self.runner_id)
        self.assertTrue(state["topics"][0]["auto_phase_finished"])
        self.assertIsNone(state["topics"][0]["claim"])

    def test_topic_done_without_results_has_no_qualified_source(self) -> None:
        claimed = self.work.claim_next(self.runner_id)

        result = self.work.done(
            self.runner_id,
            claimed["work_id"],
            claimed["claim_token"],
        )

        self.assertEqual("no_qualified_source", result["topic"]["status"])

    def test_review_work_cannot_call_done(self) -> None:
        review = self.create_review()
        self.review.return_to_agent(self.runner_id, review["review_item_id"], 1)
        claimed = self.work.claim_next(self.runner_id)

        with self.assertRaises(ClientError) as error:
            self.work.done(
                self.runner_id,
                claimed["work_id"],
                claimed["claim_token"],
            )

        self.assertEqual("WORK_DONE_NOT_ALLOWED", error.exception.code)

    def test_topic_fail_releases_claim_and_records_error(self) -> None:
        claimed = self.work.claim_next(self.runner_id)

        result = self.work.fail(
            self.runner_id,
            claimed["work_id"],
            claimed["claim_token"],
            "BROWSER_CRASHED",
            "浏览器异常退出",
        )

        self.assertEqual("failed", result["topic"]["status"])
        state = self.store.read(self.runner_id)
        topic = state["topics"][0]
        self.assertIsNone(topic["claim"])
        self.assertEqual("BROWSER_CRASHED", topic["last_error"]["code"])

    def test_review_fail_returns_same_item_to_agent_queue(self) -> None:
        review = self.create_review()
        self.review.return_to_agent(self.runner_id, review["review_item_id"], 1)
        claimed = self.work.claim_next(self.runner_id)

        result = self.work.fail(
            self.runner_id,
            claimed["work_id"],
            claimed["claim_token"],
            "SOURCE_UNAVAILABLE",
            "来源暂时无法访问",
        )

        self.assertEqual("returned_to_agent", result["review"]["status"])
        self.assertEqual("review_test", result["work_id"])
        state = self.store.read(self.runner_id)
        stored = state["topics"][0]["review_items"][0]
        self.assertIsNone(stored["agent_claim"])
        self.assertEqual("work_failed", stored["events"][-1]["type"])


if __name__ == "__main__":
    unittest.main()
