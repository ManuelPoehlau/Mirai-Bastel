"""Gespiegelter Knife, headless (Handoff Slice 6 §2 A8–A11 / E16–E22, §7).

Charakterisierung P1–P3 (Ebene X, Seam aus Slice 3 E3) und Verhalten der
Lab-Engine `lab_knife`. Die Zahlen sind Charakterisierung der heutigen
Assets, keine Capability-Regel. Positionen werden exakt verglichen (A5).
"""

from __future__ import annotations

import pytest

from core import Scene
from core.operations.topology import MeshStateCommand
from mirai.application import Application
from mirai.interaction.tool import ToolState
from mirai.symmetry import (
    CorrespondenceState,
    SymmetryState,
    mirror_position,
    symmetry_state,
    vertex_correspondence,
)

from symmetry_lab import lab_knife
from symmetry_lab.lab_knife import (
    CHECK_POSITION,
    KnifeRejected,
    LabKnifeTool,
    connect_in_shared_face,
    edge_between,
    validate_step,
)
from symmetry_lab.lab_scene import load_asset_into
from symmetry_lab.lab_symmetry import definition_for_axis
from symmetry_lab.lab_topology import topological_pairing, topological_sides, topology_report

PLANE = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0))


# -- Hilfen --------------------------------------------------------------------------


def make_scene(asset: str, axis: str | None = "X") -> Scene:
    app = Application()
    load_asset_into(app, asset)
    mesh = app.scene.mesh
    mesh.symmetry_definition = definition_for_axis(mesh, axis)
    return app.scene


def start_knife(scene: Scene) -> LabKnifeTool:
    knife = LabKnifeTool()
    knife.activate()
    knife.begin(mesh=scene.mesh, scene=scene)
    return knife


def plus_quad(mesh):
    """Niedrigste FaceId unter den Quads mit allen Vertices auf +X (subd_cube 12, head 163)."""
    return min(
        (
            f for f in mesh.all_face_ids()
            if len(mesh.face_vertices(f)) == 4
            and all(mesh.vertex_position(v)[0] > 0 for v in mesh.face_vertices(f))
        ),
        key=int,
    )


def quad_edges(mesh, face):
    """Zwei gegenüberliegende Edges der Quad: (v0, v1) und (v2, v3)."""
    vs = mesh.face_vertices(face)
    return edge_between(mesh, vs[0], vs[1]), edge_between(mesh, vs[2], vs[3])


def seam_quad(mesh, sign: float = 1.0):
    """Quad mit genau einer Seam-Edge, die übrigen Vertices auf der Seite `sign`.

    Rückgabe: (face, seam_edge, gegenüberliegende Edge).
    """
    seam = mesh.symmetry_definition.seam_edges
    for f in sorted(mesh.all_face_ids(), key=int):
        vs = mesh.face_vertices(f)
        if len(vs) != 4:
            continue
        edges = [edge_between(mesh, vs[i], vs[(i + 1) % 4]) for i in range(4)]
        on_seam = [i for i, e in enumerate(edges) if e in seam]
        off = [v for v in vs if mesh.vertex_position(v)[0] != 0.0]
        if len(on_seam) == 1 and len(off) == 2 and all(
            mesh.vertex_position(v)[0] * sign > 0 for v in off
        ):
            i = on_seam[0]
            return f, edges[i], edges[(i + 2) % 4]
    raise AssertionError("keine Seam-Quad gefunden")


def edge(eid, t=0.5):
    return {"kind": "edge", "edge_id": eid, "t": t}


def vertex(vid):
    return {"kind": "vertex", "vertex_id": vid}


def counts(mesh):
    report = topology_report(mesh)
    return (
        symmetry_state(mesh),
        len(report.pairing.partners),
        len(mesh.all_vertex_ids()),
        report.sides.faces_per_side(),
    )


def assert_pairs_confirmed(mesh, intent_pairs):
    corr = vertex_correspondence(mesh)
    partners = topological_pairing(mesh).partners
    assert intent_pairs
    for x, y in intent_pairs.items():
        if x == y:
            assert corr[x].state is CorrespondenceState.SEAM
        else:
            assert corr[x] == corr[x].__class__(CorrespondenceState.PAIRED, y)
        assert partners[x] == y


def mirror(p):
    return mirror_position(p, *PLANE)


_COUNTERS = ("vertex_id_counter", "edge_id_counter", "face_id_counter")


def content(mesh) -> dict:
    """`export_state()` ohne die ID-Zähler — sonst bitgenau.

    `load_state` setzt die Zähler nur vorwärts (AD-001: eine vergebene ID wird
    nie wieder ausgegeben, auch nicht nach Undo). Nach Undo/Cancel/Rollback
    sind Vertices, Edges, Faces und Symmetrie-Definition bitgleich, die Zähler
    bleiben auf dem höheren Stand. Gleiche Ausnahme wie `_topo_snapshot` in
    den Playground-Knife-Tests.
    """
    state = mesh.export_state()
    return {k: v for k, v in state.items() if k not in _COUNTERS}


# -- Charakterisierung P1–P3 (§7) --------------------------------------------------


BASELINE = [
    # asset, Vertices, Faces je Seite, Seam-Edges
    ("subd_cube", 26, 12, 8),
    ("head_basemesh", 326, 162, 36),
]


@pytest.mark.parametrize("asset,vertices,faces,_seam", BASELINE)
def test_baseline(asset, vertices, faces, _seam):
    mesh = make_scene(asset).mesh
    assert counts(mesh) == (SymmetryState.VALID, vertices, vertices, [faces, faces])


@pytest.mark.parametrize("asset,vertices,_faces,seam", BASELINE)
def test_p1_raw_seam_split_without_tracking_breaks_seam(asset, vertices, _faces, seam):
    mesh = make_scene(asset).mesh
    definition = mesh.symmetry_definition
    new_vertex, _, _ = mesh.split_edge(min(definition.seam_edges, key=int), 0.37)
    assert mesh.vertex_position(new_vertex)[0] == 0.0
    assert symmetry_state(mesh) is SymmetryState.PARTIAL
    assert sum(mesh.is_valid_edge(e) for e in definition.seam_edges) == seam - 1
    assert topological_sides(mesh).component_count == 1


P2 = [
    # asset, Vertices danach, Face-Paar-Konflikte
    ("subd_cube", 28, 40),
    ("head_basemesh", 328, 644),
]


def one_sided_cut(mesh):
    face = plus_quad(mesh)
    e1, e2 = quad_edges(mesh, face)
    a, _, _ = mesh.split_edge(e1, 0.3)
    b, _, _ = mesh.split_edge(e2, 0.6)
    return mesh.connect_vertices(face, a, b)


@pytest.mark.parametrize("asset,vertices,face_pair_conflicts", P2)
def test_p2_one_sided_cut_collapses_topological_pairing(asset, vertices, face_pair_conflicts):
    mesh = make_scene(asset).mesh
    one_sided_cut(mesh)
    pairing = topological_pairing(mesh)
    assert len(mesh.all_vertex_ids()) == vertices
    assert len(pairing.partners) == 0
    assert len(pairing.conflicts) == vertices
    assert pairing.face_pair_conflicts == face_pair_conflicts


@pytest.mark.parametrize("asset", ["subd_cube", "head_basemesh"])
def test_p2_observation_halves_are_quads_like_their_uncut_mirror(asset):
    """README-Beobachtung zu P2: beide Hälften der geschnittenen Quad sind wieder
    4-Ecke — also gleich lang wie die ungeschnittene Spiegel-Quad — und selbst
    die Seam-Vertices landen im Konflikt."""
    mesh = make_scene(asset).mesh
    mirror_face_vertices = {
        vertex_correspondence(mesh)[v].partner for v in mesh.face_vertices(plus_quad(mesh))
    }
    seam_vertices = {
        v for e in mesh.symmetry_definition.seam_edges for v in mesh.edge_vertices(e)
    }
    _, half_1, half_2 = one_sided_cut(mesh)
    mirror_face = next(
        f for f in mesh.all_face_ids() if set(mesh.face_vertices(f)) == mirror_face_vertices
    )
    assert [len(mesh.face_vertices(f)) for f in (half_1, half_2, mirror_face)] == [4, 4, 4]
    assert seam_vertices <= topological_pairing(mesh).conflicts


def test_p2_counter_checks_single_operations():
    # einseitiger split_edge allein → topo 326/327 (Slice-5-README)
    mesh = make_scene("head_basemesh").mesh
    mesh.split_edge(quad_edges(mesh, plus_quad(mesh))[0], 0.3)
    assert (len(topological_pairing(mesh).partners), len(mesh.all_vertex_ids())) == (326, 327)
    # einseitiger connect_vertices allein → Position valid, Topologie asymmetrisch
    mesh = make_scene("head_basemesh").mesh
    face = plus_quad(mesh)
    vs = mesh.face_vertices(face)
    mesh.connect_vertices(face, vs[0], vs[2])
    assert symmetry_state(mesh) is SymmetryState.VALID
    assert topological_pairing(mesh).face_pair_conflicts > 0


def mirrored_cut_via_t(mesh, mirror_t):
    """Gespiegelter Schnitt von Hand; `mirror_t(t)` bestimmt die Platzierung auf der Spiegel-Edge."""
    corr = vertex_correspondence(mesh)
    face = plus_quad(mesh)
    vs = mesh.face_vertices(face)
    mirror_face_vertices = {corr[v].partner for v in vs}
    new = []
    offsets = []
    for (x, y), t in (((vs[0], vs[1]), 0.3), ((vs[2], vs[3]), 0.6)):
        e = edge_between(mesh, x, y)
        me = edge_between(mesh, corr[x].partner, corr[y].partner)
        # Charakterisierung: auf beiden Assets sind die Spiegel-Edges umgekehrt orientiert.
        assert mesh.edge_vertices(me)[0] == corr[mesh.edge_vertices(e)[1]].partner
        n, _, _ = mesh.split_edge(e, t)
        n2, _, _ = mesh.split_edge(me, mirror_t(t))
        new.append((n, n2))
        offsets.append(
            max(abs(a - b) for a, b in zip(mirror(mesh.vertex_position(n)), mesh.vertex_position(n2)))
        )
    mirror_face = next(
        f for f in mesh.all_face_ids() if set(mesh.face_vertices(f)) >= mirror_face_vertices
        and len(mesh.face_vertices(f)) == 6
    )
    mesh.connect_vertices(face, new[0][0], new[1][0])
    mesh.connect_vertices(mirror_face, new[0][1], new[1][1])
    return new, offsets


def test_p3_mirror_via_one_minus_t_misses_by_one_ulp_on_subd_cube():
    mesh = make_scene("subd_cube").mesh
    _, offsets = mirrored_cut_via_t(mesh, lambda t: 1.0 - t)
    assert sorted(offsets) == [0.0, 1.1102230246251565e-16]
    assert symmetry_state(mesh) is SymmetryState.PARTIAL
    assert (len(topological_pairing(mesh).partners), len(mesh.all_vertex_ids())) == (30, 30)


def test_p3_mirror_via_one_minus_t_is_exact_on_head():
    mesh = make_scene("head_basemesh").mesh
    _, offsets = mirrored_cut_via_t(mesh, lambda t: 1.0 - t)
    assert offsets == [0.0, 0.0]
    assert counts(mesh) == (SymmetryState.VALID, 330, 330, [163, 163])


def test_p3_prime_mirror_position_is_valid_on_subd_cube():
    mesh = make_scene("subd_cube").mesh
    new, _ = mirrored_cut_via_t(mesh, lambda t: 0.5)
    for n, n2 in new:
        mesh.set_vertex_position(n2, mirror(mesh.vertex_position(n)))
    assert counts(mesh) == (SymmetryState.VALID, 30, 30, [13, 13])


# -- Gespiegelter Schnitt (E17/E18/E19) --------------------------------------------


CUT = [
    # asset, Vertices danach, Faces je Seite danach
    ("subd_cube", 30, 13),
    ("head_basemesh", 330, 163),
]


@pytest.mark.parametrize("asset,vertices,faces", CUT)
def test_mirrored_edge_to_edge_cut_is_valid_and_confirmed(asset, vertices, faces):
    scene = make_scene(asset)
    mesh = scene.mesh
    knife = start_knife(scene)
    assert knife.mirrored
    e1, e2 = quad_edges(mesh, plus_quad(mesh))
    assert knife.click(edge(e1, 0.3))
    assert knife.click(edge(e2, 0.6))
    assert counts(mesh) == (SymmetryState.VALID, vertices, vertices, [faces, faces])
    assert len(knife.intent_pairs) == 4
    assert_pairs_confirmed(mesh, knife.intent_pairs)
    assert knife.last_validation.ok and knife.last_validation.failed == ()
    assert validate_step(mesh, knife.intent_pairs) == knife.last_validation
    assert len(knife.path_edges) == 2
    for n, n2 in knife.intent_pairs.items():
        assert mesh.vertex_position(n2) == mirror(mesh.vertex_position(n))


def _next_edge(mesh, start):
    """Eine Edge einer Face am Start, nicht am Start, beide Endpunkte auf +X."""
    faces = {f for e in mesh.vertex_edges(start) for f in mesh.edge_faces(e)}
    for f in sorted(faces, key=int):
        vs = mesh.face_vertices(f)
        for i in range(len(vs)):
            a, b = vs[i], vs[(i + 1) % len(vs)]
            if start in (a, b):
                continue
            if all(mesh.vertex_position(v)[0] > 0 for v in (a, b)):
                return edge_between(mesh, a, b)
    raise AssertionError("keine nächste Edge")


def run_session(asset, steps=4):
    scene = make_scene(asset)
    mesh = scene.mesh
    before = content(mesh)
    knife = start_knife(scene)
    e1, e2 = quad_edges(mesh, plus_quad(mesh))
    assert knife.click(edge(e1, 0.3))
    assert knife.click(edge(e2, 0.6))
    for _ in range(steps - 2):
        assert knife.click(edge(_next_edge(mesh, knife.start), 0.4)), knife.last_message
        assert knife.last_validation.ok
        assert symmetry_state(mesh) is SymmetryState.VALID
    return scene, knife, before


@pytest.mark.parametrize("asset", ["subd_cube", "head_basemesh"])
def test_session_of_several_steps_commits_one_history_entry(asset):
    scene, knife, before = run_session(asset)
    mesh = scene.mesh
    assert_pairs_confirmed(mesh, knife.intent_pairs)
    assert topological_sides(mesh).component_count == 2
    after = mesh.export_state()  # Redo: auch die Zähler bitgleich
    cmd = knife.commit()
    assert isinstance(cmd, MeshStateCommand)
    assert scene.history.can_undo()
    scene.history.undo()
    assert content(mesh) == before
    assert not scene.history.can_undo()  # genau ein Eintrag
    scene.history.redo()
    assert mesh.export_state() == after


def test_in_session_undo_and_redo_cover_both_sides():
    scene, knife, _ = run_session("subd_cube", steps=2)
    mesh = scene.mesh

    def session():
        return (content(mesh), knife.start, knife.path_edges, knife.intent_pairs)

    middle = session()
    assert knife.click(edge(_next_edge(mesh, knife.start), 0.4))
    assert len(knife.intent_pairs) == 6
    after = (mesh.export_state(), knife.start, knife.path_edges, knife.intent_pairs)
    assert knife.undo_step()
    assert session() == middle  # beide Seiten + intent_pairs zurück
    assert symmetry_state(mesh) is SymmetryState.VALID
    assert knife.redo_step()
    assert (mesh.export_state(), knife.start, knife.path_edges, knife.intent_pairs) == after


def test_cancel_restores_state_before_session_without_history():
    scene, knife, before = run_session("head_basemesh", steps=3)
    knife.cancel()
    assert content(scene.mesh) == before
    assert not scene.history.can_undo()
    assert knife.intent_pairs == {} and knife.start is None


def test_commit_without_change_creates_no_entry():
    scene = make_scene("subd_cube")
    knife = start_knife(scene)
    assert knife.click(vertex(scene.mesh.all_vertex_ids()[0]))
    assert knife.commit() is None
    assert not scene.history.can_undo()


def test_knife_does_not_touch_selection():
    scene = make_scene("subd_cube")
    v = scene.mesh.all_vertex_ids()[0]
    scene.selection.set({v})
    knife = start_knife(scene)
    e1, e2 = quad_edges(scene.mesh, plus_quad(scene.mesh))
    knife.click(edge(e1, 0.3))
    knife.click(edge(e2, 0.6))
    knife.commit()
    assert scene.selection.vertices == {v} and scene.selection.edges == set()


# -- Seam (E18) --------------------------------------------------------------------


@pytest.mark.parametrize("asset", ["subd_cube", "head_basemesh"])
def test_cut_onto_seam_edge_tracks_seam(asset):
    scene = make_scene(asset)
    mesh = scene.mesh
    old_definition = mesh.symmetry_definition
    _, seam_edge, opposite = seam_quad(mesh)
    knife = start_knife(scene)
    assert knife.click(edge(opposite, 0.3))
    assert knife.click(edge(seam_edge, 0.37)), knife.last_message
    m = knife.start
    assert knife.intent_pairs[m] == m
    assert mesh.vertex_position(m)[0] == 0.0
    definition = mesh.symmetry_definition
    assert seam_edge not in definition.seam_edges
    halves = {e for e in mesh.vertex_edges(m) if e in definition.seam_edges}
    assert len(halves) == 2
    assert definition.seam_edges == (old_definition.seam_edges - {seam_edge}) | halves
    assert (definition.plane_point, definition.plane_normal) == PLANE
    assert topological_sides(mesh).component_count == 2
    assert symmetry_state(mesh) is SymmetryState.VALID
    assert_pairs_confirmed(mesh, knife.intent_pairs)
    # In-Session-Undo nimmt auch die Seam-Nachführung zurück.
    assert knife.undo_step()
    assert mesh.symmetry_definition == old_definition


@pytest.mark.parametrize("sign", [1.0, -1.0])
def test_cut_across_the_middle_from_a_seam_vertex(sign):
    scene = make_scene("subd_cube")
    mesh = scene.mesh
    face, seam_edge, opposite = seam_quad(mesh, sign)
    knife = start_knife(scene)
    s = mesh.edge_vertices(seam_edge)[0]
    assert knife.click(vertex(s))
    assert knife.click(edge(opposite, 0.3)), knife.last_message
    n = knife.start
    n2 = knife.intent_pairs[n]
    assert mesh.vertex_position(n)[0] * sign > 0 > mesh.vertex_position(n2)[0] * sign
    assert edge_between(mesh, s, n) is not None and edge_between(mesh, s, n2) is not None
    assert counts(mesh) == (SymmetryState.VALID, 28, 28, [13, 13])
    assert_pairs_confirmed(mesh, knife.intent_pairs)


def test_clicking_the_existing_mirror_point_after_reaching_the_seam_is_rejected():
    """Beobachtung (§7): Nach a → m (m auf der Seam) existiert m–a' schon."""
    scene = make_scene("subd_cube")
    mesh = scene.mesh
    _, seam_edge, opposite = seam_quad(mesh)
    knife = start_knife(scene)
    assert knife.click(edge(opposite, 0.3))
    a = knife.start
    a2 = knife.intent_pairs[a]
    assert knife.click(edge(seam_edge, 0.5))
    m = knife.start
    before = (content(mesh), knife.start, knife.path_edges, knife.intent_pairs)
    edges_before = len(mesh.all_edge_ids())
    assert knife.click(vertex(a2)) is False
    assert "existiert bereits" in knife.last_message
    assert (content(mesh), knife.start, knife.path_edges, knife.intent_pairs) == before
    assert len(mesh.all_edge_ids()) == edges_before
    assert edge_between(mesh, m, a2) is not None


def test_seam_chord_is_rejected():
    scene = make_scene("subd_cube")
    mesh = scene.mesh
    _, seam_edge, _ = seam_quad(mesh)
    s1, s2 = mesh.edge_vertices(seam_edge)
    knife = start_knife(scene)
    assert knife.click(edge(seam_edge, 0.5))  # m
    knife.commit()
    assert symmetry_state(mesh) is SymmetryState.VALID
    # s1 und s2 liegen jetzt in derselben Face, getrennt durch m.
    shared = [f for f in mesh.all_face_ids() if {s1, s2} <= set(mesh.face_vertices(f))]
    assert shared
    before = content(mesh)
    knife = start_knife(scene)
    assert knife.click(vertex(s1))
    assert knife.click(vertex(s2)) is False
    assert "entlang der Seam" in knife.last_message
    assert content(mesh) == before
    assert knife.start == s1


# -- Gate (E20) --------------------------------------------------------------------


@pytest.mark.parametrize("asset,axis", [("man_with_shoes_basemesh", "X"), ("subd_cube", "Y")])
def test_begin_is_rejected_unless_valid_with_two_sides(asset, axis):
    scene = make_scene(asset, axis)
    before = content(scene.mesh)
    knife = LabKnifeTool()
    knife.activate()
    with pytest.raises(KnifeRejected) as exc:
        knife.begin(mesh=scene.mesh, scene=scene)
    assert knife.state is ToolState.ACTIVE
    assert "nicht gestartet" in str(exc.value)
    assert content(scene.mesh) == before


# -- Rollback (A11) ----------------------------------------------------------------


def test_one_minus_t_placement_fails_position_and_rolls_back(monkeypatch):
    def split_via_one_minus_t(self, mirror_edge, source_vertex):
        return self._mesh.split_edge(mirror_edge, 1.0 - 0.3)[0]

    monkeypatch.setattr(LabKnifeTool, "_split_mirror_edge", split_via_one_minus_t)
    scene = make_scene("subd_cube")
    mesh = scene.mesh
    knife = start_knife(scene)
    e1, _ = quad_edges(mesh, plus_quad(mesh))
    before = (content(mesh), knife.start, knife.path_edges, knife.intent_pairs)
    assert knife.click(edge(e1, 0.3)) is False
    assert (content(mesh), knife.start, knife.path_edges, knife.intent_pairs) == before
    validation = knife.last_validation
    assert CHECK_POSITION in validation.failed
    assert CHECK_POSITION in knife.last_message
    # Befund: Topologie bestätigt, Position nicht — die beiden Prüfungen urteilen unterschiedlich.
    assert validation.topology_ok and not validation.position_ok


def test_unresolvable_partner_rejects_without_mutation(monkeypatch):
    scene = make_scene("subd_cube")
    mesh = scene.mesh
    knife = start_knife(scene)
    monkeypatch.setattr(LabKnifeTool, "partner", lambda self, vid: None)
    e1, _ = quad_edges(mesh, plus_quad(mesh))
    before = content(mesh)
    assert knife.click(edge(e1, 0.3)) is False
    assert "Spiegelpartner" in knife.last_message
    assert content(mesh) == before


# -- Symmetrie aus: ungespiegelt wie im Playground (Portierung, Auswahl) -------------


def two_quads():
    """v0 - v1 - v4 / | f1 | f2 | / v3 - v2 - v5 — Symmetrie aus."""
    scene = Scene()
    mesh = scene.mesh
    v = [mesh.add_vertex(p) for p in (
        (0.0, 1.0, 0.0), (1.0, 1.0, 0.0), (1.0, 0.0, 0.0),
        (0.0, 0.0, 0.0), (2.0, 1.0, 0.0), (2.0, 0.0, 0.0),
    )]
    f1 = mesh.add_face([v[0], v[1], v[2], v[3]])
    f2 = mesh.add_face([v[1], v[4], v[5], v[2]])
    return scene, v, (f1, f2)


def test_unmirrored_first_click_edge_splits():
    scene, v, _ = two_quads()
    knife = start_knife(scene)
    assert not knife.mirrored
    e = edge_between(scene.mesh, v[0], v[1])
    assert knife.click(edge(e, 0.25))
    assert scene.mesh.vertex_position(knife.start) == (0.25, 1.0, 0.0)
    assert knife.intent_pairs == {}


def test_unmirrored_vertex_to_vertex_and_vertex_to_edge():
    scene, v, _ = two_quads()
    mesh = scene.mesh
    knife = start_knife(scene)
    assert knife.click(vertex(v[0]))
    assert knife.click(vertex(v[2]))
    assert edge_between(mesh, v[0], v[2]) is not None
    assert knife.click(edge(edge_between(mesh, v[4], v[5]), 0.5))
    assert len(knife.path_edges) == 2
    assert knife.last_validation is None  # ungespiegelt: keine Validierung


def test_unmirrored_rejections():
    scene, v, (f1, _) = two_quads()
    mesh = scene.mesh
    knife = start_knife(scene)
    assert knife.click({"kind": "face", "face_id": f1}) is False
    assert knife.click({"kind": "outside"}) is False
    assert knife.click(vertex(v[0]))
    assert knife.click(edge(edge_between(mesh, v[0], v[1]))) is False  # am Start
    assert knife.click(edge(edge_between(mesh, v[4], v[5]))) is False  # keine gemeinsame Face
    assert knife.click(vertex(v[1])) is False  # benachbart


def test_unmirrored_undo_redo_cancel_commit():
    scene, v, _ = two_quads()
    mesh = scene.mesh
    before = content(mesh)
    knife = start_knife(scene)
    knife.click(vertex(v[0]))
    knife.click(vertex(v[2]))
    after = content(mesh)
    assert knife.undo_step()
    assert content(mesh) == before and knife.start == v[0]
    assert knife.redo_step()
    assert content(mesh) == after
    assert knife.click({"kind": "outside"}) is False
    assert knife.undo_step()
    assert knife.redo_step()  # abgelehnter Klick lässt den Redo-Zweig stehen
    knife.cancel()
    assert content(mesh) == before
    assert not scene.history.can_undo()
    knife.begin(mesh=mesh, scene=scene)
    knife.click(vertex(v[0]))
    knife.click(vertex(v[2]))
    assert knife.commit() is not None
    scene.history.undo()
    assert content(mesh) == before


# -- Lab-Kopie connect_in_shared_face ---------------------------------------------


def test_connect_in_shared_face_returns_used_face_and_boundary():
    scene, v, (f1, _) = two_quads()
    mesh = scene.mesh
    boundary = tuple(mesh.face_vertices(f1))
    connection = connect_in_shared_face(mesh, v[0], v[2])
    assert connection.face == f1
    assert connection.boundary == boundary
    assert not mesh.is_valid_face(f1)
    assert edge_between(mesh, v[0], v[2]) == connection.edge
    assert connect_in_shared_face(mesh, v[0], v[4]) is None


def test_lab_knife_is_lab_local():
    assert lab_knife.__doc__.lstrip().startswith("Gespiegelter Knife — **Lab-Experiment**")
