"""FastAPI 端到端整合測試（TestClient + Fake agent + 真 sqlite）。先寫，TDD。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine
from sqlalchemy.pool import StaticPool

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
        repo = SqlTaskRepo(session_factory(engine))
        container = Container.for_testing(repo=repo, agent=agent)
        return TestClient(create_app(container))

    return _make


def test_submit_runs_in_background_and_succeeds(client_factory):
    client = client_factory(FakeBrowserAgent(success=True, output="3 quotes", n_steps=2))

    resp = client.post(
        "/tasks",
        json={"instruction": "抓名言", "start_url": "https://quotes.toscrape.com",
              "fields": ["quote", "author"]},
    )
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]

    got = client.get(f"/tasks/{job_id}")
    assert got.status_code == 200
    body = got.json()
    assert body["status"] == "succeeded"
    assert body["result"] == "3 quotes"
    assert body["steps"] == ["step 1", "step 2"]


def test_failed_agent_marks_job_failed(client_factory):
    client = client_factory(FakeBrowserAgent(success=False, output=None, error="gave up"))
    resp = client.post("/tasks", json={"instruction": "抓"})
    job_id = resp.json()["job_id"]
    body = client.get(f"/tasks/{job_id}").json()
    assert body["status"] == "failed"
    assert body["error"] == "gave up"


def test_get_unknown_job_404(client_factory):
    client = client_factory(FakeBrowserAgent())
    assert client.get("/tasks/nope").status_code == 404


def test_blank_instruction_rejected(client_factory):
    client = client_factory(FakeBrowserAgent())
    resp = client.post("/tasks", json={"instruction": "   "})
    assert resp.status_code == 422
