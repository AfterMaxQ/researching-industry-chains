"""主题身份目录测试。"""

from pathlib import Path

import pytest

from industry_chain_skills.errors import ClientError
from industry_chain_skills.identity import (
    get_identity,
    load_catalog,
    search_identities,
)


def test_load_catalog_preserves_order_and_queries_alias_and_path(tmp_path: Path) -> None:
    """目录保留配置顺序，并可按别名和路径查询。"""
    config = tmp_path / "topic_identity.yaml"
    config.write_text(
        """themes:
  半导体与精密装备:
    path: [先进制造, 半导体与精密装备]
    aliases: [半导体及设备]
  存储芯片:
    path: [先进制造, 半导体与精密装备, 半导体器件, 存储芯片]
    aliases: [Memory Chip]
""",
        encoding="utf-8",
    )

    catalog = load_catalog(config)

    assert [item.topic for item in catalog] == ["半导体与精密装备", "存储芯片"]
    assert [item.order for item in catalog] == [1, 2]
    assert get_identity(config, "存储芯片").aliases == ("Memory Chip",)
    assert [item.topic for item in search_identities(config, "memory")] == ["存储芯片"]
    assert [item.topic for item in search_identities(config, "半导体器件")] == ["存储芯片"]


def test_invalid_path_raises_stable_error(tmp_path: Path) -> None:
    """path 不是数组时返回稳定配置错误代码。"""
    config = tmp_path / "topic_identity.yaml"
    config.write_text(
        """themes:
  错误主题:
    path: 错误路径
    aliases: []
""",
        encoding="utf-8",
    )

    with pytest.raises(ClientError) as error:
        load_catalog(config)

    assert error.value.code == "TOPIC_CONFIG_INVALID"


def test_fixture_supports_exact_topic_lookup(topic_config: Path) -> None:
    """共用夹具可以用于正式主题精确查询。"""
    identity = get_identity(topic_config, "测试主题")

    assert identity.path == ("测试分类", "测试主题")
    assert identity.order == 1
