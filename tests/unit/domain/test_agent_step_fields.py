"""AgentStep / AgentRunResult 新欄位（C1 thinking、C2 login、C3 artifacts）。"""
from domain.value_objects import AgentRunResult, AgentStep


def test_agent_step_has_thinking_fields():
    s = AgentStep(description="step 1", thought="考慮中", next_goal="登入", evaluation="上步 OK")
    assert s.thought == "考慮中"
    assert s.next_goal == "登入"
    assert s.evaluation == "上步 OK"


def test_agent_step_thinking_defaults_none():
    s = AgentStep(description="step 1")
    assert s.thought is None
    assert s.next_goal is None
    assert s.evaluation is None


def test_agent_step_has_login_fields():
    s = AgentStep(
        description="step 2",
        login_detected=True,
        login_url="https://accounts.google.com/signin",
    )
    assert s.login_detected is True
    assert s.login_url == "https://accounts.google.com/signin"


def test_agent_step_login_defaults_false():
    s = AgentStep(description="step 1")
    assert s.login_detected is False
    assert s.login_url is None


def test_agent_run_result_has_artifacts():
    r = AgentRunResult(success=True, artifacts=("file.pdf", "audio.mp3"))
    assert r.artifacts == ("file.pdf", "audio.mp3")


def test_agent_run_result_artifacts_default_empty():
    r = AgentRunResult(success=True)
    assert r.artifacts == ()
