"""錯誤分類與復原決策（純邏輯政策）。對應計畫的錯誤分級處置表。"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ErrorKind(Enum):
    TRANSIENT = "transient"  # 逾時、網路、元素未現 → 可重試
    LOOP = "loop"  # 步數爆量 / 無進展 → 升級人類
    UNEXPECTED_PAGE = "unexpected_page"  # 非預期頁面 / 彈窗 → 升級人類
    CAPTCHA = "captcha"  # → 人機接力
    LOGIN = "login"  # → 人機接力
    FATAL = "fatal"  # 無法復原 → 標 FAILED


class RecoveryAction(Enum):
    RETRY = "retry"
    ESCALATE = "escalate"  # 升級人類（WAITING_FOR_USER）
    FAIL = "fail"


# 關鍵字啟發式分類（順序有意義：先比對較專一的類別）
_KEYWORDS: list[tuple[ErrorKind, tuple[str, ...]]] = [
    (ErrorKind.CAPTCHA, ("captcha",)),
    (ErrorKind.LOGIN, ("login", "sign in", "authentication required")),
    (ErrorKind.LOOP, ("loop", "no progress", "stuck", "max steps")),
    (ErrorKind.UNEXPECTED_PAGE, ("unexpected", "popup", "modal")),
    (ErrorKind.TRANSIENT, ("timeout", "connection", "network", "not found", "temporarily")),
]


def classify_error(message: str) -> ErrorKind:
    text = message.lower()
    for kind, words in _KEYWORDS:
        if any(w in text for w in words):
            return kind
    return ErrorKind.FATAL


@dataclass(frozen=True)
class RecoveryDecision:
    action: RecoveryAction
    kind: ErrorKind
    reason: str
