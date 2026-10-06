"""Kontrakttests für die Entfernen-Primitive (WP Delete/Dissolve,
docs/WP_DELETE_DISSOLVE_PLAN.md): `Mesh.dissolve_vertex`, `dissolve_edges`,
`dissolve_faces`, `delete_vertices`, `delete_edges`, `delete_faces`.

Pro Methode: ID-Kontinuität (vollständige ID-Mengen vorher/nachher, Phase-C-
Stil), "nichts zu tun" (Mesh inkl. Allocator-Zählerständen unverändert) und
Fehlerfall (MeshError, Mesh inkl. Zählerständen unverändert). Dazu der
2×2-Grid-Fall aus dem Plan (§Tests) und die drei Praxis-Szenarien als
Core-Erwartung (Würfel, 3×3-Loop).
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401 — Produktionspfad src/core/

from core import HistoryStack
from core.mesh import Mesh, MeshError, SymmetryDefinition
from core.operations import MeshStateCommand
from mirai.scene_factory import create_cube
from tests.mesh_invariants import assert_mesh_invariants


# ---------------------------------------------------------------------------
# Hilfen
# ---------------------------------------------------------------------------

def _grid(n: int):
    """n×n Quad-Grid in der XY-Ebene, Winding gegen den Uhrzeigersinn (+Z).
    Rückgabe (mesh, vertices[(row, col)], faces[(row, col)])."""
    mesh = Mesh()
    p = {}
    for r in range(n + 1):
        for c in range(n + 1):
            p[(r, c)] = mesh.add_vertex((float(c), float(r), 0.0))
    f = {}
    for r in range(n):
        for c in range(n):
            f[(r, c)] = mesh.add_face([p[(r, c)], p[(r, c + 1)], p[(r + 1, c + 1)], p[(r + 1, c)]])
    return mesh, p, f


def _edge(mesh: Mesh, a, b):
    return next(e for e in mesh.all_edge_ids() if set(mesh.edge_vertices(e)) == {a, b})


def _ids(mesh: Mesh):
    return set(mesh.all_vertex_ids()), set(mesh.all_edge_ids()), set(mesh.all_face_ids())


def _signed_area_z(mesh: Mesh, fid) -> float:
    pts = [mesh.vertex_position(v) for v in mesh.face_vertices(fid)]
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1])) / 2.0


def _face_sizes(mesh: Mesh) -> list[int]:
    return sorted(len(mesh.face_vertices(f)) for f in mesh.all_face_ids())


def _assert_refused(mesh: Mesh, call) -> None:
    before = mesh.export_state()
    with pytest.raises(MeshError):
        call()
    assert mesh.export_state() == before  # inkl. Allocator-Zählerstände
    assert_mesh_invariants(mesh)


# ---------------------------------------------------------------------------
# delete_faces — inkl. 2×2-Grid-Fall aus dem Plan
# ---------------------------------------------------------------------------

def test_delete_faces_2x2_two_adjacent_faces() -> None:
    """2×2-Grid, zwei Nachbar-Faces: jede Edge, an der danach keine Face mehr
    hängt, geht mit (Innenkante und Mesh-Randkanten); die zwei Edges, die noch
    von den oberen Faces genutzt werden, bleiben (Manu 2026-10-06)."""
    mesh, p, f = _grid(2)
    shared = {_edge(mesh, p[(1, 0)], p[(1, 1)]), _edge(mesh, p[(1, 1)], p[(1, 2)])}
    bottom_region = {f[(0, 0)], f[(0, 1)]}
    gone = {e for e in mesh.all_edge_ids() if set(mesh.edge_faces(e)) <= bottom_region}
    verts, edges, faces = _ids(mesh)

    mesh.delete_faces(sorted(bottom_region))

    assert_mesh_invariants(mesh)
    v_after, e_after, f_after = _ids(mesh)
    assert f_after == faces - bottom_region
    assert len(gone) == 5 and not gone & shared
    assert e_after == edges - gone
    assert v_after == verts - {p[(0, 0)], p[(0, 1)], p[(0, 2)]}
    assert mesh.edge_faces(_edge(mesh, p[(1, 0)], p[(1, 1)])) == [f[(1, 0)]]
    assert all(mesh.edge_faces(e) for e in mesh.all_edge_ids())  # nichts schwebt


def test_delete_faces_2x2_corner_face_removes_floating_border_edges() -> None:
    mesh, p, f = _grid(2)
    corner_edges = {_edge(mesh, p[(0, 0)], p[(0, 1)]), _edge(mesh, p[(0, 0)], p[(1, 0)])}
    verts, edges, faces = _ids(mesh)

    mesh.delete_faces([f[(0, 0)]])

    assert_mesh_invariants(mesh)
    assert _ids(mesh) == (verts - {p[(0, 0)]}, edges - corner_edges, faces - {f[(0, 0)]})


def test_delete_faces_single_face_keeps_all_four_edges() -> None:
    mesh, p, f = _grid(3)
    verts, edges, faces = _ids(mesh)
    hole = f[(1, 1)]
    ring = mesh.face_edges(hole)

    mesh.delete_faces([hole])

    assert_mesh_invariants(mesh)
    assert _ids(mesh) == (verts, edges, faces - {hole})
    for eid in ring:  # Lochrand: je noch eine Nachbar-Face
        assert len(mesh.edge_faces(eid)) == 1


def test_delete_faces_block_removes_inner_vertex() -> None:
    mesh, p, f = _grid(3)
    block = [f[(0, 0)], f[(0, 1)], f[(1, 0)], f[(1, 1)]]
    center = p[(1, 1)]
    spokes = set(mesh.vertex_edges(center))

    mesh.delete_faces(block)

    assert_mesh_invariants(mesh)
    assert not mesh.is_valid_vertex(center)
    assert not any(mesh.is_valid_edge(e) for e in spokes)
    assert len(mesh.all_face_ids()) == 5


def test_delete_faces_noop_and_error() -> None:
    mesh, _, f = _grid(2)
    before = mesh.export_state()
    mesh.delete_faces([])
    assert mesh.export_state() == before
    _assert_refused(mesh, lambda: mesh.delete_faces([f[(0, 0)], type(f[(0, 0)])(999)]))


def test_delete_faces_keeps_neighbour_boundaries_and_ids_untouched() -> None:
    mesh, _, f = _grid(2)
    keep = {fid: mesh.face_vertices(fid) for fid in (f[(1, 0)], f[(1, 1)])}
    mesh.delete_faces([f[(0, 0)], f[(0, 1)]])
    assert {fid: mesh.face_vertices(fid) for fid in keep} == keep


# ---------------------------------------------------------------------------
# delete_edges / delete_vertices
# ---------------------------------------------------------------------------

def test_delete_edges_removes_edge_and_both_faces() -> None:
    mesh, p, f = _grid(2)
    eid = _edge(mesh, p[(0, 1)], p[(1, 1)])
    region = {f[(0, 0)], f[(0, 1)]}
    gone = {e for e in mesh.all_edge_ids() if set(mesh.edge_faces(e)) <= region}
    verts, edges, faces = _ids(mesh)

    mesh.delete_edges([eid])

    assert_mesh_invariants(mesh)
    assert eid in gone
    assert _ids(mesh) == (verts - {p[(0, 0)], p[(0, 1)], p[(0, 2)]}, edges - gone, faces - region)


def test_delete_edges_border_edge_of_single_quad_removes_everything() -> None:
    mesh, p, f = _grid(1)
    mesh.delete_edges([_edge(mesh, p[(0, 0)], p[(0, 1)])])
    assert_mesh_invariants(mesh)
    assert _ids(mesh) == (set(), set(), set())


def test_delete_edges_wire_edge() -> None:
    mesh, p, f = _grid(1)
    lone = mesh.add_vertex((3.0, 0.0, 0.0))
    wire = mesh.add_edge(p[(0, 1)], lone)
    verts, edges, faces = _ids(mesh)

    mesh.delete_edges([wire])

    assert_mesh_invariants(mesh)
    # Die Edge geht, `lone` hat danach keine Edge mehr und geht mit; das Quad
    # bleibt unberührt.
    assert _ids(mesh) == (verts - {lone}, edges - {wire}, faces)


def test_delete_edges_noop_and_error() -> None:
    mesh, _, _ = _grid(2)
    before = mesh.export_state()
    mesh.delete_edges([])
    assert mesh.export_state() == before
    _assert_refused(mesh, lambda: mesh.delete_edges([type(mesh.all_edge_ids()[0])(999)]))


def test_delete_vertices_center_of_2x2_removes_everything() -> None:
    """Alle vier Faces hängen am Mittel-Vertex; danach hängt keine Edge mehr an
    einer Face, also schwebt nichts stehen bleibend in der Luft."""
    mesh, p, f = _grid(2)
    mesh.delete_vertices([p[(1, 1)]])
    assert_mesh_invariants(mesh)
    assert _ids(mesh) == (set(), set(), set())


def test_delete_vertices_center_of_3x3_block_keeps_shared_ring_edges() -> None:
    mesh, p, f = _grid(3)
    v = p[(1, 1)]
    ring_faces = {f[(0, 0)], f[(0, 1)], f[(1, 0)], f[(1, 1)]}
    gone = {e for e in mesh.all_edge_ids() if set(mesh.edge_faces(e)) <= ring_faces}
    verts, edges, faces = _ids(mesh)

    mesh.delete_vertices([v])

    assert_mesh_invariants(mesh)
    v_after, e_after, f_after = _ids(mesh)
    assert f_after == faces - ring_faces
    assert e_after == edges - gone
    # Rechter und oberer Rand des 1-Rings hängen noch an Nachbar-Faces.
    assert mesh.is_valid_edge(_edge(mesh, p[(1, 2)], p[(2, 2)]))
    assert mesh.is_valid_edge(_edge(mesh, p[(2, 1)], p[(2, 2)]))
    assert v_after == verts - {v, p[(0, 0)], p[(0, 1)], p[(1, 0)]}
    assert all(mesh.edge_faces(e) for e in mesh.all_edge_ids())


def test_delete_vertices_grid_corner_and_noop_and_error() -> None:
    mesh, p, f = _grid(2)
    corner = p[(0, 0)]
    mesh.delete_vertices([corner])
    assert_mesh_invariants(mesh)
    assert not mesh.is_valid_face(f[(0, 0)])
    assert len(mesh.all_face_ids()) == 3
    before = mesh.export_state()
    mesh.delete_vertices([])
    assert mesh.export_state() == before
    _assert_refused(mesh, lambda: mesh.delete_vertices([corner]))


# ---------------------------------------------------------------------------
# dissolve_edges
# ---------------------------------------------------------------------------

def test_dissolve_edge_id_continuity_without_cleanup() -> None:
    mesh, p, f = _grid(2)
    eid = _edge(mesh, p[(0, 1)], p[(1, 1)])
    verts, edges, faces = _ids(mesh)
    outer = (set(mesh.face_edges(f[(0, 0)])) | set(mesh.face_edges(f[(0, 1)]))) - {eid}

    (new_face,) = mesh.dissolve_edges([eid], cleanup=False)

    assert_mesh_invariants(mesh)
    v_after, e_after, f_after = _ids(mesh)
    assert v_after == verts
    assert e_after == edges - {eid}
    assert f_after == (faces - {f[(0, 0)], f[(0, 1)]}) | {new_face}
    assert int(new_face) > max(int(x) for x in faces)
    assert set(mesh.face_edges(new_face)) == outer
    assert len(mesh.face_vertices(new_face)) == 6
    assert _signed_area_z(mesh, new_face) > 0  # Winding wie die Region


def test_dissolve_edge_cleanup_removes_two_valent_endpoint() -> None:
    mesh, p, f = _grid(2)
    eid = _edge(mesh, p[(0, 1)], p[(1, 1)])
    bottom = p[(0, 1)]  # Rand-Vertex, Valenz 3 -> danach 2
    old_border = {_edge(mesh, p[(0, 0)], bottom), _edge(mesh, bottom, p[(0, 2)])}
    verts, edges, faces = _ids(mesh)

    (new_face,) = mesh.dissolve_edges([eid], cleanup=True)

    assert_mesh_invariants(mesh)
    v_after, e_after, _ = _ids(mesh)
    assert v_after == verts - {bottom}  # Mitte (Valenz 4 -> 3) bleibt
    (new_edge,) = e_after - edges
    assert e_after == (edges - {eid} - old_border) | {new_edge}
    assert set(mesh.edge_vertices(new_edge)) == {p[(0, 0)], p[(0, 2)]}
    assert mesh.face_vertices(new_face).count(p[(1, 1)]) == 1
    assert len(mesh.face_vertices(new_face)) == 5


def test_dissolve_edge_cleanup_updates_neighbour_face_keeping_its_id() -> None:
    mesh = create_cube()
    eid = mesh.all_edge_ids()[0]
    merged = set(mesh.edge_faces(eid))
    a, b = mesh.edge_vertices(eid)
    neighbours = {
        fid for fid in mesh.all_face_ids()
        if fid not in merged and ({a, b} & set(mesh.face_vertices(fid)))
    }

    (new_face,) = mesh.dissolve_edges([eid], cleanup=True)

    assert_mesh_invariants(mesh)
    assert not mesh.is_valid_vertex(a) and not mesh.is_valid_vertex(b)
    assert len(mesh.face_vertices(new_face)) == 4
    for fid in neighbours:  # Nachbar-Faces behalten ihre ID, werden Dreiecke
        assert mesh.is_valid_face(fid)
        assert len(mesh.face_vertices(fid)) == 3
    assert _face_sizes(mesh) == [3, 3, 4, 4, 4]


def test_dissolve_edge_cube_both_variants() -> None:
    plain = create_cube()
    plain.dissolve_edges([plain.all_edge_ids()[0]], cleanup=False)
    assert_mesh_invariants(plain)
    assert _face_sizes(plain) == [4, 4, 4, 4, 6]
    assert len(plain.all_vertex_ids()) == 8  # 2er-Vertices bleiben sichtbar stehen

    clean = create_cube()
    clean.dissolve_edges([clean.all_edge_ids()[0]], cleanup=True)
    assert len(clean.all_vertex_ids()) == 6


def test_dissolve_edges_3x3_loop_returns_to_pure_quads() -> None:
    """Praxis-Szenario: Edge-Dissolve mit Cleanup auf jeder Kante eines Loops
    nacheinander -> reine Quads, keine Sechsecke, keine losen Punkte."""
    mesh, p, _ = _grid(3)
    for r in range(3):
        mesh.dissolve_edges([_edge(mesh, p[(r, 1)], p[(r + 1, 1)])], cleanup=True)
        assert_mesh_invariants(mesh)
    assert _face_sizes(mesh) == [4] * 6
    assert len(mesh.all_vertex_ids()) == 12
    assert all(len(mesh.vertex_edges(v)) >= 2 for v in mesh.all_vertex_ids())


def test_dissolve_edges_whole_loop_at_once_equals_sequential() -> None:
    seq, p, _ = _grid(3)
    for r in range(3):
        seq.dissolve_edges([_edge(seq, p[(r, 1)], p[(r + 1, 1)])], cleanup=True)
    once, q, _ = _grid(3)
    once.dissolve_edges([_edge(once, q[(r, 1)], q[(r + 1, 1)]) for r in range(3)], cleanup=True)
    assert_mesh_invariants(once)
    assert _face_sizes(once) == _face_sizes(seq)
    assert set(once.all_vertex_ids()) == set(seq.all_vertex_ids())


def test_dissolve_edges_two_edges_at_cube_corner_merge_as_one_region() -> None:
    """Atomar: der Cleanup der ersten Edge darf die zweite nicht verschlucken."""
    mesh = create_cube()
    corner = mesh.all_vertex_ids()[0]
    e1, e2 = mesh.vertex_edges(corner)[:2]
    region = set(mesh.edge_faces(e1)) | set(mesh.edge_faces(e2))
    assert len(region) == 3

    new_faces = mesh.dissolve_edges([e1, e2], cleanup=False)

    assert_mesh_invariants(mesh)
    assert len(new_faces) == 1
    assert not any(mesh.is_valid_face(f) for f in region)
    assert not mesh.is_valid_vertex(corner)  # alle drei Spokes innen -> kantenlos


def test_dissolve_edges_shared_chain_through_two_valent_vertex() -> None:
    """Teilen beide Faces eine Kette über einen 2er-Vertex, löst sich die ganze
    Kette auf (sonst doppelter Vertex in der neuen Face)."""
    mesh, p, f = _grid(2)
    mid, _, _ = mesh.split_edge(_edge(mesh, p[(0, 1)], p[(1, 1)]))
    eid = _edge(mesh, p[(0, 1)], mid)

    (new_face,) = mesh.dissolve_edges([eid], cleanup=False)

    assert_mesh_invariants(mesh)
    assert not mesh.is_valid_vertex(mid)
    assert len(mesh.face_vertices(new_face)) == 6


def test_dissolve_edges_cleanup_keeps_vertices_that_would_degenerate_the_face() -> None:
    """Zwei Dreiecke an einer Kante: danach haben beide Endpunkte zwei Edges,
    ihr Entfernen ließe aber nur 2 Vertices übrig -> sie bleiben, kein Fehler."""
    mesh = Mesh()
    a, b, c, d = (mesh.add_vertex(pos) for pos in ((0, 0, 0), (1, 0, 0), (0.5, 1, 0), (0.5, -1, 0)))
    first = mesh.add_face([a, b, c])
    second = mesh.add_face([b, a, d])

    (new_face,) = mesh.dissolve_edges([_edge(mesh, a, b)], cleanup=True)

    assert_mesh_invariants(mesh)
    assert set(mesh.face_vertices(new_face)) == {a, b, c, d}
    assert not mesh.is_valid_face(first) and not mesh.is_valid_face(second)


def test_dissolve_edges_noop_and_errors() -> None:
    mesh, p, f = _grid(2)
    before = mesh.export_state()
    assert mesh.dissolve_edges([], cleanup=True) == []
    assert mesh.export_state() == before
    border = _edge(mesh, p[(0, 0)], p[(0, 1)])
    _assert_refused(mesh, lambda: mesh.dissolve_edges([border], cleanup=True))
    _assert_refused(mesh, lambda: mesh.dissolve_edges([type(border)(999)], cleanup=False))
    with pytest.raises(TypeError):  # cleanup ist explizit, ohne Default
        mesh.dissolve_edges([_edge(mesh, p[(0, 1)], p[(1, 1)])])


def test_dissolve_edges_ring_around_vertex_with_hole_is_refused() -> None:
    """Edges eines geschlossenen Rings um eine nicht ausgewählte Face ergäben
    eine Face mit Loch -> abgelehnt."""
    mesh, p, f = _grid(3)
    ring = set()
    for fid in f.values():
        if fid == f[(1, 1)]:
            continue
        for eid in mesh.face_edges(fid):
            faces = mesh.edge_faces(eid)
            if len(faces) == 2 and f[(1, 1)] not in faces:
                ring.add(eid)
    _assert_refused(mesh, lambda: mesh.dissolve_edges(sorted(ring), cleanup=True))


# ---------------------------------------------------------------------------
# dissolve_faces
# ---------------------------------------------------------------------------

def test_dissolve_faces_id_continuity_and_both_variants() -> None:
    for cleanup, expected in ((False, [4, 4, 4, 4, 6]), (True, [3, 3, 4, 4, 4])):
        mesh = create_cube()
        pair = mesh.edge_faces(mesh.all_edge_ids()[0])
        verts, edges, faces = _ids(mesh)

        (new_face,) = mesh.dissolve_faces(pair, cleanup=cleanup)

        assert_mesh_invariants(mesh)
        assert _face_sizes(mesh) == expected
        v_after, e_after, f_after = _ids(mesh)
        assert f_after == (faces - set(pair)) | {new_face}
        if not cleanup:
            assert v_after == verts
            assert len(edges - e_after) == 1 and e_after <= edges
        else:
            assert len(verts - v_after) == 2


def test_dissolve_faces_region_and_single_faces() -> None:
    mesh, p, f = _grid(3)
    block = [f[(0, 0)], f[(0, 1)], f[(1, 0)], f[(1, 1)]]
    lone = f[(2, 2)]
    lone_boundary = mesh.face_vertices(lone)

    new_faces = mesh.dissolve_faces(block + [lone], cleanup=False)

    assert_mesh_invariants(mesh)
    assert len(new_faces) == 1  # die Einzel-Face ohne Nachbarn bleibt
    assert mesh.face_vertices(lone) == lone_boundary
    assert not mesh.is_valid_vertex(p[(1, 1)])  # Innen-Vertex ist kantenlos -> weg
    assert len(mesh.face_vertices(new_faces[0])) == 8
    assert _signed_area_z(mesh, new_faces[0]) > 0


def test_dissolve_faces_two_separate_regions() -> None:
    mesh, _, f = _grid(3)
    new_faces = mesh.dissolve_faces([f[(0, 0)], f[(0, 1)], f[(2, 1)], f[(2, 2)]], cleanup=False)
    assert_mesh_invariants(mesh)
    assert len(new_faces) == 2
    assert int(new_faces[0]) < int(new_faces[1])


def test_dissolve_faces_noop_cases() -> None:
    mesh, _, f = _grid(3)
    before = mesh.export_state()
    assert mesh.dissolve_faces([], cleanup=True) == []
    assert mesh.dissolve_faces([f[(1, 1)]], cleanup=True) == []
    assert mesh.dissolve_faces([f[(0, 0)], f[(2, 2)]], cleanup=True) == []  # nur Eckkontakt
    assert mesh.export_state() == before


def test_dissolve_faces_errors() -> None:
    mesh, _, f = _grid(3)
    ring = [fid for key, fid in f.items() if key != (1, 1)]
    _assert_refused(mesh, lambda: mesh.dissolve_faces(ring, cleanup=True))  # Loch
    _assert_refused(mesh, lambda: mesh.dissolve_faces([type(ring[0])(999)], cleanup=False))
    # Rand berührt sich in einem Vertex: (1,1) und (2,2) liegen diagonal an
    # p(2,2) und sind über einen Umweg verbunden.
    big, _, g = _grid(4)
    touching = [g[k] for k in ((1, 1), (0, 1), (0, 2), (0, 3), (1, 3), (2, 3), (2, 2))]
    _assert_refused(big, lambda: big.dissolve_faces(touching, cleanup=False))


# ---------------------------------------------------------------------------
# dissolve_vertex
# ---------------------------------------------------------------------------

def test_dissolve_vertex_interior_merges_fan() -> None:
    mesh, p, f = _grid(2)
    center = p[(1, 1)]
    spokes = set(mesh.vertex_edges(center))
    verts, edges, faces = _ids(mesh)

    new_face = mesh.dissolve_vertex(center)

    assert_mesh_invariants(mesh)
    assert _ids(mesh) == (verts - {center}, edges - spokes, {new_face})
    assert len(mesh.face_vertices(new_face)) == 8  # keine Variante: 2er-Vertices bleiben
    assert _signed_area_z(mesh, new_face) > 0


def test_dissolve_vertex_cube_corner() -> None:
    mesh = create_cube()
    corner = mesh.all_vertex_ids()[0]
    new_face = mesh.dissolve_vertex(corner)
    assert_mesh_invariants(mesh)
    assert len(mesh.face_vertices(new_face)) == 6
    assert _face_sizes(mesh) == [4, 4, 4, 6]


def test_dissolve_vertex_open_fan_on_border() -> None:
    mesh, p, f = _grid(2)
    v = p[(0, 1)]
    verts, edges, _ = _ids(mesh)

    new_face = mesh.dissolve_vertex(v)

    assert_mesh_invariants(mesh)
    v_after, e_after, _ = _ids(mesh)
    assert v_after == verts - {v}
    (new_edge,) = e_after - edges
    assert set(mesh.edge_vertices(new_edge)) == {p[(0, 0)], p[(0, 2)]}
    assert len(mesh.face_vertices(new_face)) == 5


def test_dissolve_vertex_two_valent_reverses_split_edge() -> None:
    mesh, p, f = _grid(2)
    before_boundaries = {fid: mesh.face_vertices(fid) for fid in mesh.all_face_ids()}
    eid = _edge(mesh, p[(1, 0)], p[(1, 1)])
    mid, _, _ = mesh.split_edge(eid)

    assert mesh.dissolve_vertex(mid) is None

    assert_mesh_invariants(mesh)
    assert not mesh.is_valid_vertex(mid)
    assert {fid: mesh.face_vertices(fid) for fid in mesh.all_face_ids()} == before_boundaries
    new_edge = _edge(mesh, p[(1, 0)], p[(1, 1)])
    assert new_edge != eid  # neue EdgeId, Faces behalten ihre IDs


def test_dissolve_vertex_two_valent_wire() -> None:
    mesh = Mesh()
    a, b, c = (mesh.add_vertex((float(i), 0.0, 0.0)) for i in range(3))
    mesh.add_edge(a, b)
    mesh.add_edge(b, c)
    assert mesh.dissolve_vertex(b) is None
    assert_mesh_invariants(mesh)
    assert [set(mesh.edge_vertices(e)) for e in mesh.all_edge_ids()] == [{a, c}]


def test_dissolve_vertex_errors() -> None:
    mesh, p, f = _grid(2)
    _assert_refused(mesh, lambda: mesh.dissolve_vertex(type(p[(0, 0)])(999)))
    # Valenz 2 an einem Dreieck: Face fiele unter 3 Vertices.
    tri = Mesh()
    a, b, c = (tri.add_vertex(pos) for pos in ((0, 0, 0), (1, 0, 0), (0, 1, 0)))
    tri.add_face([a, b, c])
    _assert_refused(tri, lambda: tri.dissolve_vertex(a))
    # Valenz 1 (Wire-Ende) und Wire-Edge an einem Fan-Vertex.
    lone = mesh.add_vertex((5.0, 5.0, 0.0))
    mesh.add_edge(p[(1, 1)], lone)
    _assert_refused(mesh, lambda: mesh.dissolve_vertex(lone))
    _assert_refused(mesh, lambda: mesh.dissolve_vertex(p[(1, 1)]))


def test_dissolve_vertex_refused_when_replacement_edge_exists() -> None:
    mesh = Mesh()
    a, v, b, c, x = (mesh.add_vertex(pos) for pos in ((0, 0, 0), (0.5, -0.2, 0), (1, 0, 0), (0.5, 1, 0), (0.5, -1, 0)))
    mesh.add_face([a, v, b, c])
    mesh.add_face([b, a, x])  # a-b existiert schon als Edge
    _assert_refused(mesh, lambda: mesh.dissolve_vertex(v))


def test_dissolve_vertex_bowtie_is_refused() -> None:
    mesh = Mesh()
    o = mesh.add_vertex((0, 0, 0))
    a, b = mesh.add_vertex((1, 0, 0)), mesh.add_vertex((1, 1, 0))
    c, d = mesh.add_vertex((-1, 0, 0)), mesh.add_vertex((-1, -1, 0))
    mesh.add_face([o, a, b])
    mesh.add_face([o, c, d])
    _assert_refused(mesh, lambda: mesh.dissolve_vertex(o))


# ---------------------------------------------------------------------------
# Querschnitt: Undo/Redo, Serialisierung, Symmetry Definition
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "op",
    [
        lambda m, p, f: m.delete_faces([f[(0, 0)], f[(0, 1)]]),
        lambda m, p, f: m.delete_edges([_edge(m, p[(1, 1)], p[(1, 2)])]),
        lambda m, p, f: m.delete_vertices([p[(1, 1)]]),
        lambda m, p, f: m.dissolve_vertex(p[(1, 1)]),
        lambda m, p, f: m.dissolve_edges([_edge(m, p[(1, 1)], p[(1, 2)])], cleanup=True),
        lambda m, p, f: m.dissolve_faces([f[(0, 0)], f[(1, 0)]], cleanup=False),
    ],
)
def test_undo_redo_roundtrip_and_serialization(op) -> None:
    mesh, p, f = _grid(2)
    seam = frozenset({_edge(mesh, p[(0, 1)], p[(1, 1)])})
    definition = SymmetryDefinition((1.0, 0.0, 0.0), (1.0, 0.0, 0.0), seam)
    mesh.symmetry_definition = definition
    history = HistoryStack()
    before = mesh.export_state()

    op(mesh, p, f)
    after = mesh.export_state()
    history.push(MeshStateCommand(mesh=mesh, before_state=before, after_state=after, description="t"))

    assert mesh.symmetry_definition == definition  # Definition wird nicht angefasst
    assert Mesh.from_state(after).export_state() == after
    history.undo()
    assert {k: v for k, v in mesh.export_state().items() if not k.endswith("_counter")} == {
        k: v for k, v in before.items() if not k.endswith("_counter")
    }
    history.redo()
    assert mesh.export_state() == after
    assert_mesh_invariants(mesh)
