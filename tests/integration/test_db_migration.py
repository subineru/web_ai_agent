"""DB 自動補欄位 migration 測試（先寫，TDD）。

模擬「舊 schema」：先建一個缺欄位的 task 表，再讓 make_engine 補上缺的欄位。
"""
from sqlalchemy import inspect, text
from sqlmodel import create_engine

from infrastructure.db import make_engine


def test_adds_missing_columns_to_existing_table(tmp_path):
    db = tmp_path / "old.db"
    url = f"sqlite:///{db}"

    # 1) 造一個「舊版」task 表：故意缺 handoff_policy / parent_job_id
    eng = create_engine(url)
    with eng.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE task ("
                "id VARCHAR PRIMARY KEY, instruction VARCHAR, "
                "target_url VARCHAR, fields_json VARCHAR)"
            )
        )
        conn.execute(text("INSERT INTO task (id, instruction) VALUES ('t1', '舊資料')"))
    eng.dispose()

    # 2) make_engine 應自動補上缺欄位（不丟既有資料）
    engine = make_engine(url)
    cols = {c["name"] for c in inspect(engine).get_columns("task")}
    assert "handoff_policy" in cols
    assert "parent_job_id" in cols

    # 3) 舊資料還在，且能插入帶新欄位的列
    with engine.begin() as conn:
        rows = list(conn.execute(text("SELECT id FROM task")))
        assert ("t1",) in [tuple(r) for r in rows]
        conn.execute(
            text(
                "INSERT INTO task (id, instruction, handoff_policy) "
                "VALUES ('t2', 'x', 'ai_then_human')"
            )
        )
