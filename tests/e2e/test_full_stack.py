"""全棧 E2E（opt-in）：API → 背景執行 → 真實 browser-use → SSE。

預設 skip。要跑（需 .env 金鑰、會開瀏覽器、較慢）：
    $env:WAGENT_RUN_E2E=1 ; uv run pytest tests/e2e/test_full_stack.py
"""
from __future__ import annotations

import os
import time

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    os.getenv("WAGENT_RUN_E2E") != "1",
    reason="設 WAGENT_RUN_E2E=1 才跑全棧 E2E（需金鑰、開瀏覽器）",
)


def test_submit_real_task_and_get_result(tmp_path):
    os.environ.setdefault("WAGENT_HEADLESS", "true")
    from infrastructure.container import Container
    from infrastructure.web import create_app

    container = Container.create(db_url=f"sqlite:///{tmp_path / 'e2e.db'}")
    client = TestClient(create_app(container))

    resp = client.post(
        "/tasks",
        json={
            "instruction": "Extract the first quote text and its author.",
            "start_url": "https://quotes.toscrape.com",
        },
    )
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]

    # 背景任務在 TestClient 回應後已執行；輪詢確認終結
    deadline = time.time() + 120
    body = {}
    while time.time() < deadline:
        body = client.get(f"/tasks/{job_id}").json()
        if body["status"] in ("succeeded", "partial", "failed"):
            break
        time.sleep(1)

    assert body["status"] == "succeeded", body
    assert body["result"]
    assert len(body["steps"]) >= 1
