"""SqlMessageStore 整合測試（in-memory sqlite）。"""
import json

from sqlmodel import Session, SQLModel, create_engine

from adapters.persistence.sql_message_store import SqlMessageStore


def _store():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return SqlMessageStore(lambda: Session(engine))


def test_save_and_list_preserves_order_and_fields():
    store = _store()
    store.save("job1", "user", "請做某事")
    store.save("job1", "think", None, extra=json.dumps({"next_goal": "點按鈕"}))
    store.save("job1", "agent", "step 1")
    store.save("job1", "agent", "完成", kind="result", extra=json.dumps(["a.pptx"]))

    msgs = store.list_by_job("job1")
    assert [m["role"] for m in msgs] == ["user", "think", "agent", "agent"]
    assert msgs[1]["extra"] and json.loads(msgs[1]["extra"])["next_goal"] == "點按鈕"
    assert msgs[3]["kind"] == "result"
    assert json.loads(msgs[3]["extra"]) == ["a.pptx"]


def test_list_is_scoped_by_job():
    store = _store()
    store.save("jobA", "agent", "a-step")
    store.save("jobB", "agent", "b-step")
    assert len(store.list_by_job("jobA")) == 1
    assert store.list_by_job("jobA")[0]["text"] == "a-step"


def test_delete_by_job_removes_only_that_job():
    store = _store()
    store.save("jobA", "agent", "a-step")
    store.save("jobB", "agent", "b-step")

    store.delete_by_job("jobA")

    assert store.list_by_job("jobA") == []
    assert len(store.list_by_job("jobB")) == 1
