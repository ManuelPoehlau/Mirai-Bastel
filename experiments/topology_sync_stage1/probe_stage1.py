"""AD-023 stage 1 on the `topology` scenario, with p50 / p95 / max per column.

Installs the stage-1 switches (`stage1.py`), then runs the unchanged split probe
(`architecture_audit_probes/probe_topology_sync_split.py`, itself the `topology` scenario of
`drag_cost/probe_navigation_gl.py`) and replaces only its per-row report with one that prints p50, p95 and max
(the drag_cost report prints p50 and max). Nothing under `src/` or the other experiments is changed.

Options of this script (everything else goes to the split probe, e.g. `--steps`, `--row-seconds`, `--gc`,
`--history-depth`, `--assets`):
    --stage1 SPEC   `all` (default: V0,V2,V3,H0), `none` (today's code, the baseline) or a list like `V0,V2,V3`

Run (repo root; headless: prefix with `xvfb-run -a`). p95 needs n >= 20 per row to differ from max:
    python experiments/topology_sync_stage1/probe_stage1.py --stage1 none --steps 20 --row-seconds 240
    python experiments/topology_sync_stage1/probe_stage1.py --stage1 all  --steps 20 --row-seconds 240
    python experiments/topology_sync_stage1/probe_stage1.py --stage1 V0,V2,V3 --steps 20 --row-seconds 240
Copy the whole output. Container numbers (llvmpipe) are not reference-PC numbers.
"""

from __future__ import annotations

import sys
from pathlib import Path

_EXPERIMENTS = Path(__file__).resolve().parents[1]
if str(_EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS))

from topology_sync_stage1._paths import ensure_paths  # noqa: E402

ensure_paths()

from architecture_audit_probes import probe_topology_sync_split as split  # noqa: E402
from drag_cost import probe_drag_gl as drag  # noqa: E402
from topology_sync_stage1 import stage1  # noqa: E402

#: (label, TopoSample attribute or callable)
COLUMNS = (
    ("frame (op as triggered)", "frame"),
    ("  op", "op"),
    ("  history", "history"),
    ("  hover re-pick", "pick"),
    ("  viewport sync", "sync"),
    ("next hover frame", "first_hover"),
    ("undo frame", "undo"),
    ("op + undo", lambda s: s.frame + s.undo),
)


def topo_lines(r) -> list[str]:
    note = f"  ({r.note})" if r.note else ""
    lines = [f"  topology {r.name:22s} n={len(r.samples):3d}{note}"]
    for label, attr in COLUMNS:
        values = [attr(s) if callable(attr) else float(getattr(s, attr)) for s in r.samples]
        st = drag.Stats.of(values)
        lines.append(f"    {label:26s} p50 {st.p50:9.2f}  p95 {st.p95:9.2f}  max {st.max:9.2f}")
    return lines


def parse_own(argv: list[str]) -> tuple[list[str], str]:
    rest, spec = [], "all"
    it = iter(argv)
    for arg in it:
        if arg == "--stage1":
            spec = next(it)
        else:
            rest.append(arg)
    return rest, spec


def main(argv: list[str]) -> int:
    rest, spec = parse_own(list(argv))
    switches = stage1.install(spec)
    stage1.reset_stats()
    split.probe.topo_lines = topo_lines
    print(f"AD-023 stage 1 switches: {','.join(sorted(switches)) or 'none (baseline: unchanged code)'}")
    code = split.main(rest)
    print()
    print("Stage-1 counters (whole run incl. warm-up and undo frames): " + stage1.STATS.text())
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
