"""Runner 创建、主题状态和领取租约。"""

import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable
from uuid import uuid4

from .errors import ClientError
from .identity import load_catalog
from .storage import RunnerStore


LEASE_SECONDS = 3600
RENEW_INTERVAL_SECONDS = 1200
STATUSES = (
    "pending",
    "in_progress",
    "completed",
    "no_qualified_source",
    "failed",
)


def new_claim(token: str, now: datetime) -> dict:
    """创建一份新的主题领取租约。"""
    expires_at = now + timedelta(seconds=LEASE_SECONDS)
    return {
        "token": token,
        "claimed_at": now.isoformat(),
        "lease_expires_at": expires_at.isoformat(),
    }


def require_and_renew_claim(topic: dict, claim_token: str, now: datetime) -> None:
    """校验主题领取令牌，并把有效租约续期一小时。"""
    claim = topic.get("claim")
    if not claim or claim["token"] != claim_token:
        raise ClientError("CLAIM_TOKEN_INVALID", "主题领取令牌无效")
    if datetime.fromisoformat(claim["lease_expires_at"]) <= now:
        raise ClientError("CLAIM_LEASE_EXPIRED", "主题领取租约已过期")
    claim["lease_expires_at"] = (
        now + timedelta(seconds=LEASE_SECONDS)
    ).isoformat()


def _topic_view(topic: dict) -> dict:
    """返回 Agent 处理主题所需的字段。"""
    return {
        "node_id": topic["node_id"],
        "主题": topic["主题"],
        "path": topic["path"],
        "aliases": topic["aliases"],
        "status": topic["status"],
    }


class RunnerService:
    """管理 Runner 快照、主题领取和终态提交。"""

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
        """返回带时区的当前时间。"""
        now = self.clock()
        if now.tzinfo is None:
            raise ClientError("RUNNER_STATE_INVALID", "Runner 时钟必须包含时区")
        return now

    @staticmethod
    def _find_topic(state: dict, node_id: str) -> dict:
        """按节点 ID 查找 Runner 快照主题。"""
        for topic in state["topics"]:
            if topic["node_id"] == node_id:
                return topic
        raise ClientError("TOPIC_NOT_FOUND", "Runner 中不存在指定主题", {"node_id": node_id})

    @staticmethod
    def _is_expired(topic: dict, now: datetime) -> bool:
        """判断处理中主题的租约是否已过期。"""
        claim = topic.get("claim")
        return bool(
            topic["status"] == "in_progress"
            and claim
            and datetime.fromisoformat(claim["lease_expires_at"]) <= now
        )

    @classmethod
    def _status_from_state(cls, state: dict, now: datetime) -> dict:
        """从 Runner 当前状态实时计算统计信息。"""
        counts = {
            status: sum(topic["status"] == status for topic in state["topics"])
            for status in STATUSES
        }
        expired = [
            _topic_view(topic)
            for topic in state["topics"]
            if cls._is_expired(topic, now)
        ]
        pending = [
            _topic_view(topic)
            for topic in state["topics"]
            if topic["status"] == "pending"
        ]
        in_progress = [
            _topic_view(topic)
            for topic in state["topics"]
            if topic["status"] == "in_progress"
        ]
        failed_topics = [
            {**_topic_view(topic), "last_error": topic.get("last_error")}
            for topic in state["topics"]
            if topic["status"] == "failed"
        ]
        next_topic = expired[0] if expired else (pending[0] if pending else None)
        return {
            "runner_id": state["runner_id"],
            "name": state["name"],
            "total": len(state["topics"]),
            "counts": counts,
            "remaining": counts["pending"] + counts["failed"],
            "failed_count": counts["failed"],
            "in_progress": in_progress,
            "next_topic": next_topic,
            "expired_topics": expired,
            "failed_topics": failed_topics,
        }

    def create(self, name: str, config_path: Path) -> dict:
        """读取配置快照并创建独立 Runner。"""
        if not isinstance(name, str) or not name.strip():
            raise ClientError("RUNNER_NAME_INVALID", "任务名称不能为空")
        catalog = load_catalog(config_path)
        if not catalog:
            raise ClientError("TOPIC_CONFIG_INVALID", "主题身份配置中没有主题")
        now = self._now()
        local_now = now.astimezone()
        safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "-", name.strip())
        safe_name = re.sub(r"\s+", "-", safe_name).strip(" .-") or "runner"
        runner_id = (
            f"{local_now:%Y%m%d-%H%M%S}-{safe_name}-{uuid4().hex[:6]}"
        )
        timestamp = now.isoformat()
        state = {
            "runner_id": runner_id,
            "name": name.strip(),
            "topic_identity_path": str(config_path.resolve()),
            "created_at": timestamp,
            "updated_at": timestamp,
            "topics": [
                {
                    "node_id": f"node_{identity.order:04d}",
                    "主题": identity.topic,
                    "path": list(identity.path),
                    "aliases": list(identity.aliases),
                    "order": identity.order,
                    "status": "pending",
                    "last_error": None,
                    "claim": None,
                    "source_groups": [],
                }
                for identity in catalog
            ],
        }
        self.store.create(state)
        return self._status_from_state(state, now)

    def status(self, runner_id: str) -> dict:
        """返回 Runner 当前统计和待处理主题。"""
        return self._status_from_state(self.store.read(runner_id), self._now())

    def _claim_response(self, topic: dict, state: dict, now: datetime) -> dict:
        """组合主题领取结果和 Runner 即时统计。"""
        response = _topic_view(topic)
        response.update(
            {
                "claim_token": topic["claim"]["token"],
                "lease_expires_at": topic["claim"]["lease_expires_at"],
                "runner": self._status_from_state(state, now),
            }
        )
        return response

    def claim_next(self, runner_id: str) -> dict:
        """原子领取下一个过期或待处理主题。"""
        now = self._now()

        def mutation(state: dict) -> dict:
            candidates = [
                topic for topic in state["topics"] if self._is_expired(topic, now)
            ]
            if not candidates:
                candidates = [
                    topic for topic in state["topics"] if topic["status"] == "pending"
                ]
            if not candidates:
                raise ClientError("NO_PENDING_TOPIC", "没有可领取的待处理主题")
            topic = candidates[0]
            topic["status"] = "in_progress"
            topic["claim"] = new_claim(self.token_factory(), now)
            topic["last_error"] = None
            state["updated_at"] = now.isoformat()
            return self._claim_response(topic, state, now)

        return self.store.mutate_state(runner_id, mutation)

    def claim(self, runner_id: str, node_id: str, reopen: bool = False) -> dict:
        """原子领取指定主题，必要时显式重开终态主题。"""
        now = self._now()

        def mutation(state: dict) -> dict:
            topic = self._find_topic(state, node_id)
            if topic["status"] == "in_progress" and not self._is_expired(topic, now):
                raise ClientError("TOPIC_ALREADY_CLAIMED", "主题仍处于有效领取期")
            if topic["status"] in ("completed", "no_qualified_source") and not reopen:
                raise ClientError("TOPIC_REOPEN_REQUIRED", "终态主题必须显式重开")
            if topic["status"] not in ("pending", "failed", "in_progress", "completed", "no_qualified_source"):
                raise ClientError("TOPIC_STATUS_INVALID", "主题状态不允许领取")
            topic["status"] = "in_progress"
            topic["claim"] = new_claim(self.token_factory(), now)
            topic["last_error"] = None
            state["updated_at"] = now.isoformat()
            return self._claim_response(topic, state, now)

        return self.store.mutate_state(runner_id, mutation)

    def renew(self, runner_id: str, node_id: str, claim_token: str) -> dict:
        """续期指定主题的有效领取租约。"""
        now = self._now()

        def mutation(state: dict) -> dict:
            topic = self._find_topic(state, node_id)
            require_and_renew_claim(topic, claim_token, now)
            state["updated_at"] = now.isoformat()
            return self._claim_response(topic, state, now)

        return self.store.mutate_state(runner_id, mutation)

    def finish(
        self,
        runner_id: str,
        node_id: str,
        claim_token: str,
        outcome: str,
    ) -> dict:
        """把主题提交为成功完成或无合格来源。"""
        if outcome not in ("completed", "no_qualified_source"):
            raise ClientError("TOPIC_OUTCOME_INVALID", "主题结束结果无效")
        now = self._now()

        def mutation(state: dict) -> dict:
            topic = self._find_topic(state, node_id)
            require_and_renew_claim(topic, claim_token, now)
            has_sources = bool(topic["source_groups"])
            if outcome == "completed" and not has_sources:
                raise ClientError("TOPIC_HAS_NO_SOURCE_GROUP", "完成主题前必须写入来源组")
            if outcome == "no_qualified_source" and has_sources:
                raise ClientError("TOPIC_HAS_SOURCE_GROUP", "已有来源组的主题不能标记为无合格来源")
            topic["status"] = outcome
            topic["claim"] = None
            topic["last_error"] = None
            state["updated_at"] = now.isoformat()
            return self._status_from_state(state, now)

        return self.store.mutate_state(runner_id, mutation)

    def fail(
        self,
        runner_id: str,
        node_id: str,
        claim_token: str,
        code: str,
        message: str,
    ) -> dict:
        """记录主题运行异常并释放领取租约。"""
        now = self._now()

        def mutation(state: dict) -> dict:
            topic = self._find_topic(state, node_id)
            require_and_renew_claim(topic, claim_token, now)
            topic["status"] = "failed"
            topic["claim"] = None
            topic["last_error"] = {"code": code, "message": message}
            state["updated_at"] = now.isoformat()
            return self._status_from_state(state, now)

        return self.store.mutate_state(runner_id, mutation)
