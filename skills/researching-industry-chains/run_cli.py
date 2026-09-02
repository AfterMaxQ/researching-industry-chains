"""从当前 Skill 源码启动 CLI，避免 PATH 中旧安装版本干扰。"""

from __future__ import annotations

import sys
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
SRC_ROOT = PACKAGE_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from industry_chain_skills.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
