"""RunBrowserJob C1 think 事件 + C2 login 偵測 + C3 artifacts 測試。"""
from __future__ import annotations


import pytest

from application.use_cases.run_browser_job import RunBrowserJob
from domain.entities import Job, Task
from domain.value_objects import AgentRunResult, AgentStep
from tests.fakes import (
    InMemorySteeringRegistry,
    InMemoryTaskRepo,
)


class _FakePublisher:
    def __init__(self):
        self.events: list[tuple[str, str, dict]] = []

    def publish(self, job_id, event):
        self.events.append((job_id, event.type, event.data))


class _FakeAgent:
    """可注入指定 AgentStep 列表的假 agent。"""

    def __init__(self, steps: list[AgentStep], artifacts: tuple[str, ...] = ()):
        self._steps = steps
        self._artifacts = artifacts

    async def run(self, instruction, *, on_step=None, **_kw) -> AgentRunResult:
        for s in self._steps:
            if on_step:
                on_step(s)
        return AgentRunResult(success=True, output="ok", steps=tuple(self._steps), artifacts=self._artifacts)


def _setup(agent):
    repo = InMemoryTaskRepo()
    from domain.value_objects import TargetSite
    task = Task.create(instruction="task", target_site=TargetSite("https://example.com"))
    job = Job.create(task_id=task.id)
    repo.add_task(task)
    repo.add_job(job)
    pub = _FakePublisher()
    reg = InMemorySteeringRegistry()
    uc = RunBrowserJob(repo, agent, publisher=pub, registry=reg)
    return repo, job, pub, uc


# ── C1: think 事件 ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_think_event_emitted_when_thought_present():
    step = AgentStep(description="step 1", thought="考慮中", next_goal="點擊登入")
    agent = _FakeAgent([step])
    repo, job, pub, uc = _setup(agent)
    await uc.execute(job.id)

    think_events = [(jid, d) for jid, t, d in pub.events if t == "think"]
    assert len(think_events) == 1
    assert think_events[0][1]["thought"] == "考慮中"
    assert think_events[0][1]["next_goal"] == "點擊登入"


@pytest.mark.asyncio
async def test_think_event_not_emitted_when_no_thought():
    step = AgentStep(description="step 1")  # no thought/next_goal
    agent = _FakeAgent([step])
    repo, job, pub, uc = _setup(agent)
    await uc.execute(job.id)

    think_events = [t for _, t, _ in pub.events if t == "think"]
    assert len(think_events) == 0


# ── C2: login 偵測 ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_login_detected_emits_clarification_and_waits():
    step = AgentStep(
        description="step 1",
        login_detected=True,
        login_url="https://accounts.google.com/signin",
    )
    agent = _FakeAgent([step])
    repo, job, pub, uc = _setup(agent)
    await uc.execute(job.id)

    types = [t for _, t, _ in pub.events]
    assert "clarification" in types
    assert "status" in types

    # job should have transitioned to waiting then back after agent completed
    clarification_data = next(d for _, t, d in pub.events if t == "clarification")
    assert "accounts.google.com" in clarification_data["reason"]


# ── C3: artifacts 在 done 事件中 ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_artifacts_included_in_done_event():
    step = AgentStep(description="step 1")
    agent = _FakeAgent([step], artifacts=("report.pdf", "audio.mp3"))
    repo, job, pub, uc = _setup(agent)
    await uc.execute(job.id)

    done_events = [d for _, t, d in pub.events if t == "done"]
    assert done_events
    assert done_events[-1]["artifacts"] == ["report.pdf", "audio.mp3"]


@pytest.mark.asyncio
async def test_artifacts_empty_in_done_event_when_none():
    step = AgentStep(description="step 1")
    agent = _FakeAgent([step])
    repo, job, pub, uc = _setup(agent)
    await uc.execute(job.id)

    done_events = [d for _, t, d in pub.events if t == "done"]
    assert done_events[-1]["artifacts"] == []
