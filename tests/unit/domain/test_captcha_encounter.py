"""CaptchaEncounter 測試（先寫，TDD）。AI 試 2 次 → 人機接力。"""
from domain.value_objects import CaptchaEncounter, CaptchaResolution


def test_default_allows_two_ai_attempts():
    enc = CaptchaEncounter.new()
    assert enc.max_ai_attempts == 2
    assert enc.ai_attempts == 0
    assert not enc.should_handoff_to_human()


def test_handoff_after_max_ai_attempts():
    enc = CaptchaEncounter.new()
    enc.record_ai_attempt()
    assert not enc.should_handoff_to_human()
    enc.record_ai_attempt()
    # 已試 2 次仍未解 → 交人機
    assert enc.should_handoff_to_human()


def test_resolved_by_ai_stops_handoff():
    enc = CaptchaEncounter.new()
    enc.record_ai_attempt()
    enc.resolve_by_ai()
    assert enc.resolution is CaptchaResolution.AI
    assert enc.resolved
    assert not enc.should_handoff_to_human()


def test_resolved_by_human():
    enc = CaptchaEncounter.new()
    enc.record_ai_attempt()
    enc.record_ai_attempt()
    enc.resolve_by_human()
    assert enc.resolution is CaptchaResolution.HUMAN
    assert enc.resolved
    assert not enc.should_handoff_to_human()
