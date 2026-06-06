"""RunBrowserJob 接合規關卡測試（先寫，TDD）。"""
import pytest

from application.use_cases.compliance import CheckCompliance
from application.use_cases.run_browser_job import RunBrowserJob
from domain.entities import Job, Task
from domain.value_objects import JobStatus, TargetSite
from tests.fakes import FakeBrowserAgent, InMemoryTaskRepo


def _seed(repo, url: str | None) -> Job:
    site = TargetSite(url=url) if url else None
    task = Task.create(instruction="抓", target_site=site)
    job = Job.create(task_id=task.id)
    repo.add_task(task)
    repo.add_job(job)
    return job


class RecordingThrottle:
    def __init__(self) -> None:
        self.acquired: list[str] = []

    async def acquire(self, domain: str) -> None:
        self.acquired.append(domain)


@pytest.mark.asyncio
async def test_denylisted_blocks_and_agent_not_called():
    repo = InMemoryTaskRepo()
    job = _seed(repo, "https://evil.com/x")
    agent = FakeBrowserAgent()
    out = await RunBrowserJob(
        repo, agent, compliance=CheckCompliance(denylist=["evil.com"])
    ).execute(job.id)

    assert out.status is JobStatus.FAILED
    assert "合規" in out.error
    assert agent.calls == []  # 被擋下，agent 不執行


@pytest.mark.asyncio
async def test_allowed_runs_agent():
    repo = InMemoryTaskRepo()
    job = _seed(repo, "https://quotes.toscrape.com")
    agent = FakeBrowserAgent(success=True, output="ok")
    out = await RunBrowserJob(
        repo, agent, compliance=CheckCompliance(denylist=[])
    ).execute(job.id)

    assert out.status is JobStatus.SUCCEEDED
    assert agent.calls == ["抓"]


@pytest.mark.asyncio
async def test_throttle_acquired_for_domain_before_run():
    repo = InMemoryTaskRepo()
    job = _seed(repo, "https://quotes.toscrape.com/page/2")
    throttle = RecordingThrottle()
    await RunBrowserJob(repo, FakeBrowserAgent(), throttle=throttle).execute(job.id)
    assert throttle.acquired == ["quotes.toscrape.com"]


@pytest.mark.asyncio
async def test_no_compliance_dep_still_runs():
    repo = InMemoryTaskRepo()
    job = _seed(repo, "https://evil.com")  # 沒注入 compliance → 不擋
    agent = FakeBrowserAgent()
    out = await RunBrowserJob(repo, agent).execute(job.id)
    assert out.status is JobStatus.SUCCEEDED
