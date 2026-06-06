"""BrowserAgentPort 可重用契約。

任何 BrowserAgentPort 實作（FakeBrowserAgent、未來的 BrowserUseGateway、
WebwrightGateway）都應繼承此契約並提供 make_agent()，跑同一組行為測試。

注意：基底類別名稱不以 Test 開頭，pytest 不會直接收集；
由子類別（Test*）繼承並執行。
"""
from __future__ import annotations

import abc

import pytest

from domain.ports import BrowserAgentPort
from domain.value_objects import AgentStep


class BrowserAgentPortContract(abc.ABC):
    @abc.abstractmethod
    def make_agent(
        self, *, success: bool = True, output: str | None = "ok", error: str | None = None
    ) -> BrowserAgentPort:
        """回傳一個可被本契約測試的 BrowserAgentPort 實作。"""

    def test_implements_protocol(self):
        agent = self.make_agent()
        assert isinstance(agent, BrowserAgentPort)

    @pytest.mark.asyncio
    async def test_successful_run_returns_output(self):
        agent = self.make_agent(success=True, output="hello")
        result = await agent.run("do something", start_url="https://example.com")
        assert result.success is True
        assert result.output == "hello"

    @pytest.mark.asyncio
    async def test_on_step_callback_is_invoked(self):
        agent = self.make_agent(success=True)
        seen: list[AgentStep] = []
        result = await agent.run("task", on_step=seen.append)
        assert len(seen) >= 1
        assert len(result.steps) >= 1

    @pytest.mark.asyncio
    async def test_failed_run_reports_error(self):
        agent = self.make_agent(success=False, output=None, error="boom")
        result = await agent.run("task")
        assert result.success is False
        assert result.error == "boom"
