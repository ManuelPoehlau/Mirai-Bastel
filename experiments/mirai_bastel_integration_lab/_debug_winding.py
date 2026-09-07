"""Temp-Probe: Windungsrichtung der Head-OBJ-Faces (wird danach gelöscht)."""
from __future__ import annotations

import sys
from pathlib import Path

_THIS = Path(__file__).resolve().parent
for _p in (str(_THIS), str(_THIS.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _paths import ensure_paths  # noqa: E402

ensure_paths()

from adapters.obj_to_core import DEFAULT_HEAD_ASSET  # noqa: E402
from adapters.triangulate import triangulate_polygon  # noqa: E402
from loaders.obj_loader import load_obj  # noqa: E402


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def main() -> int:
    data = load_obj(DEFAULT_HEAD_ASSET)
    verts = list(data.vertices)
    center = (
        sum(v[0] for v in verts) / len(verts),
        sum(v[1] for v in verts) / len(verts),
        sum(v[2] for v in verts) / len(verts),
    )
    outward = 0
    inward = 0
    zero = 0
    for face in data.faces:
        tris = triangulate_polygon(verts, list(face))
        if not tris:
            zero += 1
            continue
        a, b, c = (verts[i] for i in tris[0])
        u = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
        v = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
        n = _cross(u, v)
        mid = ((a[0] + b[0] + c[0]) / 3.0, (a[1] + b[1] + c[1]) / 3.0,
               (a[2] + b[2] + c[2]) / 3.0)
        d = _dot(n, (mid[0] - center[0], mid[1] - center[1], mid[2] - center[2]))
        if d > 0:
            outward += 1
        elif d < 0:
            inward += 1
        else:
            zero += 1
    print(f"faces={data.face_count} outward={outward} inward={inward} zero={zero}")
    print("VERDICT:", "OUTWARD" if outward > inward else ("INWARD" if inward > outward else "MIXED"))
    return 0


if __name__ == "__main__":
    sys.exit(main())