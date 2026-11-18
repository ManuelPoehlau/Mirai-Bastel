"""AD-037 Phase 1a: the read-only UV check (`mirai.paint.uv_health`)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import tests._bootstrap  # noqa: F401

from core import Mesh, scene_from_dict
from mirai.paint import uv_health
from tests.test_paint_texel_map import grid

GOLLUM = Path(__file__).resolve().parents[1] / "scenes" / "Gollum_Head_rigging_test.mirai.json"


def test_a_clean_grid_is_clean():
    mesh = grid(4)
    health = uv_health.check(mesh, 64)
    assert health.clean and health.has_uvs
    assert (health.faces, health.mapped, health.islands, health.seams) == (16, 16, 1, 0)
    assert health.coverage == pytest.approx(1.0)
    assert health.overlap_share == 0.0  # neighbours share UV edges: no overlap
    assert health.problem_faces() == {}
    assert health.status_line().endswith("clean")


def test_each_problem_kind_is_named():
    mesh = grid(3)
    f = mesh.all_face_ids()
    mesh.set_face_uvs(f[0], None)
    mesh.set_face_uvs(f[1], [(0.4, 0.0), (0.6, 0.0), (0.6, 0.0), (0.4, 0.0)])  # a line in UV
    mesh.set_face_uvs(f[8], [(u + 0.5, v) for u, v in mesh.face_uvs(f[8])])  # beyond u = 1
    mesh.set_face_uvs(f[4], mesh.face_uvs(f[3]))  # face 4 lies on face 3
    health = uv_health.check(mesh, 96)
    assert health.unmapped == (f[0],)
    assert health.zero_area == (f[1],)
    assert health.outside == (f[8],)
    assert set(health.overlapping) == {f[3], f[4]}
    assert health.overlap_share > 0.0 and not health.clean
    assert health.problem_faces() == {f[0]: "unmapped", f[1]: "zero_area", f[8]: "outside",
                                      f[3]: "overlapping", f[4]: "overlapping"}
    line = health.status_line()
    for words in ("1 without UVs", "1 without UV area", "2 overlapping", "1 outside 0-1"):
        assert words in line


def test_a_seam_splits_islands():
    mesh = grid(2)
    right = [f for f in mesh.all_face_ids() if min(mesh.vertex_position(v)[0] for v in mesh.face_vertices(f)) >= 1.0]
    for f in right:
        mesh.set_face_uvs(f, [(u + 0.001, v) for u, v in mesh.face_uvs(f)])
    health = uv_health.check(mesh, 64)
    assert (health.islands, health.seams) == (2, 2)


def test_a_mesh_without_uvs_cannot_be_painted():
    mesh = Mesh()
    ids = [mesh.add_vertex(p) for p in ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))]
    mesh.add_face(ids)
    health = uv_health.check(mesh)
    assert not health.has_uvs and not health.clean
    assert "no UVs" in health.status_line()


def test_density_scales_with_the_resolution():
    mesh = grid(4)  # 4 x 4 units on the unit square: 1/4 UV per unit
    health = uv_health.check(mesh, 64)
    assert health.density[1] == pytest.approx(16.0, rel=0.05)
    assert health.density_at(2048)[1] == pytest.approx(16.0 * 32, rel=0.05)


def test_the_gollum_head_matches_the_audit():
    """Audit 2026-11-18 §2.2: 44 faces without UV area (the newest ids), ~3.4 % overlapping texels, 2 islands, 66.5 %
    of the square, density p50 ~970 px per unit at 2048² with a ~3.4x spread."""
    scene = scene_from_dict(json.loads(GOLLUM.read_text(encoding="utf-8")))
    head = next(o for o in scene.objects.values() if o.texture and o.eye is None and o.mesh.has_face_uvs())
    health = uv_health.check(head.mesh, 512)
    assert len(health.zero_area) == 44 and min(health.zero_area) >= 5419
    assert health.unmapped == () and health.islands == 2
    assert health.coverage == pytest.approx(0.665, abs=0.003)
    assert health.overlap_share == pytest.approx(0.034, abs=0.004)
    p5, p50, p95 = health.density_at(2048)
    assert p50 == pytest.approx(973, rel=0.03) and p95 / p5 == pytest.approx(3.4, abs=0.15)
