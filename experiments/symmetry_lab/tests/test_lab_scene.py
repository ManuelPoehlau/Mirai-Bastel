"""Szene laden per Registry-Name (Handoff Slice 2 §4.3/§7)."""

from __future__ import annotations

import pytest

from core.selection import SelectionMode
from loaders.assets import asset_names
from mirai.application import Application
from mirai.mesh_geometry import mesh_center_and_radius

from symmetry_lab import run
from symmetry_lab.lab_scene import (
    DEFAULT_ASSET,
    UnknownAssetError,
    load_asset_into,
    resolve_asset_name,
)

EXPECTED_VERTEX_COUNTS = {
    "head_basemesh": 326,
    "man_with_shoes_basemesh": 928,
    "subd_cube": 26,
}


def test_registry_matches_expected_assets():
    assert set(asset_names()) == set(EXPECTED_VERTEX_COUNTS)
    assert DEFAULT_ASSET == "subd_cube"


@pytest.mark.parametrize("name", sorted(EXPECTED_VERTEX_COUNTS))
def test_load_by_registry_name(name):
    app = Application()
    app.scene.selection.mode = SelectionMode.FACE
    load_asset_into(app, name)
    mesh = app.scene.mesh
    assert len(mesh.all_vertex_ids()) == EXPECTED_VERTEX_COUNTS[name]
    center, _radius = mesh_center_and_radius(mesh)
    assert app.camera.target == center
    assert app.scene.selection.mode is SelectionMode.VERTEX
    assert app.scene.selection.is_empty()


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


def test_run_rejects_unknown_name_before_opening_a_window(capsys):
    assert run.main(["no_such_mesh"]) == 2
    err = capsys.readouterr().err
    for name in asset_names():
        assert name in err
