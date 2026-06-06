"""Phase 0 冒煙測試：用 browser-use 對 quotes.toscrape.com 跑通一次。

驗證：LLM 後端可用、瀏覽器（CDP）可啟動、能完成任務並輸出結果與軌跡日誌。

用法：
    uv run python scripts/smoke_browseruse.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# 讓本腳本能 import 專案套件
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from browser_use import Agent  # noqa: E402

from infrastructure.config import get_settings  # noqa: E402
from infrastructure.llm.factory import build_fallback_llm, build_llm  # noqa: E402

TASK = (
    "Go to https://quotes.toscrape.com and extract the first 3 quotes. "
    "For each, return the quote text and the author name."
)

OUT_DIR = Path(__file__).resolve().parent.parent / "workspace" / "outputs" / "smoke"


async def main() -> int:
    settings = get_settings()
    print(f"[smoke] active LLM backend = {settings.active_backend()}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    steps: list[str] = []

    async def on_step(*_args, **_kwargs) -> None:
        steps.append("step")
        print(f"[smoke] step {len(steps)}")

    agent = Agent(
        task=TASK,
        llm=build_llm(settings),
        fallback_llm=build_fallback_llm(settings),
        max_failures=settings.max_failures,
        register_new_step_callback=on_step,
        save_conversation_path=str(OUT_DIR / "conversation"),
    )

    history = await agent.run(max_steps=settings.max_steps)

    result = history.final_result()
    print("\n[smoke] ===== FINAL RESULT =====")
    print(result)
    print(f"[smoke] steps={len(steps)} done={history.is_done()} "
          f"success={history.is_successful()}")
    print(f"[smoke] artifacts under: {OUT_DIR}")
    return 0 if history.is_done() else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
