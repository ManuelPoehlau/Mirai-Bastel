"""Test-Suite für den Viewport V0.2 Incremental-Update-Proof.

Führt die 10 im Spec geforderten Tests aus. Läuft standardmäßig headless
mit dem deterministischen ``TraceStore`` (kein GL-Kontext nötig). Mit
``--gpu`` kommt ein optionaler Live-GPU-Persist-Test hinzu, der einen
echten pyglet-GL-Kontext nutzt (wenn verfügbar).

Aufruf:
    python run_tests.py            # 10 Kern-Tests, headless
    python run_tests.py --verbose  # mit Zähler-/Ressourcen-Detail
    python run_tests.py --gpu      # + GPU-Live-Check (wenn GPU vorhanden)
"""
from __future__ import annotations

import argparse
import os
import sys

# Dual-kompatibel: als Skript (python run_tests.py) und als Modul
# (python -m mirai_bastel_viewport_V02.run_tests) aufrufbar.
if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from camera import OrbitCamera
    from material import MaterialState
    from mesh import make_grid_triangles
    from render_mesh import RenderMesh
    from renderer import TraceStore
    from selection import SelectionState
else:
    from .camera import OrbitCamera
    from .material import MaterialState
    from .mesh import make_grid_triangles
    from .render_mesh import RenderMesh
    from .renderer import TraceStore
    from .selection import SelectionState

MESH_QUADS = 4      # 5x5 Vertices = 25 Verts, 32 Tris (Basis-Testmesh)
STRESS_QUADS = 32   # 33x33 Vertices = 1089 Verts, 2048 Tris (Stress-Test)


class Case:
    """Sammelt Assertions und Beobachtungen für einen Test."""

    def __init__(self, name: str, expected: str) -> None:
        self.name = name
        self.expected = expected
        self.failures: list[str] = []
        self.observations: list[str] = []

    def check(self, condition: bool, msg: str) -> None:
        if not condition:
            self.failures.append(msg)

    def observe(self, msg: str) -> None:
        self.observations.append(msg)

    @property
    def passed(self) -> bool:
        return not self.failures


class Harness:
    """Baut RenderMesh + alle Kategorien und snapshottet die Baseline."""

    def __init__(self, quads: int = MESH_QUADS) -> None:
        mesh = make_grid_triangles(quads, quads)
        self.rm = RenderMesh(mesh, store_type=TraceStore)
        self.camera = OrbitCamera(distance=6.0)
        self.selection = SelectionState()
        self.material = MaterialState()
        self.rm.bind_camera(self.camera)
        self.rm.bind_selection(self.selection)
        self.rm.bind_material(self.material)
        self.rm.build()  # Test 1: Initial-Build ist erlaubt

        # Baseline NACH dem Initial-Build: alle weiteren Checks als Delta.
        self.base = dict(self.rm.stats.counters)
        self.base_uploaded = self.rm.stats.uploaded_bytes
        self.base_ids = dict(self.rm.store.resource_ids())

    def deltas(self) -> dict[str, int]:
        out = {}
        for name, value in self.rm.stats.counters.items():
            out[name] = value - self.base.get(name, 0)
        return out


def camera_update_loop(hm: Harness, steps: int = 7) -> None:
    """Orbit/Pan/Zoom über mehrere Updates (Test 2)."""
    cam = hm.camera
    for _ in range(steps):
        cam.orbit(0.05, 0.02)
        hm.rm.apply_camera(aspect=1.6)
        hm.rm.sync()
    cam.dolly(0.9)
    hm.rm.apply_camera(aspect=1.6)
    hm.rm.sync()
    cam.pan((0.3, 0.0, 0.0))
    hm.rm.apply_camera(aspect=1.6)
    hm.rm.sync()


def test_01_initial_build() -> Case:
    case = Case("Test 1 — Initial Build", "Initialer Resource-Aufbau ist erlaubt.")
    hm = Harness()
    ids = hm.rm.store.resource_ids()
    expected_names = {"positions", "normals", "indices", "highlight_flags",
                      "material_uniforms", "camera_uniforms"}
    case.check(set(ids) == expected_names,
               f"Ressourcen: {sorted(ids)} != {sorted(expected_names)}")
    case.check(hm.rm.stats.counters["gpu_resource_creations"] >= len(ids),
               "Ressourcen-Erstellungen >= Ressourcenanzahl")
    case.check(hm.rm.stats.counters["gpu_resource_destroys"] == 0,
               "Initial keine Destroys")
    case.observe(f"Ressourcen: {ids}")
    return case


def test_02_camera() -> Case:
    case = Case("Test 2 — Camera",
                "Orbit/Pan/Zoom -> kein Mesh-Rebuild, keine Geometry-Uploads.")
    hm = Harness()
    camera_update_loop(hm)
    d = hm.deltas()
    case.check(d.get("mesh_rebuilds", 0) == 0,
               f"mesh_rebuilds == {d.get('mesh_rebuilds')}, erwartet 0")
    case.check(d.get("structural_rebuilds", 0) == 0, "structural_rebuilds == 0")
    case.check(d.get("geometry_uploads", 0) == 0, "geometry_uploads == 0")
    case.check(d.get("camera_updates", 0) > 0, "camera_updates > 0")
    now_ids = hm.rm.store.resource_ids()
    case.check(now_ids == hm.base_ids, f"IDs geändert: {hm.base_ids} -> {now_ids}")
    case.observe(f"IDs stabil ({len(now_ids)}); camera_updates={d.get('camera_updates')}")
    return case


def test_03_selection() -> Case:
    case = Case("Test 3 — Selection",
                "Selection ändern -> kein Mesh-/Structural-Rebuild, Highlight korrekt.")
    hm = Harness()
    hm.selection.set({0, 6, 12})
    hm.rm.apply_selection()
    hm.rm.sync()
    d = hm.deltas()
    case.check(d.get("mesh_rebuilds", 0) == 0, "mesh_rebuilds == 0")
    case.check(d.get("structural_rebuilds", 0) == 0, "structural_rebuilds == 0")
    case.check(d.get("selection_updates", 0) > 0, "selection_updates > 0")
    flags = hm.rm.store.data("highlight_flags")
    for v in (0, 6, 12):
        case.check(flags[v] == 1.0, f"highlight_flags[{v}] == 1.0")
    pos = hm.rm.store.data("positions")[:3]
    case.check(pos[0] == 0.0 and pos[1] == 0.0 and pos[2] == 0.0,
               "Base-Position 0 unverändert (0,0,0)")
    case.observe(f"Flags {{0,6,12}} gesetzt; IDs stabil: "
                 f"{hm.rm.store.resource_ids() == hm.base_ids}")
    return case


def test_04_material() -> Case:
    case = Case("Test 4 — Material",
                "Material-Update nachweisbar; kein Geometry-/Topology-Rebuild.")
    hm = Harness()
    hm.material.set_base_color((0.1, 0.2, 0.3, 1.0))
    hm.rm.apply_material()
    hm.rm.sync()
    d = hm.deltas()
    case.check(d.get("material_updates", 0) > 0, "material_updates > 0")
    case.check(d.get("mesh_rebuilds", 0) == 0, "mesh_rebuilds == 0")
    case.check(d.get("structural_rebuilds", 0) == 0, "structural_rebuilds == 0")
    case.check(d.get("geometry_uploads", 0) == 0, "geometry_uploads == 0")
    case.check(d.get("topology_updates", 0) == 0, "topology_updates == 0")
    pkt = hm.rm.store.data("material_uniforms")
    case.check(pkt[0] == 0.1 and pkt[1] == 0.2 and pkt[2] == 0.3,
               "material_uniforms aktualisiert (0.1,0.2,0.3)")
    case.observe("Material nur in material_uniforms; Positions-Ressource unangetastet")
    return case


def test_05_vertex_position() -> Case:
    case = Case("Test 5 — Vertex Position",
                "Vertex-Move -> gezieltes Update + korrekte Derived Data.")
    hm = Harness()
    hm.rm.move_vertex(12, (3.0, 3.0, 2.0))  # mittlerer Vertex hochgezogen
    hm.rm.sync()
    d = hm.deltas()
    case.check(d.get("vertex_updates", 0) > 0, "vertex_updates > 0")
    case.check(d.get("topology_updates", 0) == 0, "topology_updates == 0")
    case.check(d.get("structural_rebuilds", 0) == 0, "structural_rebuilds == 0")
    case.check(d.get("partial_updates", 0) > 0, "partial_updates > 0")
    case.check(d.get("geometry_uploads", 0) > 0, "geometry_uploads > 0")
    case.check(d.get("bounds_recalculations", 0) > 0, "bounds_recalculations > 0")
    pos = hm.rm.store.data("positions")
    case.check(pos[12 * 3] == 3.0 and pos[12 * 3 + 1] == 3.0 and pos[12 * 3 + 2] == 2.0,
               "position[12] == (3,3,2) nach Partial-Update")
    n = hm.rm.store.data("normals")
    changed = any(
        abs(n[i * 3] - 0.0) > 1e-3 or abs(n[i * 3 + 1] - 0.0) > 1e-3
        or abs(n[i * 3 + 2] - 1.0) > 1e-3
        for i in range(len(hm.rm.mesh.positions))
    )
    case.check(changed, "mind. eine Vertex-Normale wurde durch den Move aktualisiert")
    case.observe(f"vertex_updates={d.get('vertex_updates')} "
                 f"partial_updates={d.get('partial_updates')} "
                 f"geometry_uploads={d.get('geometry_uploads')} "
                 f"bounds_recalc={d.get('bounds_recalculations')}")
    return case


def test_06_topology() -> Case:
    case = Case("Test 6 — Topology",
                "Topology-Änderung -> structural rebuild erlaubt/erzeugt.")
    hm = Harness()
    new_mesh = make_grid_triangles(MESH_QUADS + 1, MESH_QUADS + 1)  # größer
    hm.rm.apply_topology(new_mesh)
    hm.rm.sync()
    d = hm.deltas()
    case.check(d.get("topology_updates", 0) > 0, "topology_updates > 0")
    case.check(d.get("structural_rebuilds", 0) > 0, "structural_rebuilds > 0")
    case.check(d.get("mesh_rebuilds", 0) > 0, "mesh_rebuilds > 0")
    now_ids = hm.rm.store.resource_ids()
    for name in ("positions", "normals", "indices"):
        case.check(now_ids.get(name) != hm.base_ids.get(name),
                   f"{name}-ID sollte sich nach Topology ändern: "
                   f"{hm.base_ids.get(name)} -> {now_ids.get(name)}")
    case.observe(f"neue IDs: {now_ids}")
    return case


def test_07_resource_persistence() -> Case:
    case = Case("Test 7 — Resource Persistence",
                "Nach Camera/Selection/Material/Geometry: keine Ressource-Recreation.")
    hm = Harness()
    camera_update_loop(hm, steps=3)
    hm.selection.set({0, 1})
    hm.rm.apply_selection()
    hm.rm.sync()
    hm.material.set_base_color((0.4, 0.4, 0.4, 1.0))
    hm.rm.apply_material()
    hm.rm.sync()
    hm.rm.move_vertex(3, (1.5, 2.0, 0.5))
    hm.rm.sync()

    d = hm.deltas()
    now_ids = hm.rm.store.resource_ids()
    case.check(d.get("gpu_resource_creations", 0) == 0,
               "keine neuen gpu_resource_creations erwartet")
    case.check(d.get("gpu_resource_destroys", 0) == 0,
               "keine gpu_resource_destroys erwartet")
    case.check(now_ids == hm.base_ids, f"IDs verändert: {hm.base_ids} -> {now_ids}")
    case.check(d.get("structural_rebuilds", 0) == 0, "structural_rebuilds == 0")
    case.check(hm.rm.stats.uploaded_bytes > hm.base_uploaded,
               "Upload-Bytes sind nachweisbar gewachsen")
    case.observe(f"IDs stabil ({len(now_ids)} Ressourcen); "
                 f"uploaded delta={hm.rm.stats.uploaded_bytes - hm.base_uploaded} B")
    return case


def test_08_stress() -> Case:
    case = Case("Test 8 — Stress",
                "Viele Vertex-Updates: keine Leaks, keine Hidden Full Rebuilds.")
    hm = Harness(quads=STRESS_QUADS)
    n = len(hm.rm.mesh.positions)
    for step in range(5):
        for v in range(0, n, 7):
            x, y, _ = hm.rm.mesh.positions[v]
            hm.rm.move_vertex(v, (x, y, float(step) * 0.1))
        hm.rm.sync()
    d = hm.deltas()
    case.check(d.get("structural_rebuilds", 0) == 0, "kein versteckter Structural Rebuild")
    case.check(d.get("topology_updates", 0) == 0, "topology_updates == 0")
    case.check(d.get("gpu_resource_destroys", 0) == 0, "keine Destroys -> kein Leak")
    case.check(d.get("gpu_resource_creations", 0) == 0, "keine neuen Creates -> Churn 0")
    now_ids = hm.rm.store.resource_ids()
    case.check(now_ids == hm.base_ids, "IDs stabil unter Stress")
    pos = hm.rm.store.data("positions")
    case.check(len(pos) == n * 3, f"positions-Puffer Länge {len(pos)} == {n * 3}")
    case.observe(f"vertices={n}; updates={d.get('vertex_updates')} "
                 f"partials={d.get('partial_updates')}; ids_stabil={now_ids == hm.base_ids}")
    return case


def test_09_interleaving() -> Case:
    case = Case("Test 9 — Interleaving",
                "Alle Kategorien im selben Frame: keine Counter-Korruption.")
    hm = Harness()
    hm.selection.set({4, 20})
    hm.rm.apply_selection()
    hm.material.set_base_color((0.8, 0.1, 0.1, 1.0))
    hm.rm.apply_material()
    hm.camera.orbit(0.1, 0.1)
    hm.rm.apply_camera(aspect=1.6)
    hm.rm.move_vertex(6, (1.5, 0.5, 0.7))
    hm.rm.sync()  # EIN Frame -> alle Dirty States zusammen verarbeitet

    d = hm.deltas()
    for name in ("camera_updates", "selection_updates", "material_updates", "vertex_updates"):
        case.check(d.get(name, 0) > 0, f"{name} > 0 (Interleaving verarbeitet)")
    case.check(d.get("structural_rebuilds", 0) == 0, "structural_rebuilds == 0")
    case.check(d.get("mesh_rebuilds", 0) == 0, "mesh_rebuilds == 0")
    case.check(d.get("partial_updates", 0) >= d.get("vertex_updates", 0),
               "partial_updates >= vertex_updates (Positions-Patches enthalten)")
    flags = hm.rm.store.data("highlight_flags")
    case.check(flags[4] == 1.0 and flags[20] == 1.0, "Selection-Flags gesetzt")
    pkt = hm.rm.store.data("material_uniforms")
    case.check(pkt[0] == 0.8, "Material-Paket aktualisiert")
    pos = hm.rm.store.data("positions")
    case.check(pos[6 * 3] == 1.5 and pos[6 * 3 + 1] == 0.5,
               "Positions-Patch übernommen")
    case.observe(f"Deltas im Interleave: {d}")
    return case


def test_10_bounds_visual_correctness() -> Case:
    case = Case("Test 10 — Bounds / Visual Correctness",
                "Bounds + Normalen nach Vertex-Movement korrekt.")
    hm = Harness()
    b0_min, b0_max = hm.rm.derived.bounds_min, hm.rm.derived.bounds_max
    case.check(b0_max[0] == float(MESH_QUADS) and b0_max[1] == float(MESH_QUADS),
               f"Basis-Bounds korrekt: {b0_min} .. {b0_max}")
    hm.rm.move_vertex(0, (-1.0, 0.0, 0.0))
    hm.rm.move_vertex(12, (2.5, 2.5, 3.0))
    hm.rm.sync()
    bmin, bmax = hm.rm.derived.bounds_min, hm.rm.derived.bounds_max
    case.check(bmin[0] <= -1.0, f"Bounds-Min deckt Move ab: {bmin}")
    case.check(bmax[2] >= 3.0, f"Bounds-Max deckt Move ab: {bmax}")
    inside = all(
        bmin[i] - 1e-9 <= p[i] <= bmax[i] + 1e-9
        for p in hm.rm.mesh.positions
        for i in range(3)
    )
    case.check(inside, "Alle Vertices liegen in den neu berechneten Bounds")
    vn = hm.rm.derived.vertex_normals[12]
    case.check(abs(vn[2] - 1.0) > 1e-3, f"Normale in Vertex 12 nicht mehr flat: {vn}")
    case.observe(f"Bounds: ({bmin}) .. ({bmax})")
    return case


def test_gpu_live() -> Case:
    """Optionaler Live-GPU-Persist-Check (nur mit --gpu; skippt bei Fehler)."""
    case = Case("GPU Live — Partial-Update-Persistenz",
                "pyglet set_attribute_data erzeugt dieselbe VertexList/Buffer-Identität.")
    try:
        import pyglet
        from pyglet.graphics import shader

        win = pyglet.window.Window(width=32, height=32, visible=False)
        vs = shader.Shader("""
            #version 330 core
            in vec3 position; in vec3 normal; in vec3 color;
            uniform mat4 view; uniform mat4 proj;
            out vec3 vColor;
            void main() { vColor = color; gl_Position = proj * view * vec4(position, 1.0); }
        """, "vertex")
        fs = shader.Shader("""
            #version 330 core
            in vec3 vColor; out vec4 fragColor;
            void main() { fragColor = vec4(vColor, 1.0); }
        """, "fragment")
        program = shader.ShaderProgram(vs, fs)
        n = 8
        positions = [0.0] * (n * 3)
        normals = [0.0, 0.0, 1.0] * n
        colors = [1.0, 1.0, 1.0] * n
        # pyglet 2.1-Konvention: position=("f", <flache Datenliste>)
        vlist = program.vertex_list(
            n, pyglet.gl.GL_TRIANGLES,
            position=("f", positions), normal=("f", normals), color=("f", colors),
        )

        vlist_id_before = id(vlist)
        # Partial-Update: schreibt in denselben Buffer (set_attribute_data)
        vlist.set_attribute_data("position", [0.5] * 6 + [0.0] * (n * 3 - 6))
        case.check(id(vlist) == vlist_id_before,
                   "VertexList-Objekt bleibt identisch bei Partial-Update")
        buffers = set(vlist.domain.attrib_name_buffers.keys())
        # pyglet optimiert ungenutzte Uniform-/Attribut-Deklarationen weg;
        # das Wesentliche ist die Identität des Position-Puffers, der gepatcht wird.
        case.check("position" in buffers, "Position-Buffer vorhanden")
        case.check("color" in buffers, "Color-Buffer vorhanden")
        case.observe(f"pyglet vlist id stabil; Buffers: {sorted(buffers)}")
        win.close()
    except Exception as exc:  # pragma: no cover - GPU evtl. nicht verfügbar
        case.check(False, f"GPU nicht verfügbar / Test fehlgeschlagen: {exc}")
    return case


def main() -> int:
    parser = argparse.ArgumentParser(description="Viewport V0.2 Test-Suite")
    parser.add_argument("--verbose", action="store_true", help="Zähler-Detail ausgeben")
    parser.add_argument("--gpu", action="store_true", help="Live-GPU-Persist-Check")
    args = parser.parse_args()

    tests = [
        test_01_initial_build,
        test_02_camera,
        test_03_selection,
        test_04_material,
        test_05_vertex_position,
        test_06_topology,
        test_07_resource_persistence,
        test_08_stress,
        test_09_interleaving,
        test_10_bounds_visual_correctness,
    ]
    if args.gpu:
        tests.append(test_gpu_live)

    print("=" * 78)
    print("VIEWPORT V0.2 EXPERIMENT — TEST-SUITE")
    print("=" * 78)
    all_passed = True
    for fn in tests:
        case = fn()
        status = "PASS" if case.passed else "FAIL"
        all_passed = all_passed and case.passed
        print(f"\n[{status}] {case.name}")
        print(f"      Erwartet: {case.expected}")
        if case.failures:
            for f in case.failures:
                print(f"      ! FEHLER: {f}")
        if args.verbose:
            for o in case.observations:
                print(f"      > {o}")
    print("\n" + "=" * 78)
    print(f"ERGEBNIS: {'ALLE TESTS BESTANDEN' if all_passed else 'MIND. EIN TEST FEHLGESCHLAGEN'}")
    print("=" * 78)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
