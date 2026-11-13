"""The capability probe in a real GL context (2026-11-13). Needs pyglet and a display (`xvfb-run -a` in a container);
skipped without them by the repo-root conftest.

These tests check what must hold on ANY driver: every check runs to a verdict, and the probe leaves no GL object and
no changed GL state behind. Whether a driver passes A-D is a hardware finding and belongs in the probe's output and
the results files, not in a test that would turn red on the reference PC for the wrong reason.
"""

from __future__ import annotations

import ctypes

import pytest

from lookdev_gpu_probe import cube_math as cm
from lookdev_gpu_probe import probe_gl_caps as probe


@pytest.fixture
def context():
    import pyglet

    window = pyglet.window.Window(width=32, height=32, visible=False)
    window.switch_to()
    yield pyglet.gl
    window.close()


def test_a_small_run_reaches_a_verdict_everywhere_and_cleans_up(tmp_path):
    args = probe.build_parser().parse_args([
        "--sizes", "64x48", "--draws", "2", "--alloc-sizes", "16", "--cube-size", "16", "--rough-lod", "2.5",
        "--images", str(tmp_path),
    ])
    lines = probe.run(args)
    text = "\n".join(lines)
    assert "ERROR" not in text, text
    assert "GL state after the probe vs before: identical" in text
    assert "still alive after release: none" in text and "glGetError at the end: none" in text
    summary = lines[lines.index("Summary (raw verdicts of this run - label them by machine in the results file):") + 1:]
    checks = {line.split()[0] for line in summary if line.startswith("  ") and line.split()}
    assert {"A", "B", "C", "D", "T", "R"} <= checks
    assert any(line.startswith("  R     hygiene PASS") for line in summary)
    assert "EVIDENCE:" in text and "Source: commit" in text
    for fmt in cm.FORMATS:
        png = (tmp_path / f"seams_{fmt.label}.png").read_bytes()
        width, height = int.from_bytes(png[16:20], "big"), int.from_bytes(png[20:24], "big")
        assert (width, height) == (2 * probe.PANORAMA[0] + 2, 4 * probe.PANORAMA[1] + 3 * 2)


def test_leak_check_and_state_restore_catch_what_they_should(context):
    gl = context
    res = probe.Resources(gl)
    tex = res.texture()
    gl.glBindTexture(gl.GL_TEXTURE_2D, tex)  # a name only exists for glIsTexture once bound
    gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
    assert any("not deleted" in leak for leak in res.leaks())
    res.release_all()
    assert res.leaks() == []

    before = probe.snapshot(gl)
    with probe.preserved(gl):
        gl.glActiveTexture(gl.GL_TEXTURE0 + probe.CUBE_UNIT)
        gl.glEnable(gl.GL_TEXTURE_CUBE_MAP_SEAMLESS)
        gl.glViewport(0, 0, 3, 3)
        assert cm.state_diff(before, probe.snapshot(gl))  # the snapshot sees the change ...
    assert cm.state_diff(before, probe.snapshot(gl)) == []  # ... and `preserved` undoes it
    assert probe.drain_errors(gl) == []


def test_the_sample_pass_reads_back_what_a_cube_holds(context):
    """One end-to-end readback on the RGBA16F path: the probe's own plumbing, independent of A-D's tolerances."""
    gl = context
    res = probe.Resources(gl)
    try:
        sp = probe.SamplePass(gl, res)
        tex, errors, driver = probe.make_cube(gl, res, cm.RGBA16F, cm.marker_pattern(4, True))
        assert errors == [] and driver.startswith("RGBA16F")
        dirs, faces = cm.marker_directions()
        values, quantum = sp.run(tex, dirs[:6], 1.0)
        expected = [cm.marker_value(1, int(f), True) for f in faces[:6]]
        assert cm.max_error(values, expected) <= 1e-5 + quantum
        value = gl.GLint()
        gl.glGetIntegerv(gl.GL_DRAW_FRAMEBUFFER_BINDING, ctypes.byref(value))
        assert value.value == 0  # the pass unbinds its framebuffer again
    finally:
        res.release_all()
    assert res.leaks() == []
