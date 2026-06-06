"""測試用 Fake 實作（in-memory）。供 contract 與 application 測試共用。"""
from __future__ import annotations

from domain.entities import Job, SessionState, Task
from domain.learning import LearnedTool
from domain.ports import StepCallback
from domain.steering import SteeringControl
from domain.value_objects import AgentRunResult, AgentStep


class FakeBrowserAgent:
    """可程式化的 BrowserAgentPort 假實作。"""

    def __init__(
        self,
        *,
        success: bool = True,
        output: str | None = "ok",
        error: str | None = None,
        n_steps: int = 1,
        raises: Exception | None = None,
    ) -> None:
        self._success = success
        self._output = output
        self._error = error
        self._n_steps = n_steps
        self._raises = raises
        self.calls: list[str] = []
        self.last_sensitive_data: dict | None = None
        self.last_allowed_domains: list[str] | None = None

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
        download_dir=None,
        user_data_dir=None,
    ) -> AgentRunResult:
        self.calls.append(instruction)
        self.last_sensitive_data = sensitive_data
        self.last_allowed_domains = allowed_domains
        if self._raises is not None:
            raise self._raises
        steps = tuple(AgentStep(description=f"step {i + 1}") for i in range(self._n_steps))
        if on_step:
            for s in steps:
                on_step(s)
        return AgentRunResult(
            success=self._success,
            output=self._output,
            steps=steps,
            error=self._error,
        )


class InMemoryTaskRepo:
    """TaskRepo 的 in-memory 假實作。"""

    def __init__(self) -> None:
        self.tasks: dict[str, Task] = {}
        self.jobs: dict[str, Job] = {}

    def add_task(self, task: Task) -> None:
        self.tasks[task.id] = task

    def get_task(self, task_id: str) -> Task | None:
        return self.tasks.get(task_id)

    def add_job(self, job: Job) -> None:
        self.jobs[job.id] = job

    def get_job(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def update_job(self, job: Job) -> None:
        self.jobs[job.id] = job


class InMemorySteeringRegistry:
    def __init__(self) -> None:
        self._controls: dict[str, SteeringControl] = {}

    def get_or_create(self, job_id: str) -> SteeringControl:
        return self._controls.setdefault(job_id, SteeringControl())

    def remove(self, job_id: str) -> None:
        self._controls.pop(job_id, None)


class InMemoryLearningStore:
    def __init__(self) -> None:
        self.tools: list[LearnedTool] = []

    def save(self, tool: LearnedTool) -> None:
        self.tools.append(tool)

    def find_for(self, site_domain: str, *, limit: int = 5) -> list[LearnedTool]:
        matched = [t for t in self.tools if t.site_domain == site_domain]
        return list(reversed(matched))[:limit]  # 近期優先


class FakeLLM:
    def __init__(self, reply: str = "reply") -> None:
        self._reply = reply

    async def complete(self, prompt: str) -> str:
        return self._reply


class FakeBUHistory:
    """模擬 browser-use 的 AgentHistoryList。"""

    def __init__(self, *, successful: bool, final: str | None) -> None:
        self._successful = successful
        self._final = final

    def is_successful(self) -> bool:
        return self._successful

    def is_done(self) -> bool:
        return True

    def final_result(self) -> str | None:
        return self._final


class FakeBUAgent:
    """模擬 browser-use 的 Agent：run() 會呼叫 step callback 數次後回傳 history。

    支援即時轉向控制方法：add_new_task / pause / resume / stop（記錄呼叫）。
    """

    def __init__(self, *, on_step, n_steps: int, history: FakeBUHistory) -> None:
        self._on_step = on_step
        self._n_steps = n_steps
        self._history = history
        self.added_tasks: list[str] = []
        self.paused = False
        self.stopped = False

    def add_new_task(self, new_task: str) -> None:
        self.added_tasks.append(new_task)

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    def stop(self) -> None:
        self.stopped = True

    async def run(self, max_steps: int = 40) -> FakeBUHistory:
        for i in range(self._n_steps):
            if self._on_step is not None:
                await self._on_step(None, None, i + 1)
            if self.stopped:
                break
        return self._history


class InMemoryFeedbackStore:
    def __init__(self) -> None:
        self.saved: list[tuple[str, str, str | None]] = []

    def save(self, job_id: str, rating: str, note: str | None = None) -> None:
        self.saved.append((job_id, rating, note))


class InMemorySessionStore:
    def __init__(self) -> None:
        self._by_domain: dict[str, SessionState] = {}

    def save(self, state: SessionState) -> None:
        self._by_domain[state.site_domain] = state

    def load(self, site_domain: str) -> SessionState | None:
        return self._by_domain.get(site_domain)
