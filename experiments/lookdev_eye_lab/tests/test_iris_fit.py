"""The radial fit of the custom iris (headless): the sidecar `out/iris_custom.json` (validation, read-only), the remap,
the iris mesh it builds, and the image estimate."""

from __future__ import annotations

import json
import math
import os
import struct
import zlib

import numpy as np
import pytest

from lookdev_gpu_probe import cube_math as cm
from lookdev_eye_lab import eye_geometry as geo
from lookdev_eye_lab import iris_fit, iris_source

FIT = iris_fit.IrisFit(0.22, 0.90)


def _sidecar(out_dir, content) -> object:
    path = out_dir / iris_fit.SIDECAR_NAME
    path.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
    os.utime(path, ns=(1_600_000_000_000_000_000, 1_600_000_000_000_000_000))
    return path


def _custom_png(out_dir):
    path = out_dir / iris_source.CUSTOM_NAME
    cm.write_png(path, np.full((32, 32, 3), 0.5))
    return path


def _snapshot(path):
    return path.read_bytes(), path.stat().st_mtime_ns


def test_a_valid_sidecar_gives_the_fit_and_is_left_untouched(tmp_path):
    path = _sidecar(tmp_path, {"pupil": 0.22, "limbus": 0.9})
    before = _snapshot(path)
    fit, note = iris_fit.load(tmp_path)
    assert fit == iris_fit.IrisFit(0.22, 0.9) and note == ""
    assert _snapshot(path) == before


def test_no_sidecar_means_no_fit(tmp_path):
    assert iris_fit.load(tmp_path) == (None, "")


@pytest.mark.parametrize("content, reason", [
    ("{not json", "not valid JSON"),
    ([0.22, 0.9], "not a JSON object"),
    ({"pupil": 0.22}, "missing 'limbus'"),
    ({"pupil": 0.22, "limbus": 0.9, "pupill": 0.2}, "unknown key 'pupill'"),
    ({"pupil": "0.22", "limbus": 0.9}, "'pupil' is not a number"),
    ({"pupil": True, "limbus": 0.9}, "'pupil' is not a number"),
    ('{"pupil": NaN, "limbus": 0.9}', "'pupil' is not a number"),
    ('{"pupil": 0.2, "limbus": Infinity}', "'limbus' is not a number"),
    ({"pupil": 0.0, "limbus": 0.9}, "0 < pupil < limbus <= 1"),
    ({"pupil": 0.5, "limbus": 0.4}, "0 < pupil < limbus <= 1"),
    ({"pupil": 0.2, "limbus": 1.2}, "0 < pupil < limbus <= 1"),
    ({"pupil": 0.2, "limbus": 0.88, "hold_outer_color": "yes"}, "'hold_outer_color' must be true or false"),
    ({"pupil": 0.2, "limbus": 0.88, "hold_outer_color": 1}, "'hold_outer_color' must be true or false"),
    ({"pupil": 0.2, "limbus": 0.88, "hold": True}, "unknown key 'hold'"),
])
def test_an_invalid_sidecar_is_ignored_with_the_reason(tmp_path, content, reason):
    path = _sidecar(tmp_path, content)
    before = _snapshot(path)
    fit, note = iris_fit.load(tmp_path)
    assert fit is None and reason in note
    _custom_png(tmp_path)
    source = iris_source.choose(tmp_path)
    assert source.custom and source.fit is None and f"{iris_fit.SIDECAR_NAME} ignored: " in source.describe()
    assert reason in source.describe()
    assert _snapshot(path) == before


def test_the_fit_applies_to_the_custom_image_only(tmp_path):
    _sidecar(tmp_path, {"pupil": 0.22, "limbus": 0.9})
    assert iris_source.choose(tmp_path).fit is None  # no custom image: the procedural iris, planar
    _custom_png(tmp_path)
    source = iris_source.choose(tmp_path)
    assert source.custom and source.fit == iris_fit.IrisFit(0.22, 0.9)
    assert "radial fit iris_custom.json: image pupil 0.220 -> 0.268" in source.describe()


def test_without_a_sidecar_the_description_is_unchanged(tmp_path):
    _custom_png(tmp_path)
    source = iris_source.choose(tmp_path)
    assert source.fit is None and source.describe() == (
        f"iris texture: CUSTOM {iris_source.CUSTOM_NAME} - {source.note}")


def test_share_map_hits_the_knots_and_is_continuous_and_monotonic():
    for target in iris_fit.TARGETS:
        fit = iris_fit.IrisFit(0.22, 0.90, target)
        lp, lt = fit.lab_knots
        assert iris_fit.share_map([0.0, lp, lt, 1.0], fit) == pytest.approx([0.0, 0.22, 0.90, 1.0], abs=1e-12)
        s = np.linspace(0.0, 1.2, 20001)
        m = iris_fit.share_map(s, fit)
        assert np.all(np.diff(m) > 0.0) and np.max(np.abs(np.diff(m))) < 3.0 * (s[1] - s[0])


def test_targets_are_the_lab_limbus_and_the_chamber_angle():
    assert iris_fit.LAB_PUPIL_SHARE == pytest.approx(0.268, abs=0.001)
    assert iris_fit.TARGETS["limbus"] == pytest.approx(0.819, abs=0.001)
    assert iris_fit.TARGETS["angle"] == pytest.approx(0.779, abs=0.001)


def test_uv_keeps_the_angle_and_the_identity_fit_is_the_planar_mapping():
    rng = np.random.default_rng(1)
    xy = rng.uniform(-geo.IRIS_RADIUS, geo.IRIS_RADIUS, (500, 2))
    uv = iris_fit.uv(xy, FIT)
    d = uv - 0.5
    assert np.allclose(np.arctan2(d[:, 1], d[:, 0]), np.arctan2(xy[:, 1], xy[:, 0]))
    identity = iris_fit.IrisFit(iris_fit.LAB_PUPIL_SHARE, iris_fit.TARGETS["limbus"])
    planar = np.array([geo.iris_uv(x, y) for x, y in xy])
    assert np.allclose(iris_fit.uv(xy, identity), planar, atol=1e-12)
    assert np.allclose(iris_fit.uv([0.0, 0.0], FIT), 0.5)
    # The image radius share at a planar point is share_map of its lab share.
    s = np.linalg.norm(xy, axis=-1) / geo.IRIS_RADIUS
    assert np.allclose(2.0 * np.linalg.norm(uv - 0.5, axis=-1), iris_fit.share_map(s, FIT))


def test_iris_mesh_default_is_unchanged_and_the_fit_adds_knot_rings():
    default = geo.iris_mesh()
    assert default.export_state() == geo.iris_mesh(uv=None, extra_radii=()).export_state()
    assert default.export_state() == geo.build_parts()["iris"].export_state()
    fitted = geo.iris_mesh(uv=iris_fit.mesh_uv(FIT), extra_radii=iris_fit.mesh_extra_radii(FIT))
    # The pupil knot is ring 0 already; the target knot is one new ring of SEGMENTS vertices.
    assert len(fitted.all_vertex_ids()) == len(default.all_vertex_ids()) + geo.SEGMENTS
    radii = {round(math.hypot(*fitted.vertex_position(v)[:2]), 9) for v in fitted.all_vertex_ids()}
    assert round(iris_fit.TARGETS["limbus"] * geo.IRIS_RADIUS, 9) in radii
    for f in fitted.all_face_ids():
        corners = [fitted.vertex_position(v) for v in fitted.face_vertices(f)]
        for (x, y, z), uv in zip(corners, fitted.face_uvs(f)):
            on_annulus = z > geo.iris_z(geo.PUPIL_RADIUS) - 1e-9 and math.hypot(x, y) > geo.PUPIL_RADIUS * 0.999
            centre_face = any(math.hypot(px, py) < geo.PUPIL_RADIUS * 0.999 or pz < geo.iris_z(geo.PUPIL_RADIUS) - 1e-9
                              for px, py, pz in corners)
            expected = (0.5, 0.5) if centre_face else tuple(iris_fit.uv((x, y), FIT))
            assert on_annulus or centre_face
            assert np.allclose(uv, expected)


def test_the_pupil_ring_samples_the_images_pupil_edge():
    to_uv = iris_fit.mesh_uv(FIT)
    for k in range(8):
        a = 2.0 * np.pi * k / 8
        u, v = to_uv(geo.PUPIL_RADIUS * np.cos(a), geo.PUPIL_RADIUS * np.sin(a))
        assert 2.0 * np.hypot(u - 0.5, v - 0.5) == pytest.approx(0.22, abs=1e-12)


def _profile_image(pupil, limbus, size=256):
    c = (np.arange(size) + 0.5) / size * 2.0 - 1.0
    y, x = np.meshgrid(c, c, indexing="ij")
    rho = np.hypot(x, y)
    rgb = np.full((size, size, 3), (0.45, 0.35, 0.25))
    rgb[rho < pupil] = 0.02
    rgb[rho >= limbus] = 1.0
    return rgb


def test_estimate_finds_the_edges_of_a_profile_image(tmp_path):
    path = tmp_path / "x.png"
    cm.write_png(path, _profile_image(0.22, 0.90))
    pupil, limbus = iris_fit.estimate(iris_fit.read_png_rgb(path))
    assert pupil == pytest.approx(0.22, abs=0.011) and limbus == pytest.approx(0.90, abs=0.011)
    assert iris_fit.estimate(np.zeros((64, 64, 3))) == (None, None)


def _encode(rows: np.ndarray, kind: int, bpp: int) -> bytes:
    """One PNG filter type applied to every row (the encoder side, for the decoder test)."""
    out, prev = bytearray(), np.zeros(rows.shape[1], dtype=int)
    for row in rows.astype(int):
        left = np.concatenate([np.zeros(bpp, dtype=int), row[:-bpp]])
        up_left = np.concatenate([np.zeros(bpp, dtype=int), prev[:-bpp]])
        if kind == 0:
            pred = np.zeros_like(row)
        elif kind == 1:
            pred = left
        elif kind == 2:
            pred = prev
        elif kind == 3:
            pred = (left + prev) // 2
        else:
            p = left + prev - up_left
            pa, pb, pc = abs(p - left), abs(p - prev), abs(p - up_left)
            pred = np.where((pa <= pb) & (pa <= pc), left, np.where(pb <= pc, prev, up_left))
        out += bytes([kind]) + bytes(((row - pred) & 0xFF).astype(np.uint8))
        prev = row
    return bytes(out)


@pytest.mark.parametrize("kind", [0, 1, 2, 3, 4])
def test_png_reader_undoes_every_filter(tmp_path, kind):
    rng = np.random.default_rng(kind)
    pixels = rng.integers(0, 256, (9, 7, 4), dtype=np.uint8)
    chunk = lambda k, d: struct.pack(">I", len(d)) + k + d + struct.pack(">I", zlib.crc32(k + d) & 0xFFFFFFFF)  # noqa
    data = (iris_source.PNG_SIGNATURE + chunk(b"IHDR", struct.pack(">IIBBBBB", 7, 9, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(_encode(pixels.reshape(9, -1), kind, 4))) + chunk(b"IEND", b""))
    path = tmp_path / "f.png"
    path.write_bytes(data)
    assert iris_source.inspect(path)[0]
    assert np.array_equal(np.round(iris_fit.read_png_rgb(path) * 255).astype(np.uint8), pixels[..., :3])


@pytest.mark.parametrize("content, outer", [
    ({"pupil": 0.22, "limbus": 0.88}, 1.0),
    ({"pupil": 0.22, "limbus": 0.88, "hold_outer_color": False}, 1.0),
    ({"pupil": 0.22, "limbus": 0.88, "hold_outer_color": True}, 0.88),
])
def test_hold_outer_color_is_optional_and_off_by_default(tmp_path, content, outer):
    _sidecar(tmp_path, content)
    fit, note = iris_fit.load(tmp_path)
    assert note == "" and fit.outer == outer and fit.hold == (outer != 1.0)
    assert ("outer colour held" in fit.describe()) == fit.hold


def test_hold_keeps_the_iris_edge_colour_beyond_the_target():
    fit = iris_fit.IrisFit(0.22, 0.88, outer=0.88)
    lt = fit.lab_knots[1]
    s = np.linspace(lt, 1.3, 50)
    assert np.allclose(iris_fit.share_map(s, fit), 0.88)
    assert iris_fit.share_map(lt - 1e-9, fit) == pytest.approx(0.88, abs=1e-6)  # continuous at the knot
