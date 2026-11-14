"""The lab in a real GL context: the probe's own checks in a small run, and T-A drawn exactly as production draws
(needs pyglet and a display; `xvfb-run -a` in a container)."""

from __future__ import annotations

import numpy as np

from lookdev_gpu_probe import probe_gl_caps as pg
from lookdev_eye_lab import gl_lab, lab_scene, lab_state as ls, probe_eye
from lookdev_eye_lab._paths import CACHE_DIR


def test_a_small_probe_run_passes_every_check_and_cleans_up(tmp_path):
    lines = probe_eye.run(probe_eye.quick_args(str(tmp_path)))
    text = "\n".join(lines)
    summary = lines[lines.index("Summary (raw verdicts - label them by machine in the results file):") + 1:]
    assert summary and all(line.split()[0] == "PASS" for line in summary), text
    for check in ("S seams", "Q5 sRGB", "P parity", "V every variant", "W roughness sweep", "R hygiene"):
        assert any(check in line for line in summary), check
    assert (tmp_path / "sheet_front.png").exists() and len(list(tmp_path.glob("eye_front_*.png"))) == 11


def test_t_a_is_the_production_draw_pixel_for_pixel(tmp_path):
    import pyglet
    from pyglet import gl

    window = pyglet.window.Window(width=32, height=32, visible=False)
    window.switch_to()
    state = ls.LabState(technique="T-A", cornea="C2", view="three_quarter")
    scene = lab_scene.build_scene(state, tmp_path, CACHE_DIR, 320, 240)
    target = gl_lab.Target(gl, scene.renderer.res, 320, 240)
    try:
        images = []
        for lab in (scene.renderer, None):  # None: the stores fall back to GLRenderStore.draw for every part
            for store in [scene.viewport.render_mesh.store] + [e.store for e in scene.viewport.object_entries.values()]:
                store.lab = lab
            target.bind()
            scene.renderer.frame(scene.viewport, 320, 240)
            target.unbind()
            images.append(target.read_rgb())
        assert pg.drain_errors(gl) == []
        assert np.array_equal(images[0], images[1])
        assert np.any(images[0] != images[0][0, 0])  # something was drawn
    finally:
        target.release()
        scene.release()
        window.close()
