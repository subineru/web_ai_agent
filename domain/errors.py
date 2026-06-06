"""Domain 層例外。純邏輯，無框架依賴。"""
from __future__ import annotations


class DomainError(Exception):
    """所有 domain 例外的基底。"""


class InvalidStateTransition(DomainError):
    """Job 狀態機不允許的轉移。"""

    def __init__(self, current: object, target: object) -> None:
        super().__init__(f"不允許的狀態轉移：{current} → {target}")
        self.current = current
        self.target = target
