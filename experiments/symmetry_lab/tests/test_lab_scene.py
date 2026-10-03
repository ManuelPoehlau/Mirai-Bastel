"""Asset-Namen und GL-freies Laden (Handoff Slice 2 §4.3/§7) — `lab_scene`.

Registry, Laden per Name und der Abbruch von `run.py` vor dem Fenster laufen seit
WP-SYM-LAB-03 auf dem App-Pfad: `test_app_lab_cycle.py` (Plan A2-Tabelle, Slice 5).
Hier bleiben die zwei Fälle, die nur `lab_scene` selbst betreffen.
"""

from __future__ import annotations

import pytest

from loaders.assets import asset_names
from mirai.application import Application

from symmetry_lab.lab_scene import UnknownAssetError, load_asset_into, resolve_asset_name


def test_unknown_name_raises_with_valid_names():
    with pytest.raises(UnknownAssetError) as info:
        resolve_asset_name("no_such_mesh")
    message = str(info.value)
    assert "no_such_mesh" in message
    for name in asset_names():
        assert name in message


def test_load_unknown_name_leaves_scene_untouched():
    app = Application()
    mesh_before = app.scene.mesh
    with pytest.raises(UnknownAssetError):
        load_asset_into(app, "no_such_mesh")
    assert app.scene.mesh is mesh_before
