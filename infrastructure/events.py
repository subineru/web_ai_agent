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
        # 1) 先訂閱 queue（在取 snapshot 之前），確保 snapshot 回放期間 publish 的事件
        #    不會因「還沒有訂閱者」而遺失。
        #    asyncio 單執行緒：append + list 之間無 await，其他協程無法插入，
        #    故 snapshot 只含訂閱前的事件，queue 只含訂閱後的事件，無重複也無遺漏。
        q: asyncio.Queue[JobEvent] = asyncio.Queue()
        self._subs[job_id].append(q)

        try:
            # 2) 回放 snapshot（訂閱之前已發生的事件）
            snapshot = list(self._history.get(job_id, []))
            for ev in snapshot:
                yield ev
                if ev.is_terminal:
                    return

            # 3) 接即時事件（訂閱之後 publish 的，含 snapshot 回放期間新增的）
            while True:
                ev = await q.get()
                yield ev
                if ev.is_terminal:
                    return
        finally:
            self._subs[job_id].remove(q)
