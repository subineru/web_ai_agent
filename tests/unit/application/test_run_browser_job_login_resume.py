"""v3 迴歸測試：登入接棒後，本地 job stale 停在 WAITING_FOR_USER 不可導致結果遺失。

重現真因：
- on_step 偵測登入 → RunBrowserJob 的「本地 job」轉 WAITING_FOR_USER。
- 使用者「已登入」由 AnswerClarification 在「另一個 job 實例」resume 並寫回 DB。
- 本地 job 仍 stale；agent 成功返回後，舊程式碼用 stale 狀態提早 return → 不發 done、不存 result。

必須用 SqlTaskRepo（每次 get_job 回傳新實例）才能重現；InMemoryTaskRepo 回同一物件無法重現。
"""
from __future__ import annotations

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine

from adapters.persistence.sql_message_store import SqlMessageStore
from adapters.persistence.sql_task_repo import SqlTaskRepo
from application.use_cases.run_browser_job import RunBrowserJob
from domain.entities import Job, Task
from domain.value_objects import AgentRunResult, AgentStep, TargetSite
from infrastructure.db import session_factory
from tests.fakes import InMemorySteeringRegistry


class _FakePublisher:
    def __init__(self):
        self.events: list[tuple[str, str, dict]] = []

    def publish(self, job_id, event):
        self.events.append((job_id, event.type, event.data))


class _LoginThenResumeAgent:
    """模擬：先發 login_detected step，再模擬使用者『已登入』（另一實例 resume DB），最後成功。"""

    def __init__(self, repo, job_id: str):
        self._repo = repo
        self._job_id = job_id

    async def run(self, instruction, *, on_step=None, **_kw) -> AgentRunResult:
        if on_step:
            on_step(
                AgentStep(
                    description="step 1",
                    login_detected=True,
                    login_url="https://accounts.google.com/signin",
                )
            )
        # 模擬 AnswerClarification：在「另一個 job 實例」上 resume 並寫回 DB
        other = self._repo.get_job(self._job_id)
        other.resume()
        self._repo.update_job(other)
        return AgentRunResult(
            success=True,
            output="完成簡報並下載",
            steps=(),
            artifacts=("deck.pptx",),
        )


@pytest.mark.asyncio
async def test_login_handoff_then_success_emits_done_and_persists_result():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    sf = session_factory(engine)
    repo = SqlTaskRepo(sf)
    msg_store = SqlMessageStore(sf)

    task = Task.create(instruction="做簡報", target_site=TargetSite("https://notebooklm.google.com"))
    job = Job.create(task_id=task.id)
    repo.add_task(task)
    repo.add_job(job)

    pub = _FakePublisher()
    uc = RunBrowserJob(
        repo,
        _LoginThenResumeAgent(repo, job.id),
        publisher=pub,
        registry=InMemorySteeringRegistry(),
        message_store=msg_store,
    )

    result_job = await uc.execute(job.id)

    # 1) 最終狀態必須是 succeeded（不可卡在 waiting_for_user）
    assert result_job.status.value == "succeeded"
    assert repo.get_job(job.id).status.value == "succeeded"

    # 2) done 事件必須發出且帶 result + artifacts
    done = [d for _, t, d in pub.events if t == "done"]
    assert done, "登入接棒後仍必須發 done 事件"
    assert done[-1]["result"] == "完成簡報並下載"
    assert done[-1]["artifacts"] == ["deck.pptx"]

    # 3) message-db 必須有 result 訊息（前端對帳的真相來源）
    msgs = msg_store.list_by_job(job.id)
    result_msgs = [m for m in msgs if m["kind"] == "result"]
    assert result_msgs and result_msgs[-1]["text"] == "完成簡報並下載"


@pytest.mark.asyncio
async def test_login_without_resume_stays_waiting():
    """對照：若使用者『沒有』回覆（DB 仍 waiting），則保持等待、不誤判為成功。"""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    sf = session_factory(engine)
    repo = SqlTaskRepo(sf)

    task = Task.create(instruction="做簡報", target_site=TargetSite("https://notebooklm.google.com"))
    job = Job.create(task_id=task.id)
    repo.add_task(task)
    repo.add_job(job)

    class _LoginNoResumeAgent:
        async def run(self, instruction, *, on_step=None, **_kw) -> AgentRunResult:
            if on_step:
                on_step(
                    AgentStep(
                        description="step 1",
                        login_detected=True,
                        login_url="https://accounts.google.com/signin",
                    )
                )
            return AgentRunResult(success=True, output="x", steps=())

    pub = _FakePublisher()
    uc = RunBrowserJob(
        repo, _LoginNoResumeAgent(), publisher=pub, registry=InMemorySteeringRegistry()
    )
    await uc.execute(job.id)

    assert repo.get_job(job.id).status.value == "waiting_for_user"
    assert not [t for _, t, _ in pub.events if t == "done"]
