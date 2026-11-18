"""AD-037 §8 Phase 2: the brush (`mirai.paint.brush`) and the paint surface (`mirai.paint.surface`).

Pinned: the curves are the Soft Selection's; the falloff's plateau and edge; Normal / erase blending; opacity does not
build up inside a stroke while flow does; Esc is exact; the hit is `face_hit`'s point on the cage; the footprint equals a
brute-force search; a dab crosses a UV seam; the mirror; seam padding; a dab painted on the SubD surface is round there
(§8.1's out-of-round row) while one painted on the cage is not.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

import tests._bootstrap  # noqa: F401

from core import Mesh, ObjectId, PaintLayer, PaintStack, SceneObject, SymmetryDefinition
from mirai.paint import brush
from mirai.paint.store import PaintStore
from mirai.paint.surface import PaintSurface, mirror, seam_pad
from mirai.soft_selection.influence import CURVES
from tests.test_paint_texel_map import _head, _subd_mesh, grid


# -- the brush --------------------------------------------------------------------------------------------------------


def test_the_curves_are_the_soft_selection_formulas():
    t = np.linspace(0.0, 1.0, 101)
    for name, curve in brush.CURVE_ARRAYS.items():
        assert np.allclose(curve(t), [CURVES[name](float(x)) for x in t], atol=1e-12), name


def test_falloff_is_full_in_the_plateau_and_zero_from_the_radius():
    x = np.array([0.0, 0.3, 0.5, 0.75, 0.999, 1.0, 1.5])
    out = brush.falloff(x, 0.5, "linear")
    assert out[0] == out[1] == out[2] == 1.0
    assert out[3] == pytest.approx(0.5)
    assert 0.0 < out[4] < 0.01 and out[5] == 0.0 and out[6] == 0.0
    assert np.all(np.diff(brush.falloff(np.linspace(0, 1, 50), 0.2, "smooth")) <= 1e-12)  # monotone
    assert np.array_equal(brush.falloff(np.array([0.2, 0.99, 1.0]), 1.0, "smooth"), [1.0, 1.0, 0.0])


def test_blend_paint_and_erase():
    clear = np.zeros((1, 4), np.uint8)
    assert brush.blend_paint(clear, (1.0, 0.0, 0.0), np.array([1.0])).tolist() == [[255, 0, 0, 255]]
    half = brush.blend_paint(clear, (0.0, 0.0, 1.0), np.array([0.5]))
    assert half.tolist() == [[0, 0, 255, 128]]  # straight alpha: the colour is the paint's, the alpha half
    red = np.array([[255, 0, 0, 255]], np.uint8)
    assert brush.blend_paint(red, (0.0, 0.0, 1.0), np.array([0.5])).tolist() == [[128, 0, 128, 255]]
    assert brush.blend_erase(red, np.array([0.25])).tolist() == [[255, 0, 0, 191]]
    assert brush.blend_erase(red, np.array([1.0])).tolist() == [[255, 0, 0, 0]]


def _stroke(settings, size=16):
    store = PaintStore()
    obj = SceneObject(ObjectId(1), Mesh(), name="o")
    obj.paint = PaintStack(size, size, (PaintLayer("L", None),))
    recorder = store.begin_stroke(obj, "L")
    return store, obj, recorder, brush.PaintStroke(recorder, settings)


def test_opacity_does_not_build_up_inside_a_stroke_and_flow_does():
    texels = np.arange(10)
    full = np.ones(10, np.float32)
    store, obj, _, stroke = _stroke(brush.BrushSettings(opacity=0.5, flow=1.0))
    stroke.dab(texels, full)
    stroke.dab(texels, full)
    assert set(store.pixels(obj, "L").reshape(-1, 4)[texels, 3].tolist()) == {128}  # capped by the opacity
    store, obj, _, stroke = _stroke(brush.BrushSettings(opacity=1.0, flow=0.5))
    stroke.dab(texels, full)
    assert set(store.pixels(obj, "L").reshape(-1, 4)[texels, 3].tolist()) == {128}
    stroke.dab(texels, full)
    assert set(store.pixels(obj, "L").reshape(-1, 4)[texels, 3].tolist()) == {191}  # 0.5 + 0.5 * 0.5


def test_a_texel_in_a_dab_and_its_mirror_counts_once_with_the_larger_coverage():
    store, obj, _, stroke = _stroke(brush.BrushSettings(flow=0.5))
    stroke.dab(np.array([3, 3]), np.array([0.2, 1.0], np.float32))
    assert store.pixels(obj, "L").reshape(-1, 4)[3, 3] == 128


def test_cancel_restores_every_touched_texel_exactly():
    store, obj, recorder, stroke = _stroke(brush.BrushSettings())
    before = store.pixels(obj, "L").copy()
    stroke.dab(np.arange(0, 200, 3), np.ones(67, np.float32))
    assert not np.array_equal(store.pixels(obj, "L"), before)
    recorder.cancel()
    assert np.array_equal(store.pixels(obj, "L"), before)


def test_settings_are_validated_and_step():
    settings = brush.BrushSettings()
    assert settings.radius_percent == 3.0 and settings.tool == brush.TOOL_PAINT
    with pytest.raises(ValueError):
        brush.BrushSettings(opacity=1.5)
    with pytest.raises(ValueError):
        brush.BrushSettings(tool="smudge")
    assert settings.with_(opacity=2.0).opacity == 1.0 and settings.with_(radius_step=99).radius_step == len(
        brush.RADIUS_STEPS_PERCENT) - 1
    assert settings.with_opacity_step(-1).opacity == 0.9 and settings.with_(opacity=0.33).with_opacity_step(1).opacity == 0.4
    assert settings.world_radius(2.0) == pytest.approx(0.06)


# -- the surface ------------------------------------------------------------------------------------------------------


def _ray_at(point, direction):
    d = np.asarray(direction, float)
    d /= np.linalg.norm(d)
    return np.asarray(point, float) - 5.0 * d, d


def test_the_hit_is_on_the_drawn_cage_with_the_faces_uv():
    from mirai.viewport.picking import _ray_triangle_intersection
    from viewport.derived import triangulate_mesh_face

    mesh = _head()
    surface = PaintSurface(mesh, 256, 256)
    rng = np.random.default_rng(3)
    checked = 0
    for fid in rng.choice(mesh.all_face_ids(), 25, replace=False):
        tri = triangulate_mesh_face(mesh, fid)[0]
        p = np.mean([mesh.vertex_position(v) for v in tri], axis=0)
        normal = np.cross(*(np.subtract(mesh.vertex_position(v), mesh.vertex_position(tri[0])) for v in tri[1:]))
        origin, d = _ray_at(p, -normal)
        hit = surface.hit(origin, d)
        assert hit is not None
        # nearest along the ray: no triangle of the mesh is hit closer
        best = min(t for f in mesh.all_face_ids() for tr in triangulate_mesh_face(mesh, f)
                   if (t := _ray_triangle_intersection(tuple(origin), tuple(d),
                                                       *(mesh.vertex_position(v) for v in tr))) is not None)
        assert hit.distance == pytest.approx(best, abs=1e-9)
        checked += 1
    assert checked == 25


def test_the_footprint_equals_a_brute_force_search():
    mesh = grid(6)
    surface = PaintSurface(mesh, 96, 96)
    texel_map = surface.map
    mapped = texel_map.mapped()
    points = texel_map.surface_points(mapped)
    centre, radius = np.array([2.6, 3.1, 0.2]), 1.3
    texels, x = surface.footprint(centre, radius)
    expected = mapped[np.linalg.norm(points - centre, axis=1) < radius]
    assert np.array_equal(np.sort(texels), np.sort(expected))
    assert np.all((x >= 0.0) & (x < 1.0))


def test_the_footprint_skips_triangles_facing_away():
    mesh = grid(2, uv_scale=0.5)
    back = [mesh.add_vertex((x, y, -0.05)) for x, y in ((0.0, 0.0), (0.0, 2.0), (2.0, 2.0), (2.0, 0.0))]
    mesh.add_face(back, uvs=[(0.6, 0.6), (0.6, 0.9), (0.9, 0.9), (0.9, 0.6)], infer_uvs=False)  # facing -Z
    surface = PaintSurface(mesh, 64, 64)
    all_texels, _ = surface.footprint((1.0, 1.0, 0.0), 3.0)
    front_texels, _ = surface.footprint((1.0, 1.0, 0.0), 3.0, facing=(0.0, 0.0, 1.0))
    back_face_texels = {int(t) for t in all_texels} - {int(t) for t in front_texels}
    assert back_face_texels and all(
        surface.map.owner([t])[0][0] == mesh.all_face_ids()[-1] for t in back_face_texels)


def test_a_dab_crosses_a_uv_seam():
    """Two quads side by side in 3D whose UV islands lie apart: a dab on their shared edge paints both islands."""
    mesh = Mesh()
    v = [mesh.add_vertex(p) for p in ((0, 0, 0), (1, 0, 0), (2, 0, 0), (0, 1, 0), (1, 1, 0), (2, 1, 0))]
    a = mesh.add_face([v[0], v[1], v[4], v[3]], uvs=[(0.0, 0.0), (0.4, 0.0), (0.4, 0.4), (0.0, 0.4)])
    b = mesh.add_face([v[1], v[2], v[5], v[4]], uvs=[(0.6, 0.6), (1.0, 0.6), (1.0, 1.0), (0.6, 1.0)], infer_uvs=False)
    surface = PaintSurface(mesh, 64, 64)
    texels, _ = surface.footprint((1.0, 0.5, 0.0), 0.3)
    faces = {surface.map.owner([t])[0][0] for t in texels}
    assert faces == {a, b}


def test_mirror_reflects_point_and_normal():
    definition = SymmetryDefinition((0.0, 0.0, 0.0), (1.0, 0.0, 0.0))
    point, normal = mirror(definition, (0.3, 1.0, 2.0), (0.6, 0.8, 0.0))
    assert np.allclose(point, (-0.3, 1.0, 2.0)) and np.allclose(normal, (-0.6, 0.8, 0.0))


def test_seam_padding_spreads_island_colours_outward_only():
    mesh = Mesh()
    v = [mesh.add_vertex(p) for p in ((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0))]
    mesh.add_face(v, uvs=[(0.25, 0.25), (0.75, 0.25), (0.75, 0.75), (0.25, 0.75)])
    surface = PaintSurface(mesh, 32, 32)
    mapped = (surface.map.slot >= 0).reshape(32, 32)
    dst, src = seam_pad(surface.map, [(0, 0, 32, 32)], 2)
    assert dst.size and not mapped.reshape(-1)[dst].any() and mapped.reshape(-1)[src].all()
    ys, xs = np.nonzero(mapped)
    dy, dx = dst // 32, dst % 32
    distance = np.maximum(np.maximum(ys.min() - dy, dy - ys.max()), np.maximum(xs.min() - dx, dx - xs.max()))
    assert distance.max() == 2 and distance.min() == 1  # exactly two rings around the island
    assert seam_pad(surface.map, [(0, 0, 4, 4)], 2)[0].size < dst.size  # only around the given boxes


def _out_of_round(points: np.ndarray, centre: np.ndarray, normal: np.ndarray, bins: int = 16) -> float:
    """Longest / shortest radius of a footprint's points around `centre` in the plane normal to `normal`."""
    n = normal / np.linalg.norm(normal)
    a = np.cross(n, (1.0, 0.0, 0.0) if abs(n[0]) < 0.9 else (0.0, 1.0, 0.0))
    a /= np.linalg.norm(a)
    b = np.cross(n, a)
    rel = points - centre
    angle = np.arctan2(rel @ b, rel @ a)
    radius = np.hypot(rel @ a, rel @ b)
    index = ((angle + math.pi) / (2 * math.pi) * bins).astype(int) % bins
    outer = np.array([radius[index == k].max() for k in range(bins) if np.any(index == k)])
    return float(outer.max() / outer.min())


def test_a_dab_painted_on_the_subd_surface_is_round_there_and_one_painted_on_the_cage_is_not():
    """§8.1 acceptance row (P-10 revised), 1024², 5 % radius, 80 dab centres on the Gollum head, all seen on SubD level 1:
    painted on SubD the dab is round there (out-of-round p50 1.04 measured), painted on the cage it is oval (1.20; §8.1
    measured 1.23 : 1 at p50 from the cage to SubD 2)."""
    from mirai.mesh_geometry import mesh_center_and_radius

    cage_mesh = _head()
    subd_mesh = _subd_mesh(cage_mesh, 1)
    cage = PaintSurface(cage_mesh, 1024, 1024)
    subd = PaintSurface(subd_mesh, 1024, 1024)
    radius = 0.05 * mesh_center_and_radius(cage_mesh)[1]
    on_cage, on_subd = [], []
    for texel in np.random.default_rng(7).choice(subd.map.mapped(), 80, replace=False):
        if cage.map.slot[texel] < 0:
            continue
        centre = subd.map.surface_points([texel])[0]
        normal = subd._tri_normal[subd.map.slot[texel]]
        texels, _ = subd.footprint(centre, radius, normal)
        cage_texels, _ = cage.footprint(cage.map.surface_points([texel])[0], radius,
                                        cage._tri_normal[cage.map.slot[texel]])
        cage_texels = cage_texels[subd.map.slot[cage_texels] >= 0]
        if texels.size < 80 or cage_texels.size < 80:
            continue
        on_subd.append(_out_of_round(subd.map.surface_points(texels), centre, normal))
        on_cage.append(_out_of_round(subd.map.surface_points(cage_texels), centre, normal))
    assert len(on_subd) >= 60
    assert np.median(on_subd) < 1.08
    assert np.median(on_cage) > 1.12
