"""topic 与 review 的统一工作领取和租约管理。"""

from __future__ import annotations

import copy
import secrets
from datetime import datetime, timedelta, timezone
from typing import Callable

from .errors import ClientError
from .review import append_review_event
from .runner import LEASE_SECONDS, new_claim, refresh_topic_status, require_and_renew_claim
from .storage import RunnerStore


def _claim_expired(claim: dict | None, now: datetime) -> bool:
    """判断一份存在的租约是否已经过期。"""
    return bool(
        claim
        and datetime.fromisoformat(claim["lease_expires_at"]) <= now
    )


def require_and_renew_review_claim(
    review: dict,
    claim_token: str,
    now: datetime,
) -> None:
    """校验审核工作租约并续期。"""
    claim = review.get("agent_claim")
    if review.get("status") != "in_agent" or not claim or claim["token"] != claim_token:
        raise ClientError("CLAIM_TOKEN_INVALID", "审核工作领取令牌无效")
    if _claim_expired(claim, now):
        raise ClientError("CLAIM_LEASE_EXPIRED", "审核工作领取租约已过期")
    claim["lease_expires_at"] = (
        now + timedelta(seconds=LEASE_SECONDS)
    ).isoformat()


def _topic_view(topic: dict) -> dict:
    """返回统一工作协议中的主题上下文。"""
    return {
        "node_id": topic["node_id"],
        "主题": topic["主题"],
        "path": copy.deepcopy(topic["path"]),
        "aliases": copy.deepcopy(topic["aliases"]),
        "status": topic["status"],
    }


def _review_view(review: dict) -> dict:
    """返回 Agent 继续研究所需的审核业务快照。"""
    return {
        "source": copy.deepcopy(review["source"]),
        "description": review["description"],
        "chain": copy.deepcopy(review["chain"]),
        "uncertainties": copy.deepcopy(review.get("uncertainties", [])),
    }


def find_work(state: dict, work_id: str) -> tuple[str, dict, dict | None]:
    """按 work_id 查找 topic 或 review。"""
    for topic in state["topics"]:
        if topic["node_id"] == work_id:
            return "topic", topic, None
        for review in topic.get("review_items", []):
            if review["review_item_id"] == work_id:
                return "review", topic, review
    raise ClientError("WORK_NOT_FOUND", "Runner 中不存在指定工作")


class WorkService:
    """统一领取 topic/review 工作，并结束或记录执行异常。"""

    def __init__(
        self,
        store: RunnerStore,
        clock: Callable[[], datetime] | None = None,
        token_factory: Callable[[], str] | None = None,
    ) -> None:
        self.store = store
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.token_factory = token_factory or (lambda: secrets.token_urlsafe(24))

    def _now(self) -> datetime:
        """返回带时区当前时间。"""
        now = self.clock()
        if now.tzinfo is None:
            raise ClientError("RUNNER_STATE_INVALID", "工作调度时钟必须包含时区")
        return now

    @staticmethod
    def _claim_response(
        work_type: str,
        topic: dict,
        review: dict | None,
    ) -> dict:
        """生成 Agent-facing work context。"""
        claim = topic["claim"] if review is None else review["agent_claim"]
        return {
            "work_type": work_type,
            "work_id": topic["node_id"] if review is None else review["review_item_id"],
            "claim_token": claim["token"],
            "lease_expires_at": claim["lease_expires_at"],
            "worker_label": claim.get("worker_label"),
            "topic": _topic_view(topic),
            "review": None if review is None else _review_view(review),
        }

    def claim_next(
        self,
        runner_id: str,
        worker_label: str | None = None,
    ) -> dict:
        """按 review 优先级原子领取下一份工作。"""
        if worker_label is not None and (
            not isinstance(worker_label, str) or not worker_label.strip()
        ):
            raise ClientError("WORKER_LABEL_INVALID", "worker_label 不能为空")
        now = self._now()

        def mutation(state: dict) -> dict:
            review_candidates = [
                (topic, review)
                for topic in state["topics"]
                for review in topic.get("review_items", [])
                if review["status"] == "returned_to_agent"
            ]
            if not review_candidates:
                review_candidates = [
                    (topic, review)
                    for topic in state["topics"]
                    for review in topic.get("review_items", [])
                    if review["status"] == "in_agent"
                    and _claim_expired(review.get("agent_claim"), now)
                ]
            if review_candidates:
                topic, review = review_candidates[0]
                review["status"] = "in_agent"
                review["agent_claim"] = new_claim(
                    self.token_factory(),
                    now,
                    worker_label.strip() if worker_label is not None else None,
                )
                review["updated_at"] = now.isoformat()
                append_review_event(review, "review_claimed", now.isoformat())
                state["updated_at"] = now.isoformat()
                return self._claim_response("review", topic, review)

            topic_candidates = [
                topic
                for topic in state["topics"]
                if topic["status"] == "in_progress"
                and _claim_expired(topic.get("claim"), now)
            ]
            if not topic_candidates:
                topic_candidates = [
                    topic for topic in state["topics"] if topic["status"] == "pending"
                ]
            if not topic_candidates:
                raise ClientError("NO_PENDING_WORK", "没有可领取的待处理工作")
            topic = topic_candidates[0]
            topic["status"] = "in_progress"
            topic["claim"] = new_claim(
                self.token_factory(),
                now,
                worker_label.strip() if worker_label is not None else None,
            )
            topic["last_error"] = None
            state["updated_at"] = now.isoformat()
            return self._claim_response("topic", topic, None)

        return self.store.mutate_state(runner_id, mutation)

    def done(self, runner_id: str, work_id: str, claim_token: str) -> dict:
        """结束 topic 的自动搜索阶段并由 Client 推导主题状态。"""
        now = self._now()

        def mutation(state: dict) -> dict:
            work_type, topic, review = find_work(state, work_id)
            if work_type == "review":
                raise ClientError(
                    "WORK_DONE_NOT_ALLOWED",
                    "review work 在 source submit 后自动结束，不能调用 work done",
                )
            require_and_renew_claim(topic, claim_token, now)
            if topic["status"] != "in_progress":
                raise ClientError("WORK_STATE_INVALID", "当前 topic work 不在处理中")
            topic["auto_phase_finished"] = True
            topic["claim"] = None
            topic["last_error"] = None
            refresh_topic_status(topic)
            state["updated_at"] = now.isoformat()
            return {
                "work_type": work_type,
                "work_id": work_id,
                "topic": _topic_view(topic),
            }

        return self.store.mutate_state(runner_id, mutation)

    def fail(
        self,
        runner_id: str,
        work_id: str,
        claim_token: str,
        code: str,
        message: str,
    ) -> dict:
        """记录真实执行异常并释放对应 work 租约。"""
        if not isinstance(code, str) or not code.strip() or not isinstance(message, str) or not message.strip():
            raise ClientError("WORK_ERROR_INVALID", "work fail 必须提供 code 和 message")
        now = self._now()
        timestamp = now.isoformat()

        def mutation(state: dict) -> dict:
            work_type, topic, review = find_work(state, work_id)
            error = {"code": code.strip(), "message": message.strip()}
            if work_type == "topic":
                require_and_renew_claim(topic, claim_token, now)
                topic["status"] = "failed"
                topic["auto_phase_finished"] = False
                topic["claim"] = None
                topic["last_error"] = error
                result = {
                    "work_type": work_type,
                    "work_id": work_id,
                    "topic": _topic_view(topic),
                }
            else:
                assert review is not None
                require_and_renew_review_claim(review, claim_token, now)
                review["status"] = "returned_to_agent"
                review["agent_claim"] = None
                review["last_error"] = error
                review["updated_at"] = timestamp
                append_review_event(review, "work_failed", timestamp)
                refresh_topic_status(topic)
                result = {
                    "work_type": work_type,
                    "work_id": work_id,
                    "topic": _topic_view(topic),
                    "review": copy.deepcopy(review),
                }
            state["updated_at"] = timestamp
            return result

        return self.store.mutate_state(runner_id, mutation)
