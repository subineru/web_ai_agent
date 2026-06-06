"""SteeringControl 測試（先寫，TDD）。可變控制物件，web 與執行中 agent 共用。"""
from domain.steering import SteeringControl


def test_push_and_drain_pending():
    c = SteeringControl()
    c.push("先去登入頁")
    c.push("再回首頁")
    assert c.drain() == ["先去登入頁", "再回首頁"]
    assert c.drain() == []  # drain 後清空


def test_pause_resume_flags():
    c = SteeringControl()
    assert not c.paused
    c.pause()
    assert c.paused
    c.resume()
    assert not c.paused


def test_stop_flag():
    c = SteeringControl()
    assert not c.stopped
    c.stop()
    assert c.stopped


def test_blank_message_rejected():
    c = SteeringControl()
    import pytest

    with pytest.raises(ValueError):
        c.push("   ")
