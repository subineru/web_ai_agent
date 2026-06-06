"""開發/示範用後端：用「慢速假 agent」讓任務維持 RUNNING 一段時間，
方便手動或視覺驗證即時轉向（steer/pause/resume/stop）與回饋 UI。

啟動：uv run uvicorn scripts.dev_fake_server:app --port 8000
（不需金鑰、不開真實瀏覽器）
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.pool import StaticPool  # noqa: E402
from sqlmodel import SQLModel, create_engine  # noqa: E402

from adapters.persistence.sql_task_repo import SqlTaskRepo  # noqa: E402
from domain.value_objects import AgentRunResult, AgentStep  # noqa: E402
from infrastructure.container import Container  # noqa: E402
from infrastructure.db import session_factory  # noqa: E402
from infrastructure.web import create_app  # noqa: E402


class SlowFakeAgent:
    """每秒一步、共 30 步；輪詢 control 以支援即時轉向。"""

    async def run(self, instruction, *, start_url=None, max_steps=40, on_step=None, control=None):
        steps: list[AgentStep] = []
        for i in range(30):
            if control is not None:
                for msg in control.drain():
                    s = AgentStep(description=f"↪️ 採納新指示：{msg}")
                    steps.append(s)
                    if on_step:
                        on_step(s)
                if control.stopped:
                    break
                while control.paused and not control.stopped:
                    await asyncio.sleep(0.2)
            step = AgentStep(description=f"step {i + 1}：模擬瀏覽動作…")
            steps.append(step)
            if on_step:
                on_step(step)
            await asyncio.sleep(1)
        return AgentRunResult(success=True, output="（示範）任務完成。", steps=tuple(steps))


_engine = create_engine(
    "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
)
SQLModel.metadata.create_all(_engine)
_container = Container.for_testing(repo=SqlTaskRepo(session_factory(_engine)), agent=SlowFakeAgent())
app = create_app(_container)
