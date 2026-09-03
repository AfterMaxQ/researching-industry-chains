"""本地 HITL FastAPI 薄 adapter 和 SPA 静态服务。"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def _mount_spa(app: FastAPI, static_dir: Path) -> None:
    """在 API 路由之后挂载生产前端静态文件。"""
    root = static_dir.resolve()
    index = root / "index.html"
    assets = root / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API 不存在")
        candidate = (root / full_path).resolve()
        if candidate.is_relative_to(root) and candidate.is_file():
            return FileResponse(candidate)
        if not index.is_file():
            raise HTTPException(status_code=404, detail="前端构建不存在")
        return FileResponse(index)


def create_app(
    runs_root: Path,
    static_dir: Path | None = None,
) -> FastAPI:
    """创建只调用共享 Python Core 的本地审核应用。"""
    app = FastAPI(title="Industry Chain HITL")
    app.state.runs_root = runs_root

    @app.get("/api/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    if static_dir is not None:
        _mount_spa(app, static_dir)
    return app
