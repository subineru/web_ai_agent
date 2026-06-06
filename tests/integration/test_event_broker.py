"""InMemoryEventBroker 測試（history 快照 + 即時串流）。先寫，TDD。"""
import pytest

from domain.value_objects import JobEvent
from infrastructure.events import InMemoryEventBroker


@pytest.mark.asyncio
async def test_stream_replays_history_then_closes_on_terminal():
    broker = InMemoryEventBroker()
    broker.publish("j1", JobEvent(type="status", data={"status": "running"}))
    broker.publish("j1", JobEvent(type="step", data={"description": "step 1"}))
    broker.publish("j1", JobEvent(type="done", data={"status": "succeeded"}))

    seen = [ev async for ev in broker.stream("j1")]
    assert [e.type for e in seen] == ["status", "step", "done"]


@pytest.mark.asyncio
async def test_live_event_delivered_then_terminal_closes():
    broker = InMemoryEventBroker()
    broker.publish("j2", JobEvent(type="status", data={"status": "running"}))

    collected = []

    async def consume():
        async for ev in broker.stream("j2"):
            collected.append(ev.type)

    import asyncio

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.01)  # 讓 consumer 先吃完 history 並開始等
    broker.publish("j2", JobEvent(type="step", data={"description": "s"}))
    broker.publish("j2", JobEvent(type="done", data={"status": "succeeded"}))
    await asyncio.wait_for(task, timeout=1.0)

    assert collected == ["status", "step", "done"]
