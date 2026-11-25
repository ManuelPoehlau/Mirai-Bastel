"""AD-037 Phase 4a: the alpha tip, the per-placement projection, world spacing and the stamp queue (§12).

Pinned first (before the rebuild): the round tip through the new pipeline paints **bit for bit** what the Phase 2 dab
painted (`_reference_dab`, a frozen copy of `PaintRoomController._dab` at `922d964`), on the Gollum head's cage and SubD 1,
with and without the mirror.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

import tests._bootstrap  # noqa: F401

from core import ObjectId, PaintLayer, PaintStack, SceneObject
from mirai.mesh_geometry import mesh_center_and_radius
from mirai.paint import brush
from mirai.paint.alpha import AlphaImage
from mirai.paint.store import PaintStore
from mirai.paint.surface import PaintSurface, mirror
from tests.test_paint_texel_map import _head, _subd_mesh

SIZE = 1024


@pytest.fixture(scope="module")
def head():
    return _head()


@pytest.fixture(scope="module")
def surfaces(head):
    return {"cage": PaintSurface(head, SIZE, SIZE, "cage"), "subd1": PaintSurface(_subd_mesh(head, 1), SIZE, SIZE, "subd1")}


def _store_and_obj(mesh):
    obj = SceneObject(ObjectId(1), mesh, name="head")
    obj.paint = PaintStack(SIZE, SIZE, (PaintLayer("Ebene 1", None),))
    return PaintStore(), obj


def _reference_dab(stroke, surface, hit, radius, settings, definition) -> None:
    """`PaintRoomController._dab` as it was at `922d964` (Phase 2), frozen."""
    texels, x = surface.footprint(hit.point, radius, hit.normal)
    parts_t, parts_c = [texels], [brush.falloff(x, settings.hardness, settings.curve)]
    if definition is not None:
        point, normal = mirror(definition, hit.point, hit.normal)
        texels, x = surface.footprint(point, radius, normal)
        parts_t.append(texels)
        parts_c.append(brush.falloff(x, settings.hardness, settings.curve))
    stroke.dab(np.concatenate(parts_t), np.concatenate(parts_c), unique=len(parts_t) == 1)


def _front_hits(surface, mesh, count: int = 14):
    """Hits of rays from the front (+Z, where the face looks) across the face at cheek, nose and lip height."""
    pts = np.array([mesh.vertex_position(v) for v in mesh.all_vertex_ids()])
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    hits = []
    for fy in (0.35, 0.5, 0.62):
        for fx in np.linspace(0.25, 0.75, count // 3 + 1):
            origin = (lo[0] + fx * (hi[0] - lo[0]), lo[1] + fy * (hi[1] - lo[1]), hi[2] + 2.0)
            hit = surface.hit(origin, (0.0, 0.0, -1.0))
            if hit is not None:
                hits.append(hit)
    return hits


@pytest.mark.parametrize("kind", ["cage", "subd1"])
@pytest.mark.parametrize("mirrored", [False, True])
def test_the_round_tip_through_the_new_pipeline_is_bit_identical_to_the_phase_2_dab(head, surfaces, kind, mirrored):
    from mirai.paint import stamp

    surface = surfaces[kind]
    radius = 0.03 * mesh_center_and_radius(head)[1]
    definition = head.symmetry_definition if mirrored else None
    assert not mirrored or definition is not None
    hits = _front_hits(surface, head)
    assert len(hits) >= 10
    for settings in (brush.BrushSettings(opacity=0.6, flow=0.45, hardness=0.3, curve="sphere"),
                     brush.BrushSettings(tool=brush.TOOL_ERASE, flow=0.8, hardness=0.0, curve="linear")):
        layers = []
        for reference in (True, False):
            store, obj = _store_and_obj(surface.mesh)
            rgba = np.zeros((SIZE, SIZE, 4), np.uint8)
            rgba[..., :3] = 90
            rgba[..., 3] = 200
            store.set_pixels(obj, "Ebene 1", rgba)
            stroke = brush.PaintStroke(store.begin_stroke(obj, "Ebene 1"), settings)
            for hit in hits:
                if reference:
                    _reference_dab(stroke, surface, hit, radius, settings, definition)
                else:
                    texels, coverage, unique = stamp.evaluate(surface, stamp.Placement(0, hit.point, hit.normal),
                                                              radius, settings, definition)
                    stroke.dab(texels, coverage, unique=unique)
            layers.append((store.pixels(obj, "Ebene 1").copy(), stroke.cover.copy()))
        assert np.array_equal(layers[0][0], layers[1][0])
        assert np.array_equal(layers[0][1], layers[1][1])


# -- the alpha image -------------------------------------------------------------------------------------------------


def test_the_mip_chain_halves_down_to_four_pixels_and_sampling_is_bilinear():
    from mirai.paint.alpha import AlphaImage

    pixels = np.zeros((40, 100), np.uint8)
    pixels[10:30, 20:80] = 255
    image = AlphaImage.from_pixels("t", "t", pixels)
    assert [m.shape for m in image.mips] == [(40, 100), (20, 50), (10, 25), (5, 13), (3, 7)]  # short side >= 2
    assert image.half_extents == (1.0, 0.4)
    # texel centres read the texel exactly; between two texels the mean; outside the rectangle 0
    u = (np.array([20.5, 19.5, 20.0, 50.0]) / 100.0).astype(np.float32)
    v = (np.array([15.5, 15.5, 15.5, 15.5]) / 40.0).astype(np.float32)
    assert np.allclose(image.sample(0, u, v), [1.0, 0.0, 0.5, 1.0], atol=1e-6)
    assert image.sample(0, np.array([-0.01, 1.01], np.float32), np.array([0.5, 0.5], np.float32)).tolist() == [0, 0]
    assert image.level_for(100.0) == 0 and image.level_for(50.0) == 1 and image.level_for(6.0) == 4
    assert image.level_for(0.5) == len(image.mips) - 1


def test_the_test_alphas_are_deterministic_and_have_a_black_border():
    from mirai.paint import alpha

    assert [alpha.alpha_name(i) for i in alpha.TEST_ALPHAS] == ["Poren", "Ader", "Kratzer", "Fleck", "Punkte", "Quadrat"]
    for alpha_id, (_, make) in alpha.TEST_ALPHAS.items():
        image = alpha.generated_alpha(alpha_id)
        assert np.array_equal(image.pixels, np.clip(np.rint(make() * 255.0), 0, 255).astype(np.uint8))
        p = image.pixels
        assert p.max() >= 200, alpha_id  # a visible shape
        assert max(p[0].max(), p[-1].max(), p[:, 0].max(), p[:, -1].max()) == 0, alpha_id
    assert alpha.resolve(None) is None and alpha.resolve("missing") is None


# -- the stamp on a flat surface --------------------------------------------------------------------------------------


def _plane(n: int = 6):
    """A flat n x n quad grid in z = 0 (1 unit per quad), planar UVs."""
    from core import Mesh

    mesh = Mesh()
    vid = {(x, y): mesh.add_vertex((float(x), float(y), 0.0)) for y in range(n + 1) for x in range(n + 1)}
    for y in range(n):
        for x in range(n):
            corners = [(x, y), (x + 1, y), (x + 1, y + 1), (x, y + 1)]
            mesh.add_face([vid[c] for c in corners], uvs=[(cx / n, cy / n) for cx, cy in corners])
    return mesh


def _principal_axis(surface, stamp_result):
    points = surface.map.surface_points(stamp_result.texels)
    w = stamp_result.coverage.astype(np.float64)
    mean = (points * w[:, None]).sum(axis=0) / w.sum()
    rel = points - mean
    values, vectors = np.linalg.eigh((rel * w[:, None]).T @ rel / w.sum())
    return mean, vectors[:, -1], math.sqrt(values[-1] / max(values[-2], 1e-30))


def test_a_flat_stamp_is_the_alpha_turned_by_the_stroke_direction_and_the_angle():
    from mirai.paint import alpha, stamp

    surface = PaintSurface(_plane(), 512, 512)
    vein = alpha.generated_alpha("test/ader")  # long along its x
    centre, up = np.array([3.0, 3.0, 0.0]), np.array([0.0, 0.0, 1.0])
    along_x = stamp.alpha_stamp(surface, centre, up, 1.5, vein, tangent=(1.0, 0.0, 0.0))
    assert along_x.projection == stamp.PLANAR and along_x.stress == 0.0
    mean, axis, aspect = _principal_axis(surface, along_x)
    assert abs(axis[0]) > 0.95 and aspect > 2.0  # (the vein wanders a little)
    assert np.allclose(along_x.frame.n, up) and np.allclose(along_x.frame.t, (1, 0, 0))
    turned = stamp.alpha_stamp(surface, centre, up, 1.5, vein, tangent=(1.0, 0.0, 0.0), angle=90.0)
    assert abs(_principal_axis(surface, turned)[1][1]) > 0.95
    # the stamp's coverage is the alpha read at the texels' local coordinates
    points = surface.map.surface_points(along_x.texels)
    hw, hh = vein.half_extents
    a, b = (points[:, 0] - 3.0) / 1.5, (points[:, 1] - 3.0) / 1.5
    expected = vein.sample(along_x.level, 0.5 + a / (2 * hw), 0.5 - b / (2 * hh))
    assert np.allclose(along_x.coverage, expected, atol=1e-5)
    # no direction: the view's up; neither: any perpendicular
    view = stamp.alpha_stamp(surface, centre, up, 1.5, vein, view_up=(0.0, 1.0, 0.0))
    assert np.allclose(view.frame.t, (0, 1, 0))


def test_the_mip_level_follows_the_stamps_size_in_texels():
    from mirai.paint import alpha, stamp

    surface = PaintSurface(_plane(), 512, 512)
    pores = alpha.generated_alpha("test/poren")  # 256 px
    small = stamp.alpha_stamp(surface, (3.0, 3.0, 0.0), (0, 0, 1), 0.1, pores, view_up=(0, 1, 0))
    large = stamp.alpha_stamp(surface, (3.0, 3.0, 0.0), (0, 0, 1), 2.0, pores, view_up=(0, 1, 0))
    # 0.1 units = 8.5 texels across a 512² map of 6 units: 256 / 17 ≈ 2^4; 2 units ≈ 341 texels: level 0
    assert small.level == 4 and large.level == 0
    assert abs(small.diameter - 2 * 0.1 * 512 / 6) < 2.0


def test_k_stamps_combine_in_one_write_as_applied_one_by_one():
    from mirai.paint import stamp

    store, obj = _store_and_obj(_plane())
    settings = brush.BrushSettings(flow=0.6)
    rng = np.random.default_rng(4)
    stamps = [(rng.choice(400, 120, replace=False), rng.random(120).astype(np.float32)) for _ in range(5)]
    flows = rng.uniform(0.2, 1.0, 5)
    one_by_one = brush.PaintStroke(store.begin_stroke(obj, "Ebene 1"), settings)
    for (texels, coverage), flow in zip(stamps, flows):
        one_by_one.dab(np.sort(texels), coverage[np.argsort(texels)] * flow / settings.flow, unique=True)
    store2, obj2 = _store_and_obj(_plane())
    combined = brush.PaintStroke(store2.begin_stroke(obj2, "Ebene 1"), settings)
    texels, product = stamp.combine([t for t, _ in stamps], [c for _, c in stamps], flows)
    assert np.array_equal(texels, np.unique(np.concatenate([t for t, _ in stamps])))
    combined.dab_product(texels, product)
    assert np.allclose(one_by_one.cover, combined.cover, atol=1e-6)
    assert np.abs(store.pixels(obj, "Ebene 1").astype(int) - store2.pixels(obj2, "Ebene 1").astype(int)).max() <= 1


# -- the curvature validation (proposal §4.3) on the Gollum head -------------------------------------------------------


@pytest.fixture(scope="module")
def reference(head):
    return PaintSurface(_subd_mesh(head, 2), 512, 512, "subd2")


@pytest.fixture(scope="module")
def surfaces_2048(head):
    return {"cage": PaintSurface(head, 2048, 2048, "cage"), "subd1": PaintSurface(_subd_mesh(head, 1), 2048, 2048, "subd1")}


@pytest.mark.parametrize("kind", ["cage", "subd1"])
def test_the_stamp_is_not_stretched_and_does_not_leak_at_the_probe_placements(head, surfaces_2048, kind):
    """§4.3 at 3 %, at the default 2048²: painted area within ±25 % of the planar ideal, aspect <= 1.3 - or, where the
    surface itself is curved about as tightly as the stamp (the nostril wing), no worse than the round dab Manu
    already paints with at the same place (cage 1.42, SubD 1 1.33: a faithful stamp cannot be rounder there, AD-037
    §12.4) -, no texel on another sheet. Below `WRAP_FROM_PERCENT` every placement is planar; at 5 % the wrap
    projection rounds the wing's stamp (planar 1.34 / 1.50)."""
    from mirai.paint import stamp
    from mirai.paint.stamp import Stamp
    from tests import paint_alpha_regions as pr

    surface = surfaces_2048[kind]
    camera = pr.front_camera(head)
    bounding = mesh_center_and_radius(head)[1]
    radius = 0.03 * bounding
    disc = pr.disc_alpha()
    projections = {}
    for name in pr.REGIONS:
        hit = pr.region_hit(surface, camera, name)
        result = stamp.alpha_stamp(surface, hit.point, hit.normal, radius, disc, view_up=(0.0, 1.0, 0.0),
                                   projection=stamp.projection_for(3.0))
        area, aspect = pr.stretch(surface, result, radius, disc)
        texels, _ = surface.footprint(hit.point, radius * 0.95, hit.normal)  # the round dab, the disc's size
        round_aspect = pr.stretch(surface, Stamp(texels, np.ones(texels.size, np.float32), None), radius, disc)[1]
        assert 0.75 <= area <= 1.25, (name, area)
        assert aspect <= max(1.3, round_aspect + 0.03), (name, aspect, round_aspect)
        if name != "nostril_wing":
            assert aspect <= 1.3, (name, aspect)
        assert pr.leaked(surface, result, hit.point, radius * math.sqrt(2.0)) == 0, name
        projections[name] = result.projection
    assert set(projections.values()) == {stamp.PLANAR}
    hit = pr.region_hit(surface, camera, "nostril_wing")
    wide = stamp.alpha_stamp(surface, hit.point, hit.normal, 0.05 * bounding, disc, view_up=(0.0, 1.0, 0.0),
                             projection=stamp.projection_for(5.0))
    assert wide.projection == stamp.WRAP and pr.stretch(surface, wide, 0.05 * bounding, disc)[1] <= 1.3


@pytest.mark.parametrize("kind", ["cage", "subd1"])
def test_the_lower_lip_is_not_painted_through_the_upper_one_from_4_percent(head, surfaces_2048, kind):
    """The planar stamp on the lip edge reaches the lower lip from 4 % on (cage 88 texels at 4 %, 435 / 315 at 5 %; the
    round dab 531 / 385 at 5 %); from `WRAP_FROM_PERCENT` the stressed placement wraps and paints none there."""
    from mirai.paint import stamp
    from tests import paint_alpha_regions as pr

    surface = surfaces_2048[kind]
    bounding = mesh_center_and_radius(head)[1]
    hit = pr.region_hit(surface, pr.front_camera(head), "lip_edge")
    disc = pr.disc_alpha()
    assert stamp.projection_for(3.0) == stamp.PLANAR and stamp.projection_for(4.0) is None
    for percent in (4.0, 5.0, 8.0):
        radius = percent / 100.0 * bounding
        chosen = stamp.alpha_stamp(surface, hit.point, hit.normal, radius, disc, view_up=(0, 1, 0),
                                   projection=stamp.projection_for(percent))
        assert pr.leaked(surface, chosen, hit.point, radius * math.sqrt(2.0)) == 0, percent
    radius = 0.05 * bounding
    planar = stamp.alpha_stamp(surface, hit.point, hit.normal, radius, disc, view_up=(0, 1, 0), projection=stamp.PLANAR)
    assert pr.leaked(surface, planar, hit.point, radius * math.sqrt(2.0)) > 50


@pytest.mark.parametrize("kind", ["cage", "subd1"])
def test_a_stamp_on_the_uv_seam_paints_both_islands_continuously(head, surfaces, kind):
    from mirai.paint import stamp
    from tests import paint_alpha_regions as pr

    surface = surfaces[kind]
    radius = 0.03 * mesh_center_and_radius(head)[1]
    hit = pr.region_hit(surface, pr.front_camera(head), "uv_seam")
    # a cone (1 at the centre, 0 at the radius): its slope is bounded, so neighbours differ by little
    y, x = np.mgrid[0:128, 0:128]
    cone = np.clip(1.0 - np.hypot(x + 0.5 - 64, y + 0.5 - 64) / 60.0, 0.0, 1.0)
    image = AlphaImage.from_pixels("test/cone", "Kegel", np.rint(cone * 255).astype(np.uint8))
    result = stamp.alpha_stamp(surface, hit.point, hit.normal, radius, image, view_up=(0, 1, 0))
    points = surface.map.surface_points(result.texels)
    left, right = points[:, 0] < 0.0, points[:, 0] > 0.0
    uv_x = result.texels % SIZE
    assert left.sum() > 0.3 * len(points) and right.sum() > 0.3 * len(points)
    assert abs(np.median(uv_x[left]) - np.median(uv_x[right])) > 50  # two islands apart in the image
    # continuity in 3D: across the seam each texel near the plane has a neighbour on the other side of similar coverage
    texel_size = math.sqrt(float(np.median(surface._texel_area[surface.map.slot[result.texels]])))
    near = np.abs(points[:, 0]) < 1.5 * texel_size
    a, b = np.flatnonzero(near & left), np.flatnonzero(near & right)
    assert a.size > 5 and b.size > 5
    d = np.linalg.norm(points[a][:, None] - points[b][None], axis=2)
    pairs = d.argmin(axis=1)
    close = d[np.arange(a.size), pairs] < 2.0 * texel_size
    slope = 2.0 * texel_size / (radius * 60.0 / 64.0)  # the most two texels can change on the cone
    assert np.abs(result.coverage[a][close] - result.coverage[b][pairs][close]).max() < slope + 0.03


def _stroke_frames(surface, camera, radius, image, stroke):
    from mirai.paint import dynamics, stamp
    from tests import paint_alpha_regions as pr

    frames, normals = [], []

    def evaluate(placement):
        result = stamp.alpha_stamp(surface, placement.point, placement.normal, radius, image,
                                   tangent=placement.tangent, view_up=(0.0, 1.0, 0.0),
                                   projection=stamp.projection_for(3.0))
        frames.append(result.frame)
        normals.append(placement.normal)

    queue = dynamics.StrokeQueue(surface.hit, 2.0 * radius, 2.0 * radius, True, evaluate, radius=radius)
    (x0, y0), (x1, y1) = pr.STROKES[stroke]
    for k in range(41):
        queue.add_ray(*pr.ray(camera, (x0 + (x1 - x0) * k / 40, y0 + (y1 - y0) * k / 40)), samples=3)
    queue.end_input()
    queue.run(None)
    return frames, normals


@pytest.mark.parametrize("kind", ["cage", "subd1"])
def test_the_frame_does_not_jump_between_placements_at_100_percent_spacing(head, surfaces, reference, kind):
    """§4.3 frame jump at 3 %, 100 % spacing. Literally (n, t between successive placements) the surface itself turns
    up to 60° per placement across the nose - no frame avoids that; the frame's own error is the excess over a smooth
    reference's turn (the same estimator on SubD 2) and the tangent's angle from the stroke's direction: <= 15°, except
    at the lips' line on SubD 1 (17.5° measured: a disc centred on the crease averages both lips, see AD-037 §12)."""
    from tests import paint_alpha_regions as pr

    surface = surfaces[kind]
    camera = pr.front_camera(head)
    radius = 0.03 * mesh_center_and_radius(head)[1]
    for stroke in pr.STROKES:
        frames, normals = _stroke_frames(surface, camera, radius, pr.disc_alpha(), stroke)
        assert len(frames) >= 3, stroke
        excess, twist = pr.frame_excess(frames, reference, radius, normals)
        limit = 20.0 if stroke == "over_lip" else 15.0
        assert max(excess) <= limit, (stroke, excess)
        assert max(twist) <= 15.0, (stroke, twist)


def test_an_alpha_stamp_and_its_mirror_are_mirror_images(head, surfaces):
    """The asymmetric vein at the cheek with the head's X plane: the mirror stamp's coverage at each texel equals the
    main stamp's at the reflected point (the frame's handedness flips)."""
    from mirai.paint import stamp
    from mirai.paint.dynamics import Placement
    from tests import paint_alpha_regions as pr

    surface = surfaces["subd1"]
    definition = head.symmetry_definition
    radius = 0.03 * mesh_center_and_radius(head)[1]
    hit = pr.region_hit(surface, pr.front_camera(head), "cheek")
    stamps: list = []
    settings = brush.BrushSettings(tip=brush.TipSettings("test/ader"))
    texels, coverage, unique = stamp.evaluate(surface, Placement(0, hit.point, hit.normal, np.array([0.8, 0.6, 0.0])),
                                              radius, settings, definition, view_up=(0, 1, 0), stamps=stamps)
    main, mirrored = stamps
    assert not unique and texels.size == main.texels.size + mirrored.texels.size
    assert main.projection == mirrored.projection
    a = surface.map.surface_points(main.texels)
    b = surface.map.surface_points(mirrored.texels) * np.array([-1.0, 1.0, 1.0])  # reflected across x = 0
    assert abs(main.coverage.sum() - mirrored.coverage.sum()) < 0.05 * main.coverage.sum()
    d = np.linalg.norm(b[:, None] - a[None], axis=2)
    nearest = d.argmin(axis=1)
    texel = math.sqrt(float(np.median(surface._texel_area[surface.map.slot[main.texels]])))
    close = d[np.arange(len(b)), nearest] < texel
    assert close.mean() > 0.8
    assert np.mean(np.abs(mirrored.coverage[close] - main.coverage[nearest[close]])) < 0.06
    # the handedness: the reflected frame's b is the reflection of b, not n × t
    assert np.allclose(mirrored.frame.b, main.frame.b * np.array([-1, 1, 1]))
    assert np.dot(np.cross(mirrored.frame.n, mirrored.frame.t), mirrored.frame.b) < 0.0


# -- the path sampler and the queue ------------------------------------------------------------------------------------


class _Hit:
    def __init__(self, point, normal=(0.0, 0.0, 1.0)):
        self.point = np.asarray(point, dtype=np.float64)
        self.normal = np.asarray(normal, dtype=np.float64)


def _plane_hit(origin, direction):
    """A ray on the plane z = 0 for x in [0, 10] (beyond: a gap)."""
    o, d = np.asarray(origin, float), np.asarray(direction, float)
    t = -o[2] / d[2]
    p = o + t * d
    return _Hit(p) if 0.0 <= p[0] <= 10.0 else None


def _down(x, y=0.0):
    return (x, y, 5.0), (0.0, 0.0, -1.0)


def _queue(spacing=0.5, directed=False, jump=3.0):
    placements = []
    from mirai.paint.dynamics import StrokeQueue

    queue = StrokeQueue(_plane_hit, spacing, jump, directed, placements.append, radius=spacing)
    return queue, placements


def test_placements_lie_every_spacing_of_arc_length_across_events_whatever_the_chunking():
    xs = [0.0, 0.13, 1.9, 2.0, 4.71, 7.3, 7.31, 9.0]
    queue, placements = _queue()
    for i, x in enumerate(xs):
        queue.add_ray(*_down(x), samples=1 if i == 0 else 7)
    queue.end_input()
    queue.run(None)
    positions = [float(p.point[0]) for p in placements]
    assert np.allclose(positions, np.arange(0.0, 9.0 + 1e-9, 0.5))
    # the same rays in one budget-starved run per frame: the same placements, in the same order
    again, placed = _queue()
    for i, x in enumerate(xs):
        again.add_ray(*_down(x), samples=1 if i == 0 else 7)
        again.run(1e-9)
    again.end_input()
    while not again.done:
        again.run(1e-9)
    assert [p.point.tolist() for p in placed] == [p.point.tolist() for p in placements]


def test_a_fast_stroke_has_no_gaps_and_a_hit_gap_ends_the_run():
    queue, placements = _queue(spacing=0.25)
    for i, x in enumerate([0.0, 3.0, 6.0, 9.5]):  # 3 units per event: 12 placements per event
        queue.add_ray(*_down(x), samples=1 if i == 0 else 6)
    queue.add_ray(*_down(14.0), samples=4)  # off the plane: a gap
    queue.add_ray(*_down(9.0), samples=3)   # back on: a new run starts at its first hit
    queue.end_input()
    queue.run(None)
    xs = np.array([p.point[0] for p in placements])
    first_run = xs[: np.argmax(np.diff(xs) < 0) + 1]
    gaps = np.diff(first_run)
    assert gaps.max() <= 1.1 * 0.25 and gaps.min() >= 0.25 - 1e-9
    assert first_run[-1] >= 9.5 - 0.25
    assert xs[len(first_run)] <= 10.0  # the second run's first placement is its first hit, nothing across the gap


def test_alpha_placements_follow_the_stroke_and_the_first_waits_for_a_direction():
    queue, placements = _queue(spacing=0.5, directed=True)
    queue.add_ray(*_down(1.0, 1.0))
    queue.run(None)
    assert placements == []  # the press alone: no direction yet
    queue.add_ray((2.0, 2.0, 5.0), (0.0, 0.0, -1.0), samples=4)
    queue.end_input()
    queue.run(None)
    assert len(placements) >= 2
    for p in placements:
        assert np.allclose(p.tangent, np.array([1.0, 1.0, 0.0]) / math.sqrt(2.0))
    # a click without movement: one placement, no tangent (the view's up)
    click, placed = _queue(directed=True)
    click.add_ray(*_down(5.0))
    click.end_input()
    click.run(None)
    assert len(placed) == 1 and placed[0].tangent is None
