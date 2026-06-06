"""可配置接棒策略測試（先寫，TDD）。"""
import pytest

from domain.handoff import HandoffPolicy, decide_handoff
from domain.recovery import ErrorKind


@pytest.mark.parametrize("policy", [HandoffPolicy.HUMAN_FIRST, HandoffPolicy.AI_THEN_HUMAN])
def test_hard_captcha_human_unless_ai_only(policy):
    # 複雜 CAPTCHA 在「容許交人」的策略下一律交人
    assert decide_handoff(ErrorKind.CAPTCHA, hard=True, stalled=False, policy=policy) == "human"


def test_hard_captcha_under_ai_only_stays_ai():
    # AI_ONLY 永不交人，即使複雜 CAPTCHA（會嘗試後失敗）
    assert decide_handoff(ErrorKind.CAPTCHA, hard=True, stalled=False,
                          policy=HandoffPolicy.AI_ONLY) == "ai"


def test_human_first_escalates_immediately():
    assert decide_handoff(ErrorKind.LOGIN, hard=False, stalled=False,
                          policy=HandoffPolicy.HUMAN_FIRST) == "human"


def test_ai_then_human_lets_ai_try_until_stalled():
    # 簡單情況、未停滯 → 讓 AI 繼續
    assert decide_handoff(ErrorKind.CAPTCHA, hard=False, stalled=False,
                          policy=HandoffPolicy.AI_THEN_HUMAN) == "ai"
    # 停滯 → 交人
    assert decide_handoff(ErrorKind.CAPTCHA, hard=False, stalled=True,
                          policy=HandoffPolicy.AI_THEN_HUMAN) == "human"


def test_ai_only_never_human():
    assert decide_handoff(ErrorKind.LOGIN, hard=False, stalled=True,
                          policy=HandoffPolicy.AI_ONLY) == "ai"


def test_policy_from_str():
    assert HandoffPolicy.from_str("human_first") is HandoffPolicy.HUMAN_FIRST
    assert HandoffPolicy.from_str("bogus") is HandoffPolicy.AI_THEN_HUMAN  # 預設
