"""Domain 合規政策測試（先寫，TDD）。"""
from domain.compliance import ComplianceDecision, domain_of, is_denylisted


def test_domain_of():
    assert domain_of("https://quotes.toscrape.com/page/2") == "quotes.toscrape.com"
    assert domain_of("http://Example.COM/x") == "example.com"
    assert domain_of("not a url") == ""


def test_denylist_exact_and_subdomain():
    deny = ["evil.com"]
    assert is_denylisted("https://evil.com/x", deny)
    assert is_denylisted("https://api.evil.com/x", deny)  # 子網域
    assert not is_denylisted("https://notevil.com/x", deny)
    assert not is_denylisted("https://example.com", deny)


def test_decision_allowed_default():
    d = ComplianceDecision(allowed=True)
    assert d.allowed and d.reasons == () and d.warnings == ()
