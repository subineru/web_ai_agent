"""InMemoryLearningStore：測試/單一程序用的 LearningStore 實作。"""
from __future__ import annotations

from domain.learning import LearnedTool


class InMemoryLearningStore:
    def __init__(self) -> None:
        self._tools: list[LearnedTool] = []

    def save(self, tool: LearnedTool) -> None:
        self._tools.append(tool)

    def find_for(self, site_domain: str, *, limit: int = 5) -> list[LearnedTool]:
        matched = [t for t in self._tools if t.site_domain == site_domain]
        return list(reversed(matched))[:limit]
