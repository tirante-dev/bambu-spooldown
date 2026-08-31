from spooldown.http import USER_AGENT


def test_user_agent_is_not_python() -> None:
    assert "python" not in USER_AGENT.lower()
