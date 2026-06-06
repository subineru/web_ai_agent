"""SqlLearningStore：以 SQLModel/SQLite 實作 LearningStore（LearnedTool 沉澱）。"""
from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlmodel import Field, Session, SQLModel, desc, select

from domain.learning import LearnedTool


class LearnedToolRow(SQLModel, table=True):
    __tablename__ = "learned_tool"
    id: int | None = Field(default=None, primary_key=True)
    site_domain: str = Field(index=True)
    instruction: str
    guidance: str
    kind: str
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class SqlLearningStore:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._sf = session_factory

    def save(self, tool: LearnedTool) -> None:
        with self._sf() as s:
            s.add(
                LearnedToolRow(
                    site_domain=tool.site_domain,
                    instruction=tool.instruction,
                    guidance=tool.guidance,
                    kind=tool.kind,
                )
            )
            s.commit()

    def find_for(self, site_domain: str, *, limit: int = 5) -> list[LearnedTool]:
        with self._sf() as s:
            rows = s.exec(
                select(LearnedToolRow)
                .where(LearnedToolRow.site_domain == site_domain)
                .order_by(desc(LearnedToolRow.id))
                .limit(limit)
            ).all()
        return [
            LearnedTool(
                site_domain=r.site_domain,
                instruction=r.instruction,
                guidance=r.guidance,
                kind=r.kind,
            )
            for r in rows
        ]
