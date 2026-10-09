"""Replay of the Knife resolver's kept-call report (AD-017 §13 item 5) — shared by
`tests/test_knife_kept_calls.py` and `playground/tests/test_knife_kept_calls_golden.py`.

Not a test module (no `test_` prefix). A reader of the report works like this: a copy of the session-start
state, each entry's call made verbatim with the ids it names mapped through the results of the calls
before it (an id that no entry created is an id of the session-start mesh and maps to itself).

The resolved mesh and the replay agree up to ids: a call that a rollback took back still burned its ids
(`Mesh.load_state` moves the allocator counters only forward, AD-001), so the resolved mesh's later ids are
higher than the replay's. `assert_report_replays` therefore compares the two through the id maps the replay
built (counters only have to be at least the replay's), and compares the raw `export_state()` of both as
well whenever no rollback burned an id.

The id types are `int` subclasses that compare equal across kinds (`VertexId(3) == EdgeId(3)`), so the
maps are kept per kind.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core import Mesh


@dataclass
class IdMaps:
    """Report id -> replay id, per kind."""

    vertices: dict = field(default_factory=dict)
    edges: dict = field(default_factory=dict)
    faces: dict = field(default_factory=dict)


def replay_kept_calls(start_state: dict, kept) -> tuple[Mesh, IdMaps]:
    """(the replayed mesh, the id maps). An unknown op kind is an error, never treated as a known
    one (AD-017 §13 item 6)."""
    mesh = Mesh.from_state(start_state)
    ids = IdMaps()

    def v(x):
        return ids.vertices.get(x, x)

    for call in kept:
        if call.op == "split_edge":
            vertex, half_1, half_2 = mesh.split_edge(ids.edges.get(call.edge_id, call.edge_id), call.t)
            ids.vertices[call.vertex] = vertex
            ids.edges[call.half_1], ids.edges[call.half_2] = half_1, half_2
        elif call.op == "split_face":
            new_vs, new_edges, face_1, face_2 = mesh.split_face(
                ids.faces.get(call.face_id, call.face_id), v(call.a), v(call.b), call.positions)
            ids.vertices.update(zip(call.new_vertices, new_vs))
            ids.edges.update(zip(call.new_edges, new_edges))
            ids.faces[call.face_1], ids.faces[call.face_2] = face_1, face_2
        else:
            raise AssertionError(f"unknown kept-call op {call.op!r}")
    return mesh, ids


def _content(state: dict) -> dict:
    return {k: v for k, v in state.items() if not k.endswith("_counter")}


def _relabelled(state: dict, ids: IdMaps) -> dict:
    """`state` with every id the report created renamed to the replay's id."""
    vmap = {int(k): int(v) for k, v in ids.vertices.items()}
    emap = {int(k): int(v) for k, v in ids.edges.items()}
    fmap = {int(k): int(v) for k, v in ids.faces.items()}

    def v(x):
        return vmap.get(int(x), int(x))

    def e(x):
        return emap.get(int(x), int(x))

    def f(x):
        return fmap.get(int(x), int(x))

    out = dict(_content(state))
    out["vertices"] = {v(k): pos for k, pos in state["vertices"].items()}
    out["edges"] = {e(k): {"v0": v(d["v0"]), "v1": v(d["v1"]), "faces": [f(x) for x in d["faces"]]}
                    for k, d in state["edges"].items()}
    out["faces"] = {f(k): [v(x) for x in b] for k, b in state["faces"].items()}
    if "symmetry" in state and state["symmetry"] is not None:
        out["symmetry"] = dict(state["symmetry"], seam_edges=[e(x) for x in state["symmetry"]["seam_edges"]])
    return out


def assert_report_replays(start_state: dict, kept, resolved_state: dict, context: str = "") -> bool:
    """The report, replayed verbatim on a copy of `start_state`, rebuilds `resolved_state` (up to the ids
    a rollback burned, see the module docstring). Returns True if rollbacks burned ids (the resolved
    mesh's counters are ahead of the replay's), False if the two `export_state()` are equal outright."""
    replay, ids = replay_kept_calls(start_state, kept)
    replayed = replay.export_state()
    got, want = _relabelled(resolved_state, ids), _content(replayed)
    assert got == want, f"the replayed report does not rebuild the resolved mesh {context}"
    counters = [k for k in replayed if k.endswith("_counter")]
    assert all(resolved_state[k] >= replayed[k] for k in counters), f"counters moved backwards {context}"
    burned = any(resolved_state[k] != replayed[k] for k in counters)
    if not burned:
        assert resolved_state == replayed, f"export_state differs {context}"
    return burned
