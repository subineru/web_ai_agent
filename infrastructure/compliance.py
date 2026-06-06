"""UrllibRobotsChecker：用標準庫 urllib.robotparser 查 robots.txt（每網域快取）。

阻塞式抓取放到執行緒，避免卡住事件迴圈。取不到 robots.txt 視為「允許」
（urllib.robotparser 的預設行為）。
"""
from __future__ import annotations

import asyncio
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser


class UrllibRobotsChecker:
    def __init__(self) -> None:
        self._cache: dict[str, RobotFileParser] = {}

    def _get_parser(self, robots_url: str) -> RobotFileParser:
        rp = self._cache.get(robots_url)
        if rp is None:
            rp = RobotFileParser()
            rp.set_url(robots_url)
            try:
                rp.read()
            except Exception:  # noqa: BLE001 — 取不到就當作無限制
                rp.allow_all = True
            self._cache[robots_url] = rp
        return rp

    async def is_allowed(self, url: str, user_agent: str) -> bool:
        parts = urlparse(url)
        if not parts.scheme or not parts.netloc:
            return True
        robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
        rp = await asyncio.to_thread(self._get_parser, robots_url)
        return rp.can_fetch(user_agent, url)
