"""SessionStore 實作：登入狀態（storage_state）的持久化。

- InMemorySessionStore：測試/單一程序用。
- FileSessionStore：把 domain→storage_path 的索引存成 JSON 檔，
  對應 browser-use 的 profile / storage_state 路徑，讓下次同站點免再驗。
"""
from __future__ import annotations

import json
from pathlib import Path

from domain.entities import SessionState


class InMemorySessionStore:
    def __init__(self) -> None:
        self._by_domain: dict[str, SessionState] = {}

    def save(self, state: SessionState) -> None:
        self._by_domain[state.site_domain] = state

    def load(self, site_domain: str) -> SessionState | None:
        return self._by_domain.get(site_domain)


class FileSessionStore:
    def __init__(self, index_path: str = "workspace/sessions/index.json") -> None:
        self._index = Path(index_path)
        self._index.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> dict[str, str]:
        if not self._index.exists():
            return {}
        return json.loads(self._index.read_text(encoding="utf-8"))

    def save(self, state: SessionState) -> None:
        data = self._read()
        data[state.site_domain] = state.storage_path
        self._index.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self, site_domain: str) -> SessionState | None:
        path = self._read().get(site_domain)
        return SessionState(site_domain=site_domain, storage_path=path) if path else None
