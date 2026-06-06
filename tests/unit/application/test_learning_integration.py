"""RunBrowserJob 重用經驗 + SubmitFeedback 沉澱（先寫，TDD）。"""
import pytest

from application.use_cases.feedback import SubmitFeedback
from application.use_cases.run_browser_job import RunBrowserJob
from domain.entities import Job, Task
from domain.learning import FEEDBACK, SUCCESS, LearnedTool
from domain.value_objects import TargetSite
from tests.fakes import (
    FakeBrowserAgent,
    InMemoryFeedbackStore,
    InMemoryLearningStore,
    InMemoryTaskRepo,
)

DOMAIN = "quotes.toscrape.com"


def _seed(repo, *, url=f"https://{DOMAIN}", status=None) -> Job:
    task = Task.create(instruction="抓名言", target_site=TargetSite(url=url) if url else None)
    job = Job.create(task_id=task.id)
    if status == "succeeded":
        job.start_planning()
        job.start_running()
        job.succeed(result="ok")
    repo.add_task(task)
    repo.add_job(job)
    return job


class CapturingPublisher:
    def __init__(self):
        self.types = []

    def publish(self, job_id, event):
        self.types.append(event.type)


@pytest.mark.asyncio
async def test_reuses_prior_experience_and_emits_event():
    repo = InMemoryTaskRepo()
    job = _seed(repo)
    learning = InMemoryLearningStore()
    learning.save(LearnedTool(DOMAIN, "抓名言", "資料在 .quote 區塊", SUCCESS))
    agent = FakeBrowserAgent(success=True, output="done")
    pub = CapturingPublisher()

    await RunBrowserJob(repo, agent, publisher=pub, learning=learning).execute(job.id)

    # agent 收到的指示已被增強
    assert "資料在 .quote 區塊" in agent.calls[0]
    assert "reuse" in pub.types


@pytest.mark.asyncio
async def test_records_success_experience():
    repo = InMemoryTaskRepo()
    job = _seed(repo)
    learning = InMemoryLearningStore()
    await RunBrowserJob(repo, FakeBrowserAgent(success=True, output="3 quotes"),
                        learning=learning).execute(job.id)

    saved = learning.find_for(DOMAIN)
    assert len(saved) == 1
    assert saved[0].kind is SUCCESS


@pytest.mark.asyncio
async def test_no_learning_dep_unaffected():
    repo = InMemoryTaskRepo()
    job = _seed(repo)
    out = await RunBrowserJob(repo, FakeBrowserAgent(success=True)).execute(job.id)
    assert out.status.value == "succeeded"


def test_feedback_edited_with_note_sediments():
    repo = InMemoryTaskRepo()
    store = InMemoryFeedbackStore()
    learning = InMemoryLearningStore()
    job = _seed(repo, status="succeeded")

    SubmitFeedback(repo, store, learning=learning).execute(
        job.id, rating="edited", note="作者要含全名"
    )

    tools = learning.find_for(DOMAIN)
    assert len(tools) == 1
    assert tools[0].kind is FEEDBACK
    assert tools[0].guidance == "作者要含全名"


def test_feedback_good_without_note_no_sediment():
    repo = InMemoryTaskRepo()
    store = InMemoryFeedbackStore()
    learning = InMemoryLearningStore()
    job = _seed(repo, status="succeeded")
    SubmitFeedback(repo, store, learning=learning).execute(job.id, rating="good")
    assert learning.find_for(DOMAIN) == []
