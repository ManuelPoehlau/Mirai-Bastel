"""Split of the viewport topology rebuild into its parts (architecture audit follow-up, 2026-10-20).

Why: `probe_navigation_gl.py --profile-top N` profiles only orbit, zoom and first hover, not the `topology`
scenario, so the 2026-10-20 reference-PC run could not say where the ~1.26 s of one structural rebuild goes.
This script runs the unchanged `topology` scenario of `drag_cost/probe_navigation_gl.py` and wraps the rebuild's
building blocks from the outside with wall-clock timers (no cProfile, so no profiler overhead). Nothing under
`src/` or `experiments/drag_cost/` is changed.

Per wrapped function: calls, total ms over the whole run, average ms per call. The rows are NESTED
(`_sync_topology` contains `full_recompute`, `_rebuild_index_mapping`, `_rebuild_resources`; `_rebuild_resources`
contains the store calls), so they do not add up to 100 %; the nesting is shown by indentation.
The per-face triangulation wrapper adds timer overhead on ~1 million calls, so that row (and its parent) is slightly
overstated; `_rebuild_resources` minus its store rows is the Python flattening of positions, normals, indices and face rows.

Options of this script (everything else is passed on to `probe_navigation_gl.py`, e.g. `--steps`, `--row-seconds`):
    --gc on|off|freeze   cyclic garbage collector during the topology run: `on` (default, as the app), `off`
                         (`gc.disable()`), `freeze` (`gc.collect()` + `gc.freeze()` after the set-up: the live mesh and the
                         history snapshots are no longer scanned). AD-023 review CLAUDE-001 B-1 names the GC as the likely
                         main cost of `export_state` / `load_state`.
    --history-depth N    before measuring, push N real `MeshStateCommand` entries (a 1e-6 vertex move through
                         `Application.apply_mesh_change`, so each holds two whole-mesh snapshots) that stay on the undo
                         stack; the probe's own undo pops only its operation. Default 0 (the probe's usual depth ~1).

Run (repo root, Windows and Linux; headless: prefix with `xvfb-run -a`):
    python experiments/architecture_audit_probes/probe_topology_sync_split.py
    python experiments/architecture_audit_probes/probe_topology_sync_split.py --assets examples/meshes/gollum.obj
    python experiments/architecture_audit_probes/probe_topology_sync_split.py --steps 12 --row-seconds 90 --gc off --history-depth 20
Copy the whole output. Container numbers (llvmpipe) are not reference-PC numbers.
"""

from __future__ import annotations

import contextlib
import gc
import io
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments"))

from drag_cost import probe_navigation_gl as probe  # noqa: E402  (also sets up sys.path for src/)

#: (label, indentation level, "module:Class.method" or "module:function")
TARGETS = (
    ("RenderMesh._sync_topology", 0, "viewport.render_mesh:RenderMesh._sync_topology"),
    ("DerivedGeometry.full_recompute (adjacency + all normals)", 1, "viewport.derived:DerivedGeometry.full_recompute"),
    ("RenderMesh._rebuild_index_mapping (index map + triangulation)", 1, "viewport.render_mesh:RenderMesh._rebuild_index_mapping"),
    ("triangulate_mesh_face (all calls)", 2, "viewport.render_mesh:triangulate_mesh_face"),
    ("RenderMesh._rebuild_resources (flatten + upload)", 1, "viewport.render_mesh:RenderMesh._rebuild_resources"),
    ("GLRenderStore.allocate", 2, "viewport.gl_render_store:GLRenderStore.allocate"),
    ("GLRenderStore.update", 2, "viewport.gl_render_store:GLRenderStore.update"),
    ("GLRenderStore.end_rebuild (VertexList creation)", 2, "viewport.gl_render_store:GLRenderStore.end_rebuild"),
    ("Mesh.export_state", 0, "core.mesh:Mesh.export_state"),
    ("Mesh.load_state", 0, "core.mesh:Mesh.load_state"),
    ("PickCache.refresh (only when the signature changed: see calls)", 0, "mirai.viewport.picking_cache:PickCache.refresh"),
)


def resolve(spec: str):
    import importlib

    module_name, attr = spec.split(":")
    owner = importlib.import_module(module_name)
    parts = attr.split(".")
    for part in parts[:-1]:
        owner = getattr(owner, part)
    return owner, parts[-1]


def install(stats: dict) -> None:
    for label, _level, spec in TARGETS:
        owner, name = resolve(spec)
        original = getattr(owner, name)
        record = stats.setdefault(label, [0, 0.0])

        def wrapper(*args, _orig=original, _rec=record, **kwargs):
            start = time.perf_counter()
            try:
                return _orig(*args, **kwargs)
            finally:
                _rec[0] += 1
                _rec[1] += (time.perf_counter() - start) * 1000.0

        setattr(owner, name, wrapper)


def pad_history(rig, depth: int) -> None:
    """`depth` real undo entries (each with two whole-mesh snapshots) that stay on the stack."""
    app = rig.app
    mesh = app.scene.mesh
    vertex = mesh.all_vertex_ids()[-1]
    for i in range(depth):
        x, y, z = mesh.vertex_position(vertex)

        def mutate(_v=vertex, _p=(x + 1e-6, y, z)):
            mesh.set_vertex_position(_v, _p)
            return {_v}

        if not app.apply_mesh_change("history pad", mutate):
            raise RuntimeError("history pad did not record an entry")
    rig.settle()


def parse_own(argv: list[str]) -> tuple[list[str], str, int]:
    rest: list[str] = []
    mode, depth = "on", 0
    it = iter(argv)
    for arg in it:
        if arg == "--gc":
            mode = next(it)
            if mode not in ("on", "off", "freeze"):
                raise SystemExit("--gc takes on, off or freeze")
        elif arg == "--history-depth":
            depth = int(next(it))
        else:
            rest.append(arg)
    return rest, mode, depth


def main(argv: list[str]) -> int:
    args, gc_mode, depth = parse_own(list(argv))
    stats: dict = {}
    install(stats)

    original_run_topology = probe.run_topology

    def run_topology(rig, cfg):
        if depth:
            pad_history(rig, depth)
        if gc_mode == "off":
            gc.disable()
        elif gc_mode == "freeze":
            gc.collect()
            gc.freeze()
        return original_run_topology(rig, cfg)

    probe.run_topology = run_topology
    if "--assets" not in args:
        args += ["--assets", probe.GOLLUM_20K]
    if "--scenarios" not in args:
        args += ["--scenarios", "topology"]
    if "--profile-top" not in args:
        args += ["--profile-top", "0"]
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = probe.main(args)
    print(f"Split probe options: --gc {gc_mode} --history-depth {depth} (GC threshold {gc.get_threshold()})")
    print(out.getvalue(), end="")
    print()
    print("Rebuild split (wall clock, nested; calls over the whole run incl. warm-up and undo frames)")
    print(f"  {'function':66s} {'calls':>6s} {'total ms':>10s} {'avg ms':>9s}")
    for label, level, _spec in TARGETS:
        calls, total = stats[label]
        avg = total / calls if calls else 0.0
        print(f"  {'  ' * level + label:66s} {calls:6d} {total:10.1f} {avg:9.2f}")
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
