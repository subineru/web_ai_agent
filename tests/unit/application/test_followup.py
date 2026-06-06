"""FollowUpTask use case 測試（先寫，TDD）。"""
import pytest

from application.use_cases.followup import FollowUpTask
from domain.entities import Job, Task
from domain.value_objects import JobStatus, TargetSite
from tests.fakes import InMemoryTaskRepo


def _finished_parent(repo) -> Job:
    task = Task.create(
        instruction="抓前 3 則名言",
        target_site=TargetSite(url="https://quotes.toscrape.com"),
        handoff_policy="human_first",
    )
    job = Job.create(task_id=task.id)
    job.start_planning()
    job.start_running()
    job.succeed(result="愛因斯坦、羅琳…")
    repo.add_task(task)
    repo.add_job(job)
    return job


def test_followup_creates_linked_task_carrying_context():
    repo = InMemoryTaskRepo()
    parent = _finished_parent(repo)

    res = FollowUpTask(repo).execute(parent.id, "再多抓 5 則")

    new_task = repo.get_task(res.task_id)
    new_job = repo.get_job(res.job_id)
    assert new_job.status is JobStatus.SUBMITTED
    assert new_task.parent_job_id == parent.id
    # 承接前文：指示含使用者新訊息 + 前次脈絡
    assert "再多抓 5 則" in new_task.instruction
    assert "抓前 3 則名言" in new_task.instruction  # 前次指示
    assert "愛因斯坦" in new_task.instruction  # 前次結果摘要
    # 沿用目標站與接棒策略
    assert new_task.target_site.url == "https://quotes.toscrape.com"
    assert new_task.handoff_policy == "human_first"


def test_followup_missing_parent_raises():
    repo = InMemoryTaskRepo()
    with pytest.raises(KeyError):
        FollowUpTask(repo).execute("nope", "msg")


def test_followup_blank_message_rejected():
    repo = InMemoryTaskRepo()
    parent = _finished_parent(repo)
    with pytest.raises(ValueError):
        FollowUpTask(repo).execute(parent.id, "   ")
