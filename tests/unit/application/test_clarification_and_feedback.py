"""AnswerClarification 與 SubmitFeedback use case 測試（先寫，TDD）。"""
import pytest

from application.use_cases.clarification import AnswerClarification
from application.use_cases.feedback import SubmitFeedback
from domain.entities import Job, Task
from domain.value_objects import JobStatus
from tests.fakes import InMemoryFeedbackStore, InMemorySteeringRegistry, InMemoryTaskRepo


def _job_in(repo, status: JobStatus) -> Job:
    task = Task.create(instruction="抓")
    job = Job.create(task_id=task.id)
    job.start_planning()
    job.start_running()
    if status is JobStatus.WAITING_FOR_USER:
        job.wait_for_user(reason="captcha")
    elif status is JobStatus.SUCCEEDED:
        job.succeed(result="ok")
    elif status is JobStatus.FAILED:
        job.fail(error="boom")
    repo.add_task(task)
    repo.add_job(job)
    return job


# --- AnswerClarification ---
def test_answer_resumes_with_context_message():
    """AnswerClarification 應格式化上下文訊息（含原始指示 + 使用者回覆），而非直接推送原始文字。"""
    repo = InMemoryTaskRepo()
    reg = InMemorySteeringRegistry()
    job = _job_in(repo, JobStatus.WAITING_FOR_USER)  # _job_in 已建立 task + job

    AnswerClarification(repo, reg).execute(job.id, "我已手動過了驗證")

    assert repo.get_job(job.id).status is JobStatus.RUNNING
    msgs = reg.get_or_create(job.id).drain()
    assert len(msgs) == 1
    msg = msgs[0]
    # 訊息以原始任務指示開頭（judge 評估時看到真實目標）
    assert msg.startswith("抓")
    # 包含使用者回覆與上下文標記
    assert "我已手動過了驗證" in msg
    assert "[人工操作完成]" in msg


def test_answer_rejected_when_not_waiting():
    repo = InMemoryTaskRepo()
    reg = InMemorySteeringRegistry()
    job = _job_in(repo, JobStatus.SUCCEEDED)
    with pytest.raises(ValueError):
        AnswerClarification(repo, reg).execute(job.id, "ans")


# --- SubmitFeedback ---
def test_feedback_saved_and_job_closed():
    repo = InMemoryTaskRepo()
    store = InMemoryFeedbackStore()
    job = _job_in(repo, JobStatus.SUCCEEDED)

    SubmitFeedback(repo, store).execute(job.id, rating="good", note="讚")

    assert store.saved == [(job.id, "good", "讚")]
    assert repo.get_job(job.id).status is JobStatus.CLOSED


def test_feedback_on_failed_job_ok():
    repo = InMemoryTaskRepo()
    store = InMemoryFeedbackStore()
    job = _job_in(repo, JobStatus.FAILED)
    SubmitFeedback(repo, store).execute(job.id, rating="rejected")
    assert store.saved[0][1] == "rejected"
    assert repo.get_job(job.id).status is JobStatus.CLOSED


def test_invalid_rating_rejected():
    repo = InMemoryTaskRepo()
    store = InMemoryFeedbackStore()
    job = _job_in(repo, JobStatus.SUCCEEDED)
    with pytest.raises(ValueError):
        SubmitFeedback(repo, store).execute(job.id, rating="lgtm")
