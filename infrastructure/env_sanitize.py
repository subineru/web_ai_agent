"""清掉「設成空字串」的認證環境變數。

某些宿主環境（如 Claude Code）會把 ANTHROPIC_AUTH_TOKEN / ANTHROPIC_API_KEY
設成空字串。anthropic SDK 會把空的 ANTHROPIC_AUTH_TOKEN 轉成非法的
`Authorization: Bearer ` 標頭，導致 async 請求失敗（APIConnectionError）。

在建立任何 LLM client 前呼叫 sanitize_env()，移除這些空值，
讓 SDK 只使用我們由 .env 明確提供的金鑰。
"""
from __future__ import annotations

import os

# 這些變數若為空字串會污染 SDK 的認證，移除之
_AUTH_VARS = (
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
)


def sanitize_env() -> list[str]:
    """移除值為空字串的認證環境變數。回傳被移除的變數名清單。"""
    removed: list[str] = []
    for name in _AUTH_VARS:
        if name in os.environ and os.environ[name].strip() == "":
            del os.environ[name]
            removed.append(name)
    return removed
