"""Task entity 與相關 value object 測試（先寫，TDD）。"""
import pytest

from domain.entities import Task
from domain.value_objects import DataSchema, TargetSite


def test_create_task_minimal():
    task = Task.create(instruction="抓首頁標題")
    assert task.id
    assert task.instruction == "抓首頁標題"
    assert task.target_site is None
    assert task.data_schema is None


def test_create_task_with_site_and_schema():
    task = Task.create(
        instruction="抓產品",
        target_site=TargetSite(url="https://quotes.toscrape.com"),
        data_schema=DataSchema(fields=["quote", "author"]),
    )
    assert task.target_site.url == "https://quotes.toscrape.com"
    assert task.data_schema.fields == ["quote", "author"]


def test_blank_instruction_rejected():
    with pytest.raises(ValueError):
        Task.create(instruction="   ")


def test_target_site_requires_http_scheme():
    with pytest.raises(ValueError):
        TargetSite(url="ftp://example.com")
