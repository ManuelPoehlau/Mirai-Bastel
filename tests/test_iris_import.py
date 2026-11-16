"""Eye LookDev phase 5 (Manu 2026-11-16), headless: the iris import's pieces (`mirai.iris_import`) - PNG files, the
landmark estimate, the symmetry check, the copy and its fit, the height in alpha, and §H row 5's landmark error in the
frontal model. A synthetic "photo" is the procedural iris seen through the eye's own cornea (`eye_optics.trace`), so
the refraction it carries is known exactly."""

from __future__ import annotations

import json
import math
from functools import lru_cache

import numpy as np
import pytest

import tests._bootstrap  # noqa: F401

from mirai import iris_import as ii
from mirai.eye_object import DEFAULT_EYE
from viewport import eye_optics as eo

G = eo.EyeGeometry.from_values(DEFAULT_EYE)
SIZE = 384


def _flat_iris() -> np.ndarray:
    """The procedural iris as an 8-bit RGBA image (a flat / painted iris: its own layout, planar mapping)."""
    rgb = eo.procedural_iris(G, SIZE)
    out = np.full((SIZE, SIZE, 4), 255, np.uint8)
    out[..., :3] = np.clip(np.round(rgb * 255.0), 0, 255).astype(np.uint8)
    return out


@lru_cache(maxsize=4)
def _photo(scale: float = 0.42) -> tuple[np.ndarray, ii.Landmarks]:
    """The flat iris photographed frontally through the cornea, on a white background: each pixel's apparent radius
    traced to the iris (planar mapping), outside the visible limbus white. Returns the photo and its exact landmarks."""
    flat = _flat_iris().astype(np.float64)
    n = SIZE
    half = n / 2.0
    px_per_unit = scale * half / G.limbus_radius  # the visible limbus spans `scale` of half the photo
    c = (np.arange(n) + 0.5 - half) / px_per_unit
    y, x = np.meshgrid(c, c, indexing="ij")
    eye = np.stack([x, -y, np.full_like(x, 10.0)], axis=-1)
    hit = eo.trace(eye, np.broadcast_to([0.0, 0.0, -1.0], eye.shape), "V2", G)
    seen = (hit.kind == eo.IRIS) | (hit.kind == eo.PUPIL)
    uv = eo.iris_uv(hit.hit[..., :2], G)  # planar
    sample = ii._bilinear(flat, uv[..., 0] * SIZE, (1.0 - uv[..., 1]) * SIZE)
    photo = np.where(seen[..., None], sample, 255.0)
    photo = np.clip(np.round(photo), 0, 255).astype(np.uint8)
    photo[..., 3] = 255
    pupil = float(ii.apparent_radius(G.pupil_radius, G)) * px_per_unit
    limbus = ii.visible_limbus(G) * px_per_unit
    return photo, ii.Landmarks(ii.Circle(half, half, pupil), ii.Circle(half, half, limbus))


def _render_frontal(result: ii.ImportResult, size: int) -> tuple[np.ndarray, np.ndarray]:
    """The copy drawn frontally through the cornea with its fit (the eye pass's path, NumPy): (rgb, seen)."""
    half = size / 2.0
    _, marks = _photo()
    px_per_unit = marks.iris.r / ii.visible_limbus(G)
    c = (np.arange(size) + 0.5 - half) / px_per_unit
    y, x = np.meshgrid(c, c, indexing="ij")
    eye = np.stack([x, -y, np.full_like(x, 10.0)], axis=-1)
    hit = eo.trace(eye, np.broadcast_to([0.0, 0.0, -1.0], eye.shape), "V2", G)
    seen = (hit.kind == eo.IRIS) | (hit.kind == eo.PUPIL)
    spec = type("Fit", (), dict(fit_pupil=result.fit_pupil, fit_limbus=result.fit_limbus,
                                hold_outer_color=result.hold_outer_color))()
    uv = eo.iris_uv(hit.hit[..., :2], G, eo.fit_knots(spec, G))
    n = result.rgba.shape[0]
    rgb = ii._bilinear(result.rgba.astype(np.float64), uv[..., 0] * n, (1.0 - uv[..., 1]) * n)[..., :3]
    return rgb, seen


# -- PNG ---------------------------------------------------------------------------------------------------------------


def test_png_round_trip_and_filters():
    rng = np.random.default_rng(3)
    rgba = rng.integers(0, 256, (37, 53, 4), dtype=np.uint8)
    assert np.array_equal(ii.decode_png(ii.encode_png(rgba)), rgba)
    # every filter type, written by hand: each row filtered with its own type
    import struct
    import zlib

    h, w, bpp = rgba.shape[0], rgba.shape[1], 4
    rows, prev = [], np.zeros(w * bpp, np.int64)
    for y in range(h):
        line = rgba[y].reshape(-1).astype(np.int64)
        kind = y % 5
        left = np.concatenate([np.zeros(bpp, np.int64), line[:-bpp]])
        upleft = np.concatenate([np.zeros(bpp, np.int64), prev[:-bpp]])
        if kind == 0:
            pred = np.zeros_like(line)
        elif kind == 1:
            pred = left
        elif kind == 2:
            pred = prev
        elif kind == 3:
            pred = (left + prev) // 2
        else:
            p = left + prev - upleft
            pa, pb, pc = np.abs(p - left), np.abs(p - prev), np.abs(p - upleft)
            pred = np.where((pa <= pb) & (pa <= pc), left, np.where(pb <= pc, prev, upleft))
        rows.append(bytes([kind]) + ((line - pred) % 256).astype(np.uint8).tobytes())
        prev = line

    def chunk(kind, payload):
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))

    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(b"".join(rows))) + chunk(b"IEND", b""))
    assert np.array_equal(ii.decode_png(png), rgba)
    with pytest.raises(ValueError):
        ii.decode_png(b"GIF89a")


# -- landmarks ---------------------------------------------------------------------------------------------------------


def test_the_estimate_finds_both_circles_and_the_pupil_centre():
    photo, truth = _photo()
    marks, note = ii.estimate(photo)
    assert note == "" and marks is not None
    assert abs(marks.pupil.r - truth.pupil.r) < 0.02 * truth.iris.r
    assert abs(marks.iris.r - truth.iris.r) < 0.02 * truth.iris.r
    shifted = np.roll(photo, (9, -14), axis=(0, 1))  # the eye off the image centre
    moved, _ = ii.estimate(shifted)
    assert abs(moved.pupil.x - (truth.pupil.x - 14)) < 1.0 and abs(moved.pupil.y - (truth.pupil.y + 9)) < 1.0
    assert ii.estimate(np.full((64, 64, 4), 255, np.uint8))[0] is None  # nothing to find: no suggestion, a reason


def test_the_symmetry_check_flags_an_oblique_photo():
    photo, truth = _photo()
    ellipticity, offset, hint = ii.edge_check(photo, truth)
    assert ellipticity < 0.01 and offset == 0.0 and hint == ""
    # the same eye seen 30 degrees from the side: squeezed horizontally by cos 30
    n = photo.shape[0]
    c = np.arange(n) + 0.5
    y, x = np.meshgrid(c, c, indexing="ij")
    squeezed = ii._bilinear(photo.astype(np.float64), n / 2 + (x - n / 2) / math.cos(math.radians(30)), y)
    oblique = np.clip(np.round(squeezed), 0, 255).astype(np.uint8)
    ellipticity, _, hint = ii.edge_check(oblique, truth)
    assert ellipticity > ii.MAX_ELLIPTICITY and "schräg" in hint
    off = ii.Landmarks(truth.pupil.moved(x=truth.pupil.x + 0.2 * truth.iris.r), truth.iris)
    assert "neben der Irismitte" in ii.edge_check(photo, off)[2]


def test_unusable_landmarks_are_refused():
    iris = ii.Circle(100, 100, 50)
    assert ii.Landmarks(ii.Circle(100, 100, 60), iris).problem()
    assert ii.Landmarks(ii.Circle(140, 100, 20), iris).problem()
    with pytest.raises(ValueError):
        ii.build_copy(np.zeros((8, 8, 4), np.uint8), ii.Landmarks(ii.Circle(4, 4, 5), ii.Circle(4, 4, 3)), "flat")
    with pytest.raises(ValueError):
        ii.build_copy(np.zeros((8, 8, 4), np.uint8), ii.Landmarks(ii.Circle(4, 4, 1), ii.Circle(4, 4, 3)), "photo",
                      correct=True)  # the correction needs the anatomy


# -- the copy and the landmark error (§H row 5) -----------------------------------------------------------------------


def test_a_flat_image_keeps_its_landmarks_exactly():
    flat = _flat_iris()
    edge = G.limbus_radius / G.iris_radius * SIZE / 2  # where the planar procedural iris has the limbus
    marks = ii.Landmarks(ii.Circle(SIZE / 2, SIZE / 2, G.pupil_radius / G.iris_radius * SIZE / 2),
                         ii.Circle(SIZE / 2, SIZE / 2, edge))
    result = ii.build_copy(flat, marks, "flat", DEFAULT_EYE)
    assert result.fit_limbus == ii.TARGET_SHARE and result.hold_outer_color
    assert result.fit_pupil == pytest.approx(ii.TARGET_SHARE * marks.pupil.r / marks.iris.r)
    assert ii.frontal_error(result, marks, "flat", DEFAULT_EYE, False) < 1e-9


def test_a_frontal_photo_needs_the_correction_and_meets_the_limit_with_it():
    photo, truth = _photo()
    plain = ii.build_copy(photo, truth, "photo", DEFAULT_EYE, correct=False)
    fixed = ii.build_copy(photo, truth, "photo", DEFAULT_EYE, correct=True)
    plain_error = ii.frontal_error(plain, truth, "photo", DEFAULT_EYE, False)
    assert plain_error > 0.04  # the cornea's magnification twice: about 5 % at the visible limbus
    assert ii.frontal_error(fixed, truth, "photo", DEFAULT_EYE, True) < 1e-6
    estimated, _ = ii.estimate(photo)  # with the suggested landmarks, uncorrected by hand
    with_estimate = ii.build_copy(photo, estimated, "photo", DEFAULT_EYE, correct=True)
    assert ii.frontal_error(with_estimate, truth, "photo", DEFAULT_EYE, True) <= ii.MAX_LANDMARK_ERROR


def test_the_corrected_copy_draws_the_photo_back_through_the_cornea():
    """Drawn frontally through the cornea (the eye pass's path in NumPy), the corrected copy reproduces the photo:
    neither a doubled limbus nor a pupil of another size; the uncorrected copy does not."""
    photo, truth = _photo()
    seen_photo = ii.luminance(photo) < 0.99
    diffs = {}
    for correct in (True, False):
        result = ii.build_copy(photo, truth, "photo", DEFAULT_EYE, correct=correct)
        rgb, seen = _render_frontal(result, SIZE)
        assert np.array_equal(seen, seen_photo)
        diffs[correct] = np.abs(rgb - photo[..., :3].astype(np.float64)).mean(axis=-1)[seen].mean()
        if correct:
            drawn = np.concatenate([np.clip(np.round(rgb), 0, 255).astype(np.uint8),
                                    np.full(rgb.shape[:2] + (1,), 255, np.uint8)], -1)
            found = ii.estimate(np.where(seen[..., None], drawn, 255).astype(np.uint8))[0]
            assert abs(found.pupil.r - ii.estimate(photo)[0].pupil.r) <= 1.0  # no swimming pupil
            assert abs(found.iris.r - ii.estimate(photo)[0].iris.r) <= 1.0  # no doubled limbus
    assert diffs[True] < 3.0 and diffs[False] > 2.5 * diffs[True]  # grey levels, 8 bit (resampling twice)


def test_the_height_lands_in_alpha_or_the_source_alpha_is_kept():
    photo, truth = _photo()
    result = ii.build_copy(photo, truth, "photo", DEFAULT_EYE, correct=True)
    expected = eo.iris_height(result.rgba[..., :3] / 255.0, result.fit_pupil, result.fit_limbus)
    assert np.array_equal(result.rgba[..., 3], np.clip(np.round(expected * 255.0), 0, 255).astype(np.uint8))
    assert "no alpha" in ii.build_copy(photo, truth, "photo", DEFAULT_EYE, correct=True, keep_alpha=True).note
    painted = photo.copy()
    painted[..., 3] = 77
    kept = ii.build_copy(painted, truth, "flat", keep_alpha=True)
    assert kept.note == "" and np.all(kept.rgba[..., 3] == 77)


# -- the app path --------------------------------------------------------------------------------------------------


from pathlib import Path  # noqa: E402

from mirai import application as application_module  # noqa: E402
from mirai import eye_presets  # noqa: E402
from mirai.application import Application  # noqa: E402
from mirai.eye_object import DEFAULT_IRIS, look_value  # noqa: E402
from mirai.interaction.input import Input  # noqa: E402

CTRL_Z = Input("key", "z", frozenset({"ctrl"}))


@pytest.fixture
def app(tmp_path, monkeypatch) -> Application:
    monkeypatch.setattr(application_module, "EYE_IMPORT_DIR", tmp_path / "eye_import")
    app = Application()
    app.init_scene("cube")
    app.set_viewport_size(800, 600)
    return app


def _photo_file(directory: Path) -> tuple[Path, ii.Landmarks]:
    photo, truth = _photo()
    path = directory / "my iris.png"
    path.write_bytes(ii.encode_png(photo))
    return path, truth


def test_import_is_one_undo_step_and_lands_in_eye_import_until_saved(app, tmp_path):
    left, right = app.add_eye("L"), app.add_eye("R")
    app.select_objects([left.id, right.id])
    source, marks = _photo_file(tmp_path)
    depth = len(app._selection_undo_stack)
    assert app.import_eye_iris(source, marks, "photo", correct=True) is True
    assert len(app._selection_undo_stack) == depth + 1 and "landmark error 0.0 %" in app.status_message
    copy = Path(left.texture)
    assert copy.parent == tmp_path / "eye_import" and right.texture == left.texture
    assert copy.name.startswith("my_iris_iris_") and copy.suffix == ".png"
    for eye in (left, right):
        assert look_value(eye.eye, "iris.relief_source") == "alpha"
        assert eye.eye.fit_limbus == ii.TARGET_SHARE and not eye.eye.hold_outer_color
        assert all(getattr(eye.eye.look.iris, n) == 0.0 for n in eo.IRIS_AMOUNTS)  # still neutral to draw
    stored = ii.decode_png(copy.read_bytes())
    assert ii.has_alpha(stored)  # the height in alpha
    scene = tmp_path / "scenes" / "Kopf.mirai.json"
    assert app.save_scene_file(scene) is True
    assert Path(left.texture).parent == scene.parent / "Kopf_textures" and copy.exists()
    app.key_press(CTRL_Z)  # the save is no step: this undoes the import
    assert left.texture is None and left.eye.look is None and left.eye.fit_pupil is None


def test_import_into_a_saved_scene_writes_beside_it_and_opens_elsewhere(app, tmp_path, monkeypatch):
    eye = app.add_eye()
    scene = tmp_path / "clone" / "scenes" / "Test.mirai.json"
    assert app.save_scene_file(scene) is True
    source, marks = _photo_file(tmp_path)
    assert app.import_eye_iris(source, marks, "flat", hold_outer_color=False) is True
    assert Path(eye.texture).parent == scene.parent / "Test_textures"
    assert eye.eye.fit_pupil == pytest.approx(ii.TARGET_SHARE * marks.pupil.r / marks.iris.r)
    assert app.save_scene_file(scene) is True
    raw = json.loads(scene.read_text(encoding="utf-8"))
    assert [o["texture"] for o in raw["objects"] if "texture" in o] == [f"Test_textures/{Path(eye.texture).name}"]
    moved = tmp_path / "elsewhere"
    (scene.parent).rename(moved)  # a fresh clone at another place
    monkeypatch.chdir(tmp_path)
    fresh = Application()
    fresh.init_scene("cube")
    fresh.load_scene("file", scene_path=moved / "Test.mirai.json")
    texture = next(o.texture for o in fresh.scene.objects.values() if o.eye is not None)
    assert Path(texture) == moved / "Test_textures" / Path(eye.texture).name and Path(texture).is_file()


def test_import_refusals(app, tmp_path):
    source, marks = _photo_file(tmp_path)
    assert app.import_eye_iris(source, marks) is False  # no eye selected
    app.add_eye()
    assert app.import_eye_iris(tmp_path / "missing.png", marks) is False and "missing.png" in app.status_message
    bad = ii.Landmarks(marks.iris, marks.pupil)
    assert app.import_eye_iris(source, bad) is False and "smaller" in app.status_message


def test_presets_and_reset_keep_the_relief_source(app, tmp_path):
    eye = app.add_eye()
    source, marks = _photo_file(tmp_path)
    assert app.import_eye_iris(source, marks) is True
    assert app.apply_eye_preset(eye_presets.IRIS_START_NAME) is True  # carries relief_source "luminance"
    assert eye.eye.look.iris.relief == eye_presets.IRIS_START["look.iris"].relief
    assert eye.eye.look.iris.relief_source == "alpha"
    assert app.apply_eye_preset(eye_presets.BUILTIN_NAME) is True  # removes the look
    assert look_value(eye.eye, "iris.relief_source") == "alpha" and eye.eye.look.iris.relief == 0.0
    app.set_eye(**{"look.iris.relief": 0.5})
    assert app.reset_eye_iris() is True
    assert eye.eye.look.iris == DEFAULT_IRIS.__class__(**{**DEFAULT_IRIS.to_dict(), "relief_source": "alpha"})
    other = app.add_eye()  # an eye without an import: presets behave as before phase 5
    app.set_eye(**{"look.iris.relief": 0.5})
    assert app.apply_eye_preset(eye_presets.BUILTIN_NAME) is True and other.eye.look is None
