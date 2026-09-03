"""按 work context 接收并路由完整 Agent SourceResult。"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Callable

from .dataset import DatasetService
from .errors import ClientError
from .review import ReviewService, append_review_event
from .runner import refresh_topic_status, require_and_renew_claim
from .source_result import (
    compile_tree_records,
    strip_uncertainties,
    validate_source_result,
)
from .storage import RunnerStore
from .work import find_work, require_and_renew_review_claim


class SourceService:
    """把 Agent 业务结果路由到正式来源或同一个审核对象。"""

    def __init__(
        self,
        store: RunnerStore,
        clock: Callable[[], datetime] | None = None,
        review_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.store = store
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.dataset = DatasetService(store, clock=self.clock)
        self.review = ReviewService(
            store,
            clock=self.clock,
            review_id_factory=review_id_factory,
        )

    def _now(self) -> datetime:
        """返回带时区当前时间。"""
        now = self.clock()
        if now.tzinfo is None:
            raise ClientError("RUNNER_STATE_INVALID", "来源提交时钟必须包含时区")
        return now

    def submit(
        self,
        runner_id: str,
        work_id: str,
        claim_token: str,
        payload: dict,
    ) -> dict:
        """验证 SourceResult，并在一个事务中完成正式写入或送审。"""
        source_result = validate_source_result(payload)
        now = self._now()
        timestamp = now.isoformat()

        def mutation(state: dict) -> dict:
            work_type, topic, review = find_work(state, work_id)
            if work_type == "topic":
                if topic["status"] != "in_progress":
                    raise ClientError("WORK_STATE_INVALID", "当前 topic work 不在处理中")
                require_and_renew_claim(topic, claim_token, now)
            else:
                assert review is not None
                require_and_renew_review_claim(review, claim_token, now)

            if source_result["outcome"] == "accept":
                clean_chain = strip_uncertainties(source_result["chain"])
                records = compile_tree_records(
                    topic["主题"],
                    source_result["source"],
                    source_result["description"],
                    clean_chain,
                )
                group = self.dataset.insert_source_group_in_state(
                    state,
                    topic,
                    {"records": records},
                    timestamp,
                )
                result = {
                    "result": "accepted",
                    "source_group_id": group["source_group_id"],
                }
                if review is not None:
                    review["status"] = "approved"
                    review["source"] = copy.deepcopy(source_result["source"])
                    review["description"] = source_result["description"].strip()
                    review["chain"] = clean_chain
                    review["agent_claim"] = None
                    review.pop("last_error", None)
                    review["version"] += 1
                    review["updated_at"] = timestamp
                    append_review_event(review, "review_agent_accepted", timestamp)
                    refresh_topic_status(topic)
                    result["review_item_id"] = review["review_item_id"]
                    result["version"] = review["version"]
            elif review is None:
                created = self.review.create_in_state(
                    topic,
                    source_result,
                    timestamp,
                )
                result = {
                    "result": "queued_for_review",
                    "review_item_id": created["review_item_id"],
                    "version": created["version"],
                }
            else:
                replaced = self.review.replace_from_agent_in_state(
                    review,
                    source_result,
                    timestamp,
                )
                refresh_topic_status(topic)
                result = {
                    "result": "queued_for_review",
                    "review_item_id": replaced["review_item_id"],
                    "version": replaced["version"],
                }

            state["updated_at"] = timestamp
            return result

        if source_result["outcome"] == "accept":
            return self.store.mutate_dataset(runner_id, mutation)
        return self.store.mutate_state(runner_id, mutation)
