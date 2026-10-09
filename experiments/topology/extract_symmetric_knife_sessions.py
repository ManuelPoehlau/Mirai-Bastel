"""One-off extraction of the symmetric Knife's regression sessions from the Discovery probe into frozen
path data (AD-SYM-03 slice 6b): `tests/fixtures/symmetric_knife_sessions.json`.

The probe (`symmetry_knife_probe.py`) stays Discovery evidence; the tests of `mirai.symmetric_knife` do not
import it. This script is the provenance of the fixture: it replays the probe's recipes (R1, the closed
loops, R8, K7, N5, and every K4 / K5 camera session including the R9 / R10 ones) and stores, per session,
the **full session path** (points in space included, record format of `knife_resolve`, element ids of the
session-start mesh) plus what the probe's K-C+clip produced on it (status, counts) as a pin.

Run from the repo root:  python experiments/topology/extract_symmetric_knife_sessions.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import symmetry_knife_probe as probe  # noqa: E402
from core import Mesh  # noqa: E402
from core.ids import ElementId  # noqa: E402

OUT = probe.REPO / "tests" / "fixtures" / "symmetric_knife_sessions.json"


def jsonable(value):
    if isinstance(value, ElementId):
        return int(value)
    if isinstance(value, tuple):
        return [jsonable(v) for v in value]
    return value


def record(p: dict) -> dict:
    return {k: jsonable(v) for k, v in p.items() if k != "clip"}


def pin(result: "probe.Res") -> dict:
    out = {"status": result.status.split(":")[0] if not result.ok else "committed"}
    if result.status.startswith("refused"):
        out["reason"] = result.status[len("refused: "):]
    if result.mesh is not None:
        m = result.mesh
        out["counts"] = [len(m.all_vertex_ids()), len(m.all_edge_ids()), len(m.all_face_ids())]
        out["flags"] = result.flags()
    return out


def entry(group: str, name: str, label: str, session: "probe.Session", **extra) -> dict:
    old, new = probe.run("K-C", session), probe.run_kc_clip(session)
    rule = new.info.get("rule")
    return {
        "group": group,
        "mesh": name,
        "label": label,
        "path": [record(p) for p in probe.session_path(session)],
        "source_valid": session.ref_ok,
        "k_c_refused": old.status.startswith("refused"),
        "side": getattr(rule, "side", 0),
        "expect": pin(new),
        **extra,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20261008)
    args = ap.parse_args()
    args.quick = False
    sessions = []

    for name, label, actions in probe.r1_cases() + probe.loop_cases():
        group = "loop" if label.startswith(("closed loop", "the same with")) else "R1"
        sessions.append(entry(group, name, label, probe.session_from(name, actions)))

    for asset in ("tie_grid", "subd_cube", "head_basemesh"):
        for i, (F, H, actions) in enumerate(probe.seam_vertex_crossings(asset)):
            s = probe.session_from(asset, actions)
            sessions.append(entry("R8", asset, f"f{int(F)} -> seam vertex -> f{int(H)}", s, index=i))

    for asset in ("subd_cube", "head_basemesh", "tie_grid"):
        for label, actions in probe.k7_cases(asset).items():
            sessions.append(entry("K7", asset, label, probe.session_from(asset, actions)))
    for (name, label), actions in probe.k7_synthetic().items():
        sessions.append(entry("K7", name, label, probe.session_from(name, actions)))

    sp = probe.fresh("span_grid")
    pos = {tuple(probe.vpos(sp, v)): v for v in sp.all_vertex_ids()}
    bottom = probe.kr.find_edge(sp, pos[(-0.5, 0.0, 0.0)], pos[(0.5, 0.0, 0.0)])
    top = probe.kr.find_edge(sp, pos[(-0.5, 1.0, 0.0)], pos[(0.5, 1.0, 0.0)])
    right = probe.kr.find_edge(sp, pos[(0.5, 0.0, 0.0)], pos[(0.5, 1.0, 0.0)])
    for label, actions in (
        ("N5 path: crossing edge t=0.5 -> crossing edge t=0.5 (a chord in the plane)",
         [("click", probe.T_e(bottom, 0.5)), ("click", probe.T_e(top, 0.5))]),
        ("N5 path: crossing edge t=0.5 -> right edge t=0.5 (into +X, same face)",
         [("click", probe.T_e(bottom, 0.5)), ("click", probe.T_e(right, 0.5))]),
    ):
        sessions.append(entry("N5", "span_grid", label, probe.session_from("span_grid", actions)))

    for sec, name, cam_key, i, s in probe.camera_samples(args):
        sessions.append(entry(sec, name, f"{sec} {name} {cam_key} #{i}", s, camera=cam_key, index=i,
                              r10=(sec == "K5" and name == "head_basemesh" and cam_key == "side (+X)" and i == 15)))

    doc = {
        "about": "Frozen sessions of the symmetric Knife regression rows (AD-SYM-03 §10.8, slice 6b). Extracted once "
                 "from experiments/topology/symmetry_knife_probe.py by experiments/topology/extract_symmetric_knife_"
                 "sessions.py; `expect` pins what the probe's K-C+clip produced. Paths are the full session path "
                 "(points in space included); ids are those of the session-start mesh (examples/meshes assets with "
                 "the plane x = 0 and the derived seam, or the synthetic grids of tests/test_symmetric_knife.py).",
        "seed": args.seed,
        "sessions": sessions,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, separators=(",", ":")) + "\n", encoding="utf-8")
    groups = {}
    for s in sessions:
        groups.setdefault(s["group"], []).append(s["expect"]["status"])
    for g, st in groups.items():
        print(g, len(st), {k: st.count(k) for k in set(st)})
    print(f"{len(sessions)} sessions, {OUT.stat().st_size} bytes -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
