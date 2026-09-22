"""Connect Lab — headless tests (no GL, no window).

Covers the Discovery variant `connect_per_face.py`, the variant resolver
`playground.experiments.connect.active_connect_fn`, and the grid test scene.
These tests pin mechanics only; whether the per-face semantics are RIGHT
is an open Artist question (CONNECT_NONQUAD_DISCOVERY.md §6).
"""

from __future__ import annotations

import collections
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_REPO_ROOT / "src"), str(_REPO_ROOT), str(_REPO_ROOT / "tests"),
           str(_REPO_ROOT / "experiments" / "rigging-skinning-morphing")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402

from mesh_invariants import assert_mesh_invariants  # noqa: E402
from playground.app import PlaygroundApp  # noqa: E402
from playground.slot import ExperimentSlot, VariantEntry  # noqa: E402
from playground.experiments.connect import active_connect_fn  # noqa: E402
from playground.experiments.connect.demo_grid import build_grid  # noqa: E402
from playground.experiments.connect.variant_strip import ConnectStripVariant  # noqa: E402
from playground.experiments.connect.variant_per_face import ConnectPerFaceVariant  # noqa: E402
from playground.topology_tools.connect_edges import (  # noqa: E402
    connect_selected_edges,
    TopologyToolError,
)
from playground.topology_tools.connect_per_face import (  # noqa: E402
    connect_selected_edges_per_face as connect_pf,
)


# ---------------------------------------------------------------------------
# Helpers — 4x4 grid with integer coordinates (as in the characterization tests)
# ---------------------------------------------------------------------------

def _app_with_grid(n: int = 4):
    app = PlaygroundApp()
    app.load_grid()
    grid = build_grid(n=n, size=float(n))  # unit spacing, centred
    app.scene.mesh.load_state(grid.export_state())
    mesh = app.scene.mesh
    half = n / 2.0
    p = {}
    for v in mesh.all_vertex_ids():
        x, y, _ = mesh.vertex_position(v)
        p[(round(y + half), round(x + half))] = v
    return app, mesh, p


def _e(mesh, a, b):
    return next(e for e in mesh.all_edge_ids() if set(mesh.edge_vertices(e)) == {a, b})


def _sizes(mesh):
    return dict(collections.Counter(len(mesh.face_vertices(f)) for f in mesh.all_face_ids()))


SCENARIOS = {
    "A_partial_1": (lambda m, p: {_e(m, p[(1, 1)], p[(2, 1)]), _e(m, p[(1, 2)], p[(2, 2)])},
                    {4: 15, 5: 2}),
    "B_partial_2": (lambda m, p: {_e(m, p[(1, c)], p[(2, c)]) for c in (1, 2, 3)},
                    {4: 16, 5: 2}),
    "C_boundary": (lambda m, p: {_e(m, p[(1, c)], p[(2, c)]) for c in range(5)},
                   {4: 20}),
    "D_corner": (lambda m, p: {_e(m, p[(1, 1)], p[(1, 2)]), _e(m, p[(1, 2)], p[(2, 2)])},
                 {3: 1, 4: 13, 5: 3}),
    "G_turn": (lambda m, p: {_e(m, p[(1, 1)], p[(2, 1)]), _e(m, p[(1, 2)], p[(2, 2)]),
                             _e(m, p[(2, 2)], p[(2, 3)])},
               {3: 1, 4: 14, 5: 3}),
    "I_all_four": (lambda m, p: {_e(m, p[(1, 1)], p[(1, 2)]), _e(m, p[(1, 2)], p[(2, 2)]),
                                 _e(m, p[(2, 2)], p[(2, 1)]), _e(m, p[(2, 1)], p[(1, 1)])},
                   {3: 4, 4: 12, 5: 4}),
}


# ---------------------------------------------------------------------------
# Per-face variant — results, invariants, history
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", list(SCENARIOS))
def test_per_face_scenario_results_and_invariants(name):
    sel_fn, expected = SCENARIOS[name]
    app, mesh, p = _app_with_grid()
    created = connect_pf(app.scene, sel_fn(mesh, p))
    assert created
    assert _sizes(mesh) == expected
    assert not [e for e in mesh.all_edge_ids() if len(mesh.edge_faces(e)) == 0]
    assert_mesh_invariants(mesh, context=name)
    assert len(app.scene.history) == 1


@pytest.mark.parametrize("sel", [
    lambda m, p: {_e(m, p[(2, 1)], p[(2, 2)]), _e(m, p[(2, 2)], p[(2, 3)])},  # "kind v"
    lambda m, p: {_e(m, p[(1, 1)], p[(2, 1)]), _e(m, p[(1, 3)], p[(2, 3)])},  # gap
])
def test_per_face_unconnectable_selection_is_rejected_atomically(sel):
    app, mesh, p = _app_with_grid()
    state = mesh.export_state()
    with pytest.raises(TopologyToolError):
        connect_pf(app.scene, sel(mesh, p))
    assert mesh.export_state() == state
    assert len(app.scene.history) == 0


def test_per_face_single_edge_rejected():
    app, mesh, p = _app_with_grid()
    with pytest.raises(TopologyToolError):
        connect_pf(app.scene, {_e(mesh, p[(1, 1)], p[(2, 1)])})


def test_per_face_works_on_pentagon_left_by_previous_partial_connect():
    """The core difference to the baseline (F2): work continues next to a pentagon."""
    app, mesh, p = _app_with_grid()
    connect_pf(app.scene, SCENARIOS["A_partial_1"][0](mesh, p))
    # Corner cut in the pentagon to the right of the first cut.
    top = _e(mesh, p[(1, 2)], p[(1, 3)])
    right = _e(mesh, p[(1, 3)], p[(2, 3)])
    connect_pf(app.scene, {top, right})
    assert_mesh_invariants(mesh, context="after pentagon connect")
    assert len(app.scene.history) == 2

    # Baseline refuses exactly this step (characterization F2).
    app2, mesh2, p2 = _app_with_grid()
    connect_selected_edges(app2.scene, SCENARIOS["A_partial_1"][0](mesh2, p2))
    with pytest.raises(TopologyToolError):
        connect_selected_edges(app2.scene, {_e(mesh2, p2[(1, 2)], p2[(1, 3)]),
                                            _e(mesh2, p2[(1, 3)], p2[(2, 3)])})


def _topology(mesh):
    """State without the monotonic ID counters (AD-001: IDs are never reused,
    so counters legitimately keep advancing across undo)."""
    return {k: v for k, v in mesh.export_state().items() if not k.endswith("_id_counter")}


def test_per_face_undo_redo_roundtrip():
    app, mesh, p = _app_with_grid()
    before = _topology(mesh)
    connect_pf(app.scene, SCENARIOS["D_corner"][0](mesh, p))
    after = _topology(mesh)
    app.undo()
    assert _topology(mesh) == before
    app.redo()
    assert _topology(mesh) == after


def test_per_face_deterministic_regardless_of_set_order():
    results = []
    for rev in (False, True):
        app, mesh, p = _app_with_grid()
        edges = sorted(SCENARIOS["I_all_four"][0](mesh, p), key=int, reverse=rev)
        connect_pf(app.scene, set(edges))
        results.append(mesh.export_state())
    assert results[0] == results[1]


def test_boundary_to_boundary_matches_baseline_result():
    """Ring/boundary case: both semantics give the same topology (D7, Loop Insert safety)."""
    app1, m1, p1 = _app_with_grid()
    connect_selected_edges(app1.scene, SCENARIOS["C_boundary"][0](m1, p1))
    app2, m2, p2 = _app_with_grid()
    connect_pf(app2.scene, SCENARIOS["C_boundary"][0](m2, p2))
    assert _sizes(m1) == _sizes(m2) == {4: 20}
    pos1 = sorted(tuple(round(c, 9) for c in m1.vertex_position(v)) for v in m1.all_vertex_ids())
    pos2 = sorted(tuple(round(c, 9) for c in m2.vertex_position(v)) for v in m2.all_vertex_ids())
    assert pos1 == pos2


# ---------------------------------------------------------------------------
# Resolver — baseline stays default (AD-013 A2)
# ---------------------------------------------------------------------------

def test_resolver_without_connect_family_returns_baseline():
    assert active_connect_fn({}) is connect_selected_edges


def test_resolver_default_variant_is_baseline_and_switches():
    app = PlaygroundApp()
    slot = ExperimentSlot(
        VariantEntry(ConnectStripVariant(app)),
        VariantEntry(ConnectPerFaceVariant(app)),
    )
    app.register_slot(slot, "connect")
    assert active_connect_fn(app.slots) is connect_selected_edges
    app.activate_variant("connect", 1)
    assert active_connect_fn(app.slots) is connect_pf
    app.activate_variant("connect", 0)
    assert active_connect_fn(app.slots) is connect_selected_edges


def test_loop_insert_still_uses_baseline_connect():
    import playground.topology_tools.loop_insert as li
    assert li.connect_selected_edges is connect_selected_edges


# ---------------------------------------------------------------------------
# Grid scene
# ---------------------------------------------------------------------------

def test_load_grid_scene():
    app = PlaygroundApp()
    app.load_grid()
    mesh = app.scene.mesh
    assert _sizes(mesh) == {4: 64}
    assert len(list(mesh.all_vertex_ids())) == 81
    assert_mesh_invariants(mesh, context="grid")
