"""RunBrowserJob use case 測試（先寫，TDD）。對 mock BrowserAgentPort。"""
import pytest

from application.use_cases.run_browser_job import RunBrowserJob
from domain.entities import Job, Task
from domain.value_objects import JobStatus, TargetSite
from tests.fakes import FakeBrowserAgent, InMemoryTaskRepo


def _seed(repo: InMemoryTaskRepo, *, url: str | None = None) -> Job:
    site = TargetSite(url=url) if url else None
    task = Task.create(instruction="抓資料", target_site=site)
    job = Job.create(task_id=task.id)
    repo.add_task(task)
    repo.add_job(job)
    return job


@pytest.mark.asyncio
async def test_success_path_marks_succeeded_and_records_steps():
    repo = InMemoryTaskRepo()
    job = _seed(repo, url="https://quotes.toscrape.com")
    agent = FakeBrowserAgent(success=True, output="3 quotes", n_steps=2)

    out = await RunBrowserJob(repo, agent).execute(job.id)

    assert out.status is JobStatus.SUCCEEDED
    assert out.result == "3 quotes"
    assert len(out.steps) == 2
    assert agent.calls == ["抓資料"]
    # 確認有持久化最終狀態
    assert repo.get_job(job.id).status is JobStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_unsuccessful_result_marks_failed():
    repo = InMemoryTaskRepo()
    job = _seed(repo)
    agent = FakeBrowserAgent(success=False, output=None, error="agent gave up")

    out = await RunBrowserJob(repo, agent).execute(job.id)

    assert out.status is JobStatus.FAILED
    assert out.error == "agent gave up"


@pytest.mark.asyncio
async def test_agent_exception_marks_failed():
    repo = InMemoryTaskRepo()
    job = _seed(repo)
    agent = FakeBrowserAgent(raises=RuntimeError("connection error"))

    out = await RunBrowserJob(repo, agent).execute(job.id)

    assert out.status is JobStatus.FAILED
    assert "connection error" in out.error


@pytest.mark.asyncio
async def test_missing_job_raises():
    repo = InMemoryTaskRepo()
    with pytest.raises(KeyError):
        await RunBrowserJob(repo, FakeBrowserAgent()).execute("nope")
