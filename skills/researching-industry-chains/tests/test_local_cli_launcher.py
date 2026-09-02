"""项目本地 CLI launcher 回归测试。"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = PACKAGE_ROOT / "run_cli.py"


class LocalCliLauncherTests(unittest.TestCase):
    """确保当前 checkout 的 CLI 能绕过 PATH 中的陈旧安装。"""

    def test_single_topic_runner_create_uses_current_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [
                    sys.executable,
                    str(LAUNCHER),
                    "--runs-root",
                    tmpdir,
                    "runner",
                    "create",
                    "--name",
                    "单主题回归",
                    "--topic",
                    "锡膏",
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            runner_id = payload["data"]["runner_id"]

            runner_path = Path(tmpdir) / runner_id / "runner.json"
            state = json.loads(runner_path.read_text(encoding="utf-8"))
            self.assertEqual("锡膏", state["topics"][0]["主题"])
            self.assertEqual(["锡膏"], state["topics"][0]["path"])
            self.assertEqual([], state["topics"][0]["aliases"])


if __name__ == "__main__":
    unittest.main()
