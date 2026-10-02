"""WP-KNIFE-01 S4 oracle — the Lab's Q5 on cross-face sequences with fixed cameras, frozen before the planner moves.

Not a test module itself (no `test_` prefix): `test_knife_cross_face_golden.py` replays what this driver
recorded in `golden/knife_cross_face.json` through the Lab's Q5 (must stay identical: the planner moves to
`src`, behaviour unchanged, S5 of the S4 handoff) and through the Production `KnifeTool` (must reproduce it
once it plans across faces — the intended P10 flip). Run directly to (re)write or check the file:

    python playground/tests/knife_cross_face_golden_driver.py           # write golden/knife_cross_face.json
    python playground/tests/knife_cross_face_golden_driver.py --check   # compare only, print differences

Sequences are click specs in world positions (`knife_q5_differential_driver`'s format — `v` / `e` / `f`,
`"undo"` / `"redo"`, `("cam", yaw, pitch)` = orbit, `("occl", bool)` = occlusion on / off, `"commit"` = commit
and a new session on the same mesh) under a starting view `(yaw, pitch, occlusion)` of the play-test camera
(1280 x 800). The head sequences are generated once from seeded screen picks (`knife_face_pick` with
occlusion) and stored with the results, so the oracle never depends on regenerating them.

Recorded per sequence (no ids): which clicks were accepted, per click the planner's method, its hidden
crossing count and the crossings the click stored (kind + position), the final path (kinds, positions, point
identity, breaks, the crossing flag), V/E/F, a position-canonical hash of the faces, the residue and mode,
the History length and its Undo / Redo, and every count of the commit's `KnifeResolution`.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT / "src"), str(_ROOT), str(_ROOT / "tests"),
           str(_ROOT / "experiments" / "rigging-skinning-morphing")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core import Mesh  # noqa: E402

from playground.experiments.knife_face.engine import knife_face_pick  # noqa: E402
from playground.tests.knife_golden_driver import H, W, build_grid, build_scene, camera  # noqa: E402
from playground.tests.knife_q5_differential_driver import (  # noqa: E402
    FACE_CLEARANCE_PX,
    Side,
    e,
    f,
    face_key,
    play_production,
    play_q5,
    v,
)

GOLDEN_PATH = Path(__file__).resolve().parent / "golden" / "knife_cross_face.json"
GRID_VIEW = (20.0, 35.0, True)
FRONT_VIEW = (0.0, 0.0, True)
CUBE_VIEW = (35.0, 30.0, True)


# -- scenes ------------------------------------------------------------------------------------

def _grid_with(n: int = 4, hole=None, occluder: bool = False) -> Mesh:
    mesh, p = Mesh(), {}
    for r in range(n + 1):
        for c in range(n + 1):
            p[(r, c)] = mesh.add_vertex((float(c), float(r), 0.0))
    for r in range(n):
        for c in range(n):
            if (c, r) != hole:
                mesh.add_face([p[(r, c)], p[(r, c + 1)], p[(r + 1, c + 1)], p[(r + 1, c)]])
    if occluder:  # a small quad in front hiding the x = 2 crossing of a y = 1.5 line seen from the front
        occ = [mesh.add_vertex(q) for q in ((1.6, 1.2, 0.6), (2.4, 1.2, 0.6), (2.4, 1.8, 0.6), (1.6, 1.8, 0.6))]
        mesh.add_face(occ)
    return mesh


def scene(name: str) -> Mesh:
    if name == "grid6":
        return build_grid(6)
    if name == "grid_hole":
        return _grid_with(hole=(2, 1))
    if name == "grid_occluded":
        return _grid_with(occluder=True)
    return build_scene(name)


# -- handwritten sequences (the Q5 tests and play-test tasks, decision.md "Q5 — Artist test") ----------
# Grid: quad (c, r) = [c, c+1] x [r, r+1] in z = 0. Cube: [-1, 1]^3; with (35, 30) the top (y = 1), front
# (z = 1) and right (x = 1) faces face the camera.

def _g(c, r):
    return (float(c), float(r), 0.0)


TOP_RIGHT = ((1, 1, -1), (1, 1, 1))     # top / right edge
FRONT_LEFT = ((-1, -1, 1), (-1, 1, 1))  # front / left edge
FRONT_BOTTOM = ((-1, -1, 1), (1, -1, 1))
RIGHT_BOTTOM = ((1, -1, -1), (1, -1, 1))
RIGHT_BACK = ((1, -1, -1), (1, 1, -1))
TOP_BACK = ((-1, 1, -1), (1, 1, -1))
TOP_LEFT = ((-1, 1, -1), (-1, 1, 1))

GRID_A, GRID_B, GRID_C, GRID_D, GRID_E = (e(_g(0, 1), _g(0, 2), .5), e(_g(2, 1), _g(2, 2), .5),
                                          e(_g(2, 3), _g(3, 3), .5), e(_g(2, 1), _g(3, 1), .5),
                                          e(_g(2, 0), _g(3, 0), .5))
LOOP4 = [f((1.5, 1.5, 0)), f((2.5, 1.5, 0)), f((2.5, 2.5, 0)), f((1.5, 2.5, 0))]
CUBE_LOOP = [f((0.2, 1, 0.3)), f((0.3, 0.2, 1)), f((1, 0.3, 0.2))]

SEQUENCES: dict[str, tuple[str, tuple, list]] = {
    # -- grid ---------------------------------------------------------------------------------------------
    "grid task 1: edge -> 3 quads -> edge": ("grid", GRID_VIEW, [e(_g(0, 1), _g(0, 2), .3), e(_g(3, 1), _g(3, 2), .6)]),
    "grid task 2: edge, interior, neighbour interior, edge": (
        "grid", GRID_VIEW, [e(_g(0, 1), _g(0, 2), .5), f((0.5, 1.4, 0)), f((1.5, 1.6, 0)), e(_g(2, 1), _g(2, 2), .5)]),
    "grid task 3: interior start, neighbour interior, edge": (
        "grid", GRID_VIEW, [f((0.5, 1.5, 0)), f((1.5, 1.5, 0)), e(_g(2, 1), _g(2, 2), .5)]),
    "grid6 far click over 6 quads": ("grid6", GRID_VIEW, [e(_g(0, 3), _g(0, 4), .5), e(_g(6, 3), _g(6, 4), .5)]),
    "grid vertex pass-through (0.2 px)": ("grid", GRID_VIEW, [e(_g(0, 0), _g(1, 0), .502), e(_g(1, 2), _g(2, 2), .502)]),
    "grid no over-snap (2 px)": ("grid", GRID_VIEW, [e(_g(0, 0), _g(1, 0), .52), e(_g(1, 2), _g(2, 2), .52)]),
    "grid hole: visible pieces cut, gap skipped": (
        "grid_hole", GRID_VIEW, [e(_g(0, 1), _g(0, 2), .5), e(_g(4, 1), _g(4, 2), .5)]),
    "grid occluded: hidden crossing not cut": (
        "grid_occluded", FRONT_VIEW, [e(_g(0, 1), _g(0, 2), .5), e(_g(4, 1), _g(4, 2), .5)]),
    "grid occluded, wireframe: nothing hidden": (
        "grid_occluded", (0.0, 0.0, False), [e(_g(0, 1), _g(0, 2), .5), e(_g(4, 1), _g(4, 2), .5)]),
    "grid occlusion switched off between clicks": (
        "grid_occluded", FRONT_VIEW, [e(_g(0, 1), _g(0, 2), .5), ("occl", False), e(_g(4, 1), _g(4, 2), .5)]),
    "grid along an existing edge: skip": ("grid", GRID_VIEW, [v(_g(0, 1)), v(_g(1, 1)), v(_g(3, 1))]),
    "grid interior loop over 4 quads, closed by click": ("grid", GRID_VIEW, LOOP4 + [LOOP4[0]]),
    "grid boundary-start loop across faces": (
        "grid", GRID_VIEW, [e(_g(2, 1), _g(2, 2), .2), f((1.4, 1.5, 0)), e(_g(2, 1), _g(2, 2), .8), f((2.6, 1.5, 0)),
                            e(_g(2, 1), _g(2, 2), .2)]),
    "grid vertex-start loop across faces": (
        "grid", GRID_VIEW, [v(_g(2, 2)), f((1.5, 1.5, 0)), f((2.5, 1.5, 0)), f((2.5, 2.5, 0)), v(_g(2, 2))]),
    "grid loop, then continue from the seed": ("grid", GRID_VIEW, LOOP4 + [LOOP4[0], e(_g(3, 0), _g(4, 0), .5)]),
    "grid earlier edge point across faces, continue": ("grid", GRID_VIEW, [GRID_A, GRID_B, GRID_C, GRID_D, GRID_B, GRID_E]),
    "grid earlier vertex point across faces": (
        "grid", GRID_VIEW, [GRID_A, v(_g(1, 1)), e(_g(3, 1), _g(3, 2), .5), e(_g(2, 3), _g(3, 3), .5), v(_g(1, 1)),
                            e(_g(3, 0), _g(4, 0), .5)]),
    "grid retraced across faces": ("grid", GRID_VIEW, [GRID_A, GRID_B, GRID_C, GRID_B, GRID_E]),
    "grid k crossings undo / redo": (
        "grid", GRID_VIEW, [e(_g(0, 1), _g(0, 2), .3), e(_g(3, 1), _g(3, 2), .6), "undo", "redo", "undo",
                            e(_g(4, 1), _g(4, 2), .4)]),
    "grid plane planner: vertex hit, not an edge end": (
        "grid", FRONT_VIEW, [v(_g(3, 3)), e(_g(1, 3), _g(2, 3), .514)]),
    "grid concave face planned across": (
        "grid", FRONT_VIEW, [e(_g(0, 0), _g(1, 0), .5), f((0.5, 0.5, 0)), e(_g(0, 0), _g(0, 1), .5), "commit",
                             e(_g(0.5, 0), _g(1, 0), .6), e(_g(0, 0.5), _g(0, 1), .6)]),
    "grid orbit between clicks": (
        "grid", GRID_VIEW, [e(_g(0, 1), _g(0, 2), .3), ("cam", 60.0, 50.0), e(_g(3, 3), _g(4, 3), .6),
                            ("cam", -30.0, 60.0), e(_g(1, 0), _g(2, 0), .4)]),
    "grid crossing an earlier cross-face segment": (
        "grid", GRID_VIEW, [e(_g(0, 1), _g(0, 2), .5), e(_g(4, 1), _g(4, 2), .5), e(_g(3, 0), _g(4, 0), .5),
                            e(_g(1, 4), _g(2, 4), .5)]),
    # -- cube ---------------------------------------------------------------------------------------------
    "cube far click top -> front (2 faces)": ("cube", CUBE_VIEW, [e(*TOP_RIGHT, .5), e(*FRONT_LEFT, .5)]),
    "cube right -> front -> top (3 faces)": ("cube", CUBE_VIEW, [e(*RIGHT_BACK, .3), e(*TOP_LEFT, .3)]),
    "cube interior right -> interior top": ("cube", CUBE_VIEW, [f((1, 0.2, -0.3)), f((-0.4, 1, 0.5))]),
    "cube tail join (Manu), as clicked": (
        "cube", CUBE_VIEW, [e(*TOP_RIGHT, .6), f((-0.5, 1, -0.6)), f((0.6, 1, -0.7)), f((-0.4, 0.3, 1))]),
    "cube bow-tie across faces": (
        "cube", CUBE_VIEW, [f((-0.5, 1, 0.2)), f((0.5, 0.2, 1)), f((0.5, 1, 0.2)), f((-0.5, 0.2, 1))]),
    "cube cyclic close across 3 faces": ("cube", CUBE_VIEW, CUBE_LOOP + [CUBE_LOOP[0]]),
    "cube close across faces, then continue from the seed": (
        "cube", CUBE_VIEW, CUBE_LOOP + [CUBE_LOOP[0], e(*FRONT_BOTTOM, .3)]),
    "cube earlier-point click across faces": (
        "cube", CUBE_VIEW, [e(*TOP_BACK, .5), e(*FRONT_LEFT, .5), e(*RIGHT_BOTTOM, .5), e(*FRONT_LEFT, .5),
                            e(*TOP_LEFT, .2)]),
    "cube silhouette: edge to a hidden back edge": (
        "cube", CUBE_VIEW, [e(*TOP_RIGHT, .5), e((-1, -1, -1), (-1, 1, -1), .5)]),
    "cube orbit between clicks": (
        "cube", CUBE_VIEW, [e(*TOP_RIGHT, .5), ("cam", 70.0, 20.0), e(*FRONT_LEFT, .4), ("cam", 20.0, 45.0),
                            e(*RIGHT_BOTTOM, .7)]),
    "cube wireframe far click": ("cube", (35.0, 30.0, False), [e(*TOP_RIGHT, .5), e(*FRONT_LEFT, .5)]),
}


# -- head sequences: seeded screen picks, stored with the results -----------------------------------------

HEAD_CAMERAS = ((0.0, 10.0), (225.0, 25.0), (90.0, 20.0), (330.0, 5.0), (30.0, 15.0), (300.0, 20.0))
HEAD_SEQUENCES = 14


def _spec_from_pick(mesh, target):
    kind = target["kind"]
    if kind == "vertex":
        return v(mesh.vertex_position(target["vertex_id"]))
    if kind == "edge":
        a, b = (mesh.vertex_position(x) for x in mesh.edge_vertices(target["edge_id"]))
        return e(a, b, target["t"])
    if kind == "face" and (target.get("distance_px") or 0.0) >= 9.0:
        return f(target["position"], FACE_CLEARANCE_PX, face_key(mesh, target["face_id"]))
    return None


def _head_sequence(seed: int):
    rnd = random.Random(f"head/cross-face/{seed}")
    mesh = scene("head")
    yaw, pitch = HEAD_CAMERAS[seed % len(HEAD_CAMERAS)]
    occlusion = seed % 7 != 6
    cam = camera(mesh, yaw, pitch)
    xs = [cam.project_to_screen(mesh.vertex_position(x), W, H) for x in mesh.all_vertex_ids()]
    xs = [x for x in xs if x is not None]
    lo_x, hi_x = min(x[0] for x in xs), max(x[0] for x in xs)
    lo_y, hi_y = min(x[1] for x in xs), max(x[1] for x in xs)
    specs, start, last = [], None, None
    n_clicks = rnd.randint(2, 4)
    for _try in range(400):
        if len([s for s in specs if s[0] in "vef"]) >= n_clicks:
            break
        if last is None:
            sx, sy = rnd.uniform(lo_x, hi_x), rnd.uniform(lo_y, hi_y)
        else:
            ang, dist = rnd.uniform(0, 2 * math.pi), rnd.uniform(60, 220)
            sx, sy = last[0] + dist * math.cos(ang), last[1] + dist * math.sin(ang)
        spec = _spec_from_pick(mesh, knife_face_pick(cam, mesh, sx, sy, W, H, occlusion=occlusion))
        if spec is None:
            continue
        specs.append(spec)
        last = (sx, sy)
        start = start or spec
        if seed % 4 == 1 and len(specs) == 1:   # orbit after the first click
            yaw2 = yaw + rnd.choice((-25.0, 25.0))
            specs.append(("cam", yaw2, pitch))
            cam = camera(mesh, yaw2, pitch)
    if seed % 5 == 2 and start is not None and start[0] in "ve" and len(specs) >= 3:
        specs.append(start)                      # back on the start: a close across faces
    return "head", (yaw, pitch, occlusion), specs


# -- signatures ------------------------------------------------------------------------------------------

def _hash(obj) -> str:
    return hashlib.sha256(repr(obj).encode()).hexdigest()[:16]


def signature(side: Side) -> dict:
    return {
        "accepted": side.accepted,
        "steps": side.steps,
        "planned": [None if p is None else [p[0], p[1], [[k, list(pos)] for k, pos in p[2]]] for p in side.planned],
        "path": _hash(side.paths[-1] if side.paths else []),
        "vef": side.vef,
        "faces": _hash(side.faces),
        "residue": _hash((side.residue, side.mode)),
        "history": side.history,
        "undo_redo": f"{side.undo_restores}/{side.redo_restores}",
        "resolution": json.loads(json.dumps(side.resolution)),
        "rolled_back": side.problem is not None,
    }


def to_json(spec):
    if isinstance(spec, str):
        return spec
    if spec[0] == "f":
        return ["f", list(spec[1]), spec[2], None if spec[3] is None else sorted(list(p) for p in spec[3])]
    return [x if not isinstance(x, tuple) else list(x) for x in spec]


def from_json(spec):
    if isinstance(spec, str):
        return spec
    if spec[0] == "f":
        return ("f", tuple(spec[1]), spec[2], None if spec[3] is None else frozenset(tuple(p) for p in spec[3]))
    return tuple(tuple(x) if isinstance(x, list) else x for x in spec)


def play(tool: str, name: str, scene_name: str, view, specs) -> Side:
    player = play_q5 if tool == "q5" else play_production
    return player(scene(scene_name), specs, "commit", tuple(view))


def sequences() -> dict:
    out = {name: (sc, view, specs) for name, (sc, view, specs) in SEQUENCES.items()}
    for seed in range(HEAD_SEQUENCES):
        out[f"head {seed}"] = _head_sequence(seed)
    return out


def record_all() -> dict:
    data = {}
    for name, (sc, view, specs) in sequences().items():
        data[name] = {"scene": sc, "view": list(view), "specs": [to_json(s) for s in specs],
                      "q5": signature(play("q5", name, sc, view, specs))}
    return data


def load() -> dict:
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def replay(tool: str, entry: dict) -> dict:
    """Play a stored sequence through `tool` ("q5" / "production"); its signature."""
    specs = [from_json(s) for s in entry["specs"]]
    return signature(play(tool, "", entry["scene"], entry["view"], specs))


def dumps(data: dict) -> str:
    lines = ["{"]
    keys = list(data)
    for i, key in enumerate(keys):
        sep = "," if i < len(keys) - 1 else ""
        lines.append(f" {json.dumps(key)}: {json.dumps(data[key], sort_keys=True, ensure_ascii=False)}{sep}")
    lines.append("}")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--check" in argv:
        golden, bad = load(), 0
        for name, entry in golden.items():
            for tool in ("q5", "production"):
                sig = replay(tool, entry)
                if sig != entry["q5"]:
                    bad += 1
                    diff = {k: (entry["q5"][k], sig[k]) for k in sig if sig[k] != entry["q5"][k]}
                    print(f"DIFF {tool} {name}: {diff}")
        print("golden: identical" if not bad else f"{bad} difference(s)")
        return 1 if bad else 0
    text = dumps(record_all())
    GOLDEN_PATH.parent.mkdir(exist_ok=True)
    GOLDEN_PATH.write_text(text, encoding="utf-8")
    print(f"wrote {GOLDEN_PATH} ({len(text)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
