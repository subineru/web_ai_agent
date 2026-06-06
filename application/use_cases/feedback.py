"""SubmitFeedback use case：結果回饋（好 / 修正 / 重來），存入 FeedbackPort 並收尾任務。

若回饋帶有修正說明（edited / rejected + note），會沉澱成 LearnedTool，
供同網域下次任務當 few-shot 注入（務實版 RLHF「下次更好」）。
"""
from __future__ import annotations

from domain.compliance import domain_of
from domain.learning import FEEDBACK, LearnedTool
from domain.ports import FeedbackPort, LearningStore, TaskRepo
from domain.value_objects import JobStatus

_VALID_RATINGS = frozenset({"good", "edited", "rejected"})
_FEEDBACK_ELIGIBLE = frozenset(
    {JobStatus.SUCCEEDED, JobStatus.PARTIAL, JobStatus.FAILED, JobStatus.AWAITING_FEEDBACK}
)


class SubmitFeedback:
    def __init__(
        self, repo: TaskRepo, store: FeedbackPort, learning: LearningStore | None = None
    ) -> None:
        self._repo = repo
        self._store = store
        self._learning = learning

    def execute(self, job_id: str, *, rating: str, note: str | None = None) -> None:
        if rating not in _VALID_RATINGS:
            raise ValueError(f"rating 必須是 {sorted(_VALID_RATINGS)} 之一")
        job = self._repo.get_job(job_id)
        if job is None:
            raise KeyError(f"job 不存在：{job_id}")
        if job.status not in _FEEDBACK_ELIGIBLE:
            raise ValueError(f"此狀態不可回饋（目前 {job.status.value}）")

        self._store.save(job_id, rating, note)

        # 帶修正說明的回饋 → 沉澱為下次可用的經驗。
        if self._learning is not None and rating in ("edited", "rejected") and note and note.strip():
            task = self._repo.get_task(job.task_id)
            if task is not None and task.target_site is not None:
                site = domain_of(task.target_site.url)
                if site:
                    self._learning.save(
                        LearnedTool(site, task.instruction, note.strip(), FEEDBACK)
                    )

        if job.status is not JobStatus.AWAITING_FEEDBACK:
            job.await_feedback()
        job.close()
        self._repo.update_job(job)
