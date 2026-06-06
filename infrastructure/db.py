"""DB engine 與 schema 建立。Infrastructure 層。"""
from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

# 確保所有 table 模型在 create_all/migration 前已註冊到 metadata
import adapters.persistence.sql_feedback_store  # noqa: F401
import adapters.persistence.sql_learning_store  # noqa: F401
import adapters.persistence.sql_message_store  # noqa: F401
import adapters.persistence.sql_task_repo  # noqa: F401


def _migrate_add_missing_columns(engine) -> None:
    """additive migration：替既有表補上模型有、但 DB 缺的欄位。

    SQLModel.create_all 只建缺少的「表」，不會替既有表加「欄位」。這裡用
    ALTER TABLE ADD COLUMN 補齊（SQLite 支援）。只加欄位、不刪不改；
    新欄位需為 nullable 或有 default（本專案新增欄位皆 nullable）。
    """
    insp = inspect(engine)
    existing = set(insp.get_table_names())
    for table in SQLModel.metadata.sorted_tables:
        if table.name not in existing:
            continue  # 不存在的表交給 create_all
        db_cols = {c["name"] for c in insp.get_columns(table.name)}
        for col in table.columns:
            if col.name in db_cols:
                continue
            coltype = col.type.compile(engine.dialect)
            with engine.begin() as conn:
                conn.execute(
                    text(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {coltype}')
                )


def make_engine(url: str = "sqlite:///wagent.db"):
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args)
    SQLModel.metadata.create_all(engine)
    _migrate_add_missing_columns(engine)
    return engine


def session_factory(engine) -> Callable[[], Session]:
    def _make() -> Session:
        return Session(engine)

    return _make
