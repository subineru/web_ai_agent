"""InMemoryFeedbackStore：測試/單一程序用的 FeedbackPort 實作。"""
from __future__ import annotations


class InMemoryFeedbackStore:
    def __init__(self) -> None:
        self.saved: list[tuple[str, str, str | None]] = []

    def save(self, job_id: str, rating: str, note: str | None = None) -> None:
        self.saved.append((job_id, rating, note))
