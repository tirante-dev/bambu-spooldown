import zipfile
from io import BytesIO

import pytest

from spooldown import usage

SLICE_INFO = """<?xml version="1.0" encoding="UTF-8"?>
<config>
  <plate>
    <metadata key="index" value="1"/>
    <metadata key="weight" value="17.92"/>
    <filament id="1" tray_info_idx="GFB00" type="ABS" color="#000000" used_m="5.92" used_g="14.71"/>
    <filament id="2" tray_info_idx="GFB98" type="ASA" color="#BCBCBC" used_m="1.30" used_g="3.21"/>
  </plate>
  <plate>
    <metadata key="index" value="2"/>
    <filament id="1" type="ABS" color="#000000" used_m="1.00" used_g="2.50"/>
  </plate>
</config>
"""


def make_threemf() -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("Metadata/slice_info.config", SLICE_INFO)
    return buf.getvalue()


def test_parse_slice_info_selects_plate() -> None:
    assert usage.parse_slice_info(make_threemf(), 1) == {1: 14.71, 2: 3.21}
    assert usage.parse_slice_info(make_threemf(), 2) == {1: 2.50}


def test_parse_slice_info_missing_plate_raises() -> None:
    with pytest.raises(ValueError, match="plate 3"):
        usage.parse_slice_info(make_threemf(), 3)


def test_plate_index_from_gcode_path() -> None:
    assert usage.plate_index_from_gcode_path("/data/Metadata/plate_1.gcode") == 1
    assert usage.plate_index_from_gcode_path("/data/Metadata/plate_12.gcode") == 12
    assert usage.plate_index_from_gcode_path("weird.gcode") == 1


def test_per_tray_usage_maps_filaments_to_trays() -> None:
    grams = {1: 14.71, 2: 3.21}
    assert usage.per_tray_usage(grams, [0, 3]) == {0: 14.71, 3: 3.21}


def test_per_tray_usage_drops_unmapped_and_unused() -> None:
    grams = {1: 10.0, 2: 5.0, 3: 0.0}
    assert usage.per_tray_usage(grams, [2, -1]) == {2: 10.0}


def test_per_tray_usage_merges_same_tray() -> None:
    grams = {1: 10.0, 2: 5.0}
    assert usage.per_tray_usage(grams, [1, 1]) == {1: 15.0}
