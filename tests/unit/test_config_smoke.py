"""Phase 0 健全性測試：確認設定載入與後端切換邏輯可運作。

真正的 TDD 測試從 Phase 1 開始；這裡只證明測試工具鏈可用。
"""
from infrastructure.config import Settings


def test_active_backend_falls_back_when_primary_key_missing():
    s = Settings(
        WAGENT_LLM_BACKEND="anthropic",
        ANTHROPIC_API_KEY="",
        OPENAI_API_KEY="sk-test",
    )
    assert s.active_backend() == "openai_compat"


def test_active_backend_keeps_choice_when_key_present():
    s = Settings(
        WAGENT_LLM_BACKEND="anthropic",
        ANTHROPIC_API_KEY="key",
        OPENAI_API_KEY="",
    )
    assert s.active_backend() == "anthropic"
