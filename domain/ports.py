"""Domain ports：內層只認介面，外層提供實作（依賴反轉）。

全部用 typing.Protocol 定義。Domain/Application 只 import 本檔，
不 import 任何具體框架（browser-use、fastapi、sqlmodel…）。
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol, runtime_checkable

from domain.entities import Job, SessionState, Task
from domain.learning import LearnedTool
from domain.steering import SteeringControl
from domain.value_objects import AgentRunResult, AgentStep, JobEvent

StepCallback = Callable[[AgentStep], None]


@runtime_checkable
class SteeringRegistry(Protocol):
    """per-job 的 SteeringControl 登錄處（即時轉向用）。"""

    def get_or_create(self, job_id: str) -> SteeringControl: ...

    def remove(self, job_id: str) -> None: ...


@runtime_checkable
class JobEventPublisher(Protocol):
    """把任務執行事件廣播出去（給 SSE/即時串流）。"""

    def publish(self, job_id: str, event: JobEvent) -> None: ...


@runtime_checkable
class BrowserAgentPort(Protocol):
    """驅動瀏覽器完成自然語言任務的 agent。v1 由 browser-use 實作。"""

    async def run(
        self,
        instruction: str,
        *,
        start_url: str | None = None,
        max_steps: int = 40,
        on_step: StepCallback | None = None,
        control: SteeringControl | None = None,
        sensitive_data: dict | None = None,
        allowed_domains: list[str] | None = None,
        download_dir: Path | None = None,
        user_data_dir: Path | None = None,
    ) -> AgentRunResult:
        """執行任務並回傳結果；每進行一步呼叫 on_step（若提供）。

        - 若提供 control，實作應每步輪詢它以採納即時轉向（drain/pause/stop）。
        - 若提供 sensitive_data，實作應交給底層 agent 以佔位符安全填表（LLM 不見原值），
          並用 allowed_domains 限制帳密可用網域。
        """
        ...


@runtime_checkable
class LLMPort(Protocol):
    """純文字 LLM 推理（摘要、澄清判斷等）。"""

    async def complete(self, prompt: str) -> str:
        ...


@runtime_checkable
class TaskRepo(Protocol):
    """Task 與 Job 的持久化。"""

    def add_task(self, task: Task) -> None: ...

    def get_task(self, task_id: str) -> Task | None: ...

    def add_job(self, job: Job) -> None: ...

    def get_job(self, job_id: str) -> Job | None: ...

    def update_job(self, job: Job) -> None: ...


@runtime_checkable
class FeedbackPort(Protocol):
    """使用者回饋的儲存。"""

    def save(self, job_id: str, rating: str, note: str | None = None) -> None: ...


@runtime_checkable
class SessionStore(Protocol):
    """瀏覽器登入狀態的持久化（對應 storage_state / profile）。"""

    def save(self, state: SessionState) -> None: ...

    def load(self, site_domain: str) -> SessionState | None: ...


@runtime_checkable
class CaptchaSolverPort(Protocol):
    """第三方自動解題接縫。v1 不實作（CAPTCHA 走 AI 試 2 次 → 人機接力）。"""

    async def try_solve(self, challenge_image_path: str) -> bool: ...


@runtime_checkable
class RobotsChecker(Protocol):
    """查詢目標 URL 是否被該站 robots.txt 允許抓取。"""

    async def is_allowed(self, url: str, user_agent: str) -> bool: ...


@runtime_checkable
class DomainThrottle(Protocol):
    """每網域節流：acquire 會視需要等待以維持禮貌間隔。"""

    async def acquire(self, domain: str) -> None: ...


@runtime_checkable
class LearningStore(Protocol):
    """沉澱與取回 LearnedTool（成功經驗 / 使用者回饋）。"""

    def save(self, tool: LearnedTool) -> None: ...

    def find_for(self, site_domain: str, *, limit: int = 5) -> list[LearnedTool]: ...


@runtime_checkable
class CredentialVault(Protocol):
    """暫存使用者提供的帳密（依網域），供 agent 以 sensitive_data 安全填表。

    實作**不得**把帳密寫進日誌/DB；僅存於記憶體。
    """

    def store(self, site_domain: str, mapping: dict[str, str]) -> None: ...

    def get(self, site_domain: str) -> dict[str, str] | None: ...

    def clear(self, site_domain: str) -> None: ...
