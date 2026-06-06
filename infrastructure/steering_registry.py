"""InMemorySteeringRegistry：per-job SteeringControl 登錄處（單一程序）。"""
from __future__ import annotations

from domain.steering import SteeringControl


class InMemorySteeringRegistry:
    def __init__(self) -> None:
        self._controls: dict[str, SteeringControl] = {}

    def get_or_create(self, job_id: str) -> SteeringControl:
        return self._controls.setdefault(job_id, SteeringControl())

    def remove(self, job_id: str) -> None:
        self._controls.pop(job_id, None)
