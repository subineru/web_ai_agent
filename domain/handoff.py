"""可配置的接棒（人機交棒）策略。純邏輯。

取代「寫死的立即升級」與「硬數 2 次」：用策略 + 是否停滯 + CAPTCHA 難度決定。
"""
from __future__ import annotations

from enum import Enum

from domain.recovery import ErrorKind


class HandoffPolicy(Enum):
    HUMAN_FIRST = "human_first"  # 一遇驗證/登入立刻交人
    AI_THEN_HUMAN = "ai_then_human"  # AI 先試，停滯才交人（預設）
    AI_ONLY = "ai_only"  # 永不交人

    @classmethod
    def from_str(cls, value: str) -> HandoffPolicy:
        try:
            return cls(value)
        except ValueError:
            return cls.AI_THEN_HUMAN


# 需要接棒判斷的錯誤類別（驗證/登入類）
_HANDOFF_KINDS = frozenset({ErrorKind.CAPTCHA, ErrorKind.LOGIN})


def decide_handoff(
    kind: ErrorKind,
    *,
    hard: bool = False,
    stalled: bool = False,
    policy: HandoffPolicy = HandoffPolicy.AI_THEN_HUMAN,
) -> str:
    """回傳 "human"（交人）或 "ai"（讓 AI 繼續）。

    - 複雜 CAPTCHA（hard）→ 一律交人（自動解不穩且多違 ToS）。
    - AI_ONLY → 永不交人。
    - HUMAN_FIRST → 立刻交人。
    - AI_THEN_HUMAN → 未停滯讓 AI 試，停滯才交人。
    """
    if policy is HandoffPolicy.AI_ONLY:
        return "ai"
    if hard and kind is ErrorKind.CAPTCHA:
        return "human"
    if policy is HandoffPolicy.HUMAN_FIRST:
        return "human"
    # AI_THEN_HUMAN
    return "human" if stalled else "ai"
