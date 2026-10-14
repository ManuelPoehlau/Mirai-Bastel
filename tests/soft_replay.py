"""Replay oracle for non-symmetric Soft (AD-SYM-05 §6 T-3, review CLAUDE-001 R-4).

A pure function, no Core base class and no soft op: a copy of the Q2-D arithmetic of
`src/mirai/soft_selection/ops.py` as it stood before SS1 (`afe51df`), so it cannot follow a
change of the Core loop. It was checked bit for bit against the pre-SS1 ops before the Core
was rebuilt; after SS1 the thin soft ops must still reproduce it bit for bit.

Copied, not imported: the Scale arithmetic (`_scale_about`), the factor normalisation
(`_triple`) and Move's tuple sum. Imported: the public `rotate_around_axis`, which SS1 does
not touch (Q2-D called it the same way: `angle if w == 1.0 else w * angle`).
"""

from __future__ import annotations

import math
from typing import Any, Iterable, Mapping

import tests._bootstrap  # noqa: F401

from core.operations.transform import rotate_around_axis

Position = tuple[float, float, float]
Basis = tuple[Position, Position, Position]


def _triple(factor: "float | Iterable[float]") -> Position:
    if isinstance(factor, (int, float)):
        f = float(factor)
        return (f, f, f)
    values = tuple(float(v) for v in factor)
    if len(values) != 3:
        raise ValueError(f"Scale factor expects a float or 3 components, got {values!r}.")
    if not all(math.isfinite(v) for v in values):
        raise ValueError(f"Scale factor must be finite, got {values!r}.")
    return values  # type: ignore[return-value]


def _scale_about(pivot: Position, pos: Position, f: Position, basis: "Basis | None") -> Position:
    q = (pos[0] - pivot[0], pos[1] - pivot[1], pos[2] - pivot[2])
    if basis is None:
        return (pivot[0] + f[0] * q[0], pivot[1] + f[1] * q[1], pivot[2] + f[2] * q[2])
    b0, b1, b2 = basis
    c0 = q[0] * b0[0] + q[1] * b0[1] + q[2] * b0[2]
    c1 = q[0] * b1[0] + q[1] * b1[1] + q[2] * b1[2]
    c2 = q[0] * b2[0] + q[1] * b2[1] + q[2] * b2[2]
    s0, s1, s2 = f[0] * c0, f[1] * c1, f[2] * c2
    scaled = (
        (b0[0] * s0 + b1[0] * s1) + b2[0] * s2,
        (b0[1] * s0 + b1[1] * s1) + b2[1] * s2,
        (b0[2] * s0 + b1[2] * s1) + b2[2] * s2,
    )
    return (pivot[0] + scaled[0], pivot[1] + scaled[1], pivot[2] + scaled[2])


def replay(
    op: str,
    start: Mapping[Any, Position],
    weights: Mapping[Any, float],
    pivot: "Position | None",
    steps: list[dict],
) -> tuple[list[dict[Any, Position]], dict[Any, Position], dict[Any, Position]]:
    """Non-symmetric Soft `op` ("move" | "rotate" | "scale") over `steps` (update kwargs).

    Returns the positions of the weighted vertices after every step, and the start and end
    maps the History entry would carry."""
    w_of = {vid: float(w) for vid, w in weights.items()}
    p = None if pivot is None else (float(pivot[0]), float(pivot[1]), float(pivot[2]))
    begin = {vid: start[vid] for vid in w_of}
    live = dict(begin)
    total: Position = (1.0, 1.0, 1.0)
    after: list[dict[Any, Position]] = []
    for kwargs in steps:
        if op == "scale":
            f = _triple(kwargs["factor"])
            total = (total[0] * f[0], total[1] * f[1], total[2] * f[2])
        for vid, w in w_of.items():
            pos = live[vid]
            if op == "move":
                d = kwargs["delta"]
                if w != 1.0:
                    d = (w * d[0], w * d[1], w * d[2])
                live[vid] = (pos[0] + d[0], pos[1] + d[1], pos[2] + d[2])
            elif op == "rotate":
                angle = kwargs["angle"]
                live[vid] = rotate_around_axis(pos, p, kwargs["axis"], angle if w == 1.0 else w * angle)
            else:
                basis = kwargs.get("basis")
                if w == 1.0:
                    live[vid] = _scale_about(p, pos, _triple(kwargs["factor"]), basis)
                else:
                    g = tuple(1.0 + w * (t - 1.0) for t in total)
                    live[vid] = _scale_about(p, begin[vid], g, basis)  # type: ignore[arg-type]
        after.append(dict(live))
    return after, begin, dict(live)
