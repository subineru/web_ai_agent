"""用 FakeBrowserAgent 驗證 BrowserAgentPort 契約。"""
from __future__ import annotations

from domain.ports import BrowserAgentPort
from tests.contract.browser_agent_contract import BrowserAgentPortContract
from tests.fakes import FakeBrowserAgent


class TestFakeBrowserAgent(BrowserAgentPortContract):
    def make_agent(
        self, *, success: bool = True, output: str | None = "ok", error: str | None = None
    ) -> BrowserAgentPort:
        return FakeBrowserAgent(success=success, output=output, error=error, n_steps=2)
