"""Runner 生命周期与主题租约测试。"""

from datetime import datetime, timedelta, timezone

import pytest

from industry_chain_skills.errors import ClientError
from industry_chain_skills.runner import RunnerService
from industry_chain_skills.storage import RunnerStore


class MutableClock:
    """测试使用的可变时钟。"""

    def __init__(self, current: datetime) -> None:
        self.current = current

    def __call__(self) -> datetime:
        """返回当前测试时间。"""
        return self.current


def test_claim_lease_expiry_reclaim_and_finish(tmp_path) -> None:
    """有效租约不可重复领取，过期后可以安全重领。"""
    now = datetime(2026, 8, 25, 8, 0, tzinfo=timezone.utc)
    topic_config = tmp_path / "one-topic.yaml"
    topic_config.write_text(
        "themes:\n  唯一主题:\n    path: [测试分类, 唯一主题]\n    aliases: []\n",
        encoding="utf-8",
    )
    clock = MutableClock(now)
    tokens = iter(["token-a", "token-b"])
    service = RunnerService(
        RunnerStore(tmp_path / "runs"),
        clock=clock,
        token_factory=lambda: next(tokens),
    )
    created = service.create("测试批次", topic_config)
    runner_id = created["runner_id"]

    first = service.claim_next(runner_id)
    assert first["claim_token"] == "token-a"
    with pytest.raises(ClientError) as error:
        service.claim_next(runner_id)
    assert error.value.code == "NO_PENDING_TOPIC"

    clock.current = now + timedelta(seconds=3601)
    reclaimed = service.claim_next(runner_id)
    assert reclaimed["node_id"] == first["node_id"]
    assert reclaimed["claim_token"] == "token-b"

    with pytest.raises(ClientError) as error:
        service.finish(runner_id, first["node_id"], "token-a", "completed")
    assert error.value.code == "CLAIM_TOKEN_INVALID"

    with pytest.raises(ClientError) as error:
        service.finish(runner_id, first["node_id"], "token-b", "completed")
    assert error.value.code == "TOPIC_HAS_NO_SOURCE_GROUP"


def test_snapshot_no_source_failure_counts_and_reopen(tmp_path, topic_config) -> None:
    """主题快照、无来源终态、失败统计和重开保持一致。"""
    now = datetime(2026, 8, 25, 8, 0, tzinfo=timezone.utc)
    store = RunnerStore(tmp_path / "runs")
    service = RunnerService(store, clock=lambda: now, token_factory=lambda: "token-a")
    created = service.create("批次", topic_config)
    runner_id = created["runner_id"]

    topic_config.write_text("themes: {}\n", encoding="utf-8")
    claimed = service.claim_next(runner_id)
    service.finish(
        runner_id,
        claimed["node_id"],
        claimed["claim_token"],
        "no_qualified_source",
    )
    status = service.status(runner_id)
    assert status["counts"]["no_qualified_source"] == 1
    assert status["total"] == 2

    reopened = service.claim(runner_id, claimed["node_id"], reopen=True)
    assert reopened["status"] == "in_progress"
    service.fail(
        runner_id,
        claimed["node_id"],
        reopened["claim_token"],
        "BROWSER_UNAVAILABLE",
        "浏览器不可用",
    )
    status = service.status(runner_id)
    assert status["counts"]["failed"] == 1
    assert status["remaining"] == 2
