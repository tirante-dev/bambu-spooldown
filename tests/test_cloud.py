import time
from pathlib import Path

from spooldown import cloud
from spooldown.cloud import FileTokenStore, TokenManager


class MemStore:
    def __init__(self, initial=None):
        self.state = initial

    def load(self):
        return self.state

    def save(self, state):
        self.state = dict(state)


def test_seed_used_when_store_empty() -> None:
    mgr = TokenManager(MemStore(), "acc", "ref")
    assert mgr.access() == "acc"
    assert mgr.should_refresh_proactively()


def test_store_wins_over_seed() -> None:
    store = MemStore({"access": "stored", "refresh": "r", "refreshed_at": str(int(time.time()))})
    mgr = TokenManager(store, "seed", "seedr")
    assert mgr.access() == "stored"
    assert not mgr.should_refresh_proactively()


def test_refresh_rotates_and_persists(monkeypatch) -> None:
    store = MemStore()
    mgr = TokenManager(store, "acc", "ref")
    monkeypatch.setattr(
        cloud,
        "request_json",
        lambda url, method="GET", body=None, headers=None, cafile=None: {
            "accessToken": "acc2",
            "refreshToken": "ref2",
        },
    )
    assert mgr.refresh()
    assert mgr.access() == "acc2"
    assert store.state["refresh"] == "ref2"
    assert not mgr.should_refresh_proactively()


def test_refresh_without_refresh_token_fails() -> None:
    mgr = TokenManager(MemStore(), "acc", None)
    assert not mgr.refresh()


def test_file_store_round_trip(tmp_path: Path) -> None:
    store = FileTokenStore(str(tmp_path / "tok.json"))
    assert store.load() is None
    store.save({"access": "a", "refresh": "b"})
    assert store.load() == {"access": "a", "refresh": "b"}
