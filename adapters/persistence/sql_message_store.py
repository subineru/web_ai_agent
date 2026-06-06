"""SqlMessageStore：以 SQLModel/SQLite 實作 MessageStore。

對話訊息的單一真相來源。前端在 mount / done / error 時向此對帳，
即使 live SSE 漏送尾段，也能取回完整對話重建畫面。
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlmodel import Field, Session, SQLModel, delete, select


class JobMessageRow(SQLModel, table=True):
    __tablename__ = "job_message"
    id: int | None = Field(default=None, primary_key=True)
    job_id: str = Field(index=True)
    role: str  # 'agent' | 'user' | 'think' | 'system'
    text: str | None = None
    kind: str | None = None  # 'result' | 'error' | 'clarify'
    extra: str | None = None  # JSON（think data 或 artifacts list）
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class SqlMessageStore:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._sf = session_factory

    def save(
        self,
        job_id: str,
        role: str,
        text: str | None,
        kind: str | None = None,
        extra: str | None = None,
    ) -> None:
        with self._sf() as s:
            s.add(
                JobMessageRow(
                    job_id=job_id, role=role, text=text, kind=kind, extra=extra
                )
            )
            s.commit()

    def list_by_job(self, job_id: str) -> list[dict]:
        with self._sf() as s:
            rows = s.exec(
                select(JobMessageRow)
                .where(JobMessageRow.job_id == job_id)
                .order_by(JobMessageRow.id)
            ).all()
            return [
                {
                    "role": r.role,
                    "text": r.text,
                    "kind": r.kind,
                    "extra": r.extra,
                }
                for r in rows
            ]

    def delete_by_job(self, job_id: str) -> None:
        with self._sf() as s:
            s.exec(delete(JobMessageRow).where(JobMessageRow.job_id == job_id))
            s.commit()
