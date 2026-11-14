"""Every shading function of `shaders.LIB_SRC` against its NumPy twin on the GPU (needs pyglet and a display;
`xvfb-run -a` in a container, skipped without them by the repo-root conftest)."""

from __future__ import annotations

import pytest

from lookdev_gpu_probe import probe_gl_caps as pg
from lookdev_eye_lab import gl_lab, parity


@pytest.fixture(scope="module")
def parity_pass():
    import pyglet
    from pyglet import gl

    window = pyglet.window.Window(width=32, height=32, visible=False)
    window.switch_to()
    res = pg.Resources(gl)
    pp = gl_lab.ParityPass(gl, res)
    yield pp
    pp.release()
    res.release_all()
    assert res.leaks() == []
    window.close()


@pytest.mark.parametrize("case", parity.cases(), ids=lambda c: c.func)
def test_shader_matches_the_python_reference(parity_pass, case):
    measured = parity_pass.run(case.func, case.inputs)
    assert pg.drain_errors(parity_pass.gl) == []
    err, ratio, bad = case.errors(measured)
    assert bad == 0, f"{case.func}: max abs error {err:.3g}, {ratio:.2f} x tolerance"
