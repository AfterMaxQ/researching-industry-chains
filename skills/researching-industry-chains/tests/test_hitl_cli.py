"""Agent-facing work/source CLI 协议测试。"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from industry_chain_skills.cli import build_parser


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = PACKAGE_ROOT / "run_cli.py"


def accept_result() -> dict:
    """创建 CLI 提交用的合法 SourceResult。"""
    return {
        "outcome": "accept",
        "source": {"name": "示例研究院", "url": "https://example.com/report"},
        "description": "该来源完整展示上下游结构。",
        "chain": [
            {
                "name": "上游",
                "children": [{"name": "锡粉", "companies": ["甲公司"]}],
            }
        ],
    }


class HitlCliTests(unittest.TestCase):
    """验证 CLI parser 与真实子进程闭环。"""

    def invoke(
        self,
        runs_root: str,
        *arguments: str,
        payload: dict | None = None,
    ) -> dict:
        """运行当前 checkout 的 CLI 并解析统一 JSON 响应。"""
        result = subprocess.run(
            [
                sys.executable,
                str(LAUNCHER),
                "--runs-root",
                runs_root,
                *arguments,
            ],
            input=None if payload is None else json.dumps(payload, ensure_ascii=False),
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        response = json.loads(result.stdout)
        self.assertTrue(response["ok"], response)
        return response["data"]

    def test_parser_exposes_work_and_source_commands(self) -> None:
        work = build_parser().parse_args(
            ["work", "claim-next", "--runner-id", "runner_test"]
        )
        source = build_parser().parse_args(
            [
                "source",
                "submit",
                "--runner-id",
                "runner_test",
                "--work-id",
                "node_0001",
                "--claim-token",
                "token",
                "--input",
                "-",
            ]
        )

        self.assertEqual(("work", "claim-next"), (work.command, work.action))
        self.assertEqual(("source", "submit"), (source.command, source.action))

    def test_local_cli_runs_complete_accept_source_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            created = self.invoke(
                tmpdir,
                "runner",
                "create",
                "--name",
                "HITL CLI 回归",
                "--topic",
                "锡膏",
            )
            runner_id = created["runner_id"]
            work = self.invoke(
                tmpdir,
                "work",
                "claim-next",
                "--runner-id",
                runner_id,
                "--worker-label",
                "Codex",
            )
            submitted = self.invoke(
                tmpdir,
                "source",
                "submit",
                "--runner-id",
                runner_id,
                "--work-id",
                work["work_id"],
                "--claim-token",
                work["claim_token"],
                "--input",
                "-",
                payload=accept_result(),
            )
            done = self.invoke(
                tmpdir,
                "work",
                "done",
                "--runner-id",
                runner_id,
                "--work-id",
                work["work_id"],
                "--claim-token",
                work["claim_token"],
            )
            status = self.invoke(
                tmpdir,
                "runner",
                "status",
                "--runner-id",
                runner_id,
            )

        self.assertEqual("accepted", submitted["result"])
        self.assertEqual("completed", done["topic"]["status"])
        self.assertEqual(1, status["counts"]["completed"])


if __name__ == "__main__":
    unittest.main()
