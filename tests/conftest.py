"""测试共用夹具。"""

from pathlib import Path

import pytest


@pytest.fixture
def topic_config(tmp_path: Path) -> Path:
    """创建最小主题身份配置。"""
    path = tmp_path / "topic_identity.yaml"
    path.write_text(
        """themes:
  测试主题:
    path: [测试分类, 测试主题]
    aliases: [测试别名]
  第二主题:
    path: [测试分类, 第二主题]
    aliases: []
""",
        encoding="utf-8",
    )
    return path
