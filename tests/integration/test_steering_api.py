"""即時轉向 / 澄清 / 回饋 端點整合測試。先寫，TDD。

用預先植入特定狀態的 Job（不跑背景 agent）來確定性驗證 web→use case→domain 串接。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine

from adapters.persistence.sql_task_repo import SqlTaskRepo
from domain.entities import Job, Task
from domain.value_objects import JobStatus
from infrastructure.container import Container
from infrastructure.db import session_factory
from infrastructure.web import create_app
from tests.fakes import FakeBrowserAgent


@pytest.fixture()
def ctx():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    repo = SqlTaskRepo(session_factory(engine))
    container = Container.for_testing(repo=repo, agent=FakeBrowserAgent())
    return container, TestClient(create_app(container))


def _seed(container, status: JobStatus) -> str:
    task = Task.create(instruction="抓")
    job = Job.create(task_id=task.id)
    job.start_planning()
    job.start_running()
    if status is JobStatus.WAITING_FOR_USER:
        job.wait_for_user(reason="captcha")
    elif status is JobStatus.SUCCEEDED:
        job.succeed(result="ok")
    container.repo.add_task(task)
    container.repo.add_job(job)
    return job.id


def test_steer_running_job(ctx):
    container, client = ctx
    jid = _seed(container, JobStatus.RUNNING)
    r = client.post(f"/jobs/{jid}/steer", json={"message": "改去登入頁"})
    assert r.status_code == 200
    assert container.registry.get_or_create(jid).drain() == ["改去登入頁"]


def test_steer_non_running_conflict(ctx):
    container, client = ctx
    jid = _seed(container, JobStatus.SUCCEEDED)
    r = client.post(f"/jobs/{jid}/steer", json={"message": "x"})
    assert r.status_code == 409


def test_pause_then_resume(ctx):
    container, client = ctx
    jid = _seed(container, JobStatus.RUNNING)
    assert client.post(f"/jobs/{jid}/pause").status_code == 200
    assert client.get(f"/tasks/{jid}").json()["status"] == "paused"
    assert client.post(f"/jobs/{jid}/resume").status_code == 200
    assert client.get(f"/tasks/{jid}").json()["status"] == "running"


def test_stop(ctx):
    container, client = ctx
    jid = _seed(container, JobStatus.RUNNING)
    assert client.post(f"/jobs/{jid}/stop").status_code == 200
    assert client.get(f"/tasks/{jid}").json()["status"] == "failed"
    assert container.registry.get_or_create(jid).stopped is True


def test_answer_resumes_waiting_job(ctx):
    container, client = ctx
    jid = _seed(container, JobStatus.WAITING_FOR_USER)
    r = client.post(f"/jobs/{jid}/answer", json={"answer": "已手動過驗證"})
    assert r.status_code == 200
    assert client.get(f"/tasks/{jid}").json()["status"] == "running"
    msgs = container.registry.get_or_create(jid).drain()
    assert len(msgs) == 1
    # 格式化訊息：以原始任務指示開頭，包含使用者回覆與上下文標記
    assert "已手動過驗證" in msgs[0]
    assert "[人工操作完成]" in msgs[0]


def test_feedback_closes_job(ctx):
    container, client = ctx
    jid = _seed(container, JobStatus.SUCCEEDED)
    r = client.post(f"/jobs/{jid}/feedback", json={"rating": "good", "note": "讚"})
    assert r.status_code == 200
    assert client.get(f"/tasks/{jid}").json()["status"] == "closed"


def test_feedback_invalid_rating(ctx):
    container, client = ctx
    jid = _seed(container, JobStatus.SUCCEEDED)
    assert client.post(f"/jobs/{jid}/feedback", json={"rating": "lgtm"}).status_code == 409


def test_unknown_job_404(ctx):
    _container, client = ctx
    assert client.post("/jobs/nope/pause").status_code == 404
