"""SubmitTask use case 測試（先寫，TDD）。"""
import pytest

from application.use_cases.submit_task import SubmitTask, SubmitTaskCommand
from domain.value_objects import JobStatus
from tests.fakes import InMemoryTaskRepo


def test_submit_creates_task_and_submitted_job():
    repo = InMemoryTaskRepo()
    use_case = SubmitTask(repo)

    result = use_case.execute(
        SubmitTaskCommand(
            instruction="抓首頁標題",
            start_url="https://quotes.toscrape.com",
            fields=["quote", "author"],
        )
    )

    task = repo.get_task(result.task_id)
    job = repo.get_job(result.job_id)
    assert task is not None
    assert task.instruction == "抓首頁標題"
    assert task.target_site.url == "https://quotes.toscrape.com"
    assert task.data_schema.fields == ["quote", "author"]
    assert job is not None
    assert job.task_id == task.id
    assert job.status is JobStatus.SUBMITTED


def test_submit_minimal_without_url_or_fields():
    repo = InMemoryTaskRepo()
    result = SubmitTask(repo).execute(SubmitTaskCommand(instruction="去 example 看看"))
    task = repo.get_task(result.task_id)
    assert task.target_site is None
    assert task.data_schema is None


def test_blank_instruction_rejected():
    repo = InMemoryTaskRepo()
    with pytest.raises(ValueError):
        SubmitTask(repo).execute(SubmitTaskCommand(instruction="  "))
