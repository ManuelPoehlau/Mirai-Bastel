"""WP-KNIFE-01 S1 safety net — deterministic Knife Face sessions and their id-free result signatures.

Not a test module itself (no `test_` prefix): `test_knife_resolver_golden.py` compares what this driver
records against the committed golden file `golden/knife_resolver.json`; run this file directly to
(re)write that file:

    python playground/tests/knife_golden_driver.py           # write golden/knife_resolver.json
    python playground/tests/knife_golden_driver.py --check   # compare only, print the first differences

Recorded per session (ids are never part of a signature — WP-KNIFE-01 Task 3.6: `Mesh.split_face`
may allocate other id *values* than the Lab's B2b stand-ins did):

- the HUD message (`last_message`) — applied / dropped counts, notes, rollback reasons;
- V/E/F counts, the number of History entries, which clicks were accepted (`+`/`-`), which
  in-session undo/redo steps succeeded;
- one hash of the position-canonical faces (each face as its cycle of positions rounded to 9 digits,
  rotated to its smallest position, winding kept), the selection residue (selected edges as sorted
  position pairs) and the selection mode; the recorded sequences also keep their new faces in full;
- whether History Undo restores the session-start mesh and Redo the committed one (position-canonical).

Sessions are driven the way `playground/window.py` drives them (screen position -> `knife_face_pick`
with occlusion -> Q5 only: `set_view` + `snap_target` -> `click`), like the seeded fuzz in
`test_knife_face_q5.py` and `experiments/topology/knife_integrity_probe.py`.
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

from core import Mesh, Scene  # noqa: E402
from mirai.mesh_geometry import mesh_center_and_radius  # noqa: E402
from mirai.scene_factory import build_core_scene_from_obj, create_cube  # noqa: E402
from mirai.viewport.camera import OrbitCamera  # noqa: E402
from viewport.derived import triangulate_face  # noqa: E402

from playground._paths import DEFAULT_HEAD_ASSET, ensure_paths  # noqa: E402

ensure_paths()  # examples/ (the OBJ loader for the head, AD-007)
from playground.experiments.knife_face.engine import (  # noqa: E402
    KnifeFaceCollected,
    KnifeFaceImmediate,
    knife_face_pick,
)
from playground.experiments.knife_face.engine_q5 import KnifeFaceCrossFace  # noqa: E402

GOLDEN_PATH = Path(__file__).resolve().parent / "golden" / "knife_resolver.json"
W, H = 1280, 800
VARIANTS = {"B": KnifeFaceImmediate, "D": KnifeFaceCollected, "Q5": KnifeFaceCrossFace}
# Runs per scene (each run: 1-3 sessions on the mesh the previous session left), per variant.
RUNS = {"grid": 50, "cube": 50, "head": 15}
CAMERAS = {
    "grid": ((20, 35), (0, 0), (-30, 60), (45, 25)),
    "cube": ((35, 30), (-40, 25), (130, -30), (60, 55)),
    "head": ((0, 10), (225, 25), (90, 20), (330, 5)),
}


# -- scenes ----------------------------------------------------------------------------------

def build_grid(n: int = 4) -> Mesh:
    mesh, p = Mesh(), {}
    for r in range(n + 1):
        for c in range(n + 1):
            p[(r, c)] = mesh.add_vertex((float(c), float(r), 0.0))
    for r in range(n):
        for c in range(n):
            mesh.add_face([p[(r, c)], p[(r, c + 1)], p[(r + 1, c + 1)], p[(r + 1, c)]])
    return mesh


_HEAD_STATE: dict | None = None


def build_scene(name: str) -> Mesh:
    global _HEAD_STATE
    if name == "grid":
        return build_grid()
    if name == "cube":
        return create_cube()
    if _HEAD_STATE is None:
        _HEAD_STATE = build_core_scene_from_obj(DEFAULT_HEAD_ASSET).mesh.export_state()
    return Mesh.from_state(_HEAD_STATE)


def camera(mesh: Mesh, yaw: float, pitch: float) -> OrbitCamera:
    cam = OrbitCamera(yaw=math.radians(yaw), pitch=math.radians(pitch))
    center, radius = mesh_center_and_radius(mesh)
    cam.frame_on_bounds(center, radius, margin=1.4)
    return cam


def begin(cls, mesh: Mesh, cam=None):
    scene = Scene()
    scene.mesh = mesh
    knife = cls()
    knife.activate()
    knife.begin(mesh=mesh, scene=scene, selection=scene.selection)
    if cam is not None and hasattr(knife, "set_view"):
        knife.set_view(cam, W, H, occlusion=True)
    return knife, scene


# -- id-free signatures ------------------------------------------------------------------------

def _r(p) -> tuple:
    return tuple(round(c, 9) + 0.0 for c in p)


def canon_faces(mesh: Mesh) -> list:
    out = []
    for f in mesh.all_face_ids():
        cyc = [_r(mesh.vertex_position(v)) for v in mesh.face_vertices(f)]
        k = cyc.index(min(cyc))
        out.append(tuple(cyc[k:] + cyc[:k]))
    return sorted(out)


def _hash(obj) -> str:
    return hashlib.sha256(repr(obj).encode()).hexdigest()[:16]


def residue(mesh: Mesh, selection) -> list:
    edges = [e for e in selection.edges if mesh.is_valid_edge(e)]
    return sorted(tuple(sorted(_r(mesh.vertex_position(v)) for v in mesh.edge_vertices(e))) for e in edges)


def signature(knife, scene, mesh: Mesh, before_faces: list, accepted: str, steps: str) -> dict:
    after_faces = canon_faces(mesh)
    sig = {
        "msg": knife.last_message,
        "vef": f"{len(mesh.all_vertex_ids())}/{len(mesh.all_edge_ids())}/{len(mesh.all_face_ids())}",
        "history": len(scene.history),
        "clicks": accepted + (f"/{steps}" if steps else ""),
        "result": _hash((after_faces, residue(mesh, scene.selection), str(scene.selection.mode))),
    }
    if len(scene.history):
        scene.history.undo()
        undo_ok = canon_faces(mesh) == before_faces
        scene.history.redo()
        sig["undo_redo"] = f"{undo_ok}/{canon_faces(mesh) == after_faces}"
    return sig


def compact(sig: dict) -> str:
    """One line per random session: V/E/F, History entries, clicks[/steps], undo/redo, result hash, HUD."""
    return f"{sig['vef']} h{sig['history']} {sig['clicks']} {sig.get('undo_redo', '-')} {sig['result']} | {sig['msg']}"


# -- seeded random sessions --------------------------------------------------------------------

def _canonical_cycle(mesh: Mesh, f) -> list:
    """`f`'s boundary rotated to start at its smallest position."""
    b = mesh.face_vertices(f)
    k = min(range(len(b)), key=lambda i: _r(mesh.vertex_position(b[i])))
    return b[k:] + b[:k]


def _random_world(rnd: random.Random, mesh: Mesh, r: float):
    """A random world position on the mesh. Chosen by position only — never by id order or by
    where a face's boundary list starts — so the choice does not depend on the id values a
    resolver allocates (WP-KNIFE-01 Task 3.6)."""
    if r < 0.45:
        faces = sorted(mesh.all_face_ids(), key=lambda f: [_r(mesh.vertex_position(v)) for v in _canonical_cycle(mesh, f)])
        cyc = _canonical_cycle(mesh, rnd.choice(faces))
        tri = rnd.choice(triangulate_face(cyc, {v: mesh.vertex_position(v) for v in cyc}))
        u, v = rnd.random(), rnd.random()
        if u + v > 1:
            u, v = 1 - u, 1 - v
        a, b, c = (mesh.vertex_position(x) for x in tri)
        return tuple(a[k] + u * (b[k] - a[k]) + v * (c[k] - a[k]) for k in range(3))
    if r < 0.6:
        return rnd.choice(sorted(_r(mesh.vertex_position(v)) for v in mesh.all_vertex_ids()))
    ends = sorted(tuple(sorted(_r(mesh.vertex_position(v)) for v in mesh.edge_vertices(e))) for e in mesh.all_edge_ids())
    pa, pb = rnd.choice(ends)
    t = rnd.uniform(0.1, 0.9)
    return tuple(pa[k] + t * (pb[k] - pa[k]) for k in range(3))


def random_run(scene_name: str, variant: str, seed: int) -> list[str]:
    """One seeded run: 1-3 sessions of 2-9 clicks each (with occasional in-session undo/redo)."""
    rnd = random.Random(f"{scene_name}/{variant}/{seed}")
    mesh = build_scene(scene_name)
    cams = [camera(mesh, y, p) for y, p in CAMERAS[scene_name]]
    out = []
    for _session_no in range(rnd.randint(1, 3)):
        before_faces = canon_faces(mesh)
        knife, scene = begin(VARIANTS[variant], mesh)
        accepted, steps = [], []
        for _ in range(rnd.randint(2, 9)):
            cam = rnd.choice(cams)
            r = rnd.random()
            world = _random_world(rnd, mesh, r)
            sp = cam.project_to_screen(world, W, H)
            if sp is None:
                continue
            jitter = r >= 0.45
            sx, sy = sp[0] + rnd.uniform(-2, 2) * jitter, sp[1] + rnd.uniform(-2, 2) * jitter
            target = knife_face_pick(cam, mesh, sx, sy, W, H, occlusion=True)
            if hasattr(knife, "set_view"):
                knife.set_view(cam, W, H, occlusion=True)
                target = knife.snap_target(target, sx, sy)
            accepted.append("+" if knife.click(target) else "-")
            u = rnd.random()
            if u < 0.08:
                steps.append("u" if knife.undo_step() else "U")
            elif u < 0.12:
                steps.append("u" if knife.undo_step() else "U")
                steps.append("r" if knife.redo_step() else "R")
        knife.commit()
        knife.deactivate()
        out.append(compact(signature(knife, scene, mesh, before_faces, "".join(accepted), "".join(steps))))
    return out


# -- recorded sequences (Artist play tests, decision.md) -----------------------------------------

def _vid_at(mesh: Mesh, pos):
    return next(v for v in mesh.all_vertex_ids() if math.dist(mesh.vertex_position(v), pos) < 1e-9)


def spec_target(mesh: Mesh, spec) -> dict:
    """("v", pos), ("e", pos_a, pos_b, t) on whichever current edge holds a + t (b - a),
    ("f", pos) the face interior holding pos (distance_px 20), ("path", index) an earlier point."""
    kind = spec[0]
    if kind == "path":
        return {"kind": "path", "index": spec[1]}
    if kind == "v":
        return {"kind": "vertex", "vertex_id": _vid_at(mesh, spec[1])}
    if kind == "e":
        a, b, t = spec[1], spec[2], spec[3]
        pos = tuple(a[k] + t * (b[k] - a[k]) for k in range(3))
        for eid in mesh.all_edge_ids():
            p0, p1 = (mesh.vertex_position(v) for v in mesh.edge_vertices(eid))
            d = [p1[k] - p0[k] for k in range(3)]
            u = sum((pos[k] - p0[k]) * d[k] for k in range(3)) / sum(c * c for c in d)
            if 1e-9 < u < 1 - 1e-9 and math.dist(pos, tuple(p0[k] + u * d[k] for k in range(3))) < 1e-9:
                return {"kind": "edge", "edge_id": eid, "t": u}
        raise LookupError(pos)
    from mirai.topology.face_geometry import FaceFrame, segment_in_face
    pos = spec[1]
    for fid in mesh.all_face_ids():
        if FaceFrame(mesh, fid).height(pos) > 1e-9:
            continue
        if segment_in_face(mesh, fid, pos, pos) == "inside":
            return {"kind": "face", "face_id": fid, "position": tuple(pos), "distance_px": 20.0}
    raise LookupError(pos)


MANU_TOP = [("e", (1, 1, -1), (1, 1, 1), 0.6), ("f", (-0.5, 1, -0.6)), ("f", (0.6, 1, -0.7))]
GRID_LOOP = [("e", (1, 0, 0), (1, 1, 0), 0.3), ("f", (0.2, 0.6, 0)), ("f", (0.8, 0.8, 0)), ("e", (0, 0, 0), (1, 0, 0), 0.4)]
GRID_HB1 = [("e", (0, 0, 0), (1, 0, 0), 0.2), ("f", (0.8, 0.5, 0)), ("e", (0, 0, 0), (1, 0, 0), 0.6),
            ("e", (0, 1, 0), (1, 1, 0), 0.5)]
GRID_BOWTIE = [("e", (1, 0, 0), (1, 1, 0), 0.5), ("f", (0.1, 0.45, 0)), ("f", (0.5, 0.9, 0)), ("f", (0.4, 0.1, 0)),
               ("path", 0)]

# name -> (scene, variants, camera (yaw, pitch), click specs, expected V/E/F or None)
RECORDED = {
    # Manu 2026-09-30 13:22-13:39: bow-tie back to the start, both bridges to outside corners (confirmed).
    "cube bow-tie (Manu)": ("cube", ("Q5",), (41.0, 43.7),
                            [("e", (1, 1, -1), (1, 1, 1), 0.6), ("f", (-0.6, 1, 0)), ("f", (0.1, 1, -0.8)),
                             ("f", (-0.2, 1, 0.8)), ("path", 0)], "13/21/10"),
    # Manu 2026-09-30: top loop, on into the front, last click inside the front joined to its corner.
    "cube tail join (Manu)": ("cube", ("Q5",), (35.0, 30.0), MANU_TOP + [("f", (-0.4, 0.3, 1))], "14/22/10"),
    "grid closed shape": ("grid", ("D", "Q5"), (20.0, 35.0),
                          [("f", (0.2, 0.2, 0)), ("f", (0.8, 0.3, 0)), ("f", (0.5, 0.8, 0))], None),
    "grid closed shape, clicked backwards": ("grid", ("D", "Q5"), (20.0, 35.0),
                                             [("f", (0.5, 0.8, 0)), ("f", (0.8, 0.3, 0)), ("f", (0.2, 0.2, 0))], None),
    "grid closed shape by click, then continue": ("grid", ("Q5",), (20.0, 35.0),
                                                  [("f", (1.5, 1.5, 0)), ("f", (2.5, 1.5, 0)), ("f", (2.5, 2.5, 0)),
                                                   ("f", (1.5, 2.5, 0)), ("path", 0),
                                                   ("e", (3, 0, 0), (4, 0, 0), 0.5)], None),
    "grid loop at a crossing": ("grid", ("D", "Q5"), (20.0, 35.0), GRID_LOOP, None),
    "grid loop at a crossing, reversed": ("grid", ("D", "Q5"), (20.0, 35.0), GRID_LOOP[::-1], None),
    "grid loop back to the start point": ("grid", ("Q5",), (20.0, 35.0),
                                          [("e", (1, 0, 0), (1, 1, 0), 0.5), ("f", (0.3, 0.3, 0)),
                                           ("f", (0.3, 0.7, 0)), ("path", 0)], None),
    "grid bow-tie back to the start": ("grid", ("Q5",), (20.0, 35.0), GRID_BOWTIE, None),
    "grid crossing cut (HB1)": ("grid", ("B", "D", "Q5"), (20.0, 35.0), GRID_HB1, None),
    "grid tail join": ("grid", ("Q5",), (20.0, 35.0), [("e", (0, 0, 0), (0, 1, 0), 0.5), ("f", (0.6, 0.7, 0))], None),
    "grid tail join, tie by position": ("grid", ("Q5",), (20.0, 35.0),
                                        [("e", (0, 0, 0), (1, 0, 0), 0.5), ("f", (0.5, 0.5, 0))], None),
    # Artist decision 2026-09-30: cutting back the same way does nothing.
    "grid out to one point and straight back": ("grid", ("D", "Q5"), (20.0, 35.0),
                                                [("v", (1, 1, 0)), ("f", (1.5, 1.4, 0)), ("v", (1, 1, 0))], None),
    "grid retraced segment": ("grid", ("Q5",), (20.0, 35.0),
                              [("e", (0, 1, 0), (0, 2, 0), 0.5), ("e", (2, 1, 0), (2, 2, 0), 0.5),
                               ("e", (0, 1, 0), (0, 2, 0), 0.5), ("e", (4, 1, 0), (4, 2, 0), 0.5)], None),
    "grid notch (FC3)": ("grid", ("B", "D", "Q5"), (20.0, 35.0),
                         [("e", (1, 1, 0), (2, 1, 0), 0.2), ("f", (1.5, 1.5, 0)), ("e", (1, 1, 0), (2, 1, 0), 0.8)],
                         None),
    "grid bent cut (FC2)": ("grid", ("B", "D", "Q5"), (20.0, 35.0),
                            [("e", (1, 1, 0), (1, 2, 0), 0.5), ("f", (1.3, 1.3, 0)), ("f", (1.7, 1.7, 0)),
                             ("e", (2, 1, 0), (2, 2, 0), 0.5)], None),
    "grid cross-face, edge to far edge": ("grid", ("Q5",), (20.0, 35.0),
                                          [("e", (0, 1, 0), (0, 2, 0), 0.5), ("e", (4, 1, 0), (4, 2, 0), 0.5)], None),
}


def recorded_case(name: str, variant: str) -> dict:
    scene_name, _variants, (yaw, pitch), specs, _expect = RECORDED[name]
    mesh = build_scene(scene_name)
    before_faces = canon_faces(mesh)
    knife, scene = begin(VARIANTS[variant], mesh, camera(mesh, yaw, pitch))
    accepted = "".join("+" if knife.click(spec_target(mesh, sp)) else "-" for sp in specs)
    knife.commit()
    knife.deactivate()
    sig = signature(knife, scene, mesh, before_faces, accepted, "")
    sig["new_faces"] = [" ".join("(%s)" % ", ".join(repr(c) for c in q) for q in f)
                        for f in canon_faces(mesh) if f not in before_faces]
    return sig


# -- the whole net ------------------------------------------------------------------------------

def record_all() -> dict:
    out: dict = {"recorded": {}, "random": {}}
    for name, (_scene, variants, _cam, _specs, _expect) in RECORDED.items():
        for variant in variants:
            out["recorded"][f"{name} [{variant}]"] = recorded_case(name, variant)
    for scene_name, runs in RUNS.items():
        for variant in VARIANTS:
            for seed in range(runs):
                out["random"][f"{scene_name} {variant} {seed}"] = random_run(scene_name, variant, seed)
    return out


def dumps(data: dict) -> str:
    """Deterministic JSON, one random run per line (diffable, small)."""
    lines = ["{", ' "recorded": ' + json.dumps(data["recorded"], indent=1, sort_keys=True, ensure_ascii=False)
             .replace("\n", "\n ") + ",", ' "random": {']
    keys = list(data["random"])
    for i, key in enumerate(keys):
        sep = "," if i < len(keys) - 1 else ""
        lines.append(f"  {json.dumps(key)}: {json.dumps(data['random'][key], ensure_ascii=False)}{sep}")
    lines += [" }", "}"]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    text = dumps(record_all())
    if "--check" in argv:
        golden = GOLDEN_PATH.read_text(encoding="utf-8")
        if text == golden:
            print("golden: identical")
            return 0
        new, old = json.loads(text), json.loads(golden)
        shown = 0
        for group in ("recorded", "random"):
            for key in old[group]:
                if old[group][key] != new[group].get(key):
                    print(f"DIFF {group} {key}:\n  golden {old[group][key]}\n  now    {new[group].get(key)}")
                    shown += 1
                    if shown >= 10:
                        return 1
        return 1
    GOLDEN_PATH.parent.mkdir(exist_ok=True)
    GOLDEN_PATH.write_text(text, encoding="utf-8")
    print(f"wrote {GOLDEN_PATH} ({len(text)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
