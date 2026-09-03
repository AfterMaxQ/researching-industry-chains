"""运行时 Skill 与 Agent-facing HITL 协议一致性测试。"""

import unittest
from pathlib import Path


SKILL_PATH = Path(__file__).resolve().parents[1] / "SKILL.md"


class SkillContractTests(unittest.TestCase):
    """防止 Agent 指令退回九字段手工写入流程。"""

    def test_skill_uses_source_result_workflow_only(self) -> None:
        content = SKILL_PATH.read_text(encoding="utf-8")

        self.assertIn("work claim-next", content)
        self.assertIn("source submit", content)
        self.assertIn("work done", content)
        self.assertIn('"outcome": "accept"', content)
        self.assertIn('"outcome": "review"', content)
        self.assertNotIn("dataset insert --runner-id", content)
        self.assertNotIn("topic finish --runner-id", content)
        self.assertNotIn("topic renew --runner-id", content)
        self.assertLessEqual(len(content.splitlines()), 500)


if __name__ == "__main__":
    unittest.main()
