"""message-db：訊息持久化 + 對帳端點 + 刪除同步清除（端到端整合測試）。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine

from adapters.persistence.sql_message_store import SqlMessageStore
from adapters.persistence.sql_task_repo import SqlTaskRepo
from infrastructure.container import Container
from infrastructure.db import session_factory
from infrastructure.web import create_app
from tests.fakes import FakeBrowserAgent


@pytest.fixture()
def client_factory():
    def _make(agent):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(engine)
        sf = session_factory(engine)
        container = Container.for_testing(repo=SqlTaskRepo(sf), agent=agent)
        container.message_store = SqlMessageStore(sf)
        return TestClient(create_app(container))

    return _make


def test_messages_persisted_and_reconcilable(client_factory):
    client = client_factory(
        FakeBrowserAgent(success=True, output="3 quotes", n_steps=2)
    )
    job_id = client.post("/tasks", json={"instruction": "抓名言"}).json()["job_id"]

    msgs = client.get(f"/jobs/{job_id}/messages").json()
    roles = [m["role"] for m in msgs]
    # 每步一則 agent 訊息 + 最後一則 result
    assert roles.count("agent") >= 3
    result_msgs = [m for m in msgs if m["kind"] == "result"]
    assert result_msgs and result_msgs[-1]["text"] == "3 quotes"


def test_failed_job_persists_error_message(client_factory):
    client = client_factory(
        FakeBrowserAgent(success=False, output=None, error="gave up")
    )
    job_id = client.post("/tasks", json={"instruction": "抓"}).json()["job_id"]
    msgs = client.get(f"/jobs/{job_id}/messages").json()
    err = [m for m in msgs if m["kind"] == "error"]
    assert err and err[-1]["text"] == "gave up"


def test_delete_job_clears_messages_and_records(client_factory):
    client = client_factory(FakeBrowserAgent(success=True, output="ok", n_steps=1))
    job_id = client.post("/tasks", json={"instruction": "抓"}).json()["job_id"]
    assert client.get(f"/jobs/{job_id}/messages").json()  # 有訊息

    resp = client.delete(f"/jobs/{job_id}")
    assert resp.status_code == 204

    assert client.get(f"/jobs/{job_id}/messages").json() == []
    assert client.get(f"/tasks/{job_id}").status_code == 404
