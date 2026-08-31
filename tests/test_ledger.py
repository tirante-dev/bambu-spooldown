from pathlib import Path

from spooldown.ledger import Ledger


def test_ledger_round_trip(tmp_path: Path) -> None:
    path = str(tmp_path / "ledger.json")
    ledger = Ledger(path)
    assert not ledger.seen("123")
    ledger.record("123")
    assert ledger.seen("123")
    assert Ledger(path).seen("123")


def test_ledger_survives_corruption(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    path.write_text("{not json")
    ledger = Ledger(str(path))
    assert not ledger.seen("x")
    ledger.record("x")
    assert Ledger(str(path)).seen("x")
