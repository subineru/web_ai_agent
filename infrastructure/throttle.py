"""InMemoryDomainThrottle：每網域禮貌間隔（單一程序）。

now/sleep 可注入以利測試（fake clock）。
"""
from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable


class InMemoryDomainThrottle:
    def __init__(
        self,
        min_interval_sec: float,
        *,
        now: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._min = min_interval_sec
        self._now = now
        self._sleep = sleep
        self._last: dict[str, float] = {}

    async def acquire(self, domain: str) -> None:
        if self._min <= 0:
            self._last[domain] = self._now()
            return
        last = self._last.get(domain)
        now = self._now()
        if last is not None:
            wait = self._min - (now - last)
            if wait > 0:
                await self._sleep(wait)
                now = self._now()
        self._last[domain] = now
