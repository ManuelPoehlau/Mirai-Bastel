"""The GL-free half of the probe (2026-11-13): face convention, patterns, expected values, interpretation. Headless."""

from __future__ import annotations

import re
import struct
import zlib

import numpy as np
import pytest

from lookdev_gpu_probe import cube_math as cm

#: GL 3.3 core, table 3.21: per face the centre direction and the directions of increasing s and t.
GL_FACE_AXES = {
    0: ((1, 0, 0), (0, 0, -1), (0, -1, 0)),
    1: ((-1, 0, 0), (0, 0, 1), (0, -1, 0)),
    2: ((0, 1, 0), (1, 0, 0), (0, 0, 1)),
    3: ((0, -1, 0), (1, 0, 0), (0, 0, -1)),
    4: ((0, 0, 1), (1, 0, 0), (0, -1, 0)),
    5: ((0, 0, -1), (-1, 0, 0), (0, -1, 0)),
}


def test_face_convention_is_the_gl_table():
    for face, (centre, ds, dt) in GL_FACE_AXES.items():
        centre, ds, dt = (np.array(v, dtype=float) for v in (centre, ds, dt))
        assert np.allclose(cm.face_st_to_direction(face, 0.5, 0.5), centre)
        assert np.allclose(cm.face_st_to_direction(face, 1.0, 0.5) - centre, ds)
        assert np.allclose(cm.face_st_to_direction(face, 0.5, 1.0) - centre, dt)
        f, s, t = cm.direction_to_face_st(centre + 0.3 * ds - 0.2 * dt)
        assert f == face and s == pytest.approx(0.65) and t == pytest.approx(0.4)


def test_direction_and_face_coordinates_round_trip():
    d = np.random.default_rng(7).normal(size=(2000, 3))
    back = cm.face_st_to_direction(*cm.direction_to_face_st(d))
    unit = d / np.linalg.norm(d, axis=1, keepdims=True)
    assert np.allclose(back / np.linalg.norm(back, axis=1, keepdims=True), unit, atol=1e-12)


def test_texel_directions_map_back_to_their_texel():
    n = 4
    face, s, t = cm.direction_to_face_st(cm.texel_directions(n))
    j, i = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
    assert np.array_equal(face, np.broadcast_to(np.arange(6)[:, None, None], face.shape))
    assert np.allclose(s * n - 0.5, i) and np.allclose(t * n - 0.5, j)


def test_level_sizes_and_memory():
    assert cm.level_sizes(64) == [64, 32, 16, 8, 4, 2, 1]
    with pytest.raises(ValueError):
        cm.level_sizes(96)
    # the audit's estimate (§5.6): an RGBA16F cube with mips is about 1.0 MiB at 128^2 and about 4 MiB at 256^2
    assert cm.cube_bytes(128, 8) == 6 * 8 * 21845 == 1_048_560
    assert cm.cube_bytes(256, 8) == 4_194_288
    assert cm.cube_bytes(64, 4, mips=False) == 6 * 4 * 64 * 64


def test_stored_models_each_storage_format():
    v = np.array([0.1, 0.5, 2.0, 1e-3])
    assert np.allclose(cm.stored(v, cm.RGBA8), np.round(np.clip(v, 0, 1) * 255) / 255)
    assert np.array_equal(cm.stored(v, cm.RGBA16F), v.astype(np.float16).astype(np.float64))
    assert np.array_equal(cm.stored(v, cm.RGBA16F_FLOAT_UPLOAD), cm.stored(v, cm.RGBA16F))
    assert np.array_equal(cm.stored(v, cm.RGBA32F), v.astype(np.float32).astype(np.float64))
    assert cm.to_upload(v, cm.RGBA8).dtype == np.uint8 and cm.to_upload(v, cm.RGBA16F).dtype == np.float16
    assert cm.to_upload(v, cm.RGBA16F_FLOAT_UPLOAD).dtype == np.float32


def test_quadrant_values_are_unique_and_float_ones_would_not_survive_8_bit():
    for hdr in (False, True):
        values = {cm.quadrant_value(f, q, hdr) for f in range(6) for q in range(4)}
        assert len(values) == 24
    rgba8 = np.array([cm.quadrant_value(f, q, False) for f in range(6) for q in range(4)])
    assert rgba8.min() >= 0 and rgba8.max() <= 1 and np.allclose(rgba8 * 255, np.round(rgba8 * 255))
    hdr = np.array([cm.quadrant_value(f, q, True) for f in range(6) for q in range(4)])
    assert hdr.max() > 100 and 0 < hdr[:, 1].min() < 0.5 / 255
    # half floats keep them exactly (except the 0.1 steps in A, which are rounded on purpose)
    assert np.array_equal(cm.stored(hdr[:, :3], cm.RGBA16F), hdr[:, :3])
    # a driver that kept them in 8 bits would be caught, with the clamp named
    as_8bit = cm.stored(hdr, cm.RGBA8)
    assert not cm.within(as_8bit, cm.stored(hdr, cm.RGBA16F), 1e-5, 1e-3).any()
    assert "clamped" in cm.clamp_diagnosis(as_8bit, hdr)
    assert cm.clamp_diagnosis(hdr, hdr) == ""


def test_quadrant_samples_hit_their_quadrant_on_every_level_size():
    dirs, keys = cm.quadrant_samples()
    for size in (8, 64):
        level0 = cm.quadrant_pattern(size, True)[0]
        expected = np.array([cm.quadrant_value(f, q, True) for f, q in keys])
        assert np.allclose(cm.bilinear_clamp(level0, dirs), expected)


def test_bilinear_clamp_reproduces_a_linear_gradient_and_clamps_at_the_edge():
    for hdr in (False, True):
        level0 = cm.gradient_pattern(16, hdr)[0]
        dirs, expected = cm.gradient_samples(16, hdr)
        assert np.allclose(cm.bilinear_clamp(level0, dirs)[:, :2], expected)
        step = cm.gradient_step(hdr)
        edge = cm.bilinear_clamp(level0, cm.face_st_to_direction(np.arange(6), 0.999, 0.5))
        assert np.allclose(edge[:, 0], 15 * step)  # past the last texel centre: clamped, not extrapolated
    xs = np.unique(np.round((cm.gradient_samples(16, True)[1][:, 0] / 0.25) % 1.0, 6))
    assert set(xs) == {0.0, 0.2, 0.4, 0.6, 0.8}  # on and between texel centres, fifths


def test_marker_expected_clamps_the_lod_and_blends_levels():
    def stored(v):
        return v

    levels = 7
    assert np.allclose(cm.marker_expected(-1.0, 2, levels, True, stored), cm.marker_value(0, 2, True))
    assert np.allclose(cm.marker_expected(8.5, 2, levels, True, stored), cm.marker_value(6, 2, True))
    half = cm.marker_expected(2.5, 2, levels, True, stored)
    assert half[0] == pytest.approx((cm.marker_value(2, 2, True)[0] + cm.marker_value(3, 2, True)[0]) / 2)
    assert half[0] - cm.marker_expected(2.0, 2, levels, True, stored)[0] == pytest.approx(cm.marker_step(True) / 2)
    mask = cm.marker_mask(3)
    assert mask.shape == (36, 4) and mask[:6].all() and not mask[6:12, 1].any() and mask[6:12, [0, 2, 3]].all()


def test_masked_comparisons_ignore_exactly_the_masked_channels():
    expected = np.zeros((2, 4))
    measured = expected.copy()
    measured[1, 1] = 5.0
    mask = np.ones((2, 4), dtype=bool)
    assert list(cm.within(measured, expected, 1e-6, 0.0)) == [True, False]
    assert cm.max_error(measured, expected) == 5.0
    mask[1, 1] = False
    assert cm.within(measured, expected, 1e-6, 0.0, mask).all() and cm.max_error(measured, expected, mask) == 0.0


def test_seam_samples_straddle_all_twelve_edges():
    samples = cm.seam_samples()
    per_edge = len(cm.SEAM_POSITIONS)
    assert all(len(v) == 12 * per_edge for v in samples.values())
    fa, sa, ta = cm.direction_to_face_st(samples["a"])
    fb, sb, tb = cm.direction_to_face_st(samples["b"])
    assert np.all(fa != fb)
    assert len({frozenset(p) for p in zip(fa.tolist(), fb.tolist())}) == 12  # every adjacent face pair once
    for s, t in ((sa, ta), (sb, tb)):  # right at an edge of the own face
        near = np.minimum(np.minimum(s, 1 - s), np.minimum(t, 1 - t))
        assert np.all(near <= cm.SEAM_DELTA)
    fi, _, _ = cm.direction_to_face_st(samples["ia"])
    assert np.array_equal(fi, fa)  # the interior pairs stay on face A
    along = np.where(np.minimum(sa, 1 - sa) <= cm.SEAM_DELTA, ta, sa)  # the coordinate parallel to the edge
    for n in cm.level_sizes(64):  # off the texel boundaries of every level
        assert np.all(np.abs(along * n - np.round(along * n)) > 1e-3)


def test_seam_step_grows_as_the_levels_shrink():
    samples = cm.seam_samples()
    steps = [cm.seam_step(level, samples) for level in cm.smooth_pattern(64)]
    assert all(0 < a < b for a, b in zip(steps, steps[1:]))
    # the smooth content itself is continuous: sampled exactly at the edge from both sides it agrees
    d = cm.seam_samples(delta=0.0)
    assert cm.max_jump(cm.smooth_value(d["a"]), cm.smooth_value(d["b"])) < 1e-12


def _rows(step, off, on, interior=1e-5):
    return [cm.SeamRow(k, 64 >> k, step * 2 ** k, off * 2 ** k, on, interior) for k in range(7)]


def test_seam_verdict_reads_the_four_cases():
    status, text = cm.seam_verdict(_rows(0.01, 0.01, 1e-4), 0.0)
    assert status == cm.PASS and "switch works" in text
    status, text = cm.seam_verdict(_rows(0.01, 1e-4, 1e-4), 0.0)
    assert status == cm.PASS and "regardless" in text
    ignored = [cm.SeamRow(r.level, r.size, r.step, r.jump_off, r.jump_off, r.interior) for r in _rows(0.01, 0.01, 0)]
    status, text = cm.seam_verdict(ignored, 0.0)
    assert status == cm.FAIL and "no effect" in text
    status, text = cm.seam_verdict(_rows(0.01, 0.01, 0.004), 0.0)
    assert status == cm.FAIL and "seams with the switch on" in text
    # an 8-bit store's step is tolerated, not a seam
    assert cm.seam_verdict(_rows(0.05, 0.05, 2.5 / 255), 1 / 255)[0] == cm.PASS


def test_timing_helpers():
    assert cm.percentile([3.0, 1.0, 2.0], 0.5) == 2.0
    assert cm.timing_summary([1.0, 2.0, 3.0, 4.0]) == (2.5, pytest.approx(3.85), 1.0, 4.0)
    assert not cm.timing_unstable({"a": [1.0, 1.1], "b": [2.0, 2.2]})
    assert cm.timing_unstable({"a": [1.0, 1.1], "b": [2.0, 4.0]})
    assert not cm.timing_unstable({"a": [0.1, 0.2], "b": [0.3, 3.0]})  # too small to mean anything
    assert not cm.timing_unstable({"a": []})


def test_software_renderers_are_recognised():
    assert cm.software_renderer("llvmpipe (LLVM 20.1.2, 256 bits)")
    assert cm.software_renderer("Microsoft Basic Render Driver")
    assert cm.software_renderer("GDI Generic")
    assert not cm.software_renderer("GeForce 9800 GTX/9800 GTX+/PCIe/SSE2")
    assert not cm.software_renderer("AMD Radeon RX 7800 XT")


def test_state_diff_names_only_changes():
    assert cm.state_diff({"a": (1,), "b": True}, {"a": (1,), "b": True}) == []
    assert cm.state_diff({"a": (1,), "b": True}, {"a": (2,), "b": True}) == ["a: (1,) -> (2,)"]


def test_equirect_directions_are_unit_and_oriented():
    d = cm.equirect_directions(8, 4)
    assert d.shape == (4, 8, 3) and np.allclose(np.linalg.norm(d, axis=-1), 1.0)
    assert d[0, :, 1].min() > 0.5 and d[-1, :, 1].max() < -0.5  # top row looks up
    assert d[1:3, 3:5, 2].min() > 0.8  # the four centre pixels (22.5 deg off-axis) look down +Z
    assert d[1:3, [0, 7], 2].max() < -0.8  # the left / right borders look down -Z


def test_png_writer_round_trips(tmp_path):
    rgb = np.zeros((2, 3, 3))
    rgb[0, 0] = (1.0, 0.0, 0.0)
    rgb[1, 2] = (0.0, 0.5, 1.0)
    path = tmp_path / "x.png"
    cm.write_png(path, rgb)
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", data[16:24])
    assert (width, height) == (3, 2)
    idat = data.index(b"IDAT")
    length = struct.unpack(">I", data[idat - 4:idat])[0]
    raw = zlib.decompress(data[idat + 4: idat + 4 + length])
    rows = [raw[k * (1 + 9) + 1:(k + 1) * (1 + 9)] for k in range(2)]
    assert rows[0][:3] == bytes((255, 0, 0)) and rows[1][6:9] == bytes((0, 128, 255))


def test_source_state_names_the_commit_and_the_src_tree():
    from lookdev_gpu_probe.probe_gl_caps import REPO_ROOT

    text = cm.source_state(REPO_ROOT)
    assert text == "commit unknown (no git)" or re.match(r"commit [0-9a-f]{10}, src/ tree [0-9a-f]{10}", text)


def test_coverage_reads_the_header_of_the_shading_probe():
    header = "[gollum_87k] 87500 V / 87500 F, 1920x1080, Smooth, 222591 px covered, 40 rounds after 5"
    assert cm.coverage(header) == (1920, 1080, 222591)
    assert cm.coverage("something else") is None
