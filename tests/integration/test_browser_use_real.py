"""真實 browser-use 整合測試（opt-in，慢、需金鑰、會開瀏覽器）。

預設 skip。要跑：在 .env 設好金鑰後，
    $env:WAGENT_RUN_REAL_BROWSER=1 ; uv run pytest tests/integration/test_browser_use_real.py
"""
from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("WAGENT_RUN_REAL_BROWSER") != "1",
    reason="設 WAGENT_RUN_REAL_BROWSER=1 才跑真實瀏覽器整合測試",
)


@pytest.mark.asyncio
async def test_real_run_extracts_quotes():
    from adapters.agents.browser_use_gateway import BrowserUseGateway

    os.environ.setdefault("WAGENT_HEADLESS", "true")
    gw = BrowserUseGateway()
    seen = []
    result = await gw.run(
        "Extract the first quote text and its author.",
        start_url="https://quotes.toscrape.com",
        max_steps=12,
        on_step=seen.append,
    )
    assert result.success is True
    assert result.output
    assert len(seen) >= 1
