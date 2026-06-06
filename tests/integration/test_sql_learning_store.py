"""SqlLearningStore 整合測試（in-memory sqlite）。"""
from sqlmodel import Session, SQLModel, create_engine

from adapters.persistence.sql_learning_store import SqlLearningStore
from domain.learning import FEEDBACK, SUCCESS, LearnedTool


def _store():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return SqlLearningStore(lambda: Session(engine))


def test_save_and_find_by_domain():
    store = _store()
    store.save(LearnedTool("a.com", "抓", "經驗1", SUCCESS))
    store.save(LearnedTool("b.com", "抓", "別站", FEEDBACK))
    store.save(LearnedTool("a.com", "抓", "經驗2", FEEDBACK))

    tools = store.find_for("a.com")
    assert [t.guidance for t in tools] == ["經驗2", "經驗1"]  # 近期優先
    assert all(t.site_domain == "a.com" for t in tools)


def test_find_respects_limit():
    store = _store()
    for i in range(10):
        store.save(LearnedTool("a.com", "抓", f"g{i}", SUCCESS))
    assert len(store.find_for("a.com", limit=3)) == 3


def test_find_unknown_domain_empty():
    assert _store().find_for("nope.com") == []
