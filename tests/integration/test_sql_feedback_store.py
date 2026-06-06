"""SqlFeedbackStore 整合測試（in-memory sqlite）。"""
from sqlmodel import Session, SQLModel, create_engine, select

from adapters.persistence.sql_feedback_store import FeedbackRow, SqlFeedbackStore


def test_save_persists_feedback():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    store = SqlFeedbackStore(lambda: Session(engine))

    store.save("job1", "good", "讚")
    store.save("job1", "edited", None)

    with Session(engine) as s:
        rows = s.exec(select(FeedbackRow)).all()
    assert len(rows) == 2
    assert {r.rating for r in rows} == {"good", "edited"}
