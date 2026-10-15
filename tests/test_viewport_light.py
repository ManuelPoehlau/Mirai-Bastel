"""`Viewport` hands the worklight to every drawable store per frame (headless)."""

from __future__ import annotations

import tests._bootstrap  # noqa: F401

from mirai.scene_factory import create_cube
from mirai.viewport.camera import OrbitCamera
from viewport import Viewport
from viewport.light_rig import PRESET_SOFTBOX, PRESETS, resolve
from viewport.resource_store import TraceStore


class LightRecordingStore(TraceStore):
    def __init__(self, stats) -> None:
        super().__init__(stats)
        self.light = None

    def set_light_uniforms(self, uniforms: dict) -> None:
        self.light = dict(uniforms)


def test_render_gives_the_resolved_light_to_edit_mesh_and_object_entries():
    vp = Viewport(create_cube(), store_type=LightRecordingStore)
    camera = OrbitCamera()
    vp.bind_camera(camera)
    vp.set_object_entry("other", create_cube(size=0.5))
    vp.set_light(PRESETS[PRESET_SOFTBOX])
    vp.sync()
    vp.render()
    expected = resolve(PRESETS[PRESET_SOFTBOX], camera)
    assert vp.render_mesh.store.light == expected
    assert vp.object_entries["other"].store.light == expected


def test_light_change_uploads_nothing():
    vp = Viewport(create_cube(), store_type=LightRecordingStore)
    vp.bind_camera(OrbitCamera())
    vp.sync()
    vp.render()
    counters = dict(vp.benchmark_counters)
    ids = vp.resource_ids()
    for name in PRESETS:
        vp.set_light(PRESETS[name])
        vp.sync()
        vp.render()
    assert dict(vp.benchmark_counters) == counters
    assert vp.resource_ids() == ids
