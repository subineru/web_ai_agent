"""RunBrowserJob 發事件測試（先寫，TDD）。"""
import pytest

from application.use_cases.run_browser_job import RunBrowserJob
from domain.entities import Job, Task
from tests.fakes import FakeBrowserAgent, InMemoryTaskRepo


class CapturingPublisher:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []  # (job_id, event.type)

    def publish(self, job_id, event) -> None:
        self.events.append((job_id, event.type))


def _seed(repo: InMemoryTaskRepo) -> Job:
    task = Task.create(instruction="抓")
    job = Job.create(task_id=task.id)
    repo.add_task(task)
    repo.add_job(job)
    return job


@pytest.mark.asyncio
async def test_emits_status_and_step_and_done_events():
    repo = InMemoryTaskRepo()
    job = _seed(repo)
    pub = CapturingPublisher()
    agent = FakeBrowserAgent(success=True, output="ok", n_steps=2)

    await RunBrowserJob(repo, agent, publisher=pub).execute(job.id)

    types = [t for (_jid, t) in pub.events]
    assert "status" in types  # 至少有狀態事件（running）
    assert types.count("step") == 2  # 每步一個
    assert types[-1] == "done"  # 最後是 done


@pytest.mark.asyncio
async def test_done_event_on_failure_too():
    repo = InMemoryTaskRepo()
    job = _seed(repo)
    pub = CapturingPublisher()
    agent = FakeBrowserAgent(success=False, output=None, error="boom")

    await RunBrowserJob(repo, agent, publisher=pub).execute(job.id)
    assert pub.events[-1][1] == "done"


@pytest.mark.asyncio
async def test_works_without_publisher():
    repo = InMemoryTaskRepo()
    job = _seed(repo)
    # 不給 publisher 也要正常
    out = await RunBrowserJob(repo, FakeBrowserAgent()).execute(job.id)
    assert out.status.value == "succeeded"
