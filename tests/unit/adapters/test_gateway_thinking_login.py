"""BrowserUseGateway C1（think）+ C2（login 偵測）+ C3（artifacts）測試。"""
from __future__ import annotations

import pytest

from adapters.agents.browser_use_gateway import BrowserUseGateway, _detect_login_page
from domain.value_objects import AgentStep
from tests.fakes import FakeBUAgent, FakeBUHistory


# ── _detect_login_page 純函式 ─────────────────────────────────────────────────


def test_detect_google_login_by_url():
    assert _detect_login_page("https://accounts.google.com/signin/v2/identifier", "Sign in") is True


def test_detect_login_by_title_only():
    assert _detect_login_page("https://notebooklm.google.com/", "Sign in - Google") is True


def test_detect_no_login_normal_page():
    assert _detect_login_page("https://notebooklm.google.com/", "My Notebook") is False


def test_detect_slash_login_path():
    assert _detect_login_page("https://example.com/login", "Example") is True


def test_detect_slash_signin_path():
    assert _detect_login_page("https://example.com/signin", "Example") is True


# ── gateway 整合：thinking 欄位被傳到 AgentStep ───────────────────────────────


class _FakeAgentOutput:
    def __init__(self, thinking=None, next_goal=None, evaluation_previous_goal=None):
        self.thinking = thinking
        self.next_goal = next_goal
        self.evaluation_previous_goal = evaluation_previous_goal


class _FakeBrowserState:
    def __init__(self, url="https://example.com", title="Example"):
        self.url = url
        self.title = title


class FakeBUAgentWithData(FakeBUAgent):
    """在 step callback 中傳真實的 browser_state + agent_output。"""

    def __init__(self, *, on_step, n_steps, history, states=None, outputs=None):
        super().__init__(on_step=on_step, n_steps=n_steps, history=history)
        self._states = states or [_FakeBrowserState()] * n_steps
        self._outputs = outputs or [None] * n_steps

    async def run(self, max_steps=40):
        for i in range(self._n_steps):
            if self._on_step is not None:
                await self._on_step(self._states[i], self._outputs[i], i + 1)
            if self.stopped:
                break
        return self._history


def _make_gw(*, n_steps=2, states=None, outputs=None, success=True, final="ok"):
    def factory(*, task, on_step, **_kw):
        return FakeBUAgentWithData(
            on_step=on_step,
            n_steps=n_steps,
            history=FakeBUHistory(successful=success, final=final),
            states=states,
            outputs=outputs,
        )

    return BrowserUseGateway(agent_factory=factory)


@pytest.mark.asyncio
async def test_thinking_forwarded_to_agent_step():
    outputs = [_FakeAgentOutput(thinking="Deep thought", next_goal="Click login")]
    gw = _make_gw(n_steps=1, outputs=outputs)
    seen: list[AgentStep] = []
    await gw.run("task", on_step=seen.append)
    assert seen[0].thought == "Deep thought"
    assert seen[0].next_goal == "Click login"


@pytest.mark.asyncio
async def test_thinking_none_when_no_agent_output():
    gw = _make_gw(n_steps=1, outputs=[None])
    seen: list[AgentStep] = []
    await gw.run("task", on_step=seen.append)
    assert seen[0].thought is None
    assert seen[0].next_goal is None


@pytest.mark.asyncio
async def test_login_detected_on_google_signin():
    states = [_FakeBrowserState(url="https://accounts.google.com/signin", title="Sign in")]
    gw = _make_gw(n_steps=1, states=states)
    seen: list[AgentStep] = []
    await gw.run("task", on_step=seen.append)
    assert seen[0].login_detected is True
    assert "accounts.google.com" in (seen[0].login_url or "")


@pytest.mark.asyncio
async def test_login_detected_only_once():
    """即使多步都是登入頁，login_detected 只在第一次為 True（防重複 clarification）。"""
    login_state = _FakeBrowserState(url="https://accounts.google.com/signin", title="Sign in")
    gw = _make_gw(n_steps=3, states=[login_state, login_state, login_state])
    seen: list[AgentStep] = []
    await gw.run("task", on_step=seen.append)
    detected = [s for s in seen if s.login_detected]
    assert len(detected) == 1  # 只有第一步偵測到


@pytest.mark.asyncio
async def test_no_login_on_normal_page():
    states = [_FakeBrowserState(url="https://notebooklm.google.com/", title="My Notebook")]
    gw = _make_gw(n_steps=1, states=states)
    seen: list[AgentStep] = []
    await gw.run("task", on_step=seen.append)
    assert seen[0].login_detected is False


@pytest.mark.asyncio
async def test_artifacts_empty_when_no_downloads():
    gw = _make_gw(n_steps=1)
    result = await gw.run("task")
    assert result.artifacts == ()
