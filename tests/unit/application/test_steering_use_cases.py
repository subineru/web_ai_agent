"""Steer/Pause/Resume/Stop use case 測試（先寫，TDD）。"""
import pytest

from application.use_cases.steering import PauseJob, ResumeJob, SteerJob, StopJob
from domain.entities import Job, Task
from domain.value_objects import JobStatus
from tests.fakes import InMemorySteeringRegistry, InMemoryTaskRepo


def _running_job(repo: InMemoryTaskRepo) -> Job:
    task = Task.create(instruction="抓")
    job = Job.create(task_id=task.id)
    job.start_planning()
    job.start_running()
    repo.add_task(task)
    repo.add_job(job)
    return job


def test_steer_pushes_message_to_control():
    repo = InMemoryTaskRepo()
    reg = InMemorySteeringRegistry()
    job = _running_job(repo)

    SteerJob(repo, reg).execute(job.id, "改去登入頁")

    assert reg.get_or_create(job.id).drain() == ["改去登入頁"]
    # steering 不改變狀態
    assert repo.get_job(job.id).status is JobStatus.RUNNING


def test_steer_rejected_when_not_running():
    repo = InMemoryTaskRepo()
    reg = InMemorySteeringRegistry()
    task = Task.create(instruction="x")
    job = Job.create(task_id=task.id)  # 還在 SUBMITTED
    repo.add_task(task)
    repo.add_job(job)
    with pytest.raises(ValueError):
        SteerJob(repo, reg).execute(job.id, "msg")


def test_pause_sets_status_and_control():
    repo = InMemoryTaskRepo()
    reg = InMemorySteeringRegistry()
    job = _running_job(repo)

    PauseJob(repo, reg).execute(job.id)

    assert repo.get_job(job.id).status is JobStatus.PAUSED
    assert reg.get_or_create(job.id).paused is True


def test_resume_from_paused():
    repo = InMemoryTaskRepo()
    reg = InMemorySteeringRegistry()
    job = _running_job(repo)
    PauseJob(repo, reg).execute(job.id)

    ResumeJob(repo, reg).execute(job.id)

    assert repo.get_job(job.id).status is JobStatus.RUNNING
    assert reg.get_or_create(job.id).paused is False


def test_stop_marks_failed_and_control():
    repo = InMemoryTaskRepo()
    reg = InMemorySteeringRegistry()
    job = _running_job(repo)

    StopJob(repo, reg).execute(job.id)

    assert repo.get_job(job.id).status is JobStatus.FAILED
    assert reg.get_or_create(job.id).stopped is True
