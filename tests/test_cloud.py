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


def test_seed_used_when_store_empty_and_dated_now() -> None:
    store = MemStore()
    mgr = TokenManager(store, "acc", "ref")
    assert mgr.access() == "acc"
    assert not mgr.should_refresh_proactively()
    assert not mgr.needs_renewal()
    assert store.state["seed"] == "acc"


def test_changed_seed_replaces_stored_pair() -> None:
    old = str(int(time.time()) - 80 * 86400)
    store = MemStore({"access": "old", "refresh": "oldr", "seed": "old", "refreshed_at": old})
    mgr = TokenManager(store, "new", "newr")
    assert mgr.access() == "new"
    assert not mgr.needs_renewal()


def test_needs_renewal_past_threshold() -> None:
    old = str(int(time.time()) - 80 * 86400)
    store = MemStore({"access": "a", "refresh": "r", "seed": "a", "refreshed_at": old})
    mgr = TokenManager(store, "a", "r")
    assert mgr.needs_renewal()
    assert mgr.should_refresh_proactively()


def test_store_wins_over_unchanged_seed() -> None:
    store = MemStore(
        {"access": "rot", "refresh": "r", "seed": "seed", "refreshed_at": str(int(time.time()))}
    )
    mgr = TokenManager(store, "seed", "seedr")
    assert mgr.access() == "rot"
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
