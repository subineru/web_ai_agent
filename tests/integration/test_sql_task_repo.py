"""SqlTaskRepo 整合測試（in-memory sqlite）。先寫，TDD。"""
import pytest
from sqlmodel import Session, SQLModel, create_engine

from adapters.persistence.sql_task_repo import SqlTaskRepo
from domain.entities import Job, Task
from domain.value_objects import DataSchema, JobStatus, TargetSite


@pytest.fixture()
def engine():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(eng)
    return eng


def test_roundtrip_task_with_site_and_schema(engine):
    repo = SqlTaskRepo(lambda: Session(engine))
    task = Task.create(
        instruction="抓產品",
        target_site=TargetSite(url="https://quotes.toscrape.com"),
        data_schema=DataSchema(fields=["quote", "author"]),
    )
    repo.add_task(task)

    loaded = repo.get_task(task.id)
    assert loaded is not None
    assert loaded.instruction == "抓產品"
    assert loaded.target_site.url == "https://quotes.toscrape.com"
    assert list(loaded.data_schema.fields) == ["quote", "author"]


def test_roundtrip_minimal_task(engine):
    repo = SqlTaskRepo(lambda: Session(engine))
    task = Task.create(instruction="看看")
    repo.add_task(task)
    loaded = repo.get_task(task.id)
    assert loaded.target_site is None
    assert loaded.data_schema is None


def test_job_persist_and_update(engine):
    repo = SqlTaskRepo(lambda: Session(engine))
    task = Task.create(instruction="抓")
    repo.add_task(task)
    job = Job.create(task_id=task.id)
    repo.add_job(job)

    # 推進狀態並更新
    job.start_planning()
    job.start_running()
    job.record_step("navigated")
    job.record_step("extracted")
    job.succeed(result="done")
    repo.update_job(job)

    loaded = repo.get_job(job.id)
    assert loaded.status is JobStatus.SUCCEEDED
    assert loaded.result == "done"
    assert loaded.steps == ["navigated", "extracted"]
    assert loaded.task_id == task.id


def test_get_missing_returns_none(engine):
    repo = SqlTaskRepo(lambda: Session(engine))
    assert repo.get_task("nope") is None
    assert repo.get_job("nope") is None


def test_delete_job_removes_job_and_orphan_task(engine):
    repo = SqlTaskRepo(lambda: Session(engine))
    task = Task.create(instruction="抓")
    repo.add_task(task)
    job = Job.create(task_id=task.id)
    repo.add_job(job)

    repo.delete_job(job.id)

    assert repo.get_job(job.id) is None
    # task 已無其他 job 參照 → 一併刪除
    assert repo.get_task(task.id) is None


def test_delete_job_is_noop_for_missing(engine):
    repo = SqlTaskRepo(lambda: Session(engine))
    repo.delete_job("nope")  # 不應拋例外
