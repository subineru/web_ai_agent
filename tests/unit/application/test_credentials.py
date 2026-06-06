"""安全帳密輸入測試（先寫，TDD）。重點：帳密不外洩到事件/日誌/結果。"""
import pytest

from application.use_cases.provide_credentials import ProvideCredentials
from application.use_cases.run_browser_job import RunBrowserJob
from domain.entities import Job, Task
from domain.value_objects import TargetSite
from infrastructure.credentials import InMemoryCredentialVault
from tests.fakes import FakeBrowserAgent, InMemoryTaskRepo

SECRET_USER = "alice@example.com"
SECRET_PASS = "hunter2-very-secret"


def _seed(repo) -> Job:
    task = Task.create(instruction="登入後抓", target_site=TargetSite(url="https://site.com"))
    job = Job.create(task_id=task.id)
    repo.add_task(task)
    repo.add_job(job)
    return job


def test_provide_validates_and_stores_by_domain():
    vault = InMemoryCredentialVault()
    ProvideCredentials(vault).execute(
        "site.com", {"x_user": SECRET_USER, "x_pass": SECRET_PASS}
    )
    assert vault.get("site.com") == {"x_user": SECRET_USER, "x_pass": SECRET_PASS}


def test_provide_rejects_empty():
    with pytest.raises(ValueError):
        ProvideCredentials(InMemoryCredentialVault()).execute("site.com", {})


class CapturingPublisher:
    def __init__(self):
        self.events = []

    def publish(self, job_id, event):
        self.events.append(event)


@pytest.mark.asyncio
async def test_credentials_passed_to_agent_but_never_leak():
    repo = InMemoryTaskRepo()
    job = _seed(repo)
    vault = InMemoryCredentialVault()
    vault.store("site.com", {"x_user": SECRET_USER, "x_pass": SECRET_PASS})
    agent = FakeBrowserAgent(success=True, output="done")
    pub = CapturingPublisher()

    await RunBrowserJob(repo, agent, publisher=pub, credentials=vault).execute(job.id)

    # 1) agent 確實收到 sensitive_data 與 allowed_domains
    assert agent.last_sensitive_data is not None
    assert SECRET_PASS in str(agent.last_sensitive_data)
    assert agent.last_allowed_domains  # 非空

    # 2) 帳密「絕不」出現在事件 / 步驟 / 結果中
    blob = repr([(e.type, e.data) for e in pub.events])
    assert SECRET_PASS not in blob
    assert SECRET_USER not in blob
    done = repo.get_job(job.id)
    assert SECRET_PASS not in repr(done.steps)
    assert SECRET_PASS not in (done.result or "")
