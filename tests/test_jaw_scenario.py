"""AD-028 T-7: the jaw scenario (Manu 2026-10-29, the Artist acceptance of AD-025 Phase 6), as readable named steps in
the AD-027 scenario style - every step one or a few events through the public entry points
(`tests/interaction_trace.py`), headless, on the head basemesh with symmetry X.

group "Jaw" -> pivot in the joint -> add the bone -> weights from the group with a width -> a Soft correction at the
mouth corner -> rotate the jaw (E, X) -> a morph target shaped beside the base -> rest -> Loop Insert at the mouth
corner -> pose again. Then: bones, weights (the rule at the new loop, W1-W4), offsets (the rule) and the posed
surface (= `skinning.evaluate` of the mix) as stated; Undo to the start and Redo to the end exact; save -> load
bit-exact (rig, weights, targets; rest pose after the load).
"""

from __future__ import annotations

import math

import tests._bootstrap  # noqa: F401
from core import Mesh
from core.mesh import LayerKind, combine_values
from mirai.morph_targets import blend, morph_target_ids
from mirai.skinning import evaluate, skin_layer
from mirai.symmetry import vertex_correspondence
from tests.interaction_trace import CTRL_Y, CTRL_Z, HEIGHT, OVERLAYS, WIDTH, Driver, key
from tests.mesh_invariants import assert_layer_invariants
from tests.rig_support import (
    BONE_ADD, CTRL_G, E, FALLOFF, O, POSE_MODE, POSE_TOGGLE, WEIGHT, head_driver, hinge_point, hold, jaw_faces,
    place_pivot, select_faces, weights,
)

#: The scenario runs with this driver; the purity check below swaps in one that checks `can_run` at every step.
make_driver = Driver

CTRL_ALT_N, CTRL_N, TAB, N, W, I, X = (
    key("n", "ctrl", "alt"), key("n", "ctrl"), key("tab"), key("n"), key("w"), key("i"), key("x")
)


# -- the steps ---------------------------------------------------------------------------------------------------


def group_jaw(d: Driver) -> set:
    """In `3` the lower front faces, Ctrl+G, then Ctrl+Alt+N until the group is called "Jaw"."""
    app = d.app
    faces = jaw_faces(app.scene.mesh)
    select_faces(d, faces)
    d.tap(CTRL_G)
    while app.active_region != "Jaw":
        d.tap(CTRL_ALT_N)
    assert app.active_region_faces == len(faces)
    return faces


def pivot_in_the_joint(d: Driver) -> None:
    place_pivot(d, hinge_point(d.app.scene.mesh))
    assert d.app.status_message.startswith("Working Pivot placed on the symmetry plane")


def add_the_bone(d: Driver):
    d.tap(BONE_ADD)
    app = d.app
    (bone,) = app.scene.rig.bones
    assert app.current_bone == bone.id
    return bone


def weights_from_the_group(d: Driver, width_px: float = 30.0) -> None:
    hold(d, FALLOFF, ((width_px, 0),))
    assert d.app.status_message.endswith("committed (Ctrl+Z takes it back)")


def mouth_corner(mesh) -> object:
    """The mouth corner: of the +X points the jaw holds partly, the one farthest forward (then highest)."""
    w = weights(mesh)
    part = [v for v, value in w.items() if value[0][1] < 1.0 and mesh.vertex_position(v)[0] > 0.0]
    return max(part, key=lambda v: (mesh.vertex_position(v)[2], mesh.vertex_position(v)[1], -int(v)))


def soft_correction_at_the_mouth_corner(d: Driver, corner) -> None:
    """`1`, the corner selected, Soft on, Set weight held + mouse right, Soft off again."""
    app = d.app
    d.tap(key("1"))
    app.selection.vertices = {corner}
    d.tap(O)
    hold(d, WEIGHT, ((45, 0),))
    assert app.status_message.endswith("committed (Ctrl+Z takes it back)") and "(Soft)" in app.status_message
    d.tap(O)


def rotate_the_jaw(d: Driver) -> None:
    """The view turned aside (Alt+LMB drag: from the front the eye lies on the hinge's plane), `5`, X, E held."""
    d.motion(WIDTH * 0.5, HEIGHT * 0.5)
    d.press("LEFT", ("alt",))
    d.motion(WIDTH * 0.5 + 120, HEIGHT * 0.5)
    d.release("LEFT")
    d.modifiers_to(())
    d.motion(WIDTH * 0.65, HEIGHT * 0.45)
    d.tap(POSE_MODE)
    d.tap(X)
    hold(d, E, ((0, -25), (4, -20)))
    assert d.app.posed and d.app.status_message.startswith("Pose: 'Bone 1' rotated"), d.app.status_message


def a_morph_target_beside_the_base(d: Driver, corner) -> None:
    """Out of pose mode, Ctrl+N, Tab, the corner moved (W), Tab back, N held + mouse = 60 %."""
    app = d.app
    d.tap(key("1"))
    d.tap(CTRL_N)
    d.tap(TAB)
    assert app.morph_view_open
    app.selection.vertices = {corner}
    hold(d, W, ((10, 6),))
    assert app.status_message == "Move committed"
    d.tap(TAB)
    assert not app.morph_view_open
    d.key_down(N)
    d.nudge(180, 0)  # 3 px per percent
    d.key_up("n")
    assert app.morph_weight == 60


def loop_insert_at_the_mouth_corner(d: Driver, corner) -> None:
    """Refused in the pose (the text names the toggle); 6 = rest, `2`, an edge at the corner, I, 6 = the pose again."""
    app = d.app
    d.tap(key("2"))
    mesh = app.scene.mesh
    edge = max(mesh.vertex_edges(corner), key=lambda e: int(e))
    app.selection.edges = {edge}
    state = mesh.export_state()
    d.tap(I)
    assert app.status_message == "Loop Insert: the mesh is posed (6 = rest pose)" and mesh.export_state() == state
    d.tap(POSE_TOGGLE)
    assert not app.posed
    app.selection.edges = {edge}
    d.tap(I)
    assert app.status_message.startswith("Loop Insert"), app.status_message
    assert len(list(mesh.all_vertex_ids())) > len(state["vertices"])
    d.tap(POSE_TOGGLE)
    assert app.posed


# -- what holds at the end ----------------------------------------------------------------------------------


def _midpoints(ref: Mesh) -> dict:
    out = {}
    for e in ref.all_edge_ids():
        a, b = ref.edge_vertices(e)
        pa, pb = ref.vertex_position(a), ref.vertex_position(b)
        out[tuple(x * 0.5 + y * 0.5 for x, y in zip(pa, pb))] = (a, b)
    return out


def assert_the_loop_follows_the_rules(ref: Mesh, mesh: Mesh) -> int:
    """Every new vertex is an edge midpoint of the mesh before the insert: weights the §3.5 blend, offsets the
    vector blend (AD-025 §3), W1-W4."""
    mids = _midpoints(ref)
    new = [v for v in mesh.all_vertex_ids() if not ref.is_valid_vertex(v)]
    skin = skin_layer(mesh)
    for v in new:
        a, b = mids[tuple(mesh.vertex_position(v))]
        for lid in mesh.point_layer_ids():
            kind = mesh.point_layer_info(lid).kind
            expected = combine_values(kind, ((ref.layer_value(lid, a), 0.5), (ref.layer_value(lid, b), 0.5)), "midpoint")
            if kind is LayerKind.VECTOR and expected == (0.0, 0.0, 0.0):
                expected = (0.0, 0.0, 0.0)
            assert mesh.layer_value(lid, v) == expected, (v, lid)
        assert skin is not None
    assert_layer_invariants(mesh)
    return len(new)


def assert_the_posed_surface_is_the_definition(d: Driver) -> None:
    app = d.app
    assert app.posed
    app.update_viewport(0)
    mesh = app.scene.mesh
    (target,) = morph_target_ids(mesh)
    mix = {v: blend(mesh.vertex_position(v), mesh.layer_value(target, v), app.morph_weight) for v in mesh.all_vertex_ids()}
    expected = evaluate(mesh, mix, app.scene.rig, app.pose, None)
    surface = app.skin.provider.surface_mesh
    assert surface is not None
    assert all(tuple(surface.vertex_position(v)) == expected[v] for v in mesh.all_vertex_ids())
    moved = [v for v in mesh.all_vertex_ids() if math.dist(expected[v], mesh.vertex_position(v)) > 1e-6]
    assert moved and all(v in weights(mesh) or mesh.layer_value(target, v) != (0.0, 0.0, 0.0) for v in moved)


def assert_symmetric_weights(mesh) -> None:
    w = weights(mesh)
    for v, c in vertex_correspondence(mesh).items():
        partner = getattr(c, "partner", None)
        if partner is not None:
            assert w.get(v) == w.get(partner), (v, partner)


# -- the scenario --------------------------------------------------------------------------------------------


def run_jaw_scenario(tmp_path) -> None:
    d = head_driver(driver=make_driver)
    app = d.app
    mesh = app.scene.mesh
    start = (mesh.export_state(), app.scene.rig)
    start_depth = len(app.history)  # symmetry X
    group_jaw(d)
    pivot_in_the_joint(d)
    bone = add_the_bone(d)
    assert abs(bone.head[0]) <= 1e-12 and abs(bone.tail[0]) <= 1e-12  # on the plane: symmetric weights allowed
    weights_from_the_group(d)
    assert_symmetric_weights(mesh)
    corner = mouth_corner(mesh)
    before = weights(mesh)[corner]
    soft_correction_at_the_mouth_corner(d, corner)
    assert weights(mesh)[corner] != before
    assert_symmetric_weights(mesh)  # the partner got the same correction (an on-plane bone)
    rotate_the_jaw(d)
    a_morph_target_beside_the_base(d, corner)
    assert_the_posed_surface_is_the_definition(d)
    ref = Mesh.from_state(mesh.export_state())
    loop_insert_at_the_mouth_corner(d, corner)
    assert assert_the_loop_follows_the_rules(ref, mesh) >= 2
    assert_symmetric_weights(mesh)
    assert app.scene.rig.bones == (bone,)
    assert_the_posed_surface_is_the_definition(d)

    # Undo to the start, Redo to the end: exact. The pose is view state: Undo never writes it, but undoing "Add bone"
    # takes the bone's pose channel with it, and Redo brings the bone back at rest (AD-028 §6).
    end = (mesh.export_state(), app.scene.rig)
    depth = len(app.history) - start_depth
    for _ in range(depth):
        d.tap(CTRL_Z)
    assert ({k: v for k, v in mesh.export_state().items() if not k.endswith("_counter")}, app.scene.rig) == (
        {k: v for k, v in start[0].items() if not k.endswith("_counter")}, start[1]
    )
    for _ in range(depth):
        d.tap(CTRL_Y)
    assert (mesh.export_state(), app.scene.rig) == end
    assert not app.posed and app.pose == {}
    rotate_the_jaw(d)
    assert_the_posed_surface_is_the_definition(d)
    d.tap(key("1"))

    # save -> load: bit-exact, at rest
    path = tmp_path / "jaw.mirai.json"
    assert app.save_scene_file(path), app.status_message
    app.load_scene("file", scene_path=path, **OVERLAYS)
    loaded = app.scene.mesh
    assert loaded.export_state() == end[0] and app.scene.rig == end[1]
    assert app.pose == {} and not app.posed and not app.pose_mode and app.morph_weight == 0


def test_the_jaw_scenario(tmp_path) -> None:
    run_jaw_scenario(tmp_path)


def test_can_run_is_pure_through_the_jaw_scenario(tmp_path, monkeypatch) -> None:
    """AD-027 E5 (iv) on this scenario: every command from every source asked twice after every event - the same
    answer, the same observation (the bound cache is not state anyone observes)."""
    from tests.test_interaction_structure import _PurityDriver

    monkeypatch.setattr(__import__(__name__, fromlist=["make_driver"]), "make_driver", _PurityDriver)
    run_jaw_scenario(tmp_path)
