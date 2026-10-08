"""AD-SYM-03 slice 3c: symmetric Delete, Dissolve and Dissolve (no cleanup) through the removal keys
(coordinator `coordinate_removal` in `mirai.symmetric_ops`, wired in `Application._removal_command`).

Headless, no gate: the coordinators run whenever a definition is set, in MARK as in BLOCK (AD-013 H2
amendment, "Runtime refusals are not G-3"); the Lab path is tested in
`experiments/symmetry_lab/tests/test_app_lab_symmetric_removal.py`.

Assets and helpers as in `tests/test_symmetric_ops.py`: plane x = 0, the x = 0 edges are the seam,
`subd_cube` / `head_basemesh` are fully paired, `man_with_shoes_basemesh` is `partial`.

Seam handling under test (AD-SYM-03 §6 A1; Case 1 is an Artist verdict, the rest an engineering
assumption): **Delete** drops the seam ids that no longer exist (M); **Dissolve** that would span the
plane or consume a seam id is refused with its own text (R, Case 2 stays UNKNOWN for the Artist).
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401 — production path src/core, src/mirai

from core import SelectionMode
from core.mesh import SymmetryDefinition
from mirai import symmetric_ops
from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.input import Input
from mirai.symmetric_ops import (
    TEXT_BOTH_SIDES_FACE,
    TEXT_DELTA,
    TEXT_NON_EXACT_PLANE,
    TEXT_SEAM_DISSOLVE,
    TEXT_UNPAIRED,
    SymmetryRefusal,
    coordinate_removal,
)
from mirai.symmetry import SymmetryState, symmetry_state
from mirai.symmetry_coordination import DeltaResult, SymmetryIndex, completeness_report
from mirai.topology.delete_dissolve import apply_removal
from tests.test_symmetric_ops import (
    CTRL_Y,
    CTRL_Z,
    ORIGIN,
    PAIRED_ASSETS,
    X,
    assert_clean,
    displaced_cube,
    edge_side,
    everything,
    far_from_unpaired,
    make_app,
    plus_side_edges,
    plus_x_quad,
    selection_state,
    spanning_face_app,
    topology_state,
)

DELETE = Input("key", "delete")
DISSOLVE = Input("key", "backspace")
DISSOLVE_NO_CLEANUP = Input("key", "backspace", frozenset({"ctrl"}))

V, E, F = SelectionMode.VERTEX, SelectionMode.EDGE, SelectionMode.FACE

#: (id, key, command, dissolve, cleanup)
COMMANDS = [
    ("delete", DELETE, cmd.DELETE, False, False),
    ("dissolve", DISSOLVE, cmd.DISSOLVE, True, True),
    ("dissolve_no_cleanup", DISSOLVE_NO_CLEANUP, cmd.DISSOLVE_NO_CLEANUP, True, False),
]
COMMAND_IDS = [c[0] for c in COMMANDS]


def select(app: Application, mode: SelectionMode, ids) -> None:
    app.selection.clear()
    app.selection.mode = mode
    setattr(app.selection, {V: "vertices", E: "edges", F: "faces"}[mode], set(ids))


def partner_of(mesh, mode: SelectionMode, element):
    index = SymmetryIndex(mesh)
    return {V: index.vertex_partner, E: index.edge_partner, F: index.face_partner}[mode](element)


def valid(mesh, mode: SelectionMode, element) -> bool:
    return {V: mesh.is_valid_vertex, E: mesh.is_valid_edge, F: mesh.is_valid_face}[mode](element)


def far_face_pair(mesh):
    """Two edge-adjacent +X faces, neither touching the seam (a Face Dissolve merges them)."""
    seam_vertices = {v for e in mesh.symmetry_definition.seam_edges for v in mesh.edge_vertices(e)}
    for f in sorted(mesh.all_face_ids()):
        if set(mesh.face_vertices(f)) & seam_vertices or min(mesh.vertex_position(v)[0] for v in mesh.face_vertices(f)) <= 0:
            continue
        for e in mesh.face_edges(f):
            for g in mesh.edge_faces(e):
                if g != f and not (set(mesh.face_vertices(g)) & seam_vertices) and min(
                    mesh.vertex_position(v)[0] for v in mesh.face_vertices(g)
                ) > 0:
                    return {f, g}
    raise LookupError("no +X face pair away from the seam")


def far_selection(app: Application, mode: SelectionMode, *, dissolve: bool) -> set:
    """One +X element away from the seam (a face pair for Face Dissolve: a single face has nothing to
    merge with)."""
    mesh = app.scene.mesh
    quad = plus_x_quad(mesh, touching_seam=False)
    if mode is V:
        return {mesh.face_vertices(quad)[0]}
    if mode is E:
        return {mesh.face_edges(quad)[0]}
    return far_face_pair(mesh) if dissolve else {quad}


def seam_edge_pair(mesh) -> set:
    """The two faces on either side of one seam edge (A1 Case 1)."""
    edge = next(e for e in sorted(mesh.symmetry_definition.seam_edges) if len(mesh.edge_faces(e)) == 2)
    return set(mesh.edge_faces(edge))


def seam_vertices(mesh) -> list:
    return sorted({v for e in mesh.symmetry_definition.seam_edges for v in mesh.edge_vertices(e)})


def assert_refused(app: Application, key: Input, text: str) -> None:
    """Visible refusal: the text is posted, no history entry, mesh, definition and selection (and
    its mirror stacks) unchanged."""
    before = everything(app)
    definition = app.scene.mesh.symmetry_definition
    serial = app.status_serial
    assert app.key_press(key) is False
    assert app.status_message == text
    assert app.status_serial == serial + 1
    assert everything(app) == before
    assert app.scene.mesh.symmetry_definition == definition


# -- one Undo step, symmetric result, report clean ----------------------------------------------


@pytest.mark.parametrize("name, key, command, dissolve, cleanup", COMMANDS, ids=COMMAND_IDS)
@pytest.mark.parametrize("mode", [V, E, F], ids=["vertex", "edge", "face"])
@pytest.mark.parametrize("asset", PAIRED_ASSETS)
def test_removal_is_one_undo_step_symmetric_and_clean(asset, mode, name, key, command, dissolve, cleanup):
    if command == cmd.DISSOLVE_NO_CLEANUP and mode is V:
        pytest.skip("Vertex Dissolve has no variant (the command does nothing there)")
    app = make_app(asset)
    mesh = app.scene.mesh
    selected = far_selection(app, mode, dissolve=dissolve)
    partners = {partner_of(mesh, mode, e) for e in selected}
    assert None not in partners and not partners & selected
    select(app, mode, selected)
    before = everything(app)
    definition = mesh.symmetry_definition
    selection_before = selection_state(app)

    assert app.key_press(key) is True
    assert len(app.history) == 1
    assert_clean(mesh)
    # Dissolve never touches the seam here; Delete may drop ids of seam edges that died with a
    # neighbouring face (the seam follows the mesh), never adds or leaves a dead one.
    seam_after = mesh.symmetry_definition.seam_edges
    assert seam_after <= definition.seam_edges and all(mesh.is_valid_edge(e) for e in seam_after)
    if dissolve:
        assert mesh.symmetry_definition == definition
    assert not any(valid(mesh, mode, e) for e in selected | partners) or mode is F and dissolve
    if mode is F and dissolve:
        # Face Dissolve merges: the originals are gone on both sides, the merged faces exist
        assert not any(mesh.is_valid_face(f) for f in selected | partners)
    after = topology_state(app)
    assert after != before[0]

    assert app.key_press(CTRL_Z) is True
    assert len(app.history) == 0
    assert topology_state(app) == before[0]
    assert selection_state(app) == selection_before
    assert mesh.symmetry_definition == definition
    assert app.key_press(CTRL_Y) is True
    assert topology_state(app) == after
    assert len(app.history) == 1


@pytest.mark.parametrize("asset", PAIRED_ASSETS)
def test_a_two_sided_selection_counts_once_and_gives_the_same_result(asset):
    """A mirror pair is one intent: the result equals the one-sided selection's."""
    for mode in (V, E, F):
        one, two = make_app(asset), make_app(asset)
        mesh = two.scene.mesh
        selected = far_selection(one, mode, dissolve=False)
        select(one, mode, selected)
        select(two, mode, selected | {partner_of(mesh, mode, e) for e in selected})
        assert one.key_press(DELETE) is True and two.key_press(DELETE) is True
        assert topology_state(one) == topology_state(two)


# -- residue --------------------------------------------------------------------------------------


@pytest.mark.parametrize("name, key, command, dissolve, cleanup", COMMANDS, ids=COMMAND_IDS)
@pytest.mark.parametrize("mode", [V, E], ids=["vertex", "edge"])
def test_residue_of_delete_and_vertex_edge_dissolve_is_a_cleared_selection_in_the_same_mode(
    mode, name, key, command, dissolve, cleanup
):
    if command == cmd.DISSOLVE_NO_CLEANUP and mode is V:
        pytest.skip("no variant")
    app = make_app("subd_cube")
    select(app, mode, far_selection(app, mode, dissolve=dissolve))
    assert app.key_press(key) is True
    s = app.selection
    assert s.mode is mode and not (s.vertices or s.edges or s.faces)


def merged_face_sides(mesh, faces) -> set:
    return {
        (lambda total: (total > 0) - (total < 0))(sum(mesh.vertex_position(v)[0] for v in mesh.face_vertices(f)))
        for f in faces
    }


@pytest.mark.parametrize("worked_on", [1, -1], ids=["plus_x", "minus_x"])
@pytest.mark.parametrize("key", [DISSOLVE, DISSOLVE_NO_CLEANUP], ids=["dissolve", "dissolve_no_cleanup"])
@pytest.mark.parametrize("asset", PAIRED_ASSETS)
def test_face_dissolve_selects_the_merged_faces_on_the_side_worked_on(asset, key, worked_on):
    app = make_app(asset)
    mesh = app.scene.mesh
    faces = far_face_pair(mesh)
    if worked_on < 0:
        faces = {partner_of(mesh, F, f) for f in faces}
    select(app, F, faces)
    selection_before = selection_state(app)
    faces_before = set(mesh.all_face_ids())
    assert app.key_press(key) is True
    merged = set(mesh.all_face_ids()) - faces_before
    assert len(merged) == 2  # one merged face per side
    selected = set(app.selection.faces)
    assert app.selection.mode is F
    assert selected and selected < merged
    assert merged_face_sides(mesh, selected) == {worked_on}
    assert app.key_press(CTRL_Z) is True
    assert selection_state(app) == selection_before


def test_face_dissolve_with_both_sides_selected_selects_the_merged_faces_of_both():
    app = make_app("subd_cube")
    mesh = app.scene.mesh
    faces = far_face_pair(mesh)
    select(app, F, faces | {partner_of(mesh, F, f) for f in faces})
    faces_before = set(mesh.all_face_ids())
    assert app.key_press(DISSOLVE) is True
    merged = set(mesh.all_face_ids()) - faces_before
    assert set(app.selection.faces) == merged and len(merged) == 2
    assert merged_face_sides(mesh, merged) == {1, -1}
    assert_clean(mesh)


# -- the seam: Delete maintains it (M), Dissolve refuses (R) --------------------------------------


@pytest.mark.parametrize("single", [False, True], ids=["pair", "one_side_only"])
@pytest.mark.parametrize("asset", PAIRED_ASSETS)
def test_delete_of_a_face_pair_at_the_seam_drops_the_dead_seam_ids_and_undo_restores_them(asset, single):
    """A1 Case 1 (Artist: M): the seam disappears only where the adjacent faces are gone."""
    app = make_app(asset)
    mesh = app.scene.mesh
    seam_before = mesh.symmetry_definition.seam_edges
    pair = seam_edge_pair(mesh)
    select(app, F, {min(pair)} if single else pair)  # one face: its mirror partner is coordinated
    state_before = topology_state(app)

    assert app.key_press(DELETE) is True
    assert not any(mesh.is_valid_face(f) for f in pair)
    seam_after = mesh.symmetry_definition.seam_edges
    dead = {e for e in seam_before if not mesh.is_valid_edge(e)}
    assert dead and dead.isdisjoint(seam_after)
    assert seam_after == seam_before - dead
    assert all(mesh.is_valid_edge(e) for e in seam_after)
    assert_clean(mesh)  # no dead seam id, state valid
    assert symmetry_state(mesh) is SymmetryState.VALID
    assert len(app.history) == 1

    assert app.key_press(CTRL_Z) is True
    assert topology_state(app) == state_before
    assert mesh.symmetry_definition.seam_edges == seam_before
    assert symmetry_state(mesh) is SymmetryState.VALID


@pytest.mark.parametrize("mode", [E, V], ids=["seam_edge", "seam_vertex"])
@pytest.mark.parametrize("asset", PAIRED_ASSETS)
def test_delete_of_a_seam_edge_or_vertex_is_coordinated_or_refused_never_one_sided(asset, mode):
    """Assumption cases (not confirmed beyond Case 1): for every seam element either the delete runs
    maintained (clean report, dead seam ids dropped, one Undo step) or the delta check refuses and
    nothing changes."""
    probe = make_app(asset)
    elements = sorted(probe.scene.mesh.symmetry_definition.seam_edges) if mode is E else seam_vertices(probe.scene.mesh)
    outcomes = set()
    for element in elements:
        app = make_app(asset)
        mesh = app.scene.mesh
        select(app, mode, {element})
        before = everything(app)
        seam_before = mesh.symmetry_definition.seam_edges
        if app.key_press(DELETE):
            outcomes.add("done")
            assert_clean(mesh)
            assert not valid(mesh, mode, element)
            assert mesh.symmetry_definition.seam_edges < seam_before
            assert len(app.history) == 1
            assert app.key_press(CTRL_Z) is True
            assert topology_state(app) == before[0]
            assert mesh.symmetry_definition.seam_edges == seam_before
        else:
            outcomes.add("refused")
            assert app.status_message == TEXT_DELTA
            assert everything(app) == before
            assert mesh.symmetry_definition.seam_edges == seam_before
    assert outcomes <= {"done", "refused"} and outcomes


@pytest.mark.parametrize("key", [DISSOLVE, DISSOLVE_NO_CLEANUP], ids=["dissolve", "dissolve_no_cleanup"])
@pytest.mark.parametrize("asset", PAIRED_ASSETS)
def test_dissolve_of_a_seam_edge_is_refused_with_the_seam_text(asset, key):
    """A1 Case 2 (Artist: UNKNOWN; engineering interim R): refused, nothing changes."""
    app = make_app(asset)
    mesh = app.scene.mesh
    seam_edge = next(e for e in sorted(mesh.symmetry_definition.seam_edges) if len(mesh.edge_faces(e)) == 2)
    select(app, E, {seam_edge})
    assert_refused(app, key, TEXT_SEAM_DISSOLVE)
    assert mesh.is_valid_edge(seam_edge)


@pytest.mark.parametrize("asset", PAIRED_ASSETS)
def test_dissolve_of_a_seam_vertex_is_refused_with_the_seam_text(asset):
    app = make_app(asset)
    mesh = app.scene.mesh
    select(app, V, {seam_vertices(mesh)[0]})
    assert_refused(app, DISSOLVE, TEXT_SEAM_DISSOLVE)


@pytest.mark.parametrize("key", [DISSOLVE, DISSOLVE_NO_CLEANUP], ids=["dissolve", "dissolve_no_cleanup"])
@pytest.mark.parametrize("asset", PAIRED_ASSETS)
def test_dissolve_of_a_face_pair_across_the_seam_is_refused_with_the_seam_text(asset, key):
    app = make_app(asset)
    select(app, F, seam_edge_pair(app.scene.mesh))
    assert_refused(app, key, TEXT_SEAM_DISSOLVE)


def test_the_seam_text_is_distinct_and_says_what_to_do():
    texts = [TEXT_UNPAIRED, TEXT_BOTH_SIDES_FACE, TEXT_NON_EXACT_PLANE, TEXT_DELTA, TEXT_SEAM_DISSOLVE]
    assert len(set(texts)) == 5
    assert TEXT_SEAM_DISSOLVE.startswith("Symmetrie:") and "Shift+S" in TEXT_SEAM_DISSOLVE


def test_a_delta_refusal_after_the_seam_was_rewritten_restores_the_definition_too(monkeypatch):
    """The definition is part of the mesh state the transaction restores."""
    app = make_app("subd_cube")
    mesh = app.scene.mesh
    select(app, F, seam_edge_pair(mesh))
    monkeypatch.setattr(symmetric_ops, "delta_check", lambda before, after: DeltaResult(("forced",)))
    assert_refused(app, DELETE, TEXT_DELTA)
    assert mesh.is_valid_face(min(seam_edge_pair(mesh)))


# -- refusals: visible, no history entry, mesh and selection unchanged -----------------------------


@pytest.mark.parametrize("name, key, command, dissolve, cleanup", COMMANDS, ids=COMMAND_IDS)
@pytest.mark.parametrize("mode", [V, E, F], ids=["vertex", "edge", "face"])
def test_an_unpaired_selection_is_refused(mode, name, key, command, dissolve, cleanup):
    if command == cmd.DISSOLVE_NO_CLEANUP and mode is V:
        pytest.skip("no variant")
    app, face = displaced_cube()
    mesh = app.scene.mesh
    index = SymmetryIndex(mesh)
    moved = next(v for v in mesh.face_vertices(face) if index.vertex_partner(v) is None)
    element = {
        V: moved,
        E: next(e for e in mesh.face_edges(face) if index.edge_partner(e) is None),
        F: face,
    }[mode]
    select(app, mode, {element})
    assert_refused(app, key, TEXT_UNPAIRED)


@pytest.mark.parametrize("name, key, command, dissolve, cleanup", COMMANDS, ids=COMMAND_IDS)
@pytest.mark.parametrize("mode", [V, E, F], ids=["vertex", "edge", "face"])
@pytest.mark.parametrize(
    "definition",
    [
        SymmetryDefinition(ORIGIN, (0.6, 0.8, 0.0)),  # oblique
        SymmetryDefinition((0.3, 0.0, 0.0), X),  # axis plane off the origin
    ],
    ids=["oblique", "off_origin"],
)
def test_a_non_exact_plane_is_refused(definition, mode, name, key, command, dissolve, cleanup):
    if command == cmd.DISSOLVE_NO_CLEANUP and mode is V:
        pytest.skip("no variant")
    app = make_app("subd_cube", definition=False)
    mesh = app.scene.mesh
    mesh.symmetry_definition = definition
    face = sorted(mesh.all_face_ids())[0]
    select(app, mode, {{V: mesh.face_vertices, E: mesh.face_edges, F: lambda f: [f]}[mode](face)[0]})
    assert_refused(app, key, TEXT_NON_EXACT_PLANE)


@pytest.mark.parametrize("key", [DELETE, DISSOLVE], ids=["delete", "dissolve"])
def test_a_face_hit_from_both_sides_is_refused_in_edge_mode(key):
    app, spanning = spanning_face_app()
    select(app, E, set(plus_side_edges(app.scene.mesh, spanning)[:2]))
    assert_refused(app, key, TEXT_BOTH_SIDES_FACE)


@pytest.mark.parametrize("key", [DELETE, DISSOLVE], ids=["delete", "dissolve"])
def test_a_face_hit_from_both_sides_is_refused_in_vertex_mode(key):
    app, spanning = spanning_face_app()
    mesh = app.scene.mesh
    vertices = [v for v in mesh.face_vertices(spanning) if mesh.vertex_position(v)[0] > 0]
    assert len(vertices) >= 2
    select(app, V, set(vertices[:2]))
    assert_refused(app, key, TEXT_BOTH_SIDES_FACE)


# -- next to unpaired geometry (D-strict, A3 = S) ---------------------------------------------------


def edge_dissolve_refused_by_delta(app: Application):
    """A +X edge of a quad that touches an unpaired vertex, paired itself, whose coordinated Dissolve
    the delta check refuses (the merged face would hold an unpaired vertex), found on a copy."""
    mesh = app.scene.mesh
    base = mesh.export_state()
    index = SymmetryIndex(mesh)
    try:
        for f in sorted(mesh.all_face_ids()):
            vs = mesh.face_vertices(f)
            if all(index.vertex_partner(v) is not None for v in vs):
                continue
            for e in mesh.face_edges(f):
                if edge_side(mesh, e) <= 0 or index.edge_partner(e) in (None, e):
                    continue
                try:
                    coordinate_removal(mesh, E, {e}, dissolve=True, cleanup=True)
                except SymmetryRefusal as exc:
                    if str(exc) == TEXT_DELTA:
                        return e
                finally:
                    mesh.load_state(base)
    finally:
        mesh.load_state(base)
    raise LookupError("no edge whose Dissolve the delta check refuses")


def test_d_strict_refuses_next_to_unpaired_geometry_and_works_far_from_it():
    """A3 = S: the same Dissolve on a partial mesh — refused where the delta check finds an element
    that lost its partner or a created one without a partner, symmetric where it does not."""
    app = make_app("man_with_shoes_basemesh")
    mesh = app.scene.mesh
    assert symmetry_state(mesh) is SymmetryState.PARTIAL
    select(app, E, {edge_dissolve_refused_by_delta(app)})
    assert_refused(app, DISSOLVE, TEXT_DELTA)

    # An element that was incomplete before stays incomplete: not a violation (INV-10).
    far = far_from_unpaired(mesh)
    edge = mesh.face_edges(far)[0]
    before_report = completeness_report(mesh)
    select(app, E, {edge})
    assert app.key_press(DISSOLVE) is True
    assert len(app.history) == 1
    after_report = completeness_report(mesh)
    assert after_report.unpaired_vertices <= before_report.unpaired_vertices
    assert after_report.faces_without_partner <= before_report.faces_without_partner
    assert after_report.edges_without_partner <= before_report.edges_without_partner
    assert not after_report.dead_seam_ids and not after_report.self_mirrored_faces
    assert not mesh.is_valid_edge(edge)
    assert app.key_press(CTRL_Z) is True
    assert len(app.history) == 0


def test_delete_far_from_unpaired_geometry_is_symmetric_on_a_partial_mesh():
    app = make_app("man_with_shoes_basemesh")
    mesh = app.scene.mesh
    far = far_from_unpaired(mesh)
    partner = partner_of(mesh, F, far)
    select(app, F, {far})
    assert app.key_press(DELETE) is True
    assert not mesh.is_valid_face(far) and not mesh.is_valid_face(partner)


# -- the coordinator itself --------------------------------------------------------------------------


def test_a_removal_coordinator_needs_a_definition():
    app = make_app("subd_cube", definition=False)
    mesh = app.scene.mesh
    with pytest.raises(ValueError):
        coordinate_removal(mesh, F, {sorted(mesh.all_face_ids())[0]}, dissolve=False, cleanup=False)


def test_a_removal_refusal_carries_the_violations_and_restores_nothing_itself():
    """A bare mutation: the caller owns the rollback (`_mesh_transaction`)."""
    app = make_app("subd_cube")
    mesh = app.scene.mesh
    pair = seam_edge_pair(mesh)
    state = topology_state(app)
    with pytest.raises(SymmetryRefusal) as caught:
        coordinate_removal(mesh, F, pair, dissolve=True, cleanup=True)
    assert str(caught.value) == TEXT_SEAM_DISSOLVE
    assert any("plane" in v or "seam" in v for v in caught.value.violations)
    assert topology_state(app) != state


def test_the_removal_coordinators_never_push_history():
    app = make_app("subd_cube")
    mesh = app.scene.mesh
    coordinate_removal(mesh, F, far_selection(app, F, dissolve=False), dissolve=False, cleanup=False)
    assert len(app.history) == 0


# -- no definition: the unchanged operation ----------------------------------------------------------


@pytest.mark.parametrize("name, key, command, dissolve, cleanup", COMMANDS, ids=COMMAND_IDS)
def test_without_a_definition_removal_is_the_unchanged_one_sided_operation(name, key, command, dissolve, cleanup):
    app = make_app("subd_cube", definition=False)
    twin = make_app("subd_cube", definition=False)
    mesh = app.scene.mesh
    quad = next(
        f for f in sorted(mesh.all_face_ids()) if len(mesh.face_vertices(f)) == 4 and min(mesh.vertex_position(v)[0] for v in mesh.face_vertices(f)) > 0
    )
    edge = mesh.face_edges(quad)[0]
    select(app, E, {edge})
    assert app.key_press(key) is True
    apply_removal(twin.scene.mesh, E, {edge}, dissolve=dissolve, cleanup=cleanup)
    assert topology_state(app) == topology_state(twin)
    assert len(app.history) == 1
    assert app.scene.mesh.symmetry_definition is None


def test_without_a_definition_face_dissolve_selects_all_merged_faces():
    app = make_app("subd_cube", definition=False)
    mesh = app.scene.mesh
    seamless = make_app("subd_cube")  # only to find an adjacent +X pair by ids
    pair = far_face_pair(seamless.scene.mesh)
    select(app, F, pair)
    before = set(mesh.all_face_ids())
    assert app.key_press(DISSOLVE) is True
    merged = set(mesh.all_face_ids()) - before
    assert merged and set(app.selection.faces) == merged
