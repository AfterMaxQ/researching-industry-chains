"""FastAPI 薄 adapter 与 SPA 静态服务合同测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from industry_chain_skills.web_app import create_app


class WebAppTests(unittest.TestCase):
    """验证 API 不依赖前端 build，SPA 不吞 API。"""

    def test_health_is_available_without_static_build(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            app = create_app(Path(tmpdir), static_dir=None)
            response = TestClient(app).get("/api/health")

        self.assertEqual(200, response.status_code)
        self.assertEqual({"ok": True}, response.json())

    def test_static_build_serves_assets_and_spa_routes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            static = root / "web_dist"
            assets = static / "assets"
            assets.mkdir(parents=True)
            (static / "index.html").write_text(
                "<main>HITL App</main>",
                encoding="utf-8",
            )
            (assets / "app.js").write_text(
                "window.hitl = true",
                encoding="utf-8",
            )
            client = TestClient(create_app(root / "runs", static_dir=static))

            home = client.get("/")
            nested = client.get("/runners/example/reviews")
            asset = client.get("/assets/app.js")
            health = client.get("/api/health")

        self.assertEqual("<main>HITL App</main>", home.text)
        self.assertEqual("<main>HITL App</main>", nested.text)
        self.assertEqual("window.hitl = true", asset.text)
        self.assertEqual({"ok": True}, health.json())


if __name__ == "__main__":
    unittest.main()
