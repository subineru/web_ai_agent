"""即時轉向 use cases：Steer / Pause / Resume / Stop。

每個都會：(1) 驗證並改寫 Job 狀態（透過 repo），(2) 操作該 job 的 SteeringControl，
讓執行中的 agent 在下一步採納。
"""
from __future__ import annotations

from domain.entities import Job
from domain.ports import JobEventPublisher, SteeringRegistry, TaskRepo
from domain.value_objects import JobEvent, JobStatus


def _require_job(repo: TaskRepo, job_id: str) -> Job:
    job = repo.get_job(job_id)
    if job is None:
        raise KeyError(f"job 不存在：{job_id}")
    return job


class _SteeringUseCase:
    def __init__(
        self,
        repo: TaskRepo,
        registry: SteeringRegistry,
        publisher: JobEventPublisher | None = None,
    ) -> None:
        self._repo = repo
        self._registry = registry
        self._publisher = publisher

    def _emit(self, job_id: str, type_: str, data: dict) -> None:
        if self._publisher is not None:
            self._publisher.publish(job_id, JobEvent(type=type_, data=data))


class SteerJob(_SteeringUseCase):
    """執行中即時送出新指示（不改變狀態）。"""

    def execute(self, job_id: str, message: str) -> None:
        job = _require_job(self._repo, job_id)
        if job.status is not JobStatus.RUNNING:
            raise ValueError(f"只有 RUNNING 的任務可即時轉向（目前 {job.status.value}）")
        self._registry.get_or_create(job_id).push(message)
        self._emit(job_id, "step", {"description": f"↪️ 已送出即時指示：{message}"})


class PauseJob(_SteeringUseCase):
    def execute(self, job_id: str) -> None:
        job = _require_job(self._repo, job_id)
        job.pause()
        self._repo.update_job(job)
        self._registry.get_or_create(job_id).pause()
        self._emit(job_id, "status", {"status": job.status.value})


class ResumeJob(_SteeringUseCase):
    def execute(self, job_id: str) -> None:
        job = _require_job(self._repo, job_id)
        job.resume()
        self._repo.update_job(job)
        self._registry.get_or_create(job_id).resume()
        self._emit(job_id, "status", {"status": job.status.value})


class StopJob(_SteeringUseCase):
    def execute(self, job_id: str) -> None:
        job = _require_job(self._repo, job_id)
        job.stop()
        self._repo.update_job(job)
        self._registry.get_or_create(job_id).stop()
        self._emit(job_id, "done", {"status": job.status.value, "error": job.error})
