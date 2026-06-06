"""CheckCompliance use case：執行任務前的合規檢查（拒絕清單 + robots.txt）。"""
from __future__ import annotations

from collections.abc import Sequence

from domain.compliance import ComplianceDecision, domain_of, is_denylisted
from domain.ports import RobotsChecker


class CheckCompliance:
    def __init__(
        self,
        *,
        robots: RobotsChecker | None = None,
        denylist: Sequence[str] = (),
        respect_robots: bool = True,
        user_agent: str = "wagent-bot",
    ) -> None:
        self._robots = robots
        self._denylist = list(denylist)
        self._respect_robots = respect_robots
        self._user_agent = user_agent

    async def evaluate(self, url: str | None) -> ComplianceDecision:
        if not url:
            return ComplianceDecision(
                allowed=True, warnings=("未提供起始網址，略過合規檢查",)
            )

        reasons: list[str] = []
        warnings: list[str] = []

        if is_denylisted(url, self._denylist):
            reasons.append(f"網域在拒絕清單：{domain_of(url)}")

        if self._respect_robots and self._robots is not None:
            try:
                if not await self._robots.is_allowed(url, self._user_agent):
                    reasons.append(f"robots.txt 不允許抓取：{url}")
            except Exception:  # noqa: BLE001 — 取不到 robots 不應阻擋，僅警告
                warnings.append("無法取得 robots.txt，略過該檢查")

        return ComplianceDecision(
            allowed=not reasons, reasons=tuple(reasons), warnings=tuple(warnings)
        )
