"""通用产业链 Skill 契约测试。"""

from pathlib import Path


def test_skill_contains_required_business_and_cli_gates() -> None:
    """Skill 包含视觉、搜索、租约、写入和结束硬约束。"""
    text = Path("SKILL.md").read_text(encoding="utf-8")
    required = [
        "topic claim-next",
        "claim_token",
        "视觉",
        "浏览器",
        "连续两个完整搜索轮次",
        "产业链图明确位置 > 企业列表 > 正文明确介绍",
        '"records"',
        "dataset insert",
        "topic finish",
    ]
    assert all(marker in text for marker in required)
    assert "Codex" not in text
    assert "Trae" not in text
