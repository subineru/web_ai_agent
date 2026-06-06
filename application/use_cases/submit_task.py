"""SubmitTask use case：把自然語言請求轉成 Task + 初始 Job 並持久化。

只依賴 domain（entities、ports）。不 import 任何框架。
"""
from __future__ import annotations

from dataclasses import dataclass

from domain.entities import Job, Task
from domain.ports import TaskRepo
from domain.value_objects import DataSchema, TargetSite


@dataclass(frozen=True)
class SubmitTaskCommand:
    instruction: str
    start_url: str | None = None
    fields: list[str] | None = None
    handoff_policy: str | None = None


@dataclass(frozen=True)
class SubmitTaskResult:
    task_id: str
    job_id: str


class SubmitTask:
    def __init__(self, repo: TaskRepo) -> None:
        self._repo = repo

    def execute(self, cmd: SubmitTaskCommand) -> SubmitTaskResult:
        target_site = TargetSite(url=cmd.start_url) if cmd.start_url else None
        data_schema = DataSchema(fields=list(cmd.fields)) if cmd.fields else None

        task = Task.create(
            instruction=cmd.instruction,
            target_site=target_site,
            data_schema=data_schema,
            handoff_policy=cmd.handoff_policy,
        )
        job = Job.create(task_id=task.id)

        self._repo.add_task(task)
        self._repo.add_job(job)
        return SubmitTaskResult(task_id=task.id, job_id=job.id)
