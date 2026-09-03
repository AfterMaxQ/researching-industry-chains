"""SourceService 按 work context 路由完整 SourceResult 的测试。"""

from __future__ import annotations

import tempfile
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from industry_chain_skills.errors import ClientError
from industry_chain_skills.review import ReviewService
from industry_chain_skills.runner import RunnerService
from industry_chain_skills.source_service import SourceService
from industry_chain_skills.storage import RunnerStore
from industry_chain_skills.work import WorkService


NOW = datetime(2026, 9, 3, tzinfo=timezone.utc)


def accept_result(url: str = "https://example.com/accepted") -> dict:
    """创建最小合法 accept SourceResult。"""
    return {
        "outcome": "accept",
        "source": {"name": "示例研究院", "url": url},
        "description": "该来源完整展示上下游结构。",
        "chain": [
            {
                "name": "上游",
                "children": [{"name": "锡粉", "companies": ["甲公司", "乙公司"]}],
            }
        ],
    }


def review_result(description: str = "部分结构仍需确认。") -> dict:
    """创建最小合法 review SourceResult。"""
    return {
        "outcome": "review",
        "source": {"name": "待审研究院", "url": "https://example.com/review"},
        "description": description,
        "chain": [{"name": "上游"}],
        "uncertainties": [
            {
                "message": "无法确认结构是否完整。",
                "evidence": [
                    {
                        "locator": "网页交互图的展开状态",
                        "description": "页面没有显示节点总数。",
                    }
                ],
            }
        ],
    }


class SourceServiceTests(unittest.TestCase):
    """验证 Agent 只提交业务 SourceResult。"""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.store = RunnerStore(Path(self.tempdir.name))
        self.now = NOW
        runner = RunnerService(self.store, clock=lambda: self.now)
        created = runner.create("来源提交", topic="锡膏")
        self.runner_id = created["runner_id"]
        self.tokens = iter(["token-1", "token-2", "token-3"])
        self.work = WorkService(
            self.store,
            clock=lambda: self.now,
            token_factory=lambda: next(self.tokens),
        )
        self.source = SourceService(
            self.store,
            clock=lambda: self.now,
            review_id_factory=lambda: "review_test",
        )
        self.review = ReviewService(self.store, clock=lambda: self.now)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def submit_topic_review_and_return(self) -> tuple[dict, dict]:
        """建立一条已交回 Agent 的 review work。"""
        topic_work = self.work.claim_next(self.runner_id)
        queued = self.source.submit(
            self.runner_id,
            topic_work["work_id"],
            topic_work["claim_token"],
            review_result(),
        )
        self.work.done(
            self.runner_id,
            topic_work["work_id"],
            topic_work["claim_token"],
        )
        self.review.return_to_agent(
            self.runner_id,
            queued["review_item_id"],
            queued["version"],
        )
        return queued, self.work.claim_next(self.runner_id)

    def test_topic_accept_writes_formal_source_and_keeps_work_open(self) -> None:
        work = self.work.claim_next(self.runner_id)
        previous_expiry = work["lease_expires_at"]
        self.now += timedelta(minutes=10)

        result = self.source.submit(
            self.runner_id,
            work["work_id"],
            work["claim_token"],
            accept_result(),
        )

        self.assertEqual("accepted", result["result"])
        state = self.store.read(self.runner_id)
        topic = state["topics"][0]
        self.assertEqual("in_progress", topic["status"])
        self.assertEqual(1, len(topic["source_groups"]))
        self.assertGreater(topic["claim"]["lease_expires_at"], previous_expiry)

    def test_topic_review_creates_queue_item_without_formal_source(self) -> None:
        work = self.work.claim_next(self.runner_id)

        result = self.source.submit(
            self.runner_id,
            work["work_id"],
            work["claim_token"],
            review_result(),
        )

        self.assertEqual("queued_for_review", result["result"])
        self.assertEqual("review_test", result["review_item_id"])
        self.assertEqual(1, result["version"])
        state = self.store.read(self.runner_id)
        topic = state["topics"][0]
        self.assertEqual([], topic["source_groups"])
        self.assertEqual(1, len(topic["review_items"]))
        self.assertEqual("in_progress", topic["status"])

    def test_invalid_source_result_leaves_runner_unchanged(self) -> None:
        work = self.work.claim_next(self.runner_id)
        before = self.store.read(self.runner_id)
        invalid = accept_result()
        invalid["description"] = ""

        with self.assertRaises(ClientError):
            self.source.submit(
                self.runner_id,
                work["work_id"],
                work["claim_token"],
                invalid,
            )

        self.assertEqual(before, self.store.read(self.runner_id))

    def test_review_work_review_result_reuses_same_item(self) -> None:
        queued, review_work = self.submit_topic_review_and_return()
        revised = review_result("Agent 再次研究后的完整说明。")

        result = self.source.submit(
            self.runner_id,
            review_work["work_id"],
            review_work["claim_token"],
            revised,
        )

        self.assertEqual("queued_for_review", result["result"])
        self.assertEqual(queued["review_item_id"], result["review_item_id"])
        self.assertEqual(3, result["version"])
        state = self.store.read(self.runner_id)
        reviews = state["topics"][0]["review_items"]
        self.assertEqual(1, len(reviews))
        self.assertEqual("pending_review", reviews[0]["status"])
        self.assertEqual(revised["description"], reviews[0]["description"])
        self.assertIsNone(reviews[0]["agent_claim"])

    def test_review_work_accept_closes_same_item_and_writes_source(self) -> None:
        queued, review_work = self.submit_topic_review_and_return()

        result = self.source.submit(
            self.runner_id,
            review_work["work_id"],
            review_work["claim_token"],
            accept_result("https://example.com/review"),
        )

        self.assertEqual("accepted", result["result"])
        self.assertEqual(queued["review_item_id"], result["review_item_id"])
        state = self.store.read(self.runner_id)
        topic = state["topics"][0]
        self.assertEqual("completed", topic["status"])
        self.assertEqual(1, len(topic["source_groups"]))
        self.assertEqual("approved", topic["review_items"][0]["status"])
        self.assertEqual(3, topic["review_items"][0]["version"])

    def test_invalid_review_resubmission_keeps_claim_and_review_snapshot(self) -> None:
        _, review_work = self.submit_topic_review_and_return()
        before = deepcopy(self.store.read(self.runner_id))
        invalid = review_result()
        invalid["uncertainties"] = []

        with self.assertRaises(ClientError):
            self.source.submit(
                self.runner_id,
                review_work["work_id"],
                review_work["claim_token"],
                invalid,
            )

        self.assertEqual(before, self.store.read(self.runner_id))


if __name__ == "__main__":
    unittest.main()
