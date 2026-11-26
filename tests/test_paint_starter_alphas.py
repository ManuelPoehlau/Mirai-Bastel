"""AD-037 Phase 4c (§14): the starter-alpha generator (`tools/make_starter_alphas.py`, proposal §6.5, P-22).

Deterministic, every alpha paints something inside a black border, the categories are P-22's; `--adopt` writes a
category where the library finds it (names from `index.json`, the hash recorded, the licence file names the generator).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

import tests._bootstrap  # noqa: F401

from mirai.paint import alpha as alpha_api
from mirai.paint import library as lib

_TOOL = Path(__file__).resolve().parents[1] / "tools" / "make_starter_alphas.py"


@pytest.fixture(scope="module")
def tool():
    spec = importlib.util.spec_from_file_location("make_starter_alphas", _TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_starter_alpha_is_deterministic_and_has_a_black_border(tool):
    assert list(tool.STARTER) == list(lib.CATEGORIES)
    for category, entries in tool.STARTER.items():
        for stem, name, make in entries:
            pixels = tool.generate(make)
            assert pixels.dtype == np.uint8 and min(pixels.shape) >= 64, stem
            assert pixels.max() >= 200 and (pixels > 25).mean() > 0.003, stem  # it paints
            ring = np.concatenate((pixels[0], pixels[-1], pixels[:, 0], pixels[:, -1]))
            assert ring.max() <= 2, stem  # a black border: no square edge
            assert not lib.border_warning(pixels)
    stem, name, make = tool.STARTER["schaden"][0]
    assert np.array_equal(tool.generate(make), tool.generate(make))


def test_adopt_writes_where_the_library_finds_it(tool, tmp_path, monkeypatch):
    monkeypatch.setattr(tool, "ASSETS", tmp_path / "assets" / "paint")
    written = tool.adopt(["formen"])
    assert [p.name for p in written] == ["kreis.png", "quadrat.png", "ring_weich.png", "linie.png"]
    library = lib.PaintLibrary(builtin_dir=tmp_path / "assets" / "paint")
    entries = {e.id: e for e in library.alphas() if e.source == "builtin"}
    ring = entries["builtin:formen/ring_weich"]
    assert (ring.name, ring.category) == ("Ring weich", "Formen")
    pixels = library.pixels(ring)
    assert ring.hash == alpha_api.pixel_hash(pixels) == alpha_api.pixel_hash(tool.generate(tool.ring_soft))
    index = json.loads((tmp_path / "assets" / "paint" / "alphas" / "index.json").read_text(encoding="utf-8"))
    assert set(index) == {"formen/kreis", "formen/quadrat", "formen/ring_weich", "formen/linie"}
    assert "make_starter_alphas.py" in (tmp_path / "assets" / "paint" / "LICENSES.md").read_text(encoding="utf-8")
    assert library.image_for(library.tip("builtin:formen/linie")).half_extents == (1.0, 0.125)


def test_the_adopted_starter_set_is_in_the_repo(tool):
    """Manu 2026-11-26, „alle übernehmen für das starterset“: every generated alpha is built in, with its name, its
    hash and its thumbnail file; the files are what the generator makes now (re-run `--adopt all` after a change)."""
    library = lib.PaintLibrary()
    builtin = {e.id: e for e in library.alphas() if e.source == "builtin"}
    expected = {f"builtin:{c}/{stem}": name for c, entries in tool.STARTER.items() for stem, name, _ in entries}
    assert {k: e.name for k, e in builtin.items()} == expected
    for category, entries in tool.STARTER.items():
        for stem, name, make in entries:
            entry = builtin[f"builtin:{category}/{stem}"]
            assert entry.category == lib.CATEGORIES[category]
            pixels = library.pixels(entry)
            assert np.array_equal(pixels, tool.generate(make)), stem
            assert entry.hash == alpha_api.pixel_hash(pixels)
            thumb_file = lib.BUILTIN_DIR / "alphas" / lib.THUMB_DIR / f"{entry.hash}.png"
            assert thumb_file.is_file()
            assert np.array_equal(library.thumbnail(entry.id), library.make_thumbnail(library.alpha(entry.id)))
    assert library.problems == []
    licences = (lib.BUILTIN_DIR / "LICENSES.md").read_text(encoding="utf-8")
    assert all(f"alphas/{key[len('builtin:'):]}.png" in licences for key in expected)
