"""SqlFeedbackStore：以 SQLModel/SQLite 實作 FeedbackPort。"""
from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlmodel import Field, Session, SQLModel


class FeedbackRow(SQLModel, table=True):
    __tablename__ = "feedback"
    id: int | None = Field(default=None, primary_key=True)
    job_id: str = Field(index=True)
    rating: str
    note: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class SqlFeedbackStore:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._sf = session_factory

    def save(self, job_id: str, rating: str, note: str | None = None) -> None:
        with self._sf() as s:
            s.add(FeedbackRow(job_id=job_id, rating=rating, note=note))
            s.commit()
