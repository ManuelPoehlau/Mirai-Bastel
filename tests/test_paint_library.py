"""AD-037 Phase 4c (§14): the brush library - alphas, presets, favourites, the import (proposal 2026-11-25 §6, §9 "4c").

The acceptance of §9 "4c": a missing alpha falls back to the round tip and keeps its reference; the same image imported
twice is one alpha (hash); a broken JSON is skipped with its reason; built-ins are read-only; presets carry no colour,
tool or mirror; user assets go to the user folder only.
"""

from __future__ import annotations

import dataclasses
import json
import os
import time
from pathlib import Path

import numpy as np
import pytest

import tests._bootstrap  # noqa: F401

from mirai.iris_import import encode_png
from mirai.paint import alpha as alpha_api
from mirai.paint import library as lib
from mirai.paint.brush import TOOL_ERASE, BrushSettings, TipSettings
from mirai.paint.dynamics import StrokeDynamics


def _rgba(grey: np.ndarray, alpha: np.ndarray | None = None) -> np.ndarray:
    out = np.empty(grey.shape + (4,), dtype=np.uint8)
    out[..., :3] = grey[..., None]
    out[..., 3] = 255 if alpha is None else alpha
    return out


def _disc(size: int = 64, value: int = 255) -> np.ndarray:
    y, x = np.mgrid[0:size, 0:size]
    r = np.hypot(x + 0.5 - size / 2, y + 0.5 - size / 2) / (size / 2)
    return (np.clip(1.0 - r, 0.0, 1.0) * value).astype(np.uint8)


def _png(path: Path, rgba: np.ndarray) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encode_png(rgba))
    return path


def _tree(root: Path) -> dict[str, float]:
    return {str(p.relative_to(root)): p.stat().st_mtime_ns for p in root.rglob("*") if p.is_file()} if root.is_dir() else {}


@pytest.fixture
def user(tmp_path):
    return tmp_path / "home" / ".mirai_bastel" / "paint"


@pytest.fixture
def library(user):
    return lib.PaintLibrary(user)


# -- built-ins -----------------------------------------------------------------------------------------------------


def test_builtin_presets_load_without_problems():
    library = lib.PaintLibrary()
    presets = library.presets()
    assert len(presets) >= 6 and library.problems == []
    assert all(p.builtin and p.id.startswith("builtin:") for p in presets)
    for preset in presets:  # every built-in preset's alpha resolves (the test alphas until the starter set is adopted)
        if preset.tip.alpha is not None:
            assert library.resolve(preset.tip) is not None, preset.name


def test_default_preset_is_todays_round_brush():
    preset = lib.PaintLibrary().preset(lib.DEFAULT_PRESET)
    assert preset is not None and preset.name == "Runder Pinsel"
    assert preset.matches(BrushSettings())
    assert preset.apply(BrushSettings()) == BrushSettings()


def test_test_alphas_are_builtin_entries():
    library = lib.PaintLibrary()
    ids = [e.id for e in library.alphas()]
    assert ids[-len(alpha_api.TEST_ALPHAS):] == list(alpha_api.TEST_ALPHAS)  # after the starter set (2026-11-26)
    test = library.alpha_entry("test/kratzer")
    assert (test.name, test.category) == ("Kratzer" + lib.TEST_SUFFIX, lib.TEST_CATEGORY)
    assert library.alpha("test/poren") is alpha_api.generated_alpha("test/poren")


# -- presets: what they carry --------------------------------------------------------------------------------------


def test_presets_carry_no_colour_tool_or_mirror(library):
    brush = BrushSettings(tool=TOOL_ERASE, colour=(0.1, 0.9, 0.2), mirror=False, opacity=0.4,
                          tip=library.tip("test/ader"), dynamics=StrokeDynamics(spacing=0.7, jitter_size=0.3))
    saved = library.save_preset_as("Meine Ader", "Haut", brush)
    raw = json.loads(saved.path.read_text(encoding="utf-8"))
    assert not {"colour", "color", "tool", "mirror", "layer"} & set(raw)
    other = BrushSettings(colour=(0.5, 0.5, 0.5), mirror=True)
    applied = saved.apply(other)
    assert (applied.colour, applied.tool, applied.mirror) == (other.colour, other.tool, other.mirror)
    assert applied.opacity == 0.4 and applied.tip.alpha == "test/ader" and applied.dynamics.spacing == 0.7


def test_preset_round_trip_and_keep_size(library):
    brush = BrushSettings(radius_step=4, hardness=0.8, curve="linear",
                          tip=library.tip("test/kratzer", TipSettings(kreismaske=True, invert=True, contrast=0.4)),
                          dynamics=StrokeDynamics(spacing=1.2, emitter="spray", spray_density=20, orientation="view"))
    saved = library.save_preset_as("Rundreise", "Test", brush)
    library.refresh()
    loaded = library.preset(saved.id)
    assert loaded is not None and loaded.matches(brush)
    assert loaded.tip.alpha_hash == library.hash_of(library.alpha_entry("test/kratzer"))
    bigger = dataclasses.replace(brush, radius_step=9)
    assert not loaded.matches(bigger) and loaded.matches(bigger, keep_size=True)
    assert loaded.apply(bigger, keep_size=True).radius_step == 9
    assert loaded.apply(bigger).radius_step == 4


def test_broken_or_foreign_json_is_skipped_with_its_reason(library, user):
    library.save_preset_as("Gut", "", BrushSettings())
    brushes = user / "brushes"
    (brushes / "kaputt.json").write_text("{ nicht json", encoding="utf-8")
    (brushes / "fremd.json").write_text(json.dumps({"format": "other/1", "name": "X"}), encoding="utf-8")
    (brushes / "bereich.json").write_text(json.dumps({"format": lib.FORMAT, "name": "Zu weit", "opacity": 3.0}),
                                          encoding="utf-8")
    (brushes / "feld.json").write_text(json.dumps({"format": lib.FORMAT, "name": "Feld", "farbe": 1}), encoding="utf-8")
    (brushes / "doppelt.json").write_text(json.dumps({"format": lib.FORMAT, "name": "Runder Pinsel"}), encoding="utf-8")
    library.refresh()
    names = [p.name for p in library.presets()]
    assert "Gut" in names and "Zu weit" not in names and "Feld" not in names
    assert names.count("Runder Pinsel") == 1
    problems = "\n".join(library.problems)
    for file in ("kaputt.json", "fremd.json", "bereich.json", "feld.json", "doppelt.json"):
        assert file in problems
    assert "vergeben" in problems and "fremdes Format" in problems


def test_builtins_are_read_only(library):
    builtin = library.preset(lib.DEFAULT_PRESET)
    for action in (lambda: library.save_preset(builtin.id, BrushSettings()),
                   lambda: library.rename_preset(builtin.id, "Neu"),
                   lambda: library.delete_preset(builtin.id),
                   lambda: library.set_preset_category(builtin.id, "X"),
                   lambda: library.rename_alpha("test/poren", "X"),
                   lambda: library.delete_alpha("test/poren")):
        with pytest.raises(lib.LibraryError, match="eingebaut"):
            action()
    copy = library.duplicate_preset(builtin.id)  # duplicating (and "Speichern als") is allowed
    assert not copy.builtin and copy.name == "Runder Pinsel Kopie" and copy.matches(BrushSettings())
    assert library.duplicate_preset(builtin.id).name == "Runder Pinsel Kopie 2"


def test_save_rename_category_delete_and_favourites(library, user):
    preset = library.save_preset_as("Mein Pinsel", "Haut", BrushSettings(opacity=0.5))
    with pytest.raises(lib.LibraryError, match="vergeben"):
        library.save_preset_as("mein pinsel", "", BrushSettings())
    with pytest.raises(lib.LibraryError, match="vergeben"):
        library.save_preset_as("Runder Pinsel", "", BrushSettings())
    library.set_favourite(preset.id, True)
    saved = library.save_preset(preset.id, BrushSettings(opacity=0.25))
    assert saved.id == preset.id and saved.opacity == 0.25
    renamed = library.rename_preset(preset.id, "Anderer Name")
    assert renamed.id == "user:anderer_name" and not (user / "brushes" / "mein_pinsel.json").exists()
    assert library.favourite(renamed.id) and not library.favourite(preset.id)
    assert library.set_preset_category(renamed.id, "Schmutz").category == "Schmutz"
    fresh = lib.PaintLibrary(user)  # favourites persist in library.json
    assert fresh.favourite(renamed.id) and fresh.preset(renamed.id).category == "Schmutz"
    library.delete_preset(renamed.id)
    assert library.preset(renamed.id) is None and not library.favourite(renamed.id)


def test_without_a_user_folder_saving_is_refused():
    library = lib.PaintLibrary(None)
    with pytest.raises(lib.LibraryError, match="Benutzerordner"):
        library.save_preset_as("X", "", BrushSettings())
    with pytest.raises(lib.LibraryError, match="Benutzerordner"):
        library.import_alpha(_disc(), "X")
    library.set_favourite("test/poren", True)  # in memory
    assert library.favourite("test/poren")


# -- references and the missing alpha ------------------------------------------------------------------------------


def test_missing_alpha_resolves_to_none_and_keeps_its_reference(library, user):
    entry, created = library.import_alpha(_disc(), "Scheibe")
    assert created
    brush = BrushSettings(tip=library.tip(entry.id))
    preset = library.save_preset_as("Mit Scheibe", "", brush)
    library.delete_alpha(entry.id)
    library.refresh()
    loaded = library.preset(preset.id)
    assert library.resolve(loaded.tip) is None and library.image_for(loaded.tip) is None  # the round tip paints
    assert (loaded.tip.alpha, loaded.tip.alpha_name, loaded.tip.alpha_hash) == (entry.id, "Scheibe", entry.hash)
    resaved = library.save_preset(loaded.id, loaded.apply(BrushSettings()))  # saving keeps the reference
    raw = json.loads(resaved.path.read_text(encoding="utf-8"))
    assert raw["tip"]["alpha"] == {"id": entry.id, "name": "Scheibe", "hash": entry.hash}


def test_resolution_order_id_hash_name(library):
    entry, _ = library.import_alpha(_disc(), "Scheibe")
    by_hash = TipSettings(alpha="user:000000000000", alpha_name="anders", alpha_hash=entry.hash)
    assert library.resolve(by_hash).id == entry.id
    poren_hash = library.hash_of(library.alpha_entry("test/poren"))  # a built-in found by its pixels' hash
    assert library.resolve(TipSettings(alpha="builtin:x/y", alpha_hash=poren_hash)).id == "test/poren"
    by_name = TipSettings(alpha="user:000000000000", alpha_name="Scheibe", alpha_hash="ffffffffffff")
    assert library.resolve(by_name).id == entry.id
    assert library.resolve(TipSettings(alpha="user:000000000000", alpha_name="weg")) is None


def test_tip_refuses_an_unknown_alpha(library):
    with pytest.raises(lib.LibraryError):
        library.tip("user:doesnotexist")


# -- the import ----------------------------------------------------------------------------------------------------


def test_same_image_imported_twice_is_one_alpha(library, user, tmp_path):
    source = _png(tmp_path / "src" / "pore_brush.png", _rgba(_disc(96)))
    first, message = lib.open_import(source)
    assert first is not None and "Luminanz" in message
    a, created_a = library.import_alpha(first.preview(), "Pore A")
    second, _ = lib.open_import(_png(tmp_path / "src" / "copy of pore.png", _rgba(_disc(96))))
    b, created_b = library.import_alpha(second.preview(), "Pore B")
    assert created_a and not created_b and a.id == b.id == f"user:{alpha_api.pixel_hash(first.preview())}"
    assert len(list((user / "alphas").glob("*.png"))) == 1
    assert library.alpha_entry(a.id).name == "Pore A"


def test_user_assets_go_to_the_user_folder_only(tmp_path):
    user = tmp_path / "u" / "paint"
    builtin_before = _tree(lib.BUILTIN_DIR)
    library = lib.PaintLibrary(user)
    source = _png(tmp_path / "in" / "a.png", _rgba(_disc()))
    source_before = _tree(source.parent)
    draft, _ = lib.open_import(source)
    entry, _ = library.import_alpha(draft.preview(), "A", "Haut")
    preset = library.save_preset_as("P", "Haut", BrushSettings(tip=library.tip(entry.id)))
    library.duplicate_preset(preset.id)
    library.set_favourite(entry.id, True)
    library.set_keep_size(True)
    written = {str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*") if p.is_file()}
    assert all(p.startswith(os.path.join("u", "paint")) or p.startswith("in") for p in written), written
    assert _tree(source.parent) == source_before and _tree(lib.BUILTIN_DIR) == builtin_before
    assert sorted(p.name for p in user.iterdir()) == ["alphas", "brushes", "library.json"]


def test_import_source_modes_and_suggestion():
    grey = _disc(64)
    assert lib.suggest(_rgba(grey))[0] == lib.MODE_LUMINANCE  # no alpha channel
    shape_on_transparency = _rgba(np.zeros_like(grey), alpha=grey)  # a black shape on transparency
    assert lib.suggest(shape_on_transparency)[0] == lib.MODE_ALPHA
    noise = (np.random.default_rng(1).random(grey.shape) * 255).astype(np.uint8)
    assert lib.suggest(_rgba(noise, alpha=grey))[0] == lib.MODE_BOTH
    assert lib.suggest(_rgba(255 - grey)) == (lib.MODE_LUMINANCE, True)  # a bright border: invert suggested
    assert np.array_equal(lib.import_pixels(shape_on_transparency, lib.MODE_ALPHA), grey)
    assert np.array_equal(lib.import_pixels(_rgba(grey), lib.MODE_LUMINANCE), grey)
    both = lib.import_pixels(_rgba(np.full_like(grey, 128), alpha=grey), lib.MODE_BOTH)
    assert np.abs(both.astype(int) - (grey.astype(int) * 128 + 127) // 255).max() <= 1
    inverted = lib.import_pixels(_rgba(255 - grey), lib.MODE_LUMINANCE, invert=True)
    assert np.array_equal(inverted, grey)


def test_import_refusals_clamp_and_border_warning(tmp_path):
    with pytest.raises(lib.LibraryError, match="zu klein"):
        lib.import_pixels(_rgba(np.full((4, 40), 255, np.uint8)), lib.MODE_LUMINANCE)
    with pytest.raises(lib.LibraryError, match="leer"):
        lib.import_pixels(_rgba(np.zeros((32, 32), np.uint8)), lib.MODE_LUMINANCE)
    draft, message = lib.open_import(_png(tmp_path / "tiny.png", _rgba(np.full((5, 5), 255, np.uint8))))
    assert draft is None and "zu klein" in message
    draft, message = lib.open_import(tmp_path / "missing.png")
    assert draft is None and "nicht lesbar" in message
    big = lib.import_pixels(_rgba(np.full((3000, 1500), 200, np.uint8)), lib.MODE_LUMINANCE)
    assert max(big.shape) <= lib.IMPORT_MAX and big.shape == (1000, 500)
    assert lib.border_warning(np.full((32, 32), 200, np.uint8))
    assert not lib.border_warning(_disc(64))


def test_import_of_a_1024_image_meets_the_gate(tmp_path, library):
    """§9 "4c": a 1024² import <= 0.5 s on the reference PC (here [C]; the probe row is in the AD)."""
    rng = np.random.default_rng(3)
    rgba = _rgba((rng.random((1024, 1024)) * 255).astype(np.uint8), alpha=_disc(1024))
    source = _png(tmp_path / "big.png", rgba)
    started = time.perf_counter()
    draft, _ = lib.open_import(source)
    library.import_alpha(draft.preview(), "Groß")
    assert time.perf_counter() - started < 0.5


def test_a_dropped_png_is_picked_up(library, user):
    _png(user / "alphas" / "Mein Fleck.png", _rgba(_disc(48)))
    entries = [e for e in library.alphas() if e.source == "user"]
    assert len(entries) == 1
    entry = entries[0]
    assert entry.name == "Mein Fleck" and entry.category == lib.UNSORTED
    assert entry.id == f"user:{alpha_api.pixel_hash(_disc(48))}"
    image = library.alpha(entry.id)
    assert image is not None and np.array_equal(image.pixels, _disc(48))
    renamed = library.rename_alpha(entry.id, "Fleck 1")
    assert renamed.name == "Fleck 1" and lib.PaintLibrary(user).alpha_entry(entry.id).name == "Fleck 1"
    assert library.set_alpha_category(entry.id, "Schmutz").category == "Schmutz"


# -- shaping and the cache -----------------------------------------------------------------------------------------


def test_contrast_lut():
    identity = alpha_api.contrast_lut(False, 0.0)
    assert np.array_equal(identity, np.arange(256))
    for c in (-1.0, -0.4, 0.5, 1.0):
        lut = alpha_api.contrast_lut(False, c)
        assert lut[0] == 0 and lut[255] == 255 and np.all(np.diff(lut.astype(int)) >= 0)
    assert alpha_api.contrast_lut(False, 1.0)[64] < 64 < alpha_api.contrast_lut(False, -1.0)[64]
    assert np.array_equal(alpha_api.contrast_lut(True, 0.0), 255 - np.arange(256))


def test_shaped_alpha_and_image_for(library):
    tip = library.tip("test/punkte", TipSettings(invert=False, contrast=0.6))
    image = library.image_for(tip)
    base = alpha_api.generated_alpha("test/punkte")
    assert np.array_equal(image.pixels, alpha_api.contrast_lut(False, 0.6)[base.pixels])
    assert library.image_for(tip) is image  # cached
    assert library.image_for(dataclasses.replace(tip, contrast=0.0)) is base


def test_alpha_cache_is_capped(tmp_path):
    library = lib.PaintLibrary(tmp_path / "u", cache_bytes=200_000)
    ids = []
    for k in range(6):
        grey = (_disc(256).astype(int) * (k + 1) // 6).astype(np.uint8)
        ids.append(library.import_alpha(grey, f"A{k}")[0].id)
    for alpha_id in ids:
        assert library.alpha(alpha_id) is not None
    assert library.cached_bytes <= 200_000
    assert lib.CACHE_BYTES == 64 * 1024 * 1024
