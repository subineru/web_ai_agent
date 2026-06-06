"""Domain learning 測試（先寫，TDD）。"""
from domain.learning import LearnedTool, augment_instruction


def test_augment_with_no_tools_returns_original():
    assert augment_instruction("抓名言", []) == "抓名言"


def test_augment_appends_guidance_block():
    tools = [
        LearnedTool(site_domain="quotes.toscrape.com", instruction="抓名言",
                    guidance="資料在 .quote 區塊", kind="success"),
        LearnedTool(site_domain="quotes.toscrape.com", instruction="抓名言",
                    guidance="作者要含全名", kind="feedback"),
    ]
    out = augment_instruction("抓名言", tools)
    assert out.startswith("抓名言")
    assert "資料在 .quote 區塊" in out
    assert "作者要含全名" in out
    # 不同來源有標記區分
    assert "成功" in out
    assert "修正" in out


def test_learned_tool_blank_guidance_rejected():
    import pytest

    with pytest.raises(ValueError):
        LearnedTool(site_domain="d", instruction="i", guidance="  ", kind="success")
