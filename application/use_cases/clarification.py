"""AnswerClarification use case：使用者回答澄清/完成人機接力後，注入上下文並續跑。

當 job 處於 WAITING_FOR_USER（澄清 / CAPTCHA / 登入 / 錯誤升級）時：
把格式化的上下文訊息推入 SteeringControl 讓執行中的 agent 採納，並把 job 轉回 RUNNING。

格式設計：以原始任務指示開頭（讓 judge 評估真實目標），後附人工操作確認與使用者回覆。
若使用者回覆只是確認（如「已登入」），AI 繼續原始任務；若含新指示，AI 依新指示行動。
"""
from __future__ import annotations

from domain.ports import JobEventPublisher, SteeringRegistry, TaskRepo
from domain.value_objects import JobEvent, JobStatus


class AnswerClarification:
    def __init__(
        self,
        repo: TaskRepo,
        registry: SteeringRegistry,
        publisher: JobEventPublisher | None = None,
    ) -> None:
        self._repo = repo
        self._registry = registry
        self._publisher = publisher

    def execute(self, job_id: str, answer: str) -> None:
        job = self._repo.get_job(job_id)
        if job is None:
            raise KeyError(f"job 不存在：{job_id}")
        if job.status is not JobStatus.WAITING_FOR_USER:
            raise ValueError(f"只有等待使用者的任務可回答（目前 {job.status.value}）")
        control = self._registry.get_or_create(job_id)

        # 取原始任務指示（讓 judge 評估真實目標，不被「已登入」等確認訊息覆蓋）
        task = self._repo.get_task(job.task_id)
        original = task.instruction if task else ""

        # 格式化上下文：原始任務 + 操作確認 + 使用者回覆
        # 若回覆為確認信號 → AI 繼續原任務；若含新指示 → AI 依新指示行動（即時轉向）
        context_msg = (
            f"{original}\n\n"
            f"[人工操作完成] 使用者回覆：「{answer}」。\n"
            f"若回覆為操作確認（如「已登入」「完成」），請繼續執行原始任務；\n"
            f"若回覆包含新指示，請依新指示行動。"
        )
        control.push(context_msg)
        control.resume()  # 解除 pause（C2 登入偵測 / 人機接力後繼續執行）
        job.resume()
        self._repo.update_job(job)
        if self._publisher is not None:
            self._publisher.publish(job_id, JobEvent(type="status", data={"status": "running"}))
