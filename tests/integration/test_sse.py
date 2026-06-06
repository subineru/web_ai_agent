"""SSE 串流端點整合測試。先寫，TDD。"""
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
def client_factory():
    def _make(agent):
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        SQLModel.metadata.create_all(engine)
        repo = SqlTaskRepo(session_factory(engine))
        return TestClient(create_app(Container.for_testing(repo=repo, agent=agent)))

    return _make


def test_sse_streams_events_until_done(client_factory):
    client = client_factory(FakeBrowserAgent(success=True, output="ok", n_steps=2))
    job_id = client.post("/tasks", json={"instruction": "抓"}).json()["job_id"]

    body = client.get(f"/tasks/{job_id}/events").text
    assert "running" in body
    assert "step 1" in body
    assert "step 2" in body
    assert "succeeded" in body


def test_sse_reports_failure(client_factory):
    client = client_factory(FakeBrowserAgent(success=False, output=None, error="boom"))
    job_id = client.post("/tasks", json={"instruction": "抓"}).json()["job_id"]
    body = client.get(f"/tasks/{job_id}/events").text
    assert "failed" in body
    assert "boom" in body
