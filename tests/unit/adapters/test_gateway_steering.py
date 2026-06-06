"""BrowserUseGateway 每步輪詢 SteeringControl 的測試（先寫，TDD）。"""
from __future__ import annotations

import asyncio

import pytest

from adapters.agents.browser_use_gateway import BrowserUseGateway
from domain.steering import SteeringControl
from tests.fakes import FakeBUAgent, FakeBUHistory


def _gateway_capturing_agent(agents: list, *, n_steps=3, success=True, final="ok"):
    def factory(*, task: str, on_step, **_kw):
        agent = FakeBUAgent(
            on_step=on_step, n_steps=n_steps, history=FakeBUHistory(successful=success, final=final)
        )
        agents.append(agent)
        return agent

    return BrowserUseGateway(agent_factory=factory)


@pytest.mark.asyncio
async def test_pending_steering_forwarded_as_add_new_task():
    agents: list[FakeBUAgent] = []
    gw = _gateway_capturing_agent(agents)
    control = SteeringControl()
    control.push("改去登入頁")

    await gw.run("抓", control=control)

    assert "改去登入頁" in agents[0].added_tasks
    assert control.drain() == []  # 已被消化


@pytest.mark.asyncio
async def test_stop_calls_agent_stop_and_ends_early():
    agents: list[FakeBUAgent] = []
    gw = _gateway_capturing_agent(agents, n_steps=5)
    control = SteeringControl()
    control.stop()

    await gw.run("抓", control=control)

    assert agents[0].stopped is True


@pytest.mark.asyncio
async def test_pause_blocks_until_resumed():
    agents: list[FakeBUAgent] = []
    gw = _gateway_capturing_agent(agents, n_steps=2)
    control = SteeringControl()
    control.pause()

    task = asyncio.create_task(gw.run("抓", control=control))
    await asyncio.sleep(0.05)
    assert not task.done()  # 暫停中，尚未完成
    control.resume()
    await asyncio.wait_for(task, timeout=2.0)
    assert task.done()
