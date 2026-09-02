import io
import urllib.request

from spooldown import http
from spooldown.http import USER_AGENT


def test_user_agent_is_not_python() -> None:
    assert "python" not in USER_AGENT.lower()


def test_empty_body_is_none(monkeypatch) -> None:

    class FakeResp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: FakeResp(b""))
    assert http.request_json("http://x") is None
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: FakeResp(b'{"a": 1}'))
    assert http.request_json("http://x") == {"a": 1}
