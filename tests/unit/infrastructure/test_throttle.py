"""InMemoryDomainThrottle 測試（fake clock/sleep，先寫 TDD）。"""
import pytest

from infrastructure.throttle import InMemoryDomainThrottle


class FakeTime:
    def __init__(self) -> None:
        self.t = 0.0
        self.slept: list[float] = []

    def now(self) -> float:
        return self.t

    async def sleep(self, s: float) -> None:
        self.slept.append(s)
        self.t += s


@pytest.mark.asyncio
async def test_first_acquire_no_wait():
    ft = FakeTime()
    t = InMemoryDomainThrottle(min_interval_sec=2.0, now=ft.now, sleep=ft.sleep)
    await t.acquire("d")
    assert ft.slept == []


@pytest.mark.asyncio
async def test_second_acquire_waits_remaining_interval():
    ft = FakeTime()
    t = InMemoryDomainThrottle(min_interval_sec=2.0, now=ft.now, sleep=ft.sleep)
    await t.acquire("d")
    await t.acquire("d")  # 立刻再來 → 等滿 2 秒
    assert ft.slept == [2.0]


@pytest.mark.asyncio
async def test_different_domains_independent():
    ft = FakeTime()
    t = InMemoryDomainThrottle(min_interval_sec=2.0, now=ft.now, sleep=ft.sleep)
    await t.acquire("a")
    await t.acquire("b")  # 不同網域，不等
    assert ft.slept == []


@pytest.mark.asyncio
async def test_zero_interval_never_waits():
    ft = FakeTime()
    t = InMemoryDomainThrottle(min_interval_sec=0.0, now=ft.now, sleep=ft.sleep)
    await t.acquire("d")
    await t.acquire("d")
    assert ft.slept == []
