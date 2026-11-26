"""AD-037 Phase 4c (§14) in the room: presets, the "geändert" marker, "Größe behalten", the import, a missing alpha.

A missing alpha paints with the round tip - pixel for pixel what the round tip with the same values paints - and the
brush keeps its reference; a preset never changes colour, tool or mirror; the library writes only into the user folder.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest

import tests._bootstrap  # noqa: F401

from mirai.paint import library as lib
from mirai.paint.brush import TOOL_ERASE, BrushSettings, TipSettings
from tests.test_paint_library import _disc, _png, _rgba
from tests.test_paint_room import _app, _stroke


@pytest.fixture
def app(tmp_path):
    app = _app()
    app.set_paint_user_dir(tmp_path / "paint")
    return app


def test_the_room_starts_on_the_round_preset(app):
    app.open_paint_room()
    assert app.paint_preset is not None and app.paint_preset.id == lib.DEFAULT_PRESET
    assert not app.paint_brush_changed
    app.set_paint_brush(opacity=0.5)
    assert app.paint_brush_changed
    assert app.reset_paint_preset() and not app.paint_brush_changed and app.paint_brush.opacity == 1.0


def test_selecting_a_preset_keeps_colour_tool_and_mirror(app):
    app.open_paint_room()
    app.set_paint_brush(colour=(0.1, 0.8, 0.3), tool=TOOL_ERASE, mirror=False)
    assert app.select_paint_preset("builtin:poren_spray")
    brush = app.paint_brush
    assert (brush.colour, brush.tool, brush.mirror) == ((0.1, 0.8, 0.3), TOOL_ERASE, False)
    assert brush.tip.alpha == "test/poren" and brush.dynamics.spray and brush.radius_percent == 2.0
    assert "Poren-Spray" in app.status_message and not app.paint_brush_changed
    assert not app.select_paint_preset("builtin:nope") and "unbekannter Pinsel" in app.status_message


def test_keep_size(app):
    app.open_paint_room()
    app.set_paint_brush(radius_step=9)
    assert app.set_paint_keep_size(True)
    app.select_paint_preset("builtin:adern_folgen")
    assert app.paint_brush.radius_step == 9 and not app.paint_brush_changed
    app.set_paint_keep_size(False)
    app.select_paint_preset("builtin:adern_folgen")
    assert app.paint_brush.radius_percent == 4.0


def test_save_as_save_and_builtin_refusal(app, tmp_path):
    app.open_paint_room()
    app.set_paint_brush(opacity=0.3)
    assert not app.save_paint_preset()  # the built-in round brush: read-only
    assert "eingebaut" in app.status_message
    assert app.save_paint_preset_as("Mein Rund", "Haut")
    assert app.paint_preset.id == "user:mein_rund" and not app.paint_brush_changed
    app.set_paint_brush(flow=0.2)
    assert app.paint_brush_changed and app.save_paint_preset() and not app.paint_brush_changed
    assert (tmp_path / "paint" / "brushes" / "mein_rund.json").is_file()
    assert app.rename_paint_preset("user:mein_rund", "Neu Rund") and app.paint_preset.id == "user:neu_rund"
    assert app.delete_paint_preset("user:neu_rund") and app.paint_preset is None and not app.paint_brush_changed
    assert app.paint_brush.flow == 0.2  # the brush keeps its values


def test_import_sets_the_tip_and_a_second_import_finds_it(app, tmp_path):
    app.open_paint_room()
    draft, _ = lib.open_import(_png(tmp_path / "in" / "scheibe.png", _rgba(_disc(64))))
    entry = app.import_paint_alpha(draft)
    assert entry is not None and app.paint_brush.tip.alpha == entry.id and "importiert" in app.status_message
    assert app.import_paint_alpha(draft).id == entry.id and "schon vorhanden" in app.status_message


def test_a_missing_alpha_paints_round_and_keeps_its_reference(tmp_path):
    """The same stroke with a missing alpha and with the round tip (same values): the same pixels."""
    missing = TipSettings(alpha="user:0123456789ab", alpha_name="Poren 02", alpha_hash="0123456789ab")
    pixels = []
    for tip in (missing, TipSettings()):
        app = _app()
        app.set_paint_user_dir(tmp_path / "paint")
        app.open_paint_room()
        app._paint_room.brush = dataclasses.replace(app.paint_brush, tip=tip)
        assert app.paint_alpha_missing is (tip is missing)
        _stroke(app, steps=10, dx=5.0)
        obj = app.scene.edit_object
        pixels.append(app.paint.pixels(obj, "Ebene 1").copy())
        assert app.paint_brush.tip == tip  # the reference stays
    assert np.array_equal(pixels[0], pixels[1]) and pixels[0][..., 3].any()


def test_a_preset_whose_alpha_is_missing_says_so(app, tmp_path):
    app.open_paint_room()
    draft, _ = lib.open_import(_png(tmp_path / "in" / "scheibe.png", _rgba(_disc(64))))
    entry = app.import_paint_alpha(draft)
    assert app.save_paint_preset_as("Mit Scheibe")
    assert app.delete_paint_alpha(entry.id)
    app.select_paint_preset("user:mit_scheibe")
    assert app.paint_alpha_missing and "Alpha fehlt" in app.status_message
    assert app.paint_brush.tip.alpha == entry.id


def test_invert_and_contrast_change_what_is_painted(tmp_path):
    painted = []
    for tip in (TipSettings(alpha="test/fleck"), TipSettings(alpha="test/fleck", contrast=0.8)):
        app = _app()
        app.open_paint_room()
        app.set_paint_tip("test/fleck")
        app._paint_room.brush = dataclasses.replace(app.paint_brush, tip=dataclasses.replace(app.paint_brush.tip,
                                                                                               contrast=tip.contrast))
        _stroke(app, steps=10, dx=5.0)
        painted.append(app.paint.pixels(app.scene.edit_object, "Ebene 1")[..., 3].copy())
    assert not np.array_equal(painted[0], painted[1])
    assert BrushSettings().tip.round
