"""create_app 服務前端靜態檔測試（先寫，TDD）。

驗證：掛載靜態檔後，GET / 回 index.html，但 API 路由（/health、/tasks）不被遮蔽。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine

from adapters.persistence.sql_task_repo import SqlTaskRepo
from infrastructure.container import Container
from infrastructure.db import session_factory
from infrastructure.web import create_app
from tests.fakes import FakeBrowserAgent


@pytest.fixture()
def client(tmp_path):
    # 造一個假的前端 dist
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html><body>wagent UI</body></html>", encoding="utf-8")
    (dist / "assets").mkdir()
    (dist / "assets" / "app.js").write_text("console.log('hi')", encoding="utf-8")

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    repo = SqlTaskRepo(session_factory(engine))
    container = Container.for_testing(repo=repo, agent=FakeBrowserAgent())
    return TestClient(create_app(container, static_dir=dist))


def test_root_serves_index_html(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "wagent UI" in r.text


def test_static_asset_served(client):
    r = client.get("/assets/app.js")
    assert r.status_code == 200
    assert "console.log" in r.text


def test_api_not_shadowed_by_static(client):
    assert client.get("/health").json() == {"status": "ok"}
    r = client.post("/tasks", json={"instruction": "抓"})
    assert r.status_code == 202
    assert "job_id" in r.json()


def test_no_static_dir_still_works():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    repo = SqlTaskRepo(session_factory(engine))
    client = TestClient(create_app(Container.for_testing(repo=repo, agent=FakeBrowserAgent())))
    # 沒有靜態目錄時，根路徑為 404，但 API 正常
    assert client.get("/health").json() == {"status": "ok"}
