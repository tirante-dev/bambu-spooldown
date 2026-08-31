from typing import Any

from spooldown.mapper import Mapper
from spooldown.spoolman import ZERO_UUID

PRINTER = "3DP-31B-432"


class FakeSpoolman:
    def __init__(self, spools: list[dict[str, Any]]):
        self._spools = spools
        self.locations: dict[int, str] = {}

    def spools(self) -> list[dict[str, Any]]:
        return self._spools

    def set_location(self, spool_id: int, location: str) -> None:
        self.locations[spool_id] = location
        for s in self._spools:
            if s["id"] == spool_id:
                s["location"] = location


def spool(sid, material, color="808080", *, tag=None, location=None):
    extra = {"tag": f'"{tag}"'} if tag else {}
    return {
        "id": sid,
        "archived": False,
        "location": location,
        "extra": extra,
        "filament": {"material": material, "color_hex": color, "name": material},
    }


def tray(material, color="808080FF", uuid=ZERO_UUID):
    return {"uuid": uuid, "type": material, "color": color}


def test_single_candidate_auto_maps() -> None:
    sm = FakeSpoolman([spool(3, "ASA")])
    m = Mapper(sm, PRINTER)  # type: ignore[arg-type]
    m.evaluate({3: tray("ASA", "BCBCBCFF")})
    assert sm.locations == {3: f"{PRINTER} - A3"}
    assert m.unmapped == {}


def test_ambiguous_same_color_stays_unmapped() -> None:
    sm = FakeSpoolman([spool(1, "ASA", "808080"), spool(2, "ASA", "828282")])
    m = Mapper(sm, PRINTER)  # type: ignore[arg-type]
    m.evaluate({3: tray("ASA", "808080FF")})
    assert sm.locations == {}
    assert m.unmapped[3].candidate_ids == [1, 2]


def test_color_breaks_material_tie() -> None:
    sm = FakeSpoolman([spool(1, "PLA", "FF0000"), spool(2, "PLA", "0000FF")])
    m = Mapper(sm, PRINTER)  # type: ignore[arg-type]
    m.evaluate({0: tray("PLA", "FE0102FF")})
    assert sm.locations == {1: f"{PRINTER} - A0"}


def test_rfid_trays_and_tagged_spools_ignored() -> None:
    sm = FakeSpoolman([spool(1, "ASA", tag="AABB")])
    m = Mapper(sm, PRINTER)  # type: ignore[arg-type]
    m.evaluate({3: tray("ASA"), 0: tray("ABS", uuid="9DA7B1759BC4450C8500EBDAFA82D24A")})
    assert sm.locations == {}
    assert list(m.unmapped) == [3]


def test_already_mapped_tray_is_quiet() -> None:
    sm = FakeSpoolman([spool(3, "ASA", location=f"{PRINTER} - A3")])
    m = Mapper(sm, PRINTER)  # type: ignore[arg-type]
    m.evaluate({3: tray("ASA")})
    assert m.unmapped == {}


def test_material_mismatch_under_stale_mapping_surfaces() -> None:
    sm = FakeSpoolman([spool(3, "ASA", location=f"{PRINTER} - A3")])
    m = Mapper(sm, PRINTER)  # type: ignore[arg-type]
    m.evaluate({3: tray("PETG")})
    assert 3 in m.unmapped


def test_spool_at_other_slot_excluded() -> None:
    sm = FakeSpoolman([spool(1, "ASA", location=f"{PRINTER} - A1"), spool(2, "ASA")])
    m = Mapper(sm, PRINTER)  # type: ignore[arg-type]
    m.evaluate({3: tray("ASA")})
    assert sm.locations.get(2) == f"{PRINTER} - A3"


def test_assign_clears_unmapped() -> None:
    sm = FakeSpoolman([spool(1, "ASA"), spool(2, "ASA")])
    m = Mapper(sm, PRINTER)  # type: ignore[arg-type]
    m.evaluate({3: tray("ASA")})
    assert 3 in m.unmapped
    m.assign(3, 2)
    assert m.unmapped == {}
    assert sm.locations[2] == f"{PRINTER} - A3"
