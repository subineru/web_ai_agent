"""錯誤分類（純函式）測試（先寫，TDD）。"""
import pytest

from domain.recovery import ErrorKind, classify_error


@pytest.mark.parametrize(
    "message, expected",
    [
        ("Connection error.", ErrorKind.TRANSIENT),
        ("Page readiness timeout (8.0s)", ErrorKind.TRANSIENT),
        ("element not found", ErrorKind.TRANSIENT),
        ("Stopping due to no progress / loop detected", ErrorKind.LOOP),
        ("max steps reached", ErrorKind.LOOP),
        ("Unexpected modal popup appeared", ErrorKind.UNEXPECTED_PAGE),
        ("CAPTCHA challenge detected", ErrorKind.CAPTCHA),
        ("Login required to continue", ErrorKind.LOGIN),
        ("totally weird thing", ErrorKind.FATAL),
    ],
)
def test_classify(message, expected):
    assert classify_error(message) is expected
