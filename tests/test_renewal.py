from datetime import UTC, datetime

from spooldown import renewal
from spooldown.cloud import TokenManager
from spooldown.renewal import Renewer, extract_code, pick_message


class MemStore:
    def __init__(self):
        self.state = None

    def load(self):
        return self.state

    def save(self, state):
        self.state = dict(state)


def test_extract_code() -> None:
    assert extract_code("Your Bambu Lab verification code is 483920, valid 10min") == "483920"
    assert extract_code("no code here 12345") is None


def test_pick_message_gates_on_created() -> None:
    gate = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
    msgs = [
        {"ID": "new", "Created": "2026-08-31T12:01:00Z"},
        {"ID": "old", "Created": "2026-08-31T11:00:00Z"},
    ]
    assert pick_message(msgs, gate) == "new"
    assert pick_message(msgs[1:], gate) is None


def test_renew_happy_path(monkeypatch) -> None:
    tokens = TokenManager(MemStore(), "seedacc", "seedref")
    calls: list[str] = []

    def fake_request(url, method="GET", body=None, headers=None, cafile=None):
        calls.append(url)
        if url == renewal.SEND_CODE_URL:
            return {}
        if "search" in url:
            return {"messages": [{"ID": "m1", "Created": "2999-01-01T00:00:00Z"}]}
        if "/message/m1" in url:
            return {"Text": "code is 654321"}
        if url == renewal.LOGIN_URL:
            assert body["code"] == "654321"
            return {"accessToken": "newacc", "refreshToken": "newref"}
        if url.endswith("/api/v1/messages"):
            return {}
        raise AssertionError(url)

    monkeypatch.setattr(renewal, "request_json", fake_request)
    r = Renewer("http://mailpit", "a@b.c", tokens, sleep=lambda s: None)
    assert r.renew()
    assert tokens.access() == "newacc"
    assert not r.renew()


def test_renew_backoff_after_failure(monkeypatch) -> None:
    tokens = TokenManager(MemStore(), "seedacc", "seedref")
    monkeypatch.setattr(
        renewal,
        "request_json",
        lambda *a, **k: (_ for _ in ()).throw(OSError("down")),
    )
    r = Renewer("http://mailpit", "a@b.c", tokens, sleep=lambda s: None)
    assert not r.renew()
    assert not r.renew()
    assert tokens.access() == "seedacc"
