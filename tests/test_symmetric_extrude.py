"""AD-SYM-03 slice 7 (WP-SYM-EXTRUDE-01): symmetric Face Extrude.

Tool level (`ExtrudeTool` + `plan_extrude`, a stub camera) and Application level (`T` hold, `make_app`). The
Lab path is tested in `experiments/symmetry_lab/tests/test_app_lab_symmetric_extrude.py`.

What is pinned (the Step-0 probe table of the AD-SYM-03 addendum, as tests):

- a one face, b face with an edge on the seam (pair across the seam: S3), d both sides, e negative distance, on
  `subd_cube` and `head_basemesh`, planes X, Y and Z: the result passes the completeness delta, every created
  vertex is a bit-identical mirror of its partner, seam vertices lie exactly on the plane, no dead seam id;
- the drag distance follows the working side (mirrored faces would cancel it) and the result is the same mirror
  image whichever side you work on;
- Artist statement 2026-10-09 ("Case 4"): a face touching the plane only at a corner and a face spanning the
  plane are **refused visibly, before any mutation** (the proper fix is a Discovery finding, not decided);
- one history entry, Undo/Redo restore mesh **and seam**, cancel and refusals leave everything exactly as it was.
"""

from __future__ import annotations

import ast
import random
from pathlib import Path

import pytest

import tests._bootstrap  # noqa: F401 — production path src/core, src/mirai

from core import Mesh, Scene, SelectionMode
from core.mesh import SymmetryDefinition
from mirai import symmetric_extrude, symmetry_coordination, symmetry_declarations
from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.input import Input
from mirai.symmetric_extrude import (
    TEXT_EXTRUDE_CORNER,
    TEXT_EXTRUDE_SPANNING,
    ExtrudeRefusal,
    plan_extrude,
)
from mirai.symmetric_ops import (
    TEXT_DELTA,
    TEXT_NON_EXACT_PLANE,
    TEXT_UNPAIRED,
    SymmetryRefusal,
)
from mirai.symmetry import mirror_position
from mirai.symmetry_coordination import (
    SymmetryIndex,
    completeness_report,
    seam_after_extrude,
)
from mirai.topology.extrude import ExtrudeTool, _compute_face_normal
from tests.symmetric_knife_support import fresh, hexagon_grid, set_plane, span_grid
from tests.test_symmetric_ops import (
    ASSETS,
    CTRL_Y,
    CTRL_Z,
    PAIRED_ASSETS,
    make_app,
    selection_state,
    topology_state,
)

T = Input("key", "t")
ESC = Input("key", "ESCAPE")
WIDTH, HEIGHT = 800, 600
ORIGIN = (0.0, 0.0, 0.0)
AXES = (0, 1, 2)


# -- helpers -----------------------------------------------------------------------------------


class _Camera:
    """World delta of every `update()`: a fixed vector chosen by the test."""

    def __init__(self, delta) -> None:
        self.delta = delta

    def screen_delta_to_world(self, point, dx, dy, width, height):
        return self.delta


def sd(d: SymmetryDefinition, p) -> float:
    return sum((x - o) * n for x, o, n in zip(p, d.plane_point, d.plane_normal))


def sign(x: float) -> int:
    return (x > 0) - (x < 0)


def scene_of(mesh: Mesh) -> Scene:
    scene = Scene()
    scene.mesh = mesh
    return scene


def face_normal(mesh: Mesh, face) -> tuple:
    return _compute_face_normal(mesh, mesh.face_vertices(face))


def pick_face(mesh: Mesh, kind: str, side: int = 1):
    """A face wholly on `side` (+1: positive coordinate on the plane's axis) with no plane vertex (`"a"`) or an
    edge on the plane (`"b"`); the middle one of the ascending ids, deterministic."""
    d = mesh.symmetry_definition
    found = []
    for f in sorted(mesh.all_face_ids()):
        ds = [sd(d, mesh.vertex_position(v)) for v in mesh.face_vertices(f)]
        on = sum(1 for x in ds if x == 0.0)
        if not (all(x * side >= 0 for x in ds) and any(x * side > 0 for x in ds)):
            continue
        if (kind == "a" and on == 0) or (kind == "b" and on == 2):
            found.append(f)
    assert found
    return found[len(found) // 2]


def drive(scene: Scene, faces, delta, *, commit: bool = True):
    """Plan, begin, one update, commit - the tool exactly as `Application` runs it."""
    plan = plan_extrude(scene.mesh, faces)
    tool = ExtrudeTool()
    tool.activate()
    tool.begin(scene=scene, camera=_Camera(delta), face_ids=set(plan.face_ids), symmetric_plan=plan)
    tool.update(dx=1.0, dy=0.0, width=WIDTH, height=HEIGHT)
    result = tool.commit() if commit else None
    return tool, plan, result


def assert_exact_result(mesh: Mesh, tool: ExtrudeTool) -> None:
    """The invariants of the Step-0 probe: bit-identical mirrors, seam vertices exactly on the plane, no dead
    seam id (the delta already passed or the commit would have been refused)."""
    d = mesh.symmetry_definition
    index = SymmetryIndex(mesh)
    for v in tool.vertex_ids:
        partner = index.vertex_partner(v)
        assert partner is not None, "a created vertex has no partner"
        pos = mesh.vertex_position(v)
        if partner == v:
            assert sd(d, pos) == 0.0
        else:
            assert tuple(mesh.vertex_position(partner)) == tuple(mirror_position(pos, d.plane_point, d.plane_normal))
    report = completeness_report(mesh)
    assert not report.dead_seam_ids
    assert not report.self_mirrored_faces
    assert not report.unpaired_vertices


def state(scene: Scene) -> dict:
    return topology_state_of(scene.mesh)


def topology_state_of(mesh: Mesh) -> dict:
    return {k: v for k, v in mesh.export_state().items() if not k.endswith("_id_counter")}


def pole_mesh() -> tuple[Mesh, dict]:
    """A valence-5 seam vertex S (seam edges S-T and S-U): the middle face of each side touches the plane only
    at S. Flat, plane x = 0."""
    m = Mesh()
    S, T_, U = m.add_vertex((0.0, 0.0, 0.0)), m.add_vertex((0.0, 1.0, 0.0)), m.add_vertex((0.0, -1.0, 0.0))
    faces = {}
    for sgn_, name in ((1.0, "p"), (-1.0, "m")):
        a, b = m.add_vertex((sgn_ * 1.0, 0.6, 0.0)), m.add_vertex((sgn_ * 1.0, -0.6, 0.0))
        p1, p2, p3 = (m.add_vertex((sgn_ * 1.2, 1.2, 0.0)), m.add_vertex((sgn_ * 2.0, 0.0, 0.0)),
                      m.add_vertex((sgn_ * 1.2, -1.2, 0.0)))
        rings = ([S, T_, p1, a], [S, a, p2, b], [S, b, p3, U]) if sgn_ > 0 else (
            [S, a, p1, T_], [S, b, p2, a], [S, U, p3, b])
        faces[name] = [m.add_face(r) for r in rings]
    set_plane(m)
    return m, faces


def slot_mesh() -> tuple[Mesh, object, object]:
    """Two mirrored walls with normals exactly +x and -x (their sum is zero): the distance scalar of the
    unchanged tool would fall back to Z."""
    m = Mesh()
    right = m.add_face([m.add_vertex((1.0, y, z)) for y, z in ((0, 0), (1, 0), (1, 1), (0, 1))])
    left = m.add_face([m.add_vertex((-1.0, y, z)) for y, z in ((0, 0), (0, 1), (1, 1), (1, 0))])
    set_plane(m)
    return m, right, left


# -- declaration and layering -----------------------------------------------------------------


def test_the_declaration_holds_exactly_the_extrude_planner():
    assert dict(symmetry_declarations.EXTRUDE_COORDINATORS) == {cmd.EXTRUDE: plan_extrude}
    assert symmetry_declarations.declared_extrude_commands() == frozenset({cmd.EXTRUDE})
    with pytest.raises(TypeError):
        symmetry_declarations.EXTRUDE_COORDINATORS[cmd.EXTRUDE] = None  # type: ignore[index]


def _imports(path: str) -> list[str]:
    imported = []
    for node in ast.walk(ast.parse(Path(path).read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom):
            imported.append(("." * node.level) + (node.module or ""))
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
    return imported


def test_the_tool_imports_nothing_from_symmetry_and_the_coordinator_never_the_application():
    assert not [n for n in _imports(ExtrudeTool.__module__.replace(".", "/").join(("src/", ".py")))
                if "symmetr" in n]
    assert not [n for n in _imports(symmetric_extrude.__file__) if "application" in n]


def test_a_planner_needs_a_definition():
    app = make_app("subd_cube", definition=False)
    with pytest.raises(ValueError):
        plan_extrude(app.scene.mesh, {sorted(app.scene.mesh.all_face_ids())[0]})


# -- S3 as a pure function --------------------------------------------------------------------


def test_s3_replaces_a_consumed_seam_edge_by_its_cap_edge_and_changes_nothing_else():
    mesh = fresh("subd_cube", 0, 1)
    scene = scene_of(mesh)
    face = pick_face(mesh, "b")
    d = mesh.symmetry_definition
    seam_ends = {e: tuple(mesh.edge_vertices(e)) for e in d.seam_edges}
    tool, plan, result = drive(scene, {face}, (0.0, 0.0, 0.1))
    assert result is not None
    new = mesh.symmetry_definition
    assert len(new.seam_edges) == len(d.seam_edges)
    died = {e for e in d.seam_edges if not mesh.is_valid_edge(e)}
    assert len(died) == 1
    born = new.seam_edges - d.seam_edges
    assert len(born) == 1
    (old,), (cap,) = tuple(died), tuple(born)
    a, b = seam_ends[old]
    assert set(mesh.edge_vertices(cap)) == {tool._old_to_new[a], tool._old_to_new[b]}
    assert new.seam_edges - born == d.seam_edges - died  # every surviving seam edge stays
    # Pure: calling it again on the final mesh changes nothing.
    assert seam_after_extrude(new, seam_ends, mesh, tool._old_to_new) == new


def test_s3_leaves_a_dead_id_when_the_ends_have_no_cap_copy():
    """Ids and incidence only: without a cap copy of its ends a consumed seam edge keeps its dead id, so the
    delta check (rule 2) is what refuses."""
    mesh = fresh("subd_cube", 0, 1)
    d = mesh.symmetry_definition
    seam_ends = {e: tuple(mesh.edge_vertices(e)) for e in d.seam_edges}
    drive(scene_of(mesh), {pick_face(mesh, "b")}, (0.0, 0.0, 0.1))
    (dead,) = [e for e in d.seam_edges if not mesh.is_valid_edge(e)]
    assert dead in seam_after_extrude(d, seam_ends, mesh, {}).seam_edges


# -- the success path at tool level -----------------------------------------------------------


CASES = [
    ("a_one_face", "a", dict()),
    ("b_seam_edge", "b", dict()),
    ("d_both_sides", "a", dict(both=True)),
    ("d_both_sides_seam", "b", dict(both=True)),
    ("e_negative", "a", dict(negative=True)),
    ("e_negative_seam", "b", dict(negative=True)),
]


@pytest.mark.parametrize("axis", AXES)
@pytest.mark.parametrize("asset", PAIRED_ASSETS)
@pytest.mark.parametrize("name,kind,opt", CASES, ids=[c[0] for c in CASES])
def test_the_step0_cases_pass_the_delta_with_exact_mirrors(asset, axis, name, kind, opt):
    mesh = fresh(asset, axis, 1)
    scene = scene_of(mesh)
    face = pick_face(mesh, kind)
    selected = {face}
    if opt.get("both"):
        selected.add(SymmetryIndex(mesh).face_partner(face))
    n = face_normal(mesh, face)
    amount = -0.1 if opt.get("negative") else 0.1
    before = state(scene)
    tool, plan, result = drive(scene, selected, tuple(amount * x for x in n))

    assert result is not None, "the commit was refused"
    assert len(scene.history) == 1
    assert abs(tool.total_distance - amount) < 1e-12  # the scalar follows the working side (X5)
    assert_exact_result(mesh, tool)
    assert state(scene) != before
    # Undo restores the mesh and the seam definition (it is part of the state).
    seam_after = mesh.symmetry_definition.seam_edges
    scene.history.undo()
    assert state(scene) == before
    assert mesh.symmetry_definition.seam_edges != seam_after or kind == "a"
    scene.history.redo()
    assert mesh.symmetry_definition.seam_edges == seam_after


def test_the_naive_union_would_have_failed_the_delta():
    """Why the placement exists: the unchanged tool on selection + partner, no plan (the Step-0 finding)."""
    mesh = fresh("head_basemesh", 0, 1)
    scene = scene_of(mesh)
    face = pick_face(mesh, "a")
    union = {face, SymmetryIndex(mesh).face_partner(face)}
    before = completeness_report(mesh)
    tool = ExtrudeTool()
    tool.activate()
    tool.begin(scene=scene, camera=_Camera(tuple(0.1 * x for x in face_normal(mesh, face))), face_ids=union)
    tool.update(dx=1.0, dy=0.0, width=WIDTH, height=HEIGHT)
    assert not symmetry_coordination.delta_check(before, completeness_report(mesh)).ok


def test_the_distance_follows_the_working_side_where_mirrored_faces_cancel():
    mesh, right, left = slot_mesh()
    scene = scene_of(mesh)
    tool, plan, result = drive(scene, {right}, (0.1, 0.0, 0.0))
    assert plan.reference_normal == (1.0, 0.0, 0.0)
    assert tool.total_distance == pytest.approx(0.1)
    assert result is not None
    assert_exact_result(mesh, tool)
    # the unchanged tool measures along the (cancelling) sum: the Z fallback, i.e. 0.0 for this drag
    other = scene_of(slot_mesh()[0])
    naive = ExtrudeTool()
    naive.activate()
    naive.begin(scene=other, camera=_Camera((0.1, 0.0, 0.0)), face_ids=set(other.mesh.all_face_ids()))
    naive.update(dx=1.0, dy=0.0, width=WIDTH, height=HEIGHT)
    assert naive.total_distance == 0.0


@pytest.mark.parametrize("asset", PAIRED_ASSETS)
@pytest.mark.parametrize("axis", AXES)
def test_the_result_is_the_same_mirror_image_whichever_side_you_work_on(asset, axis):
    base = fresh(asset, axis, 1)
    index = SymmetryIndex(base)
    d = base.symmetry_definition
    mir = lambda p: tuple(mirror_position(tuple(p), ORIGIN, d.plane_normal))  # noqa: E731
    faces = [f for f in sorted(base.all_face_ids())
             if sign(sum(sd(d, base.vertex_position(v)) for v in base.face_vertices(f))) == 1][::5]
    assert faces
    for f in faces:
        partner = index.face_partner(f)
        n = face_normal(base, f)
        runs = []
        for face, direction in ((f, n), (partner, mir(n))):
            scene = scene_of(fresh(asset, axis, 1))
            tool, plan, result = drive(scene, {face}, tuple(0.1 * x for x in direction))
            assert result is not None
            runs.append((scene.mesh, tool))
        (ma, ta), (mb, tb) = runs
        for old, new_a in ta._old_to_new.items():
            new_b = tb._old_to_new[index.vertex_partner(old)]
            a = mir(ma.vertex_position(new_a))
            b = mb.vertex_position(new_b)
            assert max(abs(x - y) for x, y in zip(a, b)) < 1e-12


@pytest.mark.parametrize("asset", PAIRED_ASSETS)
def test_both_sides_selected_is_one_intent_with_the_same_result_as_one_side(asset):
    one = scene_of(fresh(asset, 0, 1))
    both = scene_of(fresh(asset, 0, 1))
    face = pick_face(one.mesh, "a")
    partner = SymmetryIndex(one.mesh).face_partner(face)
    n = face_normal(one.mesh, face)
    delta = tuple(0.1 * x for x in n)
    drive(one, {face}, delta)
    tool, plan, result = drive(both, {face, partner}, delta)
    assert result is not None and len(both.history) == 1
    assert plan.face_ids == frozenset({face, partner})  # a pair counts once ("explicit wins")
    assert state(one) == state(both)


def test_the_working_side_is_the_side_with_more_live_selected_faces_and_a_tie_the_normals_side():
    mesh = fresh("head_basemesh", 0, 1)
    index = SymmetryIndex(mesh)
    d = mesh.symmetry_definition
    plus = [f for f in sorted(mesh.all_face_ids()) if sd(d, mesh.vertex_position(mesh.face_vertices(f)[0])) > 0
            and not any(sd(d, mesh.vertex_position(v)) == 0.0 for v in mesh.face_vertices(f))]
    a, b = plus[0], plus[40]
    ap, bp = index.face_partner(a), index.face_partner(b)
    assert plan_extrude(mesh, {a, ap}).working_side == 1                # tie -> the plane normal's side
    assert plan_extrude(mesh, {ap}).working_side == -1
    assert plan_extrude(mesh, {a, bp, b}).working_side == 1            # two faces on +, one on -
    assert plan_extrude(mesh, {ap, bp, b}).working_side == -1
    neg = fresh("head_basemesh", 0, -1)                                 # normal -X: "+1" is the -X side
    assert plan_extrude(neg, {a, ap}).working_side == 1


# -- fuzz --------------------------------------------------------------------------------------


@pytest.mark.parametrize("axis", AXES)
@pytest.mark.parametrize("asset", PAIRED_ASSETS)
def test_seeded_fuzz_every_selection_commits_exactly_or_is_refused_untouched(asset, axis):
    rnd = random.Random(20261009 + axis)
    base = fresh(asset, axis, 1)
    faces = sorted(base.all_face_ids())
    committed = 0
    for _ in range(40):
        pick = set(rnd.sample(faces, rnd.randint(1, 6)))
        scene = scene_of(fresh(asset, axis, 1))
        before = state(scene)
        n = face_normal(scene.mesh, sorted(pick)[0])
        amount = rnd.choice((0.05, -0.05, 0.12))
        try:
            tool, plan, result = drive(scene, pick, tuple(amount * x for x in n))
        except SymmetryRefusal as exc:
            assert str(exc) in (TEXT_EXTRUDE_CORNER, TEXT_EXTRUDE_SPANNING)
            assert state(scene) == before and len(scene.history) == 0
            continue
        assert result is not None, "a planned extrusion was refused at the commit (a hole in the pre-checks)"
        assert len(scene.history) == 1
        assert_exact_result(scene.mesh, tool)
        committed += 1
    assert committed >= 30


# -- refusals before any mutation --------------------------------------------------------------


def test_a_face_touching_the_plane_only_at_a_corner_is_refused_visibly_before_any_mutation():
    """Artist statement 2026-10-09 (Case 4): refuse visibly, for now."""
    mesh, faces = pole_mesh()
    assert SymmetryIndex(mesh).face_partner(faces["p"][1]) == faces["m"][1]  # paired: the refusal is the rule
    before = state(scene_of(mesh))
    for selection in ({faces["p"][1]}, {faces["m"][1]}, {faces["p"][1], faces["m"][1]}):
        with pytest.raises(SymmetryRefusal) as info:
            plan_extrude(mesh, selection)
        assert str(info.value) == TEXT_EXTRUDE_CORNER
    assert topology_state_of(mesh) == before


def test_two_separate_seam_contacts_at_one_plane_vertex_are_refused_but_one_connected_arc_is_not():
    """At S the boundary of the extruded region must pass exactly twice (one arc through the seam) or not at
    all. Two pairs across two different seam edges of S meet only at S: the wall edge S-S' would carry four
    faces -> refused. The pair across S-T plus its neighbour is one arc -> clean."""
    mesh, faces = pole_mesh()
    top, middle, bottom = faces["p"]
    plan_extrude(mesh, {top})
    plan_extrude(mesh, {top, middle})
    with pytest.raises(SymmetryRefusal) as info:
        plan_extrude(mesh, {top, bottom})
    assert str(info.value) == TEXT_EXTRUDE_CORNER


@pytest.mark.parametrize("name", ["span_grid", "hexagon_grid"])
def test_a_face_spanning_the_plane_is_refused_visibly_before_any_mutation(name):
    """Artist statement 2026-10-09 (Case 4): refuse visibly, for now."""
    mesh = fresh(name, 0, 1)
    spanning = [f for f in mesh.all_face_ids() if SymmetryIndex(mesh).face_partner(f) == f]
    assert spanning
    before = topology_state_of(mesh)
    with pytest.raises(SymmetryRefusal) as info:
        plan_extrude(mesh, {spanning[0]})
    assert str(info.value) == TEXT_EXTRUDE_SPANNING
    assert topology_state_of(mesh) == before


def test_a_spanning_face_that_is_not_its_own_mirror_is_refused_as_well():
    m = Mesh()
    a, b = m.add_vertex((-1.0, 0.0, 0.0)), m.add_vertex((2.0, 0.0, 0.0))
    c, d = m.add_vertex((2.0, 1.0, 0.0)), m.add_vertex((-1.0, 1.0, 0.0))
    a2, b2 = m.add_vertex((1.0, 0.0, 0.0)), m.add_vertex((-2.0, 0.0, 0.0))
    c2, d2 = m.add_vertex((-2.0, 1.0, 0.0)), m.add_vertex((1.0, 1.0, 0.0))
    f1 = m.add_face([a, b, c, d])
    m.add_face([b2, a2, d2, c2])
    set_plane(m)
    with pytest.raises(SymmetryRefusal) as info:
        plan_extrude(m, {f1})
    assert str(info.value) == TEXT_EXTRUDE_SPANNING


def test_a_face_without_a_partner_is_refused_as_unpaired():
    mesh = fresh("man_with_shoes_basemesh", 0, 1)
    index = SymmetryIndex(mesh)
    lonely = next(f for f in sorted(mesh.all_face_ids()) if index.face_partner(f) is None)
    with pytest.raises(SymmetryRefusal) as info:
        plan_extrude(mesh, {lonely})
    assert str(info.value) == TEXT_UNPAIRED


def test_a_plane_that_is_not_exact_is_refused():
    mesh = fresh("subd_cube", 0, 1)
    d = mesh.symmetry_definition
    mesh.symmetry_definition = SymmetryDefinition(d.plane_point, (0.6, 0.8, 0.0), d.seam_edges)
    with pytest.raises(SymmetryRefusal) as info:
        plan_extrude(mesh, {sorted(mesh.all_face_ids())[0]})
    assert str(info.value) == TEXT_NON_EXACT_PLANE


# -- the commit-time refusal (delta) -----------------------------------------------------------


def test_a_delta_violation_at_the_commit_takes_everything_back_and_pushes_no_history(monkeypatch):
    mesh = fresh("subd_cube", 0, 1)
    scene = scene_of(mesh)
    face = pick_face(mesh, "b")
    before = state(scene)
    seam_before = mesh.symmetry_definition
    # Break S3: the consumed seam edge keeps its dead id -> delta rule 2.
    monkeypatch.setattr(symmetric_extrude, "seam_after_extrude", lambda definition, *a, **k: definition)
    tool, plan, result = drive(scene, {face}, (0.0, 0.0, 0.1))
    assert result is None
    assert tool.refusal == TEXT_DELTA
    assert len(scene.history) == 0
    assert state(scene) == before
    assert mesh.symmetry_definition == seam_before


def test_a_bug_in_finish_propagates_but_the_mesh_is_exactly_restored():
    mesh = fresh("subd_cube", 0, 1)
    scene = scene_of(mesh)
    face = pick_face(mesh, "a")
    before = state(scene)

    class Broken(symmetric_extrude.SymmetricExtrudePlan):
        def finish(self, mesh, old_to_new):
            raise KeyError("bug")

    plan = plan_extrude(mesh, {face})
    plan.__class__ = Broken
    tool = ExtrudeTool()
    tool.activate()
    tool.begin(scene=scene, camera=_Camera((0.0, 0.0, 0.1)), face_ids=set(plan.face_ids), symmetric_plan=plan)
    tool.update(dx=1.0, dy=0.0, width=WIDTH, height=HEIGHT)
    with pytest.raises(KeyError):
        tool.commit()
    assert state(scene) == before and len(scene.history) == 0


def test_an_extrude_refusal_is_a_symmetry_refusal_with_the_commit_marker():
    assert issubclass(ExtrudeRefusal, SymmetryRefusal) and ExtrudeRefusal.commit_refusal is True
    assert not getattr(SymmetryRefusal("x"), "commit_refusal", False)


# -- without a plan the tool is the B9 tool ----------------------------------------------------


def test_without_a_plan_the_tool_is_unchanged():
    mesh = fresh("subd_cube", 0, 1)
    scene = scene_of(mesh)
    face = pick_face(mesh, "a")
    tool = ExtrudeTool()
    tool.activate()
    tool.begin(scene=scene, camera=_Camera((0.0, 0.0, 0.1)), face_ids={face})
    tool.update(dx=1.0, dy=0.0, width=WIDTH, height=HEIGHT)
    assert tool.commit() is not None and tool.refusal is None
    assert len(scene.history) == 1
    assert len(mesh.symmetry_definition.seam_edges) == len(fresh("subd_cube", 0, 1).symmetry_definition.seam_edges)


# -- Application: hold T --------------------------------------------------------------------


def app_face_setup(asset="head_basemesh", kind="a", side=1):
    app = make_app(asset)
    app.selection.mode = SelectionMode.FACE
    face = pick_face(app.scene.mesh, kind, side)
    return app, face


def select_faces(app, *faces) -> None:
    app.selection.mode = SelectionMode.FACE
    app.selection.set(set(faces))


def hold_t(app, steps: int = 4, dx: float = 30.0, dy: float = 20.0) -> bool:
    assert app.key_press(T)
    x, y = app._cursor or (400.0, 300.0)
    for _ in range(steps):
        x, y = x + dx, y + dy
        app.pointer_motion(x, y, dx, dy)
    return app.key_release(T)


def app_state(app) -> tuple:
    return (topology_state(app), len(app.history), selection_state(app), app.scene.mesh.symmetry_definition)


@pytest.mark.parametrize("kind", ["a", "b"])
def test_t_extrudes_both_sides_as_one_intent_in_one_undo_step(kind):
    app, face = app_face_setup(kind=kind)
    mesh = app.scene.mesh
    select_faces(app, face)
    before = app_state(app)
    assert hold_t(app)
    assert app.status_message == "Extrude committed"
    assert len(app.history) == 1
    after = app_state(app)
    assert after[0] != before[0]
    report = completeness_report(mesh)
    assert not report.dead_seam_ids and not report.faces_without_partner and not report.unpaired_vertices

    app.key_press(CTRL_Z)
    assert app_state(app) == before          # mesh, history length, selection and the seam definition
    app.key_press(CTRL_Y)
    assert app_state(app)[0] == after[0] and app_state(app)[3] == after[3]


def test_a_seam_pair_extrude_moves_the_seam_with_the_mesh_and_undo_restores_it():
    app, face = app_face_setup(kind="b")
    mesh = app.scene.mesh
    seam_before = mesh.symmetry_definition.seam_edges
    select_faces(app, face)
    hold_t(app)
    seam_after = mesh.symmetry_definition.seam_edges
    assert seam_after != seam_before and len(seam_after) == len(seam_before)
    assert all(mesh.is_valid_edge(e) for e in seam_after)
    app.key_press(CTRL_Z)
    assert mesh.symmetry_definition.seam_edges == seam_before


def test_the_selection_after_the_commit_is_the_caps_on_the_side_you_worked_on():
    """Engineering default (AD-SYM-03 §4), explicitly not an Artist decision for Extrude."""
    app, face = app_face_setup()
    mesh = app.scene.mesh
    select_faces(app, face)
    hold_t(app)
    selected = set(app.selection.faces)
    assert selected and all(mesh.is_valid_face(f) for f in selected)
    assert {sign(sum(mesh.vertex_position(v)[0] for v in mesh.face_vertices(f))) for f in selected} == {1}

    app, face = app_face_setup()
    mesh = app.scene.mesh
    partner = SymmetryIndex(mesh).face_partner(face)
    select_faces(app, face, partner)
    hold_t(app)
    sides = {sign(sum(mesh.vertex_position(v)[0] for v in mesh.face_vertices(f))) for f in app.selection.faces}
    assert sides == {1, -1}


def test_working_on_either_side_gives_a_complete_symmetric_result_with_the_same_topology():
    """The mirror-image property itself is pinned at tool level (exact camera); here the gesture on each side."""
    counts = []
    for side in (1, -1):
        app, face = app_face_setup(side=side)
        select_faces(app, face)
        assert hold_t(app) and app.status_message == "Extrude committed"
        report = completeness_report(app.scene.mesh)
        assert not report.faces_without_partner and not report.unpaired_vertices and not report.dead_seam_ids
        mesh = app.scene.mesh
        counts.append((len(mesh.all_vertex_ids()), len(mesh.all_edge_ids()), len(mesh.all_face_ids())))
    assert counts[0] == counts[1]


def test_esc_during_a_symmetric_extrude_restores_mesh_selection_and_seam_exactly():
    app, face = app_face_setup(kind="b")
    select_faces(app, face)
    before = app_state(app)
    assert app.key_press(T)
    x, y = 400.0, 300.0
    for _ in range(4):
        x, y = x + 30, y + 20
        app.pointer_motion(x, y, 30.0, 20.0)
    assert app.transform_interacting
    assert app.key_press(ESC)
    assert app_state(app) == before
    assert len(app.history) == 0


def test_a_refused_begin_leaves_mesh_history_and_selection_untouched_and_the_tool_disarmed():
    """`Application` level: the corner refusal text is the status, nothing changed, no gesture running."""
    app = make_app("subd_cube")
    mesh, faces = pole_mesh()
    app.scene.mesh = mesh
    app.selection.clear()
    select_faces(app, faces["p"][1])
    before = app_state(app)
    stacks = (len(app._selection_undo_stack), len(app._selection_redo_stack))
    assert app.key_press(T)
    x, y = 400.0, 300.0
    for _ in range(3):
        x, y = x + 30, y + 20
        app.pointer_motion(x, y, 30.0, 20.0)
    assert app.status_message == TEXT_EXTRUDE_CORNER
    assert app_state(app) == before
    assert (len(app._selection_undo_stack), len(app._selection_redo_stack)) == stacks
    assert app.transform_command is None and app.interaction_owner is None
    assert app.tool_manager.active_tool is None


def test_a_delta_refusal_at_release_is_the_b9_abort_path_with_the_refusal_as_status(monkeypatch):
    app, face = app_face_setup(kind="b")
    select_faces(app, face)
    before = app_state(app)
    stacks = (len(app._selection_undo_stack), len(app._selection_redo_stack))
    monkeypatch.setattr(symmetric_extrude, "seam_after_extrude", lambda definition, *a, **k: definition)
    hold_t(app)
    assert app.status_message == TEXT_DELTA
    assert app_state(app) == before
    assert len(app.history) == 0
    assert (len(app._selection_undo_stack), len(app._selection_redo_stack)) == stacks
    assert app.transform_command is None and app.tool_manager.active_tool is None


def test_without_a_definition_t_is_the_b9_extrude():
    app = make_app("head_basemesh", definition=False)
    app.selection.mode = SelectionMode.FACE
    face = sorted(app.scene.mesh.all_face_ids())[0]
    select_faces(app, face)
    seen = []
    original = ExtrudeTool.begin

    def spy(self, **params):
        seen.append(sorted(params))
        return original(self, **params)

    ExtrudeTool.begin = spy
    try:
        hold_t(app)
    finally:
        ExtrudeTool.begin = original
    assert seen == [["camera", "face_ids", "scene"]]  # no plan was passed
    assert app.status_message == "Extrude committed"


def test_the_arm_status_and_the_hover_fallback_are_unchanged_under_symmetry():
    app, face = app_face_setup()
    select_faces(app, face)
    assert app.key_press(T)
    assert app.status_message == "Extrude: 1 face - move the mouse, release T to commit"
    assert app.key_release(T)
    assert app.status_message == "Extrude: no change"
