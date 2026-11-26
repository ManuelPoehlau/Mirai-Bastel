"""AD-037 Phase 4c (§14): the brush picker's headless logic (`gui.brush_picker_model`) and the panel's areas 1 and 2.

Favourites first, the category filter and the search; the brush row's "geändert" and what saving offers; the tip row's
"Alpha fehlt"; thumbnails (64² RGBA, from the library's thumbnail files - the §9 gate: 50 thumbnails for the picker's
first open <= 150 ms); a headless draw of the panel and the picker.
"""

from __future__ import annotations

import dataclasses
import time

import numpy as np
import pytest

import tests._bootstrap  # noqa: F401

from gui import brush_picker_model as bm
from mirai.paint import library as lib
from mirai.paint.brush import TipSettings
from tests.test_paint_dynamics import _Imgui
from tests.test_paint_library import _disc
from tests.test_paint_room import _app


@pytest.fixture
def app(tmp_path):
    app = _app()
    app.set_paint_user_dir(tmp_path / "paint")
    app.open_paint_room()
    return app


def test_items_favourites_first_filter_and_search(app):
    items = bm.preset_items(app)
    names = [i.name for i in items]
    assert names[0] == "Adern folgen" and "Runder Pinsel" in names  # the library's (file) order
    current = [i for i in items if i.current]
    assert [i.id for i in current] == [lib.DEFAULT_PRESET]
    app.set_paint_favourite("builtin:sommersprossen", True)
    items = bm.preset_items(app)
    assert items[0].id == "builtin:sommersprossen" and items[0].label == "* Sommersprossen"
    assert [i.id for i in bm.preset_items(app, bm.FAVOURITES)] == ["builtin:sommersprossen"]
    assert {i.category for i in bm.preset_items(app, "Haut")} == {"Haut"}
    assert [i.name for i in bm.preset_items(app, search="kratz")] == ["Kratzer"]
    assert [i.name for i in bm.preset_items(app, search="schaden")] == ["Kratzer"]  # the category matches too
    cats = bm.categories(bm.preset_items(app))
    assert cats[:2] == (bm.ALL, bm.FAVOURITES) and "Haut" in cats and len(set(cats)) == len(cats)
    alphas = bm.alpha_items(app)
    assert [a.name for a in alphas[:6]] == ["Poren", "Ader", "Kratzer", "Fleck", "Punkte", "Quadrat"]
    assert not any(a.current for a in alphas)
    app.set_paint_tip("test/fleck")
    assert [a.id for a in bm.alpha_items(app) if a.current] == ["test/fleck"]
    assert bm.rows(alphas, 4)[0] == alphas[:4]


def test_brush_row_marker_and_saving(app):
    row = bm.brush_row(app)
    assert (row.name, row.changed, row.can_save) == ("Runder Pinsel", False, False)
    assert bm.brush_label(row) == "Runder Pinsel  (Grundformen)"
    app.set_paint_brush(flow=0.5)
    row = bm.brush_row(app)
    assert row.changed and not row.can_save  # a built-in: only "Speichern als"
    assert bm.brush_label(row).endswith("- geändert")
    app.save_paint_preset_as("Eigen")
    app.set_paint_brush(flow=0.4)
    assert bm.brush_row(app).can_save
    app.delete_paint_preset("user:eigen")
    assert bm.brush_row(app).name == bm.NO_PRESET


def test_tip_row_says_when_the_alpha_is_missing(app):
    assert bm.tip_row(app).text == "Rund"
    app._paint_room.brush = dataclasses.replace(app.paint_brush, tip=TipSettings(alpha="user:0123456789ab",
                                                                                   alpha_name="Poren 02"))
    row = bm.tip_row(app)
    assert row.missing and row.text == "Alpha fehlt: Poren 02 (malt rund)"


def test_thumbnails(app):
    for item in bm.preset_items(app) + bm.alpha_items(app):
        pixels = bm.thumbnail_pixels(app, item)
        assert pixels.shape == (bm.THUMB, bm.THUMB, 4) and pixels.dtype == np.uint8 and (pixels[..., 3] == 255).all()
        assert np.ptp(pixels[..., 0]) > 50, item.name  # it shows something
    assert bm.current_thumbnail(app).shape == (bm.PREVIEW, bm.PREVIEW, 4)
    poren = next(i for i in bm.alpha_items(app) if i.id == "test/poren")
    plain = bm.thumbnail_pixels(app, poren)
    app.set_paint_tip("test/poren")
    app.set_paint_brush(tip=dataclasses.replace(app.paint_brush.tip, invert=True))
    assert bm.current_key(app) != bm.thumbnail_key(app, poren)
    assert not np.array_equal(bm.current_thumbnail(app, bm.THUMB), plain)


def test_fifty_thumbnails_for_the_first_open(app, tmp_path):
    """§9 "4c": the picker's first open with 50 thumbnails <= 150 ms - 44 imported 1024² alphas and the six built in;
    a user alpha's thumbnail is its small file (no 1024² decode), and making it does not fill the alpha cache."""
    rng = np.random.default_rng(0)
    for k in range(44):
        app.paint_library.import_alpha((rng.random((1024, 1024)) * 255).astype(np.uint8), f"A{k}")
    app.paint_library.refresh()
    fresh = lib.PaintLibrary(tmp_path / "paint")  # a new session: nothing in memory
    app._paint_room.library = fresh
    items = bm.alpha_items(app)
    assert len(items) == 50
    started = time.perf_counter()
    for item in items:
        bm.thumbnail_pixels(app, item)
    assert time.perf_counter() - started < 0.15
    assert fresh.cached_bytes == 0


def test_thumbnail_files_follow_the_user_alphas(app, tmp_path):
    library = app.paint_library
    entry, _ = library.import_alpha(_disc(128), "Scheibe")
    thumb = tmp_path / "paint" / "alphas" / lib.THUMB_DIR / f"{entry.hash}.png"
    assert thumb.is_file() and library.thumbnail(entry.id).shape == (lib.THUMB, lib.THUMB)
    assert len(library.alphas()) == 7  # the thumbnail folder is not scanned as alphas
    library.delete_alpha(entry.id)
    assert not thumb.exists()


def test_import_card_model(tmp_path):
    from tests.test_paint_library import _png, _rgba

    draft, _ = lib.open_import(_png(tmp_path / "a.png", _rgba(_disc(80))))
    assert bm.import_note(draft) == "80 x 80 px, Vorschlag: Luminanz"
    assert bm.import_preview_rgba(draft).shape == (80, 80, 4)
    draft.mode = lib.MODE_ALPHA  # an opaque image's alpha channel is white everywhere: a square, warned
    assert draft.border_warning
    draft.invert = True
    assert bm.import_preview_rgba(draft) is None and "leer" in bm.import_note(draft)


def test_the_panel_and_the_picker_draw_headless(app):
    from gui.paint_panel import PaintPanel

    app.select_paint_preset("builtin:poren_spray")
    app.set_paint_brush(opacity=0.3)
    imgui = _Imgui()
    panel = PaintPanel(imgui, app, None)
    panel.draw()
    labels = imgui.labels
    for label in ("Pinsel ...", "Speichern als ...", "Zurücksetzen", "Invertieren", "Kreismaske", "Kontrast", "Rund"):
        assert label in labels, label
    panel.picker.open(bm.TAB_ALPHAS)
    imgui.labels.clear()
    panel.draw()  # the fake `begin_popup` returns False: the popup's body is the real window test's
    assert "Pinsel-Auswahl###brush_picker" in imgui.labels
    assert not panel.popup_open and panel.extra_rects == []
    panel.release()
