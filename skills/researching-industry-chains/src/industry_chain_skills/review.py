"""Human review 对象和人工审核状态机。"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from .dataset import DatasetService
from .errors import ClientError
from .runner import refresh_topic_status
from .source_result import (
    compile_tree_records,
    strip_uncertainties,
    validate_source_result,
)
from .storage import RunnerStore


def find_review(state: dict, review_id: str) -> tuple[dict, dict]:
    """查找审核对象及其所属主题。"""
    for topic in state["topics"]:
        for review in topic.get("review_items", []):
            if review["review_item_id"] == review_id:
                return topic, review
    raise ClientError(
        "REVIEW_NOT_FOUND",
        "Runner 中不存在指定审核对象",
        {"review_item_id": review_id},
    )


def _require_version(review: dict, expected_version: int) -> None:
    """执行乐观并发版本检查。"""
    if review["version"] != expected_version:
        raise ClientError(
            "REVIEW_VERSION_CONFLICT",
            "审核结果已被更新，请重新加载最新版本",
            {
                "expected_version": expected_version,
                "actual_version": review["version"],
            },
        )


def _require_pending(review: dict) -> None:
    """限制人工动作只能作用于待审核对象。"""
    if review["status"] != "pending_review":
        raise ClientError("REVIEW_ACTION_NOT_ALLOWED", "当前审核状态不允许执行该动作")


def append_review_event(review: dict, event_type: str, timestamp: str) -> None:
    """记录最小审核业务事件。"""
    review["events"].append(
        {"type": event_type, "at": timestamp, "version": review["version"]}
    )


class ReviewService:
    """创建审核对象并处理人工来源级动作。"""

    def __init__(
        self,
        store: RunnerStore,
        clock: Callable[[], datetime] | None = None,
        review_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.store = store
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.review_id_factory = review_id_factory or (
            lambda: f"review_{uuid4().hex[:12]}"
        )
        self.dataset = DatasetService(store, clock=self.clock)

    def _now(self) -> datetime:
        """返回带时区当前时间。"""
        now = self.clock()
        if now.tzinfo is None:
            raise ClientError("RUNNER_STATE_INVALID", "审核时钟必须包含时区")
        return now

    def create_in_state(
        self,
        topic: dict,
        source_result: dict,
        timestamp: str,
    ) -> dict:
        """在已有 Runner 事务中创建轻量 review_item。"""
        validated = validate_source_result(source_result)
        if validated["outcome"] != "review":
            raise ClientError(
                "SOURCE_RESULT_NOT_REVIEW",
                "只有 review 类型 SourceResult 可以创建审核对象",
            )
        reviews = topic.setdefault("review_items", [])
        review = {
            "review_item_id": self.review_id_factory(),
            "order": max((item.get("order", 0) for item in reviews), default=0) + 1,
            "status": "pending_review",
            "version": 1,
            "created_at": timestamp,
            "updated_at": timestamp,
            "source": copy.deepcopy(validated["source"]),
            "description": validated["description"],
            "chain": copy.deepcopy(validated["chain"]),
            "uncertainties": copy.deepcopy(validated.get("uncertainties", [])),
            "agent_claim": None,
            "events": [],
        }
        append_review_event(review, "review_created", timestamp)
        reviews.append(review)
        return copy.deepcopy(review)

    def replace_from_agent_in_state(
        self,
        review: dict,
        source_result: dict,
        timestamp: str,
    ) -> dict:
        """用 Agent 的最新完整 SourceResult 更新同一个 review_item。"""
        validated = validate_source_result(source_result)
        if validated["outcome"] != "review":
            raise ClientError(
                "SOURCE_RESULT_NOT_REVIEW",
                "只有 review 类型 SourceResult 可以更新待审核对象",
            )
        review["status"] = "pending_review"
        review["source"] = copy.deepcopy(validated["source"])
        review["description"] = validated["description"]
        review["chain"] = copy.deepcopy(validated["chain"])
        review["uncertainties"] = copy.deepcopy(
            validated.get("uncertainties", [])
        )
        review["agent_claim"] = None
        review.pop("last_error", None)
        review["version"] += 1
        review["updated_at"] = timestamp
        append_review_event(review, "review_resubmitted", timestamp)
        return copy.deepcopy(review)

    def approve(
        self,
        runner_id: str,
        review_id: str,
        expected_version: int,
        description: str,
        chain: list[dict],
    ) -> dict:
        """通过当前审核草稿并原子写入正式来源与 XLSX。"""
        now = self._now()
        timestamp = now.isoformat()

        def mutation(state: dict) -> dict:
            topic, review = find_review(state, review_id)
            _require_version(review, expected_version)
            _require_pending(review)
            if not isinstance(chain, list) or not chain:
                raise ClientError("REVIEW_EMPTY_CHAIN", "空产业链草稿不能通过审核")
            clean_chain = strip_uncertainties(chain)
            records = compile_tree_records(
                topic["主题"],
                review["source"],
                description,
                clean_chain,
            )
            group = self.dataset.insert_source_group_in_state(
                state,
                topic,
                {"records": records},
                timestamp,
            )
            review["status"] = "approved"
            review["description"] = description.strip()
            review["chain"] = clean_chain
            review["agent_claim"] = None
            review["version"] += 1
            review["updated_at"] = timestamp
            append_review_event(review, "review_approved", timestamp)
            refresh_topic_status(topic)
            state["updated_at"] = timestamp
            return {
                "review": copy.deepcopy(review),
                "source_group": copy.deepcopy(group),
            }

        return self.store.mutate_dataset(runner_id, mutation)

    def return_to_agent(
        self,
        runner_id: str,
        review_id: str,
        expected_version: int,
    ) -> dict:
        """把当前审核版本交回 Agent 继续研究。"""
        now = self._now()
        timestamp = now.isoformat()

        def mutation(state: dict) -> dict:
            topic, review = find_review(state, review_id)
            _require_version(review, expected_version)
            _require_pending(review)
            review["status"] = "returned_to_agent"
            review["agent_claim"] = None
            review["version"] += 1
            review["updated_at"] = timestamp
            append_review_event(review, "review_returned_to_agent", timestamp)
            refresh_topic_status(topic)
            state["updated_at"] = timestamp
            return copy.deepcopy(review)

        return self.store.mutate_state(runner_id, mutation)

    def reject(
        self,
        runner_id: str,
        review_id: str,
        expected_version: int,
    ) -> dict:
        """驳回当前来源并刷新所属主题终态。"""
        now = self._now()
        timestamp = now.isoformat()

        def mutation(state: dict) -> dict:
            topic, review = find_review(state, review_id)
            _require_version(review, expected_version)
            _require_pending(review)
            review["status"] = "rejected"
            review["agent_claim"] = None
            review["version"] += 1
            review["updated_at"] = timestamp
            append_review_event(review, "review_rejected", timestamp)
            refresh_topic_status(topic)
            state["updated_at"] = timestamp
            return copy.deepcopy(review)

        return self.store.mutate_state(runner_id, mutation)
