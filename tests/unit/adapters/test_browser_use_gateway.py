"""BrowserUseGateway 映射細節單元測試。"""
from __future__ import annotations

import pytest

from adapters.agents.browser_use_gateway import BrowserUseGateway
from domain.value_objects import AgentStep
from tests.fakes import FakeBUAgent, FakeBUHistory


def _gateway(*, success, final, n_steps=2, capture_task=None):
    def factory(*, task: str, on_step, **_kw):
        if capture_task is not None:
            capture_task.append(task)
        return FakeBUAgent(
            on_step=on_step, n_steps=n_steps, history=FakeBUHistory(successful=success, final=final)
        )

    return BrowserUseGateway(agent_factory=factory)


@pytest.mark.asyncio
async def test_success_maps_final_result_to_output():
    gw = _gateway(success=True, final="3 quotes")
    res = await gw.run("抓名言")
    assert res.success is True
    assert res.output == "3 quotes"
    assert res.error is None


@pytest.mark.asyncio
async def test_failure_maps_final_result_to_error():
    gw = _gateway(success=False, final="agent gave up")
    res = await gw.run("抓名言")
    assert res.success is False
    assert res.error == "agent gave up"
    assert res.output is None


@pytest.mark.asyncio
async def test_steps_collected_and_callback_forwarded():
    gw = _gateway(success=True, final="x", n_steps=3)
    seen: list[AgentStep] = []
    res = await gw.run("task", on_step=seen.append)
    assert len(seen) == 3
    assert len(res.steps) == 3


@pytest.mark.asyncio
async def test_start_url_appended_to_task_when_absent():
    captured: list[str] = []
    gw = _gateway(success=True, final="x", capture_task=captured)
    await gw.run("抓資料", start_url="https://quotes.toscrape.com")
    assert "https://quotes.toscrape.com" in captured[0]
