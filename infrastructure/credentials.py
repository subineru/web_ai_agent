"""InMemoryCredentialVault：帳密暫存（依網域，僅記憶體）。

安全：絕不寫進日誌/DB；__repr__ 遮罩避免不慎被記錄。
"""
from __future__ import annotations


class InMemoryCredentialVault:
    def __init__(self) -> None:
        self._by_domain: dict[str, dict[str, str]] = {}

    def store(self, site_domain: str, mapping: dict[str, str]) -> None:
        self._by_domain[site_domain] = dict(mapping)

    def get(self, site_domain: str) -> dict[str, str] | None:
        return self._by_domain.get(site_domain)

    def clear(self, site_domain: str) -> None:
        self._by_domain.pop(site_domain, None)

    def __repr__(self) -> str:  # 遮罩，避免帳密被記錄
        return f"InMemoryCredentialVault(domains={list(self._by_domain)})"
