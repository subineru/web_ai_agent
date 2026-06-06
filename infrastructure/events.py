"""InMemoryEventBroker：per-job 事件廣播。

保留每個 job 的事件 history（讓晚到的訂閱者也能拿到完整過程），
同時推給即時訂閱者。遇到終結事件（is_terminal）即關閉串流。
單一程序內使用；多程序部署時可換成 Redis pub/sub 等實作（同一 publisher port）。
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator

from domain.value_objects import JobEvent


class InMemoryEventBroker:
    def __init__(self) -> None:
        self._history: dict[str, list[JobEvent]] = defaultdict(list)
        self._subs: dict[str, list[asyncio.Queue[JobEvent]]] = defaultdict(list)

    def publish(self, job_id: str, event: JobEvent) -> None:
        self._history[job_id].append(event)
        for q in list(self._subs.get(job_id, [])):
            q.put_nowait(event)

    async def stream(self, job_id: str) -> AsyncIterator[JobEvent]:
        # 1) 先回放 history 快照
        snapshot = list(self._history.get(job_id, []))
        for ev in snapshot:
            yield ev
            if ev.is_terminal:
                return

        # 2) 再接即時事件，直到終結
        q: asyncio.Queue[JobEvent] = asyncio.Queue()
        self._subs[job_id].append(q)
        try:
            while True:
                ev = await q.get()
                yield ev
                if ev.is_terminal:
                    return
        finally:
            self._subs[job_id].remove(q)
