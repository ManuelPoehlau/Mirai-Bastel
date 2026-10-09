"""AD-SYM-03 slice 6c: the symmetric Knife in `Application` — the mirrored and clipped preview, the click-time
refusals (F3 = A), the three provisional preview variants, the wiring and the declaration.

What is pinned (the handoff's §5 table):

- preview = commit: for the frozen 6b regression sessions and a seeded both-sides fuzz, the path the preview
  draws is the path `coordinate_knife` hands the resolver (captured), and the mirror is `mirror_position` of it;
- no definition: the render data, the overlay calls and the session are what they were;
- the clipped part: a path across the seam, two chains;
- the variants (key cycle, default, layers, depth state, status text);
- P2 at hover / click on `man_with_shoes_basemesh` (a target and a cut face without partner), on a plane-spanning
  face (the asset has none) and for a partnered other-side target;
- begin on a non-exact plane; the wiring through `Application` (one history entry, Undo restores both sides and
  the seam, residue = the working side's cut edges); the declaration; the hover cost (numbers only).

Headless (TraceStore), no pyglet. Meshes and sessions: `tests/symmetric_knife_support.py`.
"""

from __future__ import annotations

import dataclasses
import itertools
import platform
import random
import statistics
import time

import pytest

import tests._bootstrap  # noqa: F401

from core import Mesh
from core.mesh import SymmetryDefinition
from mirai import symmetric_knife as sk
from mirai import symmetry_declarations
from mirai.application import (
    KNIFE_MIRROR_VARIANT_DEFAULT,
    KNIFE_MIRROR_VARIANT_KEY,
    KNIFE_MIRROR_VARIANTS,
    Application,
)
from mirai.interaction import commands as cmd
from mirai.interaction.input import KNIFE_CONTEXT, Input
from mirai.symmetric_knife import (
    TEXT_KNIFE_FACE_UNPAIRED,
    TEXT_KNIFE_PLANE_IN_FACE,
    TEXT_KNIFE_TARGET_UNPAIRED,
    KnifeRefusal,
    SymmetricKnifeView,
    _cut_pairs,
    coordinate_knife,
)
from mirai.symmetric_ops import TEXT_NON_EXACT_PLANE, TEXT_UNPAIRED
from mirai.symmetry import mirror_position
from mirai.topology.contextual_c import CContext
from mirai.topology.knife_pick import knife_pick
from mirai.topology.knife_preview import KnifeRenderData, build_knife_render_data, target_position
from tests.symmetric_knife_support import (
    T_f,
    asset_path,
    T_v,
    commit_session,
    fresh,
    frozen_sessions,
    fuzz_paths,
    make_session,
    quiet,
    set_plane,
    start_state,
    vertex_at,
)
from viewport.gl_line_overlay import GLLineOverlay
from viewport.overlay import (
    TOOL_ACTIVE_LAYER,
    TOOL_CLIPPED_LAYER,
    TOOL_MIRROR_DIM_LAYER,
    TOOL_MIRROR_LAYER,
    TOOL_MIRROR_PREVIEW_LAYER,
    TOOL_PREVIEW_LAYER,
    TOOL_REFUSED_LAYER,
    TOOL_SYMMETRY_LAYERS,
)

WIDTH, HEIGHT = 800, 600
SEED = 20261009


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


C = _key("c")
V = _key(KNIFE_MIRROR_VARIANT_KEY)
ENTER = _key("enter")
ESC = _key("ESCAPE")
CTRL_Z = _key("z", "ctrl")
CTRL_Y = _key("y", "ctrl")
LMB = Input("mouse", "LEFT", frozenset())
NEW_FIELDS = [
    f.name for f in dataclasses.fields(KnifeRenderData)
    if f.name.startswith(("mirror_", "clipped_", "refused_")) or f.name == "working_side"
]


# ---------------------------------------------------------------------------------------------
# Preview = commit
# ---------------------------------------------------------------------------------------------

def _resolver_path(state: dict, path: list[dict], monkeypatch) -> tuple[list | None, str]:
    """What `coordinate_knife` hands the resolver for `path` (captured), or None when it refused before."""
    captured: list = []
    real = sk.resolve_cross_face

    def spy(mesh, resolver_path, before):
        captured.append(list(resolver_path))
        return real(mesh, resolver_path, before)

    monkeypatch.setattr(sk, "resolve_cross_face", spy)
    out = commit_session(state, path)
    monkeypatch.setattr(sk, "resolve_cross_face", real)
    return (captured[0] if captured else None), out.status


def _check_preview_equals_commit(name: str, path: list[dict], monkeypatch) -> str:
    state = start_state(name)
    mesh = Mesh.from_state(state)
    view = SymmetricKnifeView(mesh)
    data = build_knife_render_data(mesh, path, None, None, symmetry=view)
    try:
        view.clip(path)
        refused = False
    except KnifeRefusal:
        refused = True
    resolver_path, _status = _resolver_path(state, path, monkeypatch)
    if refused:
        assert resolver_path is None                 # the commit refuses the same path before the resolve
        assert data.working_side == 0 and not data.clipped_points
        return "refused"
    if resolver_path is None:
        return "refused-later"                       # unpaired target (the commit's net under F3 = A)
    pids: dict = {}
    for p in resolver_path:
        if p["kind"] != "break" and p["pid"] not in pids:
            pids[p["pid"]] = target_position(mesh, p)
    assert list(data.placed_points) == list(pids.values())
    pairs = [(target_position(mesh, a), target_position(mesh, b)) for a, b in _cut_pairs(resolver_path)]
    assert list(data.path_segments) == pairs
    d = view.definition
    mirror = lambda p: tuple(mirror_position(tuple(p), d.plane_point, d.plane_normal))  # noqa: E731
    assert list(data.mirror_placed_points) == [mirror(p) for p in data.placed_points]
    assert list(data.mirror_path_segments) == [(mirror(a), mirror(b)) for a, b in data.path_segments]
    # the partition: every drawn point is the working side's or the clipped part's
    all_points = {target_position(mesh, p) for p in path if p["kind"] not in ("break", "space")}
    assert set(data.placed_points) | set(data.clipped_points) == all_points
    assert not set(data.placed_points) & set(data.clipped_points)
    return "equal"


def test_preview_equals_commit_for_the_frozen_sessions(monkeypatch):
    seen = {"equal": 0, "refused": 0, "refused-later": 0}
    for s in frozen_sessions():
        if s.mesh not in ("subd_cube", "head_basemesh", "tie_grid", "hole_grid", "span_grid", "hexagon_grid"):
            continue
        seen[_check_preview_equals_commit(s.mesh, s.path, monkeypatch)] += 1
    assert seen["equal"] >= 20, seen


@pytest.mark.parametrize("name", ["subd_cube", "head_basemesh"])
def test_preview_equals_commit_for_a_seeded_both_sides_fuzz(name, monkeypatch):
    rnd = random.Random(SEED)
    seen = {"equal": 0, "refused": 0, "refused-later": 0}
    for path in fuzz_paths(start_state(name), rnd, 45, region="both sides", seam_bias=True):
        seen[_check_preview_equals_commit(name, path, monkeypatch)] += 1
    assert seen["equal"] >= 20, seen


# ---------------------------------------------------------------------------------------------
# The clipped part (tie_grid: flat, x in [-3, 3], seam x = 0)
# ---------------------------------------------------------------------------------------------

def _session_clicks(mesh, *chains):
    knife, scene, view = make_session(mesh)
    with quiet():
        for i, chain in enumerate(chains):
            if i:
                assert knife.lift()
            for pos in chain:
                assert knife.click(T_v(vertex_at(mesh, pos))), (pos, knife.last_plan.reason)
    return knife, view


def test_a_path_across_the_seam_has_its_other_side_part_in_the_clipped_fields():
    mesh = fresh("tie_grid")
    knife, view = _session_clicks(mesh, [(1, 1, 0), (0, 2, 0), (-1, 3, 0)])
    data = build_knife_render_data(mesh, knife.path, None, None, symmetry=view)
    assert data.working_side == 1
    assert data.placed_points == ((1.0, 1.0, 0.0), (0.0, 2.0, 0.0))
    assert data.path_segments == (((1.0, 1.0, 0.0), (0.0, 2.0, 0.0)),)
    assert data.clipped_points == ((-1.0, 3.0, 0.0),)
    assert data.clipped_segments == (((0.0, 2.0, 0.0), (-1.0, 3.0, 0.0)),)
    # the mirror comes from the working side only: the clipped point has no mirror
    assert data.mirror_placed_points == ((-1.0, 1.0, 0.0), (0.0, 2.0, 0.0))
    assert data.mirror_path_segments == (((-1.0, 1.0, 0.0), (0.0, 2.0, 0.0)),)


def test_two_chains_only_the_side_where_the_cut_starts_the_second_side_chain_is_clipped():
    mesh = fresh("tie_grid")
    knife, view = _session_clicks(mesh, [(1, 1, 0), (2, 2, 0)], [(-2, 1, 0), (-1, 2, 0)])
    data = build_knife_render_data(mesh, knife.path, None, None, symmetry=view)
    assert data.placed_points == ((1.0, 1.0, 0.0), (2.0, 2.0, 0.0))
    assert data.clipped_points == ((-2.0, 1.0, 0.0), (-1.0, 2.0, 0.0))
    assert data.clipped_segments == (((-2.0, 1.0, 0.0), (-1.0, 2.0, 0.0)),)
    assert data.mirror_placed_points == ((-1.0, 1.0, 0.0), (-2.0, 2.0, 0.0))
    # ... and the commit does exactly that: the second chain never reaches the resolver
    out = commit_session(start_state("tie_grid"), knife.path)
    assert out.status == "committed"


def test_the_hovered_target_of_the_other_side_is_shown_clipped_not_refused():
    mesh = fresh("tie_grid")
    knife, view = _session_clicks(mesh, [(1, 1, 0), (0, 2, 0)])
    target = T_v(vertex_at(mesh, (-1, 3, 0)))
    assert knife.plan(target).ok                     # a partnered other-side target is accepted (F3 = A)
    data = build_knife_render_data(mesh, knife.path, target, None, symmetry=view)
    assert data.prospective_point is None and data.line_preview is None
    assert (-1.0, 3.0, 0.0) in data.clipped_hover_points
    assert ((0.0, 2.0, 0.0), (-1.0, 3.0, 0.0)) in data.clipped_hover_segments
    assert data.mirror_prospective_point is None and data.mirror_line_preview is None
    assert data.refused_points == ()


def test_a_working_side_hover_is_mirrored_with_its_line_and_edge():
    mesh = fresh("tie_grid")
    knife, view = _session_clicks(mesh, [(1, 1, 0)])
    target = T_v(vertex_at(mesh, (2, 2, 0)))
    data = build_knife_render_data(mesh, knife.path, target, None, symmetry=view)
    assert data.prospective_point == (2.0, 2.0, 0.0)
    assert data.line_preview == ((1.0, 1.0, 0.0), (2.0, 2.0, 0.0))
    assert data.mirror_start_point == (-1.0, 1.0, 0.0)
    assert data.mirror_prospective_point == (-2.0, 2.0, 0.0)
    assert data.mirror_line_preview == ((-1.0, 1.0, 0.0), (-2.0, 2.0, 0.0))


def test_a_pen_up_session_has_no_start_and_no_line_in_the_symmetric_fields_either():
    mesh = fresh("tie_grid")
    knife, view = _session_clicks(mesh, [(1, 1, 0), (2, 2, 0)])
    with quiet():
        assert knife.lift()
    target = T_v(vertex_at(mesh, (3, 3, 0)))
    data = build_knife_render_data(mesh, knife.path, target, None, symmetry=view, pen_up=True)
    assert data.start_point is None and data.line_preview is None
    assert data.mirror_start_point is None and data.mirror_line_preview is None
    assert data.prospective_point == (3.0, 3.0, 0.0) and data.mirror_prospective_point == (-3.0, 3.0, 0.0)


# ---------------------------------------------------------------------------------------------
# No definition: nothing changes
# ---------------------------------------------------------------------------------------------

def test_render_data_without_symmetry_has_every_additive_field_at_its_default():
    mesh = fresh("tie_grid")
    knife, _scene = None, None
    from tests.symmetric_knife_support import make_tool

    knife, _scene = make_tool(mesh, coordinator=None)
    with quiet():
        assert knife.click(T_v(vertex_at(mesh, (1, 1, 0))))
        assert knife.click(T_v(vertex_at(mesh, (2, 2, 0))))
    data = build_knife_render_data(mesh, knife.path, T_v(vertex_at(mesh, (3, 3, 0))), None)
    defaults = {f.name: f.default for f in dataclasses.fields(KnifeRenderData) if f.name in NEW_FIELDS}
    assert {n: getattr(data, n) for n in NEW_FIELDS} == defaults
    assert data.placed_points and data.path_segments


def _app(asset: str, with_definition: bool) -> Application:
    app = Application()
    app.init_scene("obj", obj_path=asset_path(asset))
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    app.knife_clock = itertools.count(0.0, 10.0).__next__
    if with_definition:
        set_plane(app.scene.mesh)
    return app


def _visible(app, side: int = 1) -> list:
    """Vertices the Knife picks as vertices from the live camera, on `side` of the x = 0 plane."""
    mesh = app.scene.mesh
    out = []
    for vid in sorted(mesh.all_vertex_ids(), key=int):
        pos = mesh.vertex_position(vid)
        if pos[0] * side <= 1e-9:
            continue
        sx, sy = app.camera.project_to_screen(pos, WIDTH, HEIGHT)
        t = knife_pick(app.camera, mesh, sx, sy, WIDTH, HEIGHT, cache=app._pick_cache, occlusion=True)
        if t.get("kind") == "vertex" and t["vertex_id"] == vid:
            out.append(vid)
    assert len(out) >= 2
    return out


def _screen(app, vid):
    return app.camera.project_to_screen(app.scene.mesh.vertex_position(vid), WIDTH, HEIGHT)


def _click_vertex(app, vid) -> bool:
    pos = _screen(app, vid)
    app.pointer_motion(*pos)
    app.pointer_press(LMB, *pos)
    return app.pointer_release("LEFT", *pos)


def _begin(app) -> None:
    app.selection.clear()
    assert app.key_press(C) is True
    assert app.knife_active


def test_without_a_definition_the_session_overlay_and_status_are_what_they_were():
    app = _app("subd_cube", with_definition=False)
    _begin(app)
    assert app._knife._symmetric_commit is None and app._knife._symmetric_view is None
    assert "Spiegel" not in app.status_message
    a, b = _visible(app)[:2]
    assert _click_vertex(app, a)
    app.pointer_motion(*_screen(app, b))
    data = app.knife_render_data
    assert {n: getattr(data, n) for n in NEW_FIELDS} == {
        f.name: f.default for f in dataclasses.fields(KnifeRenderData) if f.name in NEW_FIELDS
    }
    vp = app.viewport
    assert vp.tool_point_layers[TOOL_ACTIVE_LAYER] == [data.start_point]
    for layer in TOOL_SYMMETRY_LAYERS:
        assert vp.tool_point_layers[layer] == [] and vp.tool_line_layers[layer] == []
    assert KNIFE_MIRROR_VARIANT_KEY not in app.status_message
    assert app.key_press(V) is False                 # the variant key does nothing without a symmetric session
    assert app.knife_mirror_variant == KNIFE_MIRROR_VARIANT_DEFAULT


# ---------------------------------------------------------------------------------------------
# Variants
# ---------------------------------------------------------------------------------------------

def _symmetric_hover_session():
    app = _app("subd_cube", with_definition=True)
    _begin(app)
    a, b = _visible(app)[:2]
    assert _click_vertex(app, a)
    app.pointer_motion(*_screen(app, b))
    return app, a, b


def _layers(app):
    vp = app.viewport
    return (
        {layer: list(vp.tool_point_layers[layer]) for layer in TOOL_SYMMETRY_LAYERS},
        {layer: list(vp.tool_line_layers[layer]) for layer in TOOL_SYMMETRY_LAYERS},
    )


def test_the_variant_key_is_free_in_the_knife_context_and_not_a_lab_key():
    app = Application()
    assert app.bindings.command_for(V, KNIFE_CONTEXT) is None
    assert app.bindings.command_for(V) is None
    assert KNIFE_MIRROR_VARIANT_KEY == "v"
    assert not any(command in (cmd.KNIFE_COMMIT, cmd.KNIFE_LIFT, cmd.CANCEL, cmd.UNDO, cmd.REDO)
                   for command in [app.bindings.command_for(V, KNIFE_CONTEXT)])


def test_the_variants_cycle_in_the_knife_session_only_default_v_b_and_the_status_names_them():
    app, a, b = _symmetric_hover_session()
    assert KNIFE_MIRROR_VARIANTS == ("V-a", "V-b", "V-c") and app.knife_mirror_variant == "V-b"
    assert "V-b" in app.status_message or "V-b" in _last_say(app)
    seen = []
    for _ in range(3):
        assert app.key_press(V) is True
        seen.append(app.knife_mirror_variant)
        assert app.knife_mirror_variant in app.status_message
        assert "Taste V" in app.status_message
    assert seen == ["V-c", "V-a", "V-b"]
    assert app.key_press(ESC)
    assert app.key_press(V) is False                 # outside the session: ignored
    assert app.knife_mirror_variant == "V-b"


def _last_say(app) -> str:
    # a click's status carries the variant: "[Spiegel V-b]"
    return app.status_message


def test_each_variant_fills_its_own_layers_and_the_layer_depth_state_follows():
    app, a, b = _symmetric_hover_session()
    pa, pb = (tuple(app.scene.mesh.vertex_position(v)) for v in (a, b))
    mirror = lambda p: tuple(mirror_position(p, (0.0, 0.0, 0.0), (1.0, 0.0, 0.0)))  # noqa: E731

    # V-b (default): everything of the mirror in the dimmed always-visible layer
    points, lines = _layers(app)
    assert points[TOOL_MIRROR_DIM_LAYER][:1] == [mirror(pa)] and mirror(pb) in points[TOOL_MIRROR_DIM_LAYER]
    assert lines[TOOL_MIRROR_DIM_LAYER] and not points[TOOL_MIRROR_LAYER] and not lines[TOOL_MIRROR_LAYER]
    assert not points[TOOL_MIRROR_PREVIEW_LAYER] and not lines[TOOL_MIRROR_PREVIEW_LAYER]

    assert app.key_press(V)                           # V-c: the mirror's points only, no lines
    points, lines = _layers(app)
    assert mirror(pa) in points[TOOL_MIRROR_LAYER] and mirror(pb) in points[TOOL_MIRROR_LAYER]
    assert not any(lines[l] for l in (TOOL_MIRROR_LAYER, TOOL_MIRROR_PREVIEW_LAYER, TOOL_MIRROR_DIM_LAYER))
    assert not points[TOOL_MIRROR_DIM_LAYER]

    assert app.key_press(V)                           # V-a: like the working side's own preview
    points, lines = _layers(app)
    assert points[TOOL_MIRROR_LAYER] == [mirror(pa)]
    assert points[TOOL_MIRROR_PREVIEW_LAYER][0] == mirror(pb)   # then the mirrored planner crossings
    assert lines[TOOL_MIRROR_PREVIEW_LAYER] and not lines[TOOL_MIRROR_DIM_LAYER]
    assert not points[TOOL_MIRROR_DIM_LAYER]

    # depth state per layer: V-a's path lines are depth-tested like the working side's, its preview and V-b's
    # dimmed lines are on top; the clipped part is depth-tested like the path
    no_depth = GLLineOverlay.NO_DEPTH_LAYERS
    assert TOOL_PREVIEW_LAYER in no_depth and TOOL_ACTIVE_LAYER not in no_depth
    assert TOOL_MIRROR_LAYER not in no_depth and TOOL_CLIPPED_LAYER not in no_depth
    assert {TOOL_MIRROR_PREVIEW_LAYER, TOOL_MIRROR_DIM_LAYER, TOOL_REFUSED_LAYER} <= no_depth


def test_the_status_of_a_click_names_the_variant_in_a_symmetric_session():
    app, a, b = _symmetric_hover_session()
    assert _click_vertex(app, b)
    assert "[Spiegel V-b]" in app.status_message
    assert app.key_press(V)
    app.key_press(_key("e"))
    assert "[Spiegel V-c]" in app.status_message


# ---------------------------------------------------------------------------------------------
# P2 at hover / click
# ---------------------------------------------------------------------------------------------

def test_a_target_without_partner_is_refused_at_hover_and_click_on_the_man_with_shoes():
    mesh = fresh("man_with_shoes_basemesh", sign=-1)
    knife, _scene, view = make_session(mesh)
    unpaired = next(v for v in sorted(mesh.all_vertex_ids(), key=int) if view.index.vertex_partner(v) is None)
    plan = knife.plan(T_v(unpaired))
    assert not plan.ok and plan.refused and plan.reason == TEXT_KNIFE_TARGET_UNPAIRED
    assert knife.accepts(T_v(unpaired)) is False
    with quiet():
        assert knife.click(T_v(unpaired)) is False
    assert knife.path == []                          # a refused target never enters the path
    paired = next(v for v in sorted(mesh.all_vertex_ids(), key=int)
                  if view.index.vertex_partner(v) is not None and view.side(mesh.vertex_position(v)) == 1)
    with quiet():
        assert knife.click(T_v(paired)) is True


def test_a_cut_through_a_face_without_partner_is_refused_on_the_man_with_shoes():
    mesh = fresh("man_with_shoes_basemesh")
    knife, _scene, view = make_session(mesh)
    index = view.index
    pick = None
    for f in sorted(mesh.all_face_ids(), key=int):
        vs = mesh.face_vertices(f)
        if len(vs) != 4 or index.face_partner(f) is not None:
            continue
        a, b = vs[0], vs[2]
        if all(index.vertex_partner(v) is not None and view.side(mesh.vertex_position(v)) == 1 for v in (a, b)):
            pick = (f, a, b)
            break
    assert pick is not None, "the asset has no quad without partner between partnered corners"
    _f, a, b = pick
    with quiet():
        assert knife.click(T_v(a)) is True           # the target itself has a partner
    plan = knife.plan(T_v(b))
    assert not plan.ok and plan.refused and plan.reason == TEXT_KNIFE_FACE_UNPAIRED
    with quiet():
        assert knife.click(T_v(b)) is False
    assert len(knife.points) == 1


def test_a_cut_through_a_face_with_partner_is_accepted_on_the_man_with_shoes():
    mesh = fresh("man_with_shoes_basemesh")
    knife, _scene, view = make_session(mesh)
    index = view.index
    for f in sorted(mesh.all_face_ids(), key=int):
        vs = mesh.face_vertices(f)
        if len(vs) == 4 and index.face_partner(f) not in (None, f) and all(
                view.side(mesh.vertex_position(v)) == 1 and index.vertex_partner(v) is not None for v in vs):
            with quiet():
                assert knife.click(T_v(vs[0])) is True
                assert knife.plan(T_v(vs[2])).ok
            return
    raise AssertionError("no partnered quad on the working side")


def test_a_cut_across_the_plane_inside_a_spanning_face_is_refused():
    mesh = fresh("span_grid")
    knife, _scene, view = make_session(mesh)
    middle = next(f for f in mesh.all_face_ids() if view.index.face_partner(f) == f)
    with quiet():
        assert knife.click(T_f(middle, (0.25, 0.5, 0.0))) is True
    plan = knife.plan(T_f(middle, (-0.25, 0.5, 0.0)))
    assert not plan.ok and plan.refused and plan.reason == TEXT_KNIFE_PLANE_IN_FACE
    # a cut inside a face that spans the plane is refused on one side too (item 9, as at the commit)
    same_side = knife.plan(T_f(middle, (0.4, 0.8, 0.0)))
    assert not same_side.ok and same_side.refused and same_side.reason == sk.TEXT_KNIFE_ON_PLANE


def test_the_asset_has_no_plane_spanning_face_so_that_case_lives_on_the_span_grid():
    """The handoff names the man_with_shoes for the spanning-face case; the asset (and the head) have none."""
    for name in ("man_with_shoes_basemesh", "head_basemesh"):
        mesh = fresh(name)
        index = SymmetryIndexFor(mesh)
        assert not [f for f in mesh.all_face_ids() if index.face_partner(f) == f]


def SymmetryIndexFor(mesh):
    from mirai.symmetry_coordination import SymmetryIndex

    return SymmetryIndex(mesh)


def test_a_closing_segment_the_view_refuses_is_no_close_the_pen_lifts_instead():
    mesh = fresh("tie_grid")
    knife, _scene, view = make_session(mesh)
    with quiet():
        # a loop that walks over the seam: (1,1) -> (0,2) -> (-1,1) closes back to (1,1) across the plane
        for pos in [(1, 1, 0), (0, 2, 0), (-1, 1, 0)]:
            assert knife.click(T_v(vertex_at(mesh, pos)))
    close = knife.plan_lift(close=True)
    assert close.ok and not close.closing and "not closed" in close.reason


def test_p2_never_disagrees_with_the_commit_over_a_guarded_fuzz():
    """The stop condition of the handoff: a path built under P2 never meets a commit refusal of P2's own
    class (the clip, an unpaired target, a cut face the commit would refuse for its side), on the assets with
    unpaired elements and on the paired ones."""
    front = {TEXT_KNIFE_PLANE_IN_FACE, sk.TEXT_KNIFE_SEED_LOST, TEXT_UNPAIRED, sk.TEXT_KNIFE_ON_PLANE,
             sk.TEXT_KNIFE_OTHER_SIDE}   # the commit's texts for the same reasons
    checked = 0
    for name in ("man_with_shoes_basemesh", "subd_cube", "head_basemesh"):
        state = start_state(name)
        rnd = random.Random(SEED + len(name))
        for path in fuzz_paths(state, rnd, 40, region="both sides", seam_bias=True, guarded=True):
            out = commit_session(state, path)
            checked += 1
            if out.status == "refused":
                assert out.text not in front, (name, out.text)
    assert checked >= 100


def test_a_refused_hover_and_click_in_the_application_use_the_refused_style_and_the_status():
    app = _app("subd_cube", with_definition=False)
    mesh = app.scene.mesh
    victim = _visible(app)[0]
    x, y, z = mesh.vertex_position(victim)
    mesh.set_vertex_position(victim, (x + 0.01, y, z))      # the vertex and its edges lose their partner
    set_plane(mesh)
    _begin(app)
    app.pointer_motion(*_screen(app, victim))
    data = app.knife_render_data
    pos = tuple(mesh.vertex_position(victim))
    assert data.refused_points == (pos,) and data.prospective_point is None
    assert app.status_message == TEXT_KNIFE_TARGET_UNPAIRED
    points, _lines = _layers(app)
    assert points[TOOL_REFUSED_LAYER] == [pos]
    serial = app.status_serial
    app.pointer_motion(*_screen(app, victim))                # the same hover again: the status is not re-posted
    assert app.status_serial == serial
    assert _click_vertex(app, victim) is False               # the click is ignored ...
    assert app._knife.points == []                           # ... and adds nothing
    assert app.status_message == TEXT_KNIFE_TARGET_UNPAIRED
    other = next(v for v in _visible(app) if v != victim)
    app.pointer_motion(*_screen(app, other))                 # leaving the refused target clears it
    assert app.knife_render_data.refused_points == ()
    assert app.status_message != TEXT_KNIFE_TARGET_UNPAIRED


# ---------------------------------------------------------------------------------------------
# Begin, wiring, residue, undo
# ---------------------------------------------------------------------------------------------

def test_begin_on_a_non_exact_plane_starts_no_session():
    app = _app("subd_cube", with_definition=False)
    app.scene.mesh.symmetry_definition = SymmetryDefinition((0.0, 0.0, 0.0), (0.6, 0.8, 0.0), frozenset())
    app.selection.clear()
    serial = app.status_serial
    assert app.key_press(C) is False
    assert not app.knife_active
    assert app.status_message == TEXT_NON_EXACT_PLANE and app.status_serial == serial + 1
    assert app.key_press(V) is False


def _one_side_cut(app):
    """Two diagonal corners of a quad entirely on +X, both picked as vertices from the live camera."""
    mesh = app.scene.mesh
    for fid in sorted(mesh.all_face_ids(), key=int):
        vids = mesh.face_vertices(fid)
        if len(vids) != 4 or any(mesh.vertex_position(v)[0] <= 1e-9 for v in vids):
            continue
        ok = []
        for v in (vids[0], vids[2]):
            t = knife_pick(app.camera, mesh, *_screen(app, v), WIDTH, HEIGHT, cache=app._pick_cache, occlusion=True)
            ok.append(t.get("kind") == "vertex" and t["vertex_id"] == v)
        if all(ok):
            return vids[0], vids[2]
    raise AssertionError("no +X quad with a visible diagonal")


def _topology(mesh) -> dict:
    """`export_state()` without the monotonic ID counters (an Undo does not rewind them)."""
    return {k: v for k, v in mesh.export_state().items() if not k.endswith("_id_counter")}


def test_a_definition_makes_the_session_pass_the_coordinator_and_enter_cuts_both_sides_in_one_entry():
    app = _app("subd_cube", with_definition=True)
    mesh = app.scene.mesh
    a, b = _one_side_cut(app)
    state_before = _topology(mesh)
    definition = mesh.symmetry_definition
    entries = len(app.history)
    edges = len(mesh.all_edge_ids())
    _begin(app)
    assert app._knife._symmetric_commit is coordinate_knife
    assert _click_vertex(app, a) and _click_vertex(app, b)
    assert app.key_press(ENTER) is True
    assert not app.knife_active
    assert len(app.history) == entries + 1                     # one history entry for both sides
    assert len(mesh.all_edge_ids()) == edges + 2               # the cut and its mirror
    # residue F4 = A: only the working side's cut edge is selected
    assert len(app.selection.edges) == 1
    for e in app.selection.edges:
        assert all(mesh.vertex_position(v)[0] >= 0.0 for v in mesh.edge_vertices(e))
    after = _topology(mesh)
    assert app.key_press(CTRL_Z) is True                       # Undo restores both sides and the seam
    assert _topology(mesh) == state_before and mesh.symmetry_definition == definition
    assert app.key_press(CTRL_Y) is True
    assert _topology(mesh) == after


def test_the_application_cut_equals_the_coordinator_on_the_same_path():
    app = _app("subd_cube", with_definition=True)
    a, b = _one_side_cut(app)
    state = app.scene.mesh.export_state()
    _begin(app)
    assert _click_vertex(app, a) and _click_vertex(app, b)
    path = app._knife.path
    app.key_press(ENTER)
    reference = commit_session(state, path)
    assert reference.status == "committed"
    assert _topology(app.scene.mesh) == _topology(reference.mesh)


# ---------------------------------------------------------------------------------------------
# Declaration
# ---------------------------------------------------------------------------------------------

def test_the_knife_context_is_declared_and_the_other_rows_are_unchanged():
    assert symmetry_declarations.declared_c_contexts() == {
        CContext.SPLIT, CContext.EDGE_CONNECT, CContext.VERTEX_CONNECT, CContext.KNIFE,
    }
    assert symmetry_declarations.C_CONTEXT_COORDINATORS[CContext.KNIFE] is coordinate_knife
    assert symmetry_declarations.declared_removal_commands() == {cmd.DELETE, cmd.DISSOLVE, cmd.DISSOLVE_NO_CLEANUP}


# ---------------------------------------------------------------------------------------------
# Hover cost (numbers only)
# ---------------------------------------------------------------------------------------------

def _hover_ms(with_definition: bool, rounds: int = 3) -> tuple[float, float]:
    app = _app("head_basemesh", with_definition=with_definition)
    _begin(app)
    vis = _visible(app) if with_definition else _visible_any(app)
    assert _click_vertex(app, vis[0])
    assert _click_vertex(app, vis[1])
    positions = [_screen(app, v) for v in vis[2:42]]
    samples = []
    for _ in range(rounds):
        for pos in positions:
            t0 = time.perf_counter()
            app.pointer_motion(*pos)
            samples.append(1000 * (time.perf_counter() - t0))
    return statistics.median(samples), sorted(samples)[int(0.95 * len(samples))]


def _visible_any(app) -> list:
    """Like `_visible` but on both sides (the plain Knife has no side)."""
    mesh = app.scene.mesh
    out = []
    for vid in sorted(mesh.all_vertex_ids(), key=int):
        pos = mesh.vertex_position(vid)
        if pos[0] <= 1e-9:
            continue
        sx, sy = app.camera.project_to_screen(pos, WIDTH, HEIGHT)
        t = knife_pick(app.camera, mesh, sx, sy, WIDTH, HEIGHT, cache=app._pick_cache, occlusion=True)
        if t.get("kind") == "vertex" and t["vertex_id"] == vid:
            out.append(vid)
    return out


def test_hover_cost_with_and_without_a_definition_on_the_head(capsys):
    plain = _hover_ms(False)
    symmetric = _hover_ms(True)
    with capsys.disabled():
        print(f"\n[cost] head_basemesh hover (pick + plan + overlay): median/p95 "
              f"plain {plain[0]:.2f}/{plain[1]:.2f} ms, symmetric {symmetric[0]:.2f}/{symmetric[1]:.2f} ms "
              f"(x{symmetric[0] / plain[0]:.2f}); {platform.processor() or platform.machine()}, "
              f"python {platform.python_version()}, {platform.system()} {platform.release()}")
    assert symmetric[0] > 0 and plain[0] > 0
