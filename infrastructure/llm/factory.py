"""依設定建立 browser-use 的 LLM 物件（雙後端可切換）。

這是 LLMPort 的 Infrastructure 端組裝點之一。回傳 browser-use 的 Chat* 物件，
供 BrowserUseGateway 使用。Domain/Application 不得 import 本模組。
"""
from __future__ import annotations

from browser_use import ChatAnthropic, ChatOpenAI

from infrastructure.config import Settings, get_settings
from infrastructure.env_sanitize import sanitize_env


def build_llm(settings: Settings | None = None):
    """回傳主 LLM。依 active_backend() 決定 Anthropic 或 OpenAI-compatible。"""
    sanitize_env()
    s = settings or get_settings()
    backend = s.active_backend()
    if backend == "anthropic":
        if not s.anthropic_api_key:
            raise RuntimeError("選用 anthropic 後端但 ANTHROPIC_API_KEY 未設定")
        return ChatAnthropic(model=s.anthropic_model, api_key=s.anthropic_api_key)
    if not s.openai_api_key:
        raise RuntimeError("選用 openai_compat 後端但 OPENAI_API_KEY 未設定")
    return ChatOpenAI(
        model=s.openai_model,
        api_key=s.openai_api_key,
        base_url=s.openai_base_url,
    )


def build_fallback_llm(settings: Settings | None = None):
    """回傳備援 LLM，供 browser-use 在主模型出錯（含偶發產出格式錯誤）時改用。

    優先選「另一個有 key 的後端」；若只有單一後端金鑰，則回傳同後端的另一個實例
    —— 對間歇性的壞輸出做重抽樣，通常下一次呼叫即可得到合法結果，
    同時消除 browser-use「no fallback_llm configured」而直接放棄的情況。
    """
    sanitize_env()
    s = settings or get_settings()
    primary = s.active_backend()
    if primary == "anthropic" and s.openai_api_key:
        return ChatOpenAI(model=s.openai_model, api_key=s.openai_api_key, base_url=s.openai_base_url)
    if primary == "openai_compat" and s.anthropic_api_key:
        return ChatAnthropic(model=s.anthropic_model, api_key=s.anthropic_api_key)
    # 只有單一後端 → 同後端重抽樣
    return build_llm(s)
