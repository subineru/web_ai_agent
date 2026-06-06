"""Domain 的 value objects 與列舉。純邏輯，無框架依賴。"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class JobStatus(Enum):
    """Job 生命週期狀態。"""

    SUBMITTED = "submitted"
    PLANNING = "planning"
    RUNNING = "running"
    WAITING_FOR_USER = "waiting_for_user"  # 澄清 / CAPTCHA / 登入 / 錯誤升級
    PAUSED = "paused"  # 使用者主動暫停
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    AWAITING_FEEDBACK = "awaiting_feedback"
    CLOSED = "closed"


class CaptchaResolution(Enum):
    AI = "ai"
    HUMAN = "human"


class JobControl(Enum):
    """使用者對執行中任務的即時控制（Phase 4 即時轉向用）。"""

    REDIRECT = "redirect"
    PAUSE = "pause"
    RESUME = "resume"
    STOP = "stop"


@dataclass(frozen=True)
class TargetSite:
    """要操作的目標網站。"""

    url: str

    def __post_init__(self) -> None:
        if not self.url.startswith(("http://", "https://")):
            raise ValueError(f"TargetSite.url 必須是 http(s) 開頭：{self.url!r}")


@dataclass(frozen=True)
class DataSchema:
    """使用者想抽取的欄位。"""

    fields: tuple[str, ...] | list[str]

    def __post_init__(self) -> None:
        if not self.fields:
            raise ValueError("DataSchema.fields 不可為空")


@dataclass(frozen=True)
class SteeringMessage:
    """使用者在任務執行中即時送出的指示（Phase 4）。"""

    text: str

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("SteeringMessage.text 不可為空白")


@dataclass
class CaptchaEncounter:
    """一次 CAPTCHA 遭遇：AI 先試 max_ai_attempts 次，仍未解則交人機接力。"""

    max_ai_attempts: int = 2
    ai_attempts: int = 0
    resolution: CaptchaResolution | None = None

    @classmethod
    def new(cls, max_ai_attempts: int = 2) -> CaptchaEncounter:
        return cls(max_ai_attempts=max_ai_attempts)

    @property
    def resolved(self) -> bool:
        return self.resolution is not None

    def record_ai_attempt(self) -> None:
        self.ai_attempts += 1

    def should_handoff_to_human(self) -> bool:
        return not self.resolved and self.ai_attempts >= self.max_ai_attempts

    def resolve_by_ai(self) -> None:
        self.resolution = CaptchaResolution.AI

    def resolve_by_human(self) -> None:
        self.resolution = CaptchaResolution.HUMAN


@dataclass(frozen=True)
class JobEvent:
    """任務執行過程中對外廣播的事件（給 SSE/即時串流用）。

    type 慣例：'status'（狀態變更）、'step'（一步）、'done'（終結）。
    """

    type: str
    data: dict

    @property
    def is_terminal(self) -> bool:
        return self.type == "done"


@dataclass(frozen=True)
class AgentStep:
    """agent 執行中的一步（給軌跡/日誌用）。"""

    description: str
    screenshot_path: str | None = None
    # C1: LLM 推理摘要（browser-use AgentOutput 欄位）
    thought: str | None = None
    next_goal: str | None = None
    evaluation: str | None = None
    # C2: 主動登入頁偵測
    login_detected: bool = False
    login_url: str | None = None


@dataclass(frozen=True)
class AgentRunResult:
    """BrowserAgentPort 執行後的結果。"""

    success: bool
    output: str | None = None
    steps: tuple[AgentStep, ...] = field(default_factory=tuple)
    error: str | None = None
    artifacts: tuple[str, ...] = field(default_factory=tuple)  # C3: 下載檔案名清單
    # B8: token 用量統計（input/output/calls，可選）
    token_stats: dict = field(default_factory=dict)
