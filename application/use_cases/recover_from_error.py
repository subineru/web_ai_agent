"""RecoverFromError use case：依錯誤分級 + 接棒策略決定處置並套用到 Job。

政策：
- TRANSIENT 且仍在重試預算內 → RETRY（Job 維持 RUNNING）。
- CAPTCHA / LOGIN → 依 HandoffPolicy 決定交人（ESCALATE）或讓 AI 繼續（RETRY）。
- LOOP / UNEXPECTED_PAGE → ESCALATE（升級人類）。
- FATAL → FAIL（標 FAILED）。
"""
from __future__ import annotations

from domain.entities import Job
from domain.handoff import HandoffPolicy, decide_handoff
from domain.recovery import ErrorKind, RecoveryAction, RecoveryDecision, classify_error

# 複雜 CAPTCHA 的關鍵字（自動解不穩、多違 ToS → 直接交人）
_HARD_CAPTCHA_HINTS = ("grid", "image", "select all", "cloudflare", "turnstile", "recaptcha")
_HANDOFF_KINDS = frozenset({ErrorKind.CAPTCHA, ErrorKind.LOGIN})


def _is_hard_captcha(message: str) -> bool:
    text = message.lower()
    return any(h in text for h in _HARD_CAPTCHA_HINTS)


class RecoverFromError:
    def __init__(
        self,
        *,
        max_retries: int = 2,
        policy: HandoffPolicy = HandoffPolicy.AI_THEN_HUMAN,
    ) -> None:
        self._max_retries = max_retries
        self._policy = policy

    def execute(self, job: Job, error_message: str, *, attempt: int = 0) -> RecoveryDecision:
        kind = classify_error(error_message)

        if kind is ErrorKind.TRANSIENT and attempt < self._max_retries:
            return RecoveryDecision(
                action=RecoveryAction.RETRY,
                kind=kind,
                reason=f"暫時性錯誤，重試 {attempt + 1}/{self._max_retries}",
            )

        if kind is ErrorKind.FATAL:
            job.fail(error=error_message)
            return RecoveryDecision(action=RecoveryAction.FAIL, kind=kind, reason=error_message)

        # CAPTCHA / 登入：依接棒策略決定。
        if kind in _HANDOFF_KINDS:
            stalled = attempt >= self._max_retries
            who = decide_handoff(
                kind,
                hard=_is_hard_captcha(error_message),
                stalled=stalled,
                policy=self._policy,
            )
            if who == "ai":
                return RecoveryDecision(
                    action=RecoveryAction.RETRY,
                    kind=kind,
                    reason=f"{kind.value}：依 {self._policy.value} 由 AI 續試",
                )
            reason = f"{kind.value}: {error_message}"
            job.wait_for_user(reason=reason)
            return RecoveryDecision(action=RecoveryAction.ESCALATE, kind=kind, reason=reason)

        # LOOP / UNEXPECTED_PAGE（及超出預算的 TRANSIENT）→ 升級人類。
        reason = f"{kind.value}: {error_message}"
        job.wait_for_user(reason=reason)
        return RecoveryDecision(action=RecoveryAction.ESCALATE, kind=kind, reason=reason)
