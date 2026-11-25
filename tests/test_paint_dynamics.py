"""AD-037 Phase 4b: jitter, scatter, the orientation modes, the spray emitter and the counter-based randomness (§13).

Pinned first (before the rebuild): a brush without jitter, scatter or spray paints **bit for bit** what 4a painted - the
round tip (itself bit-identical to the Phase 2 dab, `tests/test_paint_alpha.py`) and the alpha tip against a frozen copy
of 4a's `stamp` module (`tests/paint_stamp_4a_frozen.py`), through the stroke queue on the Gollum head's cage and SubD 1,
mirror on and off, planar and wrapped placements.
"""

from __future__ import annotations

import numpy as np
import pytest

import tests._bootstrap  # noqa: F401

from mirai.mesh_geometry import mesh_center_and_radius
from mirai.paint import brush, dynamics
from mirai.paint.surface import PaintSurface
from tests import paint_alpha_regions as regions
from tests import paint_stamp_4a_frozen as frozen
from tests.test_paint_alpha import SIZE, _store_and_obj
from tests.test_paint_texel_map import _head, _subd_mesh


@pytest.fixture(scope="module")
def head():
    return _head()


@pytest.fixture(scope="module")
def surfaces(head):
    return {"cage": PaintSurface(head, SIZE, SIZE, "cage"), "subd1": PaintSurface(_subd_mesh(head, 1), SIZE, SIZE, "subd1")}


#: front-view pixels of a stroke across cheek - nose - cheek, and one over the lips (wrapped placements at 5 %)
STROKES = (((330.0, 470.0), (570.0, 470.0)), ((430.0, 500.0), (430.0, 600.0)), ((380.0, 480.0), (450.0, 450.0)))
VIEW_UP = np.array([0.0, 1.0, 0.0])


def _rays(camera, stroke, events: int = 24):
    (x0, y0), (x1, y1) = stroke
    return [regions.ray(camera, (x0 + (x1 - x0) * k / (events - 1), y0 + (y1 - y0) * k / (events - 1)))
            for k in range(events)]


def _paint(surface, settings, radius, definition, rays, evaluate, budget=None):
    """One stroke through the room's queue (`StrokeQueue`, 6 samples per event); `evaluate(stroke, placement)` paints
    a placement. Returns (pixels, cover, placements)."""
    store, obj = _store_and_obj(surface.mesh)
    rgba = np.zeros((SIZE, SIZE, 4), np.uint8)
    rgba[..., :3] = 90
    rgba[..., 3] = 200
    store.set_pixels(obj, "Ebene 1", rgba)
    stroke = brush.PaintStroke(store.begin_stroke(obj, "Ebene 1"), settings)
    spacing = settings.dynamics.spacing * 2.0 * radius
    queue = dynamics.StrokeQueue(surface.hit, spacing, 4.0 * radius, not settings.tip.round,
                                 lambda p: evaluate(stroke, p), radius=radius)
    for i, ray in enumerate(rays):
        queue.add_ray(*ray, samples=1 if i == 0 else 6)
        if budget is not None:
            queue.run(budget)
    queue.end_input()
    while not queue.done:
        queue.run(budget)
    return store.pixels(obj, "Ebene 1").copy(), stroke.cover.copy(), queue.emitted


def _frozen_4a(surface, radius, settings, definition):
    def evaluate(stroke, placement):
        texels, coverage, unique = frozen.evaluate(surface, placement, radius, settings, definition, view_up=VIEW_UP)
        stroke.dab(texels, coverage, unique=unique)
    return evaluate


def _production(surface, radius, settings, definition, seed: int = 0):
    """What `PaintRoomController._evaluate` does with a placement."""
    from mirai.paint import stamp

    def evaluate(stroke, placement):
        texels, coverage, unique = stamp.evaluate(surface, placement, radius, settings, definition, view_up=VIEW_UP)
        stroke.dab(texels, coverage, unique=unique)
    return evaluate


BRUSHES = {
    "poren 3 %": brush.BrushSettings(opacity=0.7, flow=0.6).with_tip(brush.TipSettings("test/poren")),
    "poren 5 %": brush.BrushSettings(opacity=0.7, flow=0.6, radius_step=brush.RADIUS_STEPS_PERCENT.index(5.0)).with_tip(
        brush.TipSettings("test/poren")),
    "ader 5 %, 30°, Kreismaske": brush.BrushSettings(
        flow=0.8, hardness=0.2, curve="sphere", radius_step=brush.RADIUS_STEPS_PERCENT.index(5.0)).with_tip(
        brush.TipSettings("test/ader", kreismaske=True)).with_(dynamics=dynamics.StrokeDynamics(0.5, "stroke", 30.0)),
    "round 3 %, erase": brush.BrushSettings(tool=brush.TOOL_ERASE, flow=0.5, hardness=0.3),
}


@pytest.mark.parametrize("kind", ["cage", "subd1"])
@pytest.mark.parametrize("mirrored", [False, True])
@pytest.mark.parametrize("name", list(BRUSHES))
def test_without_jitter_scatter_or_spray_every_tip_paints_bit_for_bit_what_4a_painted(head, surfaces, kind, mirrored,
                                                                                         name):
    surface = surfaces[kind]
    settings = BRUSHES[name]
    radius = settings.radius_percent / 100.0 * mesh_center_and_radius(head)[1]
    definition = head.symmetry_definition if mirrored else None
    camera = regions.front_camera(head)
    wrapped = count = 0
    for stroke in STROKES:
        rays = _rays(camera, stroke)
        reference, reference_cover, placements = _paint(surface, settings, radius, definition, rays,
                                                        _frozen_4a(surface, radius, settings, definition))
        pixels, cover, _ = _paint(surface, settings, radius, definition, rays,
                                  _production(surface, radius, settings, definition))
        count += len(placements)
        assert np.array_equal(reference, pixels)
        assert np.array_equal(reference_cover, cover)
        if not settings.tip.round and settings.radius_percent >= 5.0:
            stamps = []
            for p in placements:
                frozen.evaluate(surface, p, radius, settings, None, view_up=VIEW_UP, stamps=stamps)
            wrapped += sum(s.projection == frozen.WRAP for s in stamps)
    assert count >= 8
    if not settings.tip.round and settings.radius_percent >= 5.0:
        assert wrapped > 0  # the wrap projection is part of what is pinned
