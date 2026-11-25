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


def _paint(surface, settings, radius, definition, rays, evaluate, budget=None, samples: int = 6):
    """One stroke through the room's queue (`StrokeQueue`, 6 samples per event); `evaluate(stroke, placement)` paints
    a placement. Returns (pixels, cover, placements)."""
    store, obj = _store_and_obj(surface.mesh)
    rgba = np.zeros((SIZE, SIZE, 4), np.uint8)
    rgba[..., :3] = 90
    rgba[..., 3] = 200
    store.set_pixels(obj, "Ebene 1", rgba)
    stroke = brush.PaintStroke(store.begin_stroke(obj, "Ebene 1"), settings)
    spacing = settings.dynamics.spacing * 2.0 * radius
    directed = not settings.tip.round or settings.dynamics.scattered  # (the room's rule)
    queue = dynamics.StrokeQueue(surface.hit, spacing, 4.0 * radius, directed, lambda p: evaluate(stroke, p),
                                 radius=radius)
    for i, ray in enumerate(rays):
        queue.add_ray(*ray, samples=1 if i == 0 else samples)
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
        stamp.paint(stroke, surface, placement, radius, settings, definition, view_up=VIEW_UP, seed=seed)
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


# -- the counter-based randomness (proposal §5.7) ----------------------------------------------------------------------

JITTERY = dynamics.StrokeDynamics(jitter_rotation=40.0, jitter_size=0.5, jitter_flow=0.3, scatter_across=2.0,
                                  scatter_along=2.0, emitter="spray", spray_density=64, spray_size=0.3)


def test_random_values_are_a_pure_function_of_seed_placement_and_stamp():
    rv = dynamics.random_values
    a = rv(17, 5, range(65))
    assert a.shape == (65, dynamics.VALUES) and a.min() >= 0.0 and a.max() < 1.0
    assert np.array_equal(a, rv(17, 5, range(65)))
    # a stamp's values do not depend on which other stamps are drawn (the density) nor in which order
    assert np.array_equal(rv(17, 5, [9])[0], a[9]) and np.array_equal(rv(17, 5, [64, 3])[1], a[3])
    assert not np.array_equal(rv(18, 5, range(65)), a) and not np.array_equal(rv(17, 6, range(65)), a)
    many = np.concatenate([rv(seed, i, range(65)) for seed in range(20) for i in range(20)])
    assert abs(many.mean() - 0.5) < 0.01 and abs(np.corrcoef(many[:, 0], many[:, 1])[0, 1]) < 0.02


def test_jitter_scatter_and_spray_values_stay_inside_their_bounds_over_many_seeds():
    extremes = {"angle": 0.0, "size": [9.0, 0.0], "flow": [9.0, 0.0], "offset": 0.0, "rho": 0.0}
    for orientation in ("stroke", "random"):
        dyn = JITTERY.with_(orientation=orientation)
        for seed in range(150):
            for index in (0, 7, 123456):
                values = dynamics.random_values(seed, index, [*range(64), dynamics.PLACEMENT_ROW])
                angle, size, flow = dynamics.stamp_jitter(dyn, values[:64])
                if orientation == "stroke":
                    assert np.all(np.abs(angle) <= 40.0)
                    extremes["angle"] = max(extremes["angle"], float(np.abs(angle).max()))
                else:
                    assert np.all((angle >= -40.0) & (angle < 400.0))
                assert np.all((size >= 0.5) & (size <= 1.5)) and np.all((flow >= 0.7) & (flow <= 1.3))
                extremes["size"] = [min(extremes["size"][0], size.min()), max(extremes["size"][1], size.max())]
                extremes["flow"] = [min(extremes["flow"][0], flow.min()), max(extremes["flow"][1], flow.max())]
                along, across = dynamics.scatter_offset(dyn, values[64])
                assert abs(along) <= 2.0 and abs(across) <= 2.0 and np.hypot(along, across) <= 2.0 + 1e-12
                extremes["offset"] = max(extremes["offset"], float(np.hypot(along, across)))
                rho = np.hypot(*dynamics.spray_positions(dyn, values[:64]).T)
                assert np.all(rho <= 0.7 + 1e-12)
                extremes["rho"] = max(extremes["rho"], float(rho.max()))
    # ... and fill them (not a degenerate generator)
    assert extremes["angle"] > 39.5 and extremes["size"][0] < 0.51 and extremes["size"][1] > 1.49
    assert extremes["flow"][0] < 0.71 and extremes["flow"][1] > 1.29
    assert extremes["offset"] > 1.99 and extremes["rho"] > 0.69


def test_scatter_beyond_2_r_is_capped():
    assert dynamics.StrokeDynamics().with_(scatter_across=5.0, scatter_along=-1.0).scatter_across == 2.0
    assert dynamics.StrokeDynamics().with_(scatter_along=-1.0).scatter_along == 0.0
    with pytest.raises(ValueError):
        dynamics.StrokeDynamics(scatter_across=2.5)
    with pytest.raises(ValueError):
        dynamics.StrokeDynamics(spray_density=65)
    assert dynamics.StrokeDynamics().with_(spray_density=500).spray_density == dynamics.SPRAY_MAX
    # painted: a round tip scattered 2 r across and along stays within 2 r (+ its own radius) of its placement
    from tests.test_paint_alpha import _plane

    surface = PaintSurface(_plane(), SIZE, SIZE)
    settings = brush.BrushSettings(hardness=0.0).with_(dynamics=dynamics.StrokeDynamics(
        0.5, scatter_across=2.0, scatter_along=2.0))
    radius = 0.25
    pixels, cover, placements = _paint(surface, settings, radius, None, [_down(1.5, 3.0), _down(4.5, 3.0)],
                                       _production(surface, radius, settings, None, seed=3))
    painted = np.flatnonzero(cover > 0)
    points = surface.map.surface_points(painted)
    centres = np.array([p.point for p in placements])
    nearest = np.min(np.linalg.norm(points[:, None, :] - centres[None, :, :], axis=2), axis=1)
    assert nearest.max() <= 3.0 * radius + 6.0 / SIZE * 1.5
    assert nearest.max() > 1.5 * radius  # scattered at all


def _down(x, y):
    return np.array([x, y, 5.0]), np.array([0.0, 0.0, -1.0])


# -- determinism (proposal §5.7): budgets, seeds ---------------------------------------------------------------------

SPRAY_PORES = brush.BrushSettings(opacity=0.8, flow=0.7).with_tip(brush.TipSettings("test/poren")).with_(
    dynamics=dynamics.StrokeDynamics(0.5, jitter_rotation=180.0, jitter_size=0.4, jitter_flow=0.5, scatter_across=0.6,
                                     scatter_along=0.4, emitter="spray", spray_density=20, spray_size=0.25))
SINGLE_VEIN = brush.BrushSettings(flow=0.9).with_tip(brush.TipSettings("test/ader")).with_(
    dynamics=dynamics.StrokeDynamics(1.0, jitter_rotation=60.0, jitter_size=0.3, jitter_flow=0.4, scatter_across=1.0))
SPRAY_ROUND = brush.BrushSettings(flow=0.8, hardness=0.4).with_(
    dynamics=dynamics.StrokeDynamics(0.5, jitter_size=0.3, emitter="spray", spray_density=16, spray_size=0.2))


@pytest.mark.parametrize("name, settings", [("spray pores", SPRAY_PORES), ("single vein", SINGLE_VEIN),
                                            ("spray round", SPRAY_ROUND)])
def test_the_same_rays_and_seed_give_identical_pixels_whatever_the_budget(head, surfaces, name, settings):
    surface = surfaces["cage"]
    radius = 0.03 * mesh_center_and_radius(head)[1]
    definition = head.symmetry_definition
    rays = _rays(regions.front_camera(head), STROKES[0])
    runs = [_paint(surface, settings, radius, definition, rays, _production(surface, radius, settings, definition, 1234),
                   budget=budget) for budget in (0.001, 0.010, None)]
    assert runs[0][1].max() > 0.0
    for pixels, cover, _ in runs[1:]:
        assert np.array_equal(pixels, runs[0][0]) and np.array_equal(cover, runs[0][1])
    other = _paint(surface, settings, radius, definition, rays, _production(surface, radius, settings, definition, 1235))
    assert not np.array_equal(other[1], runs[0][1])  # another seed, another pattern


# -- the mirror reuses the same random values (proposal §5.7) ----------------------------------------------------------


def test_the_mirror_cluster_uses_the_same_random_values_reflected(head, surfaces):
    from mirai.paint import stamp
    from mirai.paint.surface import mirror

    surface = surfaces["subd1"]
    radius = 0.03 * mesh_center_and_radius(head)[1]
    definition = head.symmetry_definition
    camera = regions.front_camera(head)
    for settings in (SPRAY_PORES, SINGLE_VEIN):
        hit = regions.region_hit(surface, camera, "cheek")
        for index in range(4):
            records = []
            placement = dynamics.Placement(index, hit.point, hit.normal, np.array([1.0, 0.0, 0.0]))
            stamp.cluster(surface, placement, radius, settings, definition, view_up=VIEW_UP, seed=99, stamps=records)
            main = [r for r in records if not r.mirrored]
            other = [r for r in records if r.mirrored]
            assert len(main) == len(other) == (20 if settings.dynamics.spray else 1)
            for m, o in zip(main, other):
                assert np.allclose(o.centre, mirror(definition, m.centre, (0, 0, 1))[0], atol=1e-9)
                assert np.allclose(o.t, stamp.reflect(definition, m.t), atol=1e-9)
                assert o.radius == m.radius and o.flow == m.flow


def _symmetric_plane():
    from core import SymmetryDefinition
    from tests.test_paint_alpha import _plane

    return PaintSurface(_plane(), SIZE, SIZE), SymmetryDefinition((3.0, 0.0, 0.0), (1.0, 0.0, 0.0))


@pytest.mark.parametrize("settings", [SPRAY_PORES, SINGLE_VEIN], ids=["spray pores", "single vein"])
def test_a_randomised_stroke_with_the_mirror_is_symmetric(settings):
    surface, definition = _symmetric_plane()
    radius = 0.3
    rays = [_down(0.8 + 0.1 * k, 2.0 + 0.08 * k * k) for k in range(12)]
    _, cover, placements = _paint(surface, settings, radius, definition, rays,
                                  _production(surface, radius, settings, definition, seed=5), samples=4)
    image = cover.reshape(SIZE, SIZE)
    assert image.max() > 0.1 and image[:, :SIZE // 2].sum() > 0.0
    assert np.abs(image - image[:, ::-1]).max() < 0.02  # left half == right half mirrored (float32, bilinear)


# -- spray (proposal §5.5) -------------------------------------------------------------------------------------------


def test_spray_density_per_area_does_not_depend_on_the_stroke_speed(head, surfaces):
    surface = surfaces["cage"]
    radius = 0.03 * mesh_center_and_radius(head)[1]
    camera = regions.front_camera(head)
    (x0, y0), (x1, y1) = STROKES[0]
    results = []
    for events in (80, 8):  # the same 240 px in 1.3 s or in 0.13 s at 60 events/s
        rays = _rays(camera, STROKES[0], events)
        step = 3.0
        samples = max(1, int(np.ceil(np.hypot(x1 - x0, y1 - y0) / (events - 1) / step)))
        records = []
        from mirai.paint import stamp

        def evaluate(stroke, placement, records=records):
            stamp.paint(stroke, surface, placement, radius, SPRAY_ROUND, None, view_up=VIEW_UP, seed=8, stamps=records)
        _, cover, placements = _paint(surface, SPRAY_ROUND, radius, None, rays, evaluate, samples=samples)
        length = sum(float(np.linalg.norm(b.point - a.point)) for a, b in zip(placements, placements[1:]))
        results.append((len(records) / length, np.count_nonzero(cover), float(cover.sum()), len(placements)))
    (slow, area_s, sum_s, n_s), (fast, area_f, sum_f, n_f) = results
    assert abs(n_s - n_f) <= 1 and abs(slow - fast) / slow < 0.05
    assert abs(area_s - area_f) / area_s < 0.05 and abs(sum_s - sum_f) / sum_s < 0.05


def test_a_spray_cluster_combined_in_one_write_equals_its_stamps_applied_one_by_one():
    from mirai.paint import stamp
    from tests.test_paint_alpha import _store_and_obj as store_and_obj

    surface, _ = _symmetric_plane()
    settings = SPRAY_PORES
    dyn = settings.dynamics
    image = __import__("mirai.paint.alpha", fromlist=["resolve"]).resolve("test/poren")
    values = dynamics.random_values(3, 0, range(dyn.spray_density))
    positions = dynamics.spray_positions(dyn, values)
    angles, sizes, flows = dynamics.stamp_jitter(dyn, values)
    scales = dyn.spray_size * sizes
    flows = np.minimum(settings.flow * flows, 1.0)
    frame = stamp.Frame(np.array([3.0, 3.0, 0.0]), np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0]),
                        np.array([0.0, 0.0, 1.0]))
    args = (surface, frame.centre, frame.n, 0.8, 1.5, settings, image)
    texels, product, _ = stamp._spray_cluster(*args, positions, scales, image.reach, angles, flows, frame=frame)
    assert texels.size > 100
    covers = []
    for one_by_one in (False, True):
        store, obj = store_and_obj(surface.mesh)
        stroke = brush.PaintStroke(store.begin_stroke(obj, "Ebene 1"), settings)
        if not one_by_one:
            stroke.dab_product(texels, product)
        else:
            for k in range(len(positions)):
                part = stamp._spray_cluster(*args, positions[k:k + 1], scales[k:k + 1], image.reach, angles[k:k + 1],
                                            flows[k:k + 1], frame=frame)
                stroke.dab_product(part[0], part[1])
        covers.append((stroke.cover.copy(), store.pixels(obj, "Ebene 1").astype(int)))
    assert np.allclose(covers[0][0], covers[1][0], atol=1e-5)
    assert np.abs(covers[0][1] - covers[1][1]).max() <= 1


# -- the orientation modes (proposal §5.3) -----------------------------------------------------------------------------


def test_the_orientation_modes_view_surface_and_random():
    from core import Mesh
    from mirai.paint import alpha, stamp

    surface, _ = _symmetric_plane()
    vein = alpha.generated_alpha("test/ader")
    placement = dynamics.Placement(0, np.array([3.0, 3.0, 0.0]), np.array([0.0, 0.0, 1.0]), np.array([1.0, 0.0, 0.0]))

    def frame_t(orientation, angle=0.0, on=surface, seed=0, index=0):
        settings = brush.BrushSettings().with_tip(brush.TipSettings("test/ader")).with_(
            dynamics=dynamics.StrokeDynamics(1.0, orientation, angle))
        records = []
        p = dynamics.Placement(index, placement.point, placement.normal, placement.tangent)
        if settings.dynamics.random:
            stamp.cluster(on, p, 0.8, settings, view_up=(0.0, 1.0, 0.0), image=vein, seed=seed, stamps=records)
            return records[0].t
        stamp.evaluate(on, p, 0.8, settings, view_up=(0.0, 1.0, 0.0), image=vein, stamps=records)
        return records[0].frame.t

    assert np.allclose(frame_t("stroke"), (1, 0, 0))
    assert np.allclose(frame_t("view"), (0, 1, 0))
    assert np.allclose(frame_t("view", 90.0), (-1, 0, 0))  # the offset applies to every mode
    assert np.allclose(frame_t("surface"), (1, 0, 0), atol=1e-6)  # UV u runs along x
    turned = Mesh()  # the same plane with u running along y
    n = 6
    vid = {(x, y): turned.add_vertex((float(x), float(y), 0.0)) for y in range(n + 1) for x in range(n + 1)}
    for y in range(n):
        for x in range(n):
            corners = [(x, y), (x + 1, y), (x + 1, y + 1), (x, y + 1)]
            turned.add_face([vid[c] for c in corners], uvs=[(cy / n, 1.0 - cx / n) for cx, cy in corners])
    assert np.allclose(frame_t("surface", on=PaintSurface(turned, 256, 256)), (0, 1, 0), atol=1e-6)
    randoms = [frame_t("random", index=i) for i in range(12)]
    assert np.allclose(randoms[3], frame_t("random", index=3))  # deterministic per (seed, placement)
    angles = np.degrees(np.arctan2([t[1] for t in randoms], [t[0] for t in randoms]))
    assert np.ptp(angles) > 180.0 and len(set(np.round(angles, 3))) == 12


# -- the room: seed, one Undo step, Esc, a click is one burst ----------------------------------------------------------


@pytest.fixture()
def room():
    from tests.test_paint_room import _app

    app = _app()
    app.open_paint_room()
    app.set_paint_brush(dynamics=SPRAY_ROUND.dynamics.with_(spacing=0.25, scatter_across=0.5, jitter_flow=0.3))
    return app


def test_a_randomised_stroke_is_one_undo_step_with_its_seed_and_undo_redo_never_draw_again(room, monkeypatch):
    from mirai.controllers import paint_room
    from tests.test_paint_room import _stroke

    app = room
    obj = app.scene.edit_object
    assert "Spray 16" in app.status_message and "Streuung" in app.status_message
    monkeypatch.setattr(paint_room, "new_seed", lambda: 4242)
    _stroke(app)  # the first stroke makes the paint
    before = app.paint.pixels(obj, "Ebene 1").copy()
    history = len(app.history)
    _stroke(app, steps=10, dx=5.0)
    assert len(app.history) == history + 1
    command = app.history._undo_stack[-1]
    assert command.seed == 4242 == app._paint_room.last_seed
    after = app.paint.pixels(obj, "Ebene 1").copy()
    assert not np.array_equal(after, before)
    calls = []
    monkeypatch.setattr(dynamics, "random_values", lambda *a: calls.append(a))  # Undo / Redo must not draw
    app.dispatch_command(__import__("mirai.interaction.commands", fromlist=["UNDO"]).UNDO)
    assert np.array_equal(app.paint.pixels(obj, "Ebene 1"), before)
    app.dispatch_command(__import__("mirai.interaction.commands", fromlist=["REDO"]).REDO)
    assert np.array_equal(app.paint.pixels(obj, "Ebene 1"), after) and calls == []


def test_the_same_seed_and_input_paint_the_same_stroke_in_the_room(room, monkeypatch):
    from mirai.controllers import paint_room
    from mirai.interaction import commands
    from tests.test_paint_room import _stroke

    app = room
    obj = app.scene.edit_object
    _stroke(app)
    base = app.paint.pixels(obj, "Ebene 1").copy()
    results = []
    for seed in (7, 7, 8):
        monkeypatch.setattr(paint_room, "new_seed", lambda seed=seed: seed)
        _stroke(app, steps=10, dx=5.0, display=seed != 7 or not results)  # with and without the display's update
        results.append(app.paint.pixels(obj, "Ebene 1").copy())
        app.dispatch_command(commands.UNDO)
        assert np.array_equal(app.paint.pixels(obj, "Ebene 1"), base)
    assert np.array_equal(results[0], results[1]) and not np.array_equal(results[0], results[2])


def test_escape_restores_a_randomised_stroke_exactly(room):
    from tests.test_paint_room import ESC, _stroke

    app = room
    obj = app.scene.edit_object
    _stroke(app)
    before = app.paint.pixels(obj, "Ebene 1").copy()
    history = len(app.history)
    _stroke(app, steps=8, release=False)
    assert not np.array_equal(app.paint.pixels(obj, "Ebene 1"), before)
    assert app.key_press(ESC) is True
    assert np.array_equal(app.paint.pixels(obj, "Ebene 1"), before) and len(app.history) == history


def test_a_click_without_movement_is_one_spray_burst_and_holding_still_adds_nothing(room):
    from tests.test_paint_room import LMB, _centre, _finish

    app = room
    x, y = _centre(app)
    app.pointer_motion(x, y)
    app.pointer_press(LMB, x, y)
    for _ in range(30):  # holding still: frames pass, no movement
        app.pointer_drag(0.0, 0.0, x, y)
        app.update_viewport(0.0)
    app.pointer_release("LEFT", x, y)
    _finish(app)
    assert app._paint_room.last_dabs == 1  # one placement: one burst (one write of its cluster)
    cover = app.paint.pixels(app.scene.edit_object, "Ebene 1")[..., 3]
    assert np.count_nonzero(cover) > 0


# -- the panel (headless) ------------------------------------------------------------------------------------------------


def test_the_panel_sections_summaries_and_their_labels():
    from gui import paint_model as pm

    plain = brush.BrushSettings()
    assert [key for key, _, _ in pm.sections(plain)] == ["stroke", "scatter"]  # "Spray" only with the spray emitter
    assert pm.stroke_summary(plain) == "Abstand 12 %, Einzeln" and pm.scatter_summary(plain) == "aus"
    pores = SPRAY_PORES.with_(dynamics=SPRAY_PORES.dynamics.with_(orientation="surface", angle=30.0))
    assert [key for key, _, _ in pm.sections(pores)] == ["stroke", "scatter", "spray"]
    assert pm.stroke_summary(pores) == "Abstand 50 %, Fläche +30°, Spray"
    assert pm.scatter_summary(pores) == "Drehung ±180°, Größe ±40 %, Fluss ±50 %, quer 0,6 r, längs 0,4 r"
    assert pm.spray_summary(pores) == "20 Stempel, Größe 25 %, Intensität 100 %"
    assert pm.section_label("Strich", "Abstand 12 %", False, "stroke") == "Strich   Abstand 12 %###stroke"
    assert pm.section_label("Strich", "Abstand 12 %", True, "stroke") == "Strich###stroke"
    # switching to spray takes the spray spacing; back to single keeps it
    spray = plain.dynamics.with_(emitter="spray")
    assert spray.spacing == dynamics.SPRAY_SPACING and spray.with_(emitter="single").spacing == dynamics.SPRAY_SPACING


class _Imgui:
    """Just enough of `imgui` for `PaintPanel.draw` (every header open, every combo open, nothing clicked)."""

    class SliderFlags_:
        logarithmic = 32

    def __init__(self):
        self.labels = []

    def __getattr__(self, name):
        def call(*args, **kwargs):
            if args and isinstance(args[0], str):
                self.labels.append(args[0])
            if name in ("slider_float", "slider_int", "checkbox", "color_edit3", "input_text"):
                return False, args[1]
            if name == "selectable":
                return False, False
            if name in ("collapsing_header", "begin_combo"):
                return True
            return False
        return call


def test_the_panel_draws_every_section(room):
    from gui.paint_panel import PaintPanel

    app = room
    app.set_paint_tip("test/poren")
    imgui = _Imgui()
    panel = PaintPanel(imgui, app, None)
    panel.draw()
    panel.draw()  # (the second frame: the headers' labels follow their open state)
    labels = imgui.labels
    for label in ("Strich###stroke", "Streuung###scatter", "Spray###spray", "Abstand", "Ausrichtung", "Winkel",
                  "Einzeln", "Spray", "Drehung ±", "Größe ±", "Fluss ±", "Streuung quer", "Streuung längs", "Dichte",
                  "Stempelgröße", "Intensität", "Kreismaske"):
        assert label in labels, label
