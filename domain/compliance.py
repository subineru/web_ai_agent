"""合規與安全的純邏輯：網域解析、拒絕清單比對、合規決策。"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class ComplianceDecision:
    allowed: bool
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def domain_of(url: str) -> str:
    """取小寫 hostname；非合法 URL 回空字串。"""
    return (urlparse(url).hostname or "").lower()


def is_denylisted(url: str, denylist: Iterable[str]) -> bool:
    """網域命中拒絕清單（含子網域）即為 True。"""
    host = domain_of(url)
    if not host:
        return False
    for d in denylist:
        d = d.strip().lower()
        if d and (host == d or host.endswith("." + d)):
            return True
    return False
