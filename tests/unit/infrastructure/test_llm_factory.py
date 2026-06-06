"""LLM factory 韌性測試：單一後端金鑰也要有 fallback（避免 browser-use 直接放棄）。"""
from browser_use import ChatAnthropic, ChatOpenAI

from infrastructure.config import Settings
from infrastructure.llm.factory import build_fallback_llm, build_llm


def _settings(**kw) -> Settings:
    base = dict(WAGENT_LLM_BACKEND="anthropic", ANTHROPIC_API_KEY="", OPENAI_API_KEY="")
    base.update(kw)
    return Settings(**base)


def test_single_anthropic_key_has_same_backend_fallback():
    s = _settings(ANTHROPIC_API_KEY="k")
    assert isinstance(build_llm(s), ChatAnthropic)
    # 只有 anthropic 金鑰 → fallback 仍非 None（同後端重抽樣）
    assert isinstance(build_fallback_llm(s), ChatAnthropic)


def test_cross_provider_fallback_prefers_other_backend():
    s = _settings(ANTHROPIC_API_KEY="k", OPENAI_API_KEY="o")
    assert isinstance(build_llm(s), ChatAnthropic)
    assert isinstance(build_fallback_llm(s), ChatOpenAI)


def test_default_max_failures_is_resilient():
    assert _settings().max_failures >= 3
