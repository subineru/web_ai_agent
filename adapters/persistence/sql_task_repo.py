"""SqlTaskRepo：以 SQLModel/SQLite 實作 TaskRepo（domain Port）。

domain entities 是純 dataclass，與 DB row（SQLModel）分離；本檔負責雙向映射。
"""
from __future__ import annotations

import json
from collections.abc import Callable

from sqlmodel import Field, Session, SQLModel, select

from domain.entities import Job, Task
from domain.value_objects import DataSchema, JobStatus, TargetSite

SessionFactory = Callable[[], Session]


# --- DB rows ---
class TaskRow(SQLModel, table=True):
    __tablename__ = "task"
    id: str = Field(primary_key=True)
    instruction: str
    target_url: str | None = None
    fields_json: str | None = None  # JSON list[str]
    handoff_policy: str | None = None
    parent_job_id: str | None = None


class JobRow(SQLModel, table=True):
    __tablename__ = "job"
    id: str = Field(primary_key=True)
    task_id: str = Field(index=True)
    status: str
    steps_json: str = "[]"  # JSON list[str]
    result: str | None = None
    error: str | None = None
    wait_reason: str | None = None


# --- 映射 ---
def _task_to_row(task: Task) -> TaskRow:
    return TaskRow(
        id=task.id,
        instruction=task.instruction,
        target_url=task.target_site.url if task.target_site else None,
        fields_json=json.dumps(list(task.data_schema.fields)) if task.data_schema else None,
        handoff_policy=task.handoff_policy,
        parent_job_id=task.parent_job_id,
    )


def _row_to_task(row: TaskRow) -> Task:
    return Task(
        id=row.id,
        instruction=row.instruction,
        target_site=TargetSite(url=row.target_url) if row.target_url else None,
        data_schema=DataSchema(fields=json.loads(row.fields_json)) if row.fields_json else None,
        handoff_policy=row.handoff_policy,
        parent_job_id=row.parent_job_id,
    )


def _job_to_row(job: Job) -> JobRow:
    return JobRow(
        id=job.id,
        task_id=job.task_id,
        status=job.status.value,
        steps_json=json.dumps(job.steps),
        result=job.result,
        error=job.error,
        wait_reason=job.wait_reason,
    )


def _row_to_job(row: JobRow) -> Job:
    return Job(
        id=row.id,
        task_id=row.task_id,
        status=JobStatus(row.status),
        steps=json.loads(row.steps_json),
        result=row.result,
        error=row.error,
        wait_reason=row.wait_reason,
    )


class SqlTaskRepo:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._sf = session_factory

    def add_task(self, task: Task) -> None:
        with self._sf() as s:
            s.add(_task_to_row(task))
            s.commit()

    def get_task(self, task_id: str) -> Task | None:
        with self._sf() as s:
            row = s.get(TaskRow, task_id)
            return _row_to_task(row) if row else None

    def add_job(self, job: Job) -> None:
        with self._sf() as s:
            s.add(_job_to_row(job))
            s.commit()

    def get_job(self, job_id: str) -> Job | None:
        with self._sf() as s:
            row = s.get(JobRow, job_id)
            return _row_to_job(row) if row else None

    def update_job(self, job: Job) -> None:
        with self._sf() as s:
            row = s.get(JobRow, job.id)
            if row is None:
                s.add(_job_to_row(job))
            else:
                new = _job_to_row(job)
                row.status = new.status
                row.steps_json = new.steps_json
                row.result = new.result
                row.error = new.error
                row.wait_reason = new.wait_reason
                s.add(row)
            s.commit()

    def list_job_ids(self) -> list[str]:
        with self._sf() as s:
            return list(s.exec(select(JobRow.id)).all())

    def delete_job(self, job_id: str) -> None:
        """刪除 job；若其 task 已無其他 job 參照，連 task 一併刪除。"""
        with self._sf() as s:
            row = s.get(JobRow, job_id)
            if row is None:
                return
            task_id = row.task_id
            s.delete(row)
            s.commit()
            others = s.exec(
                select(JobRow.id).where(JobRow.task_id == task_id)
            ).first()
            if others is None:
                task_row = s.get(TaskRow, task_id)
                if task_row is not None:
                    s.delete(task_row)
                    s.commit()
