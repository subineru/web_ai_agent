"""ProvideCredentials use case：使用者透過對話提供帳密，存入 CredentialVault。

帳密之後由 RunBrowserJob 以 browser-use sensitive_data 注入（LLM 不見原值、網域綁定）。
本 use case 不記錄帳密值。
"""
from __future__ import annotations

from domain.ports import CredentialVault


class ProvideCredentials:
    def __init__(self, vault: CredentialVault) -> None:
        self._vault = vault

    def execute(self, site_domain: str, mapping: dict[str, str]) -> None:
        if not site_domain.strip():
            raise ValueError("site_domain 不可為空白")
        if not mapping or not any(v.strip() for v in mapping.values()):
            raise ValueError("帳密內容不可為空")
        self._vault.store(site_domain.strip(), mapping)
