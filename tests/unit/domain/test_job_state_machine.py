"""Job 狀態機測試（先寫，TDD）。"""
import pytest

from domain.entities import Job
from domain.errors import InvalidStateTransition
from domain.value_objects import JobStatus


def _new_job() -> Job:
    return Job.create(task_id="t1")


def test_new_job_starts_submitted():
    job = _new_job()
    assert job.status is JobStatus.SUBMITTED


def test_happy_path_to_succeeded_and_closed():
    job = _new_job()
    job.start_planning()
    assert job.status is JobStatus.PLANNING
    job.start_running()
    assert job.status is JobStatus.RUNNING
    job.succeed(result="done")
    assert job.status is JobStatus.SUCCEEDED
    assert job.result == "done"
    job.await_feedback()
    assert job.status is JobStatus.AWAITING_FEEDBACK
    job.close()
    assert job.status is JobStatus.CLOSED


def test_running_can_wait_for_user_and_resume():
    job = _new_job()
    job.start_planning()
    job.start_running()
    job.wait_for_user(reason="captcha")
    assert job.status is JobStatus.WAITING_FOR_USER
    assert job.wait_reason == "captcha"
    job.resume()
    assert job.status is JobStatus.RUNNING


def test_running_can_pause_and_resume():
    job = _new_job()
    job.start_planning()
    job.start_running()
    job.pause()
    assert job.status is JobStatus.PAUSED
    job.resume()
    assert job.status is JobStatus.RUNNING


def test_fail_records_error():
    job = _new_job()
    job.start_planning()
    job.start_running()
    job.fail(error="boom")
    assert job.status is JobStatus.FAILED
    assert job.error == "boom"


def test_invalid_transition_raises():
    job = _new_job()
    # 不能從 SUBMITTED 直接到 RUNNING
    with pytest.raises(InvalidStateTransition):
        job.start_running()


def test_cannot_transition_from_terminal_closed():
    job = _new_job()
    job.start_planning()
    job.start_running()
    job.succeed(result="x")
    job.await_feedback()
    job.close()
    with pytest.raises(InvalidStateTransition):
        job.start_planning()


def test_record_step_appends_history():
    job = _new_job()
    job.start_planning()
    job.start_running()
    job.record_step("navigated")
    job.record_step("extracted")
    assert job.steps == ["navigated", "extracted"]


def test_stop_from_running_marks_failed():
    job = _new_job()
    job.start_planning()
    job.start_running()
    job.stop(reason="user stopped")
    assert job.status is JobStatus.FAILED
    assert job.error == "user stopped"
