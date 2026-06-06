"""可執行的 ASGI 入口。

啟動：
    uv run uvicorn infrastructure.server:app --reload
（會用真實 browser-use 與本地 sqlite:///wagent.db）
"""
from __future__ import annotations

from infrastructure.container import Container
from infrastructure.web import create_app

app = create_app(Container.create())
