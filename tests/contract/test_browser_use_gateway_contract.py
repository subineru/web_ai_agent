"""BrowserUseGateway 跑同一份 BrowserAgentPort 契約（用注入的 fake browser-use Agent）。"""
from __future__ import annotations

from adapters.agents.browser_use_gateway import BrowserUseGateway
from domain.ports import BrowserAgentPort
from tests.contract.browser_agent_contract import BrowserAgentPortContract
from tests.fakes import FakeBUAgent, FakeBUHistory


class TestBrowserUseGatewayContract(BrowserAgentPortContract):
    def make_agent(
        self, *, success: bool = True, output: str | None = "ok", error: str | None = None
    ) -> BrowserAgentPort:
        final = output if success else error

        def factory(*, task: str, on_step, **_kw):
            return FakeBUAgent(
                on_step=on_step,
                n_steps=2,
                history=FakeBUHistory(successful=success, final=final),
            )

        return BrowserUseGateway(agent_factory=factory)
