"""F-a: the build-time guard that keeps the app fail-closed under symmetry (AD-SYM-04 §3.3, Q-3).

There is no runtime gate in Production (E5 MARK/BLOCK stays in the Lab). Instead every command
constant of `mirai.interaction.commands` is bound to one test GLOBAL key and pressed through
`Application` - with the default bindings and `command_gate is None`, as `src/main.py` runs it -
on a symmetric fixture (subd_cube, definition X). The oracle has no command list (review R-5):

- **if the mesh changed, completeness is unchanged** (AD-SYM-03 delta rule) and it is one Undo
  step; the only command allowed to change the plane itself is `SymmetryCycle`;
- if the press was refused, a status was posted - that part cannot tell a silent refusal from an
  unhandled constant (`return False`, nothing changed), which passes trivially.

A newly wired tool that mutates one-sided fails here until it is declared or refuses
(negative control below: Delete with its declaration removed).

**Known gaps, stated (AD-SYM-04 §3.3):** only the key path is seen - a host's
`dispatch_command(..., context=...)` and `apply_mesh_change` are outside it; only what the fixture
selections exercise is caught (vertex, one edge, two edges, one face, nothing selected); a Knife
session started here commits without clicks, so the Knife's cuts are covered by the A1 smoke
(`test_application_symmetry_cycle.py`), not by this guard.
"""

from __future__ import annotations

import sys
from types import MappingProxyType

import pytest

import tests._bootstrap  # noqa: F401
from tests._bootstrap import _REPO_ROOT

_EXAMPLES = _REPO_ROOT / "examples"
if str(_EXAMPLES) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES))

from core import SelectionMode  # noqa: E402
from loaders.assets import asset_path  # noqa: E402
from mirai import symmetry_declarations as declarations  # noqa: E402
from mirai.application import Application  # noqa: E402
from mirai.interaction import commands  # noqa: E402
from mirai.interaction.input import Input  # noqa: E402
from mirai.symmetry_axis import definition_for_axis  # noqa: E402
from mirai.symmetry_coordination import completeness_report, delta_check  # noqa: E402

WIDTH, HEIGHT = 800, 600
MISS = (2.0, 2.0)
EPS = 1e-9
TEST_KEY = Input("key", "f12")
ENTER = Input("key", "enter")

COMMANDS = sorted(
    value for name, value in vars(commands).items() if name.isupper() and isinstance(value, str)
)
FIXTURES = ("vertices", "one_edge", "two_edges", "face", "nothing")


def _plus_x_quad(mesh):
    for fid in sorted(mesh.all_face_ids(), key=int):
        vids = mesh.face_vertices(fid)
        if len(vids) == 4 and all(mesh.vertex_position(v)[0] > EPS for v in vids):
            return fid, vids
    raise AssertionError("no quad entirely on the +X side")


def _edge_between(mesh, a, b):
    return next(e for e in mesh.all_edge_ids() if set(mesh.edge_vertices(e)) == {a, b})


def symmetric_fixture(selection: str) -> Application:
    """subd_cube with the X definition set directly (no history entry, so Undo has nothing to
    take back) and one of the fixture selections, all on the +X side."""
    app = Application()
    app.init_scene("obj", obj_path=asset_path("subd_cube"))
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    app.pointer_motion(*MISS)
    mesh = app.scene.mesh
    mesh.symmetry_definition = definition_for_axis(mesh, "X")
    fid, (a, b, c, d) = _plus_x_quad(mesh)
    s = app.selection
    s.clear()
    if selection == "vertices":
        s.mode = SelectionMode.VERTEX
        s.vertices = {a, b, c, d}
    elif selection == "one_edge":
        s.mode = SelectionMode.EDGE
        s.edges = {_edge_between(mesh, a, b)}
    elif selection == "two_edges":
        s.mode = SelectionMode.EDGE
        s.edges = {_edge_between(mesh, a, b), _edge_between(mesh, c, d)}
    elif selection == "face":
        s.mode = SelectionMode.FACE
        s.faces = {fid}
    return app


def press_through(app: Application, command: str) -> bool:
    """Press the test key bound to `command`; an armed hold-key tool is moved and released, a
    Knife session is committed (no clicks: nothing to cut)."""
    app.bindings.bind(TEST_KEY, command)
    returned = app.key_press(TEST_KEY)
    if app.interaction_owner == "transform":
        for _ in range(3):
            app.pointer_motion(400, 300, 6.0, -8.0)
        app.key_release(TEST_KEY)
    elif app.interaction_owner == "knife":
        app.key_press(ENTER)
    assert app.interaction_owner is None
    return bool(returned)


def guard_violations(app: Application, command: str) -> list[str]:
    mesh = app.scene.mesh
    definition = mesh.symmetry_definition
    plane = (definition.plane_point, definition.plane_normal)
    before_state = mesh.export_state()
    before = completeness_report(mesh)
    history = len(app.history)

    press_through(app, command)

    after_definition = mesh.symmetry_definition
    if mesh.export_state() == before_state:
        # Refused (a status was posted), unhandled or ignored: nothing changed, nothing one-sided.
        return []
    problems = []
    if len(app.history) != history + 1:
        problems.append(f"{command}: {len(app.history) - history} history entries for one press")
    if after_definition is None or (after_definition.plane_point, after_definition.plane_normal) != plane:
        if command != commands.SYMMETRY_CYCLE:
            problems.append(f"{command}: changed the symmetry plane")
        return problems
    result = delta_check(before, completeness_report(mesh))
    problems.extend(f"{command}: {v}" for v in result.violations)
    return problems


@pytest.mark.parametrize("selection", FIXTURES)
@pytest.mark.parametrize("command", COMMANDS)
def test_f_a_no_command_breaks_symmetry_through_the_key_path(command, selection):
    app = symmetric_fixture(selection)
    assert app.command_gate is None
    assert guard_violations(app, command) == []


def test_f_a_the_guard_sees_real_mutations():
    """The fixtures exercise the coordinated tools (else the guard would pass by doing nothing):
    each of these changes the mesh on its fixture and keeps completeness."""
    exercised = {
        (commands.MOVE, "vertices"),
        (commands.ROTATE, "vertices"),
        (commands.SCALE, "vertices"),
        (commands.CONNECT, "one_edge"),
        (commands.CONNECT, "two_edges"),
        (commands.DELETE, "face"),
        (commands.DISSOLVE, "one_edge"),
        (commands.DISSOLVE_NO_CLEANUP, "one_edge"),
        (commands.EXTRUDE, "face"),
        (commands.SYMMETRY_CYCLE, "nothing"),
        (commands.LOOP_INSERT, "one_edge"),
        (commands.LOOP_SLIDE, "one_edge"),
    }
    for command, selection in exercised:
        app = symmetric_fixture(selection)
        before = app.scene.mesh.export_state()
        assert guard_violations(app, command) == []
        assert app.scene.mesh.export_state() != before, (command, selection)


def test_f_a_negative_control_an_undeclared_removal_runs_one_sided_and_fails(monkeypatch):
    """Without its declaration Delete runs as without a definition (T-G3a): one-sided, which the
    guard reports. This is what a newly wired, undeclared tool looks like to the guard."""
    monkeypatch.setattr(
        declarations,
        "REMOVAL_COORDINATORS",
        MappingProxyType(
            {c: f for c, f in declarations.REMOVAL_COORDINATORS.items() if c != commands.DELETE}
        ),
    )
    app = symmetric_fixture("face")
    assert guard_violations(app, commands.DELETE) != []
