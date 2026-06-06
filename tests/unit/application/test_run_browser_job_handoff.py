"""RunBrowserJob 例外分級接棒測試（先寫，TDD）。"""
import pytest

from application.use_cases.run_browser_job import RunBrowserJob
from domain.entities import Job, Task
from domain.value_objects import JobStatus, TargetSite
from tests.fakes import FakeBrowserAgent, InMemoryTaskRepo


def _seed(repo, *, policy=None) -> Job:
    task = Task.create(
        instruction="登入後抓資料",
        target_site=TargetSite(url="https://site.com"),
        handoff_policy=policy,
    )
    job = Job.create(task_id=task.id)
    repo.add_task(task)
    repo.add_job(job)
    return job


@pytest.mark.asyncio
async def test_login_error_human_first_escalates_to_waiting():
    repo = InMemoryTaskRepo()
    job = _seed(repo, policy="human_first")
    agent = FakeBrowserAgent(raises=RuntimeError("login required"))
    out = await RunBrowserJob(repo, agent).execute(job.id)
    assert out.status is JobStatus.WAITING_FOR_USER


@pytest.mark.asyncio
async def test_login_error_ai_only_fails():
    repo = InMemoryTaskRepo()
    job = _seed(repo, policy="ai_only")
    agent = FakeBrowserAgent(raises=RuntimeError("login required"))
    out = await RunBrowserJob(repo, agent).execute(job.id)
    assert out.status is JobStatus.FAILED


@pytest.mark.asyncio
async def test_generic_error_fails():
    repo = InMemoryTaskRepo()
    job = _seed(repo)
    agent = FakeBrowserAgent(raises=RuntimeError("totally weird"))
    out = await RunBrowserJob(repo, agent).execute(job.id)
    assert out.status is JobStatus.FAILED
