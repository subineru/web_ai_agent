"""CheckCompliance use case 測試（先寫，TDD）。"""
import pytest

from application.use_cases.compliance import CheckCompliance


class FakeRobots:
    def __init__(self, allowed: bool, *, raises: Exception | None = None) -> None:
        self._allowed = allowed
        self._raises = raises

    async def is_allowed(self, url: str, user_agent: str) -> bool:
        if self._raises:
            raise self._raises
        return self._allowed


@pytest.mark.asyncio
async def test_no_url_skips_with_warning():
    d = await CheckCompliance().evaluate(None)
    assert d.allowed
    assert d.warnings  # 有「略過」警告


@pytest.mark.asyncio
async def test_denylisted_blocked():
    d = await CheckCompliance(denylist=["evil.com"]).evaluate("https://evil.com/x")
    assert not d.allowed
    assert any("拒絕清單" in r for r in d.reasons)


@pytest.mark.asyncio
async def test_robots_disallow_blocks():
    d = await CheckCompliance(robots=FakeRobots(False)).evaluate("https://site.com/x")
    assert not d.allowed
    assert any("robots" in r for r in d.reasons)


@pytest.mark.asyncio
async def test_robots_allow_passes():
    d = await CheckCompliance(robots=FakeRobots(True)).evaluate("https://site.com/x")
    assert d.allowed


@pytest.mark.asyncio
async def test_robots_fetch_error_warns_but_allows():
    d = await CheckCompliance(robots=FakeRobots(True, raises=RuntimeError("net"))).evaluate(
        "https://site.com/x"
    )
    assert d.allowed
    assert d.warnings


@pytest.mark.asyncio
async def test_respect_robots_false_skips_robots():
    d = await CheckCompliance(robots=FakeRobots(False), respect_robots=False).evaluate(
        "https://site.com/x"
    )
    assert d.allowed  # 不檢查 robots
