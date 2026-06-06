"""即時轉向（real-time steering）的可變控制物件。

web 端的 use case 與「執行中的 agent」共用同一個 SteeringControl：
- web 端 push 新指示 / pause / resume / stop；
- 執行中的 gateway 每步輪詢 drain()/paused/stopped 來採納。
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SteeringControl:
    pending: list[str] = field(default_factory=list)
    paused: bool = False
    stopped: bool = False

    def push(self, message: str) -> None:
        if not message.strip():
            raise ValueError("steering 指示不可為空白")
        self.pending.append(message.strip())

    def drain(self) -> list[str]:
        msgs = list(self.pending)
        self.pending.clear()
        return msgs

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    def stop(self) -> None:
        self.stopped = True
