"""FastAPI app 組裝。Infrastructure 層。"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from adapters.web.routes import router
from infrastructure.container import Container


def create_app(container: Container, *, static_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="wagent", version="0.1.0")
    app.state.container = container
    app.include_router(router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # 服務已 build 的前端（單一程序、單一 port）。
    # 掛在最後，故 API 路由（/tasks、/jobs、/health、/docs）優先匹配，不被遮蔽。
    if static_dir is not None and Path(static_dir).is_dir():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="frontend")

    return app
