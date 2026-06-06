"""RecoverFromError use case 測試（先寫，TDD）。"""
from application.use_cases.recover_from_error import RecoverFromError
from domain.entities import Job
from domain.handoff import HandoffPolicy
from domain.value_objects import JobStatus
from domain.recovery import RecoveryAction


def _running_job() -> Job:
    job = Job.create(task_id="t1")
    job.start_planning()
    job.start_running()
    return job


def test_transient_within_budget_retries_and_stays_running():
    job = _running_job()
    decision = RecoverFromError(max_retries=2).execute(job, "Connection error.", attempt=0)
    assert decision.action is RecoveryAction.RETRY
    assert job.status is JobStatus.RUNNING


def test_transient_exceeding_budget_escalates_to_human():
    job = _running_job()
    decision = RecoverFromError(max_retries=2).execute(job, "Connection error.", attempt=2)
    assert decision.action is RecoveryAction.ESCALATE
    assert job.status is JobStatus.WAITING_FOR_USER


def test_loop_escalates_to_human():
    job = _running_job()
    decision = RecoverFromError().execute(job, "loop detected", attempt=0)
    assert decision.action is RecoveryAction.ESCALATE
    assert job.status is JobStatus.WAITING_FOR_USER


def test_captcha_human_first_escalates_immediately():
    job = _running_job()
    decision = RecoverFromError(policy=HandoffPolicy.HUMAN_FIRST).execute(
        job, "CAPTCHA detected", attempt=0
    )
    assert decision.action is RecoveryAction.ESCALATE
    assert job.status is JobStatus.WAITING_FOR_USER
    assert "captcha" in job.wait_reason.lower()


def test_captcha_ai_then_human_lets_ai_try_first():
    # 預設策略：未停滯 → 讓 AI 續試（不立刻交人）
    job = _running_job()
    decision = RecoverFromError(max_retries=2).execute(job, "simple captcha", attempt=0)
    assert decision.action is RecoveryAction.RETRY
    assert job.status is JobStatus.RUNNING


def test_captcha_ai_then_human_escalates_when_stalled():
    job = _running_job()
    decision = RecoverFromError(max_retries=2).execute(job, "simple captcha", attempt=2)
    assert decision.action is RecoveryAction.ESCALATE
    assert job.status is JobStatus.WAITING_FOR_USER


def test_hard_captcha_escalates_even_if_not_stalled():
    job = _running_job()
    decision = RecoverFromError(max_retries=5).execute(
        job, "captcha: select all images with traffic lights", attempt=0
    )
    assert decision.action is RecoveryAction.ESCALATE


def test_fatal_marks_failed():
    job = _running_job()
    decision = RecoverFromError().execute(job, "totally weird thing", attempt=0)
    assert decision.action is RecoveryAction.FAIL
    assert job.status is JobStatus.FAILED
