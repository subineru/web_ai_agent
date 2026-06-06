"""FollowUpTask use case：結束後追問 → 開一個承接前文的新任務。

讓使用者把一個任務當對話經營：任務結束後仍可追問，新任務自動帶上
前次指示與結果摘要作為脈絡，並沿用目標站與接棒策略。
"""
from __future__ import annotations

from application.use_cases.submit_task import SubmitTaskResult
from domain.entities import Job, Task
from domain.ports import TaskRepo


class FollowUpTask:
    def __init__(self, repo: TaskRepo) -> None:
        self._repo = repo

    def execute(self, parent_job_id: str, message: str) -> SubmitTaskResult:
        if not message.strip():
            raise ValueError("追問訊息不可為空白")
        parent_job = self._repo.get_job(parent_job_id)
        if parent_job is None:
            raise KeyError(f"job 不存在：{parent_job_id}")
        parent_task = self._repo.get_task(parent_job.task_id)
        if parent_task is None:
            raise KeyError(f"task 不存在：{parent_job.task_id}")

        prior_result = (parent_job.result or "").strip().replace("\n", " ")[:300]
        instruction = (
            f"{message.strip()}\n\n"
            f"（承接前一個任務）前次指示：{parent_task.instruction}"
            + (f"\n前次結果：{prior_result}" if prior_result else "")
        )

        new_task = Task.create(
            instruction=instruction,
            target_site=parent_task.target_site,
            data_schema=parent_task.data_schema,
            handoff_policy=parent_task.handoff_policy,
            parent_job_id=parent_job_id,
        )
        new_job = Job.create(task_id=new_task.id)
        self._repo.add_task(new_task)
        self._repo.add_job(new_job)
        return SubmitTaskResult(task_id=new_task.id, job_id=new_job.id)
