from spooldown.spoolman import ZERO_UUID, resolve_tray, spool_tag

SPOOLS = [
    {
        "id": 1,
        "extra": {"tag": '"9DA7B1759BC4450C8500EBDAFA82D24A"'},
        "location": "3DP-31B-432 - A0",
    },
    {
        "id": 2,
        "extra": {"tag": '"4F10CEC7DEEC44F4A98359B717FB040D"'},
        "location": "3DP-31B-432 - A2",
    },
    {"id": 3, "extra": {}, "location": "3DP-31B-432 - A3", "archived": False},
    {"id": 4, "extra": {}, "location": "3DP-31B-432 - A3", "archived": True},
]


def test_spool_tag_decodes_json_encoded_extra() -> None:
    assert spool_tag(SPOOLS[0]) == "9DA7B1759BC4450C8500EBDAFA82D24A"
    assert spool_tag(SPOOLS[2]) is None


def test_resolve_by_tag() -> None:
    assert resolve_tray(SPOOLS, 0, "9DA7B1759BC4450C8500EBDAFA82D24A", "3DP-31B-432") == 1


def test_resolve_third_party_by_location_skips_archived() -> None:
    assert resolve_tray(SPOOLS, 3, ZERO_UUID, "3DP-31B-432") == 3


def test_resolve_unknown_returns_none() -> None:
    assert resolve_tray(SPOOLS, 1, ZERO_UUID, "3DP-31B-432") is None


def test_unmatched_tag_falls_back_to_location() -> None:
    assert resolve_tray(SPOOLS, 3, "FFFF0000000000000000000000000000", "3DP-31B-432") == 3
