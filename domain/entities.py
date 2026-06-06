"""Domain entities：Task、Job（含狀態機）、SessionState。純邏輯，無框架依賴。"""
from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from domain.errors import InvalidStateTransition
from domain.value_objects import DataSchema, JobStatus, TargetSite

# 狀態機：允許的轉移。key 為當前狀態，value 為可前往的狀態集合。
_ALLOWED: dict[JobStatus, frozenset[JobStatus]] = {
    JobStatus.SUBMITTED: frozenset({JobStatus.PLANNING}),
    JobStatus.PLANNING: frozenset({JobStatus.RUNNING, JobStatus.FAILED}),
    JobStatus.RUNNING: frozenset(
        {
            JobStatus.WAITING_FOR_USER,
            JobStatus.PAUSED,
            JobStatus.SUCCEEDED,
            JobStatus.PARTIAL,
            JobStatus.FAILED,
        }
    ),
    JobStatus.WAITING_FOR_USER: frozenset({JobStatus.RUNNING, JobStatus.FAILED}),
    JobStatus.PAUSED: frozenset({JobStatus.RUNNING, JobStatus.FAILED}),
    JobStatus.SUCCEEDED: frozenset({JobStatus.AWAITING_FEEDBACK}),
    JobStatus.PARTIAL: frozenset({JobStatus.AWAITING_FEEDBACK}),
    JobStatus.FAILED: frozenset({JobStatus.AWAITING_FEEDBACK}),
    JobStatus.AWAITING_FEEDBACK: frozenset({JobStatus.CLOSED}),
    JobStatus.CLOSED: frozenset(),
}


def _new_id() -> str:
    return uuid4().hex


@dataclass
class Task:
    """使用者的請求：自然語言指示 +（可選）目標站、欄位、接棒策略、承接的父 job。"""

    id: str
    instruction: str
    target_site: TargetSite | None = None
    data_schema: DataSchema | None = None
    handoff_policy: str | None = None  # 單任務覆寫；None=用全域預設
    parent_job_id: str | None = None  # 結束後追問：承接前一個 job

    @classmethod
    def create(
        cls,
        instruction: str,
        target_site: TargetSite | None = None,
        data_schema: DataSchema | None = None,
        handoff_policy: str | None = None,
        parent_job_id: str | None = None,
    ) -> Task:
        if not instruction.strip():
            raise ValueError("Task.instruction 不可為空白")
        return cls(
            id=_new_id(),
            instruction=instruction.strip(),
            target_site=target_site,
            data_schema=data_schema,
            handoff_policy=handoff_policy,
            parent_job_id=parent_job_id,
        )


@dataclass
class Job:
    """一次任務執行。持有狀態機與軌跡。"""

    id: str
    task_id: str
    status: JobStatus = JobStatus.SUBMITTED
    steps: list[str] = field(default_factory=list)
    result: str | None = None
    error: str | None = None
    wait_reason: str | None = None

    @classmethod
    def create(cls, task_id: str) -> Job:
        return cls(id=_new_id(), task_id=task_id)

    # --- 狀態機核心 ---
    def _transition(self, target: JobStatus) -> None:
        if target not in _ALLOWED[self.status]:
            raise InvalidStateTransition(self.status, target)
        self.status = target

    # --- 具名轉移（讀起來像領域語言）---
    def start_planning(self) -> None:
        self._transition(JobStatus.PLANNING)

    def start_running(self) -> None:
        self._transition(JobStatus.RUNNING)

    def wait_for_user(self, reason: str) -> None:
        self._transition(JobStatus.WAITING_FOR_USER)
        self.wait_reason = reason

    def resume(self) -> None:
        self._transition(JobStatus.RUNNING)
        self.wait_reason = None

    def pause(self) -> None:
        self._transition(JobStatus.PAUSED)

    def succeed(self, result: str) -> None:
        self._transition(JobStatus.SUCCEEDED)
        self.result = result

    def partial(self, result: str) -> None:
        self._transition(JobStatus.PARTIAL)
        self.result = result

    def fail(self, error: str) -> None:
        self._transition(JobStatus.FAILED)
        self.error = error

    def stop(self, reason: str = "stopped by user") -> None:
        """使用者中止：由 RUNNING/PAUSED/WAITING_FOR_USER 進入 FAILED。"""
        self._transition(JobStatus.FAILED)
        self.error = reason

    def await_feedback(self) -> None:
        self._transition(JobStatus.AWAITING_FEEDBACK)

    def close(self) -> None:
        self._transition(JobStatus.CLOSED)

    # --- 軌跡 ---
    def record_step(self, description: str) -> None:
        self.steps.append(description)

    @property
    def is_terminal(self) -> bool:
        return self.status is JobStatus.CLOSED


@dataclass
class SessionState:
    """持久化的瀏覽器登入狀態參照（對應 browser-use profile / storage_state）。"""

    site_domain: str
    storage_path: str
