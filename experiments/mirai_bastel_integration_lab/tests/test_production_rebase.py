"""WP-IL-01 Regression: Das Lab läuft über den Production-Viewport-Pfad.

Sichert die Re-Basis des Integration Labs auf Gate 5/6/7-Production ab:

- LabOrbitCamera IST eine Production-OrbitCamera (eine Instanz pro Kette),
- Kamera-Operationen laufen über den kanonischen Pfad
  on_camera_changed → mark_camera_dirty → sync → camera_uniforms,
- Kamera-Änderungen fassen KEINE Geometrie an und erhalten alle
  Ressourcen-IDs (V0.2-Isolation, Gate 7-Vertrag),
- die Lab-Index-Map ist mit RenderMesh.vertex_index_of identisch,
- Selection ist ausschließlich Core-Buchhaltung (highlight_flags-Ressource),
- kein Lab-Modul importiert mehr das V0.2-Experiment.
"""

from __future__ import annotations

import sys
from pathlib import Path

_LAB = Path(__file__).resolve().parents[1]
_REPO = _LAB.parent.parent
for _p in (str(_LAB), str(_REPO), str(_REPO / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from adapters.core_to_render import CoreRenderBinding  # noqa: E402
from lab_camera import LabOrbitCamera  # noqa: E402
from scene.scene_objects import build_cube_scene  # noqa: E402

from mirai.viewport.camera import OrbitCamera as ProductionOrbitCamera  # noqa: E402
from viewport.resource_store import TraceStore  # noqa: E402  (Production, Gate 5)


def _binding_with_camera():
    core_mesh = build_cube_scene().mesh
    camera = LabOrbitCamera(distance=8.0)
    binding = CoreRenderBinding(
        core_mesh, store_type=TraceStore, camera=camera
    )
    binding.render.aspect = 1.6
    return core_mesh, binding, camera


def test_camera_instance_is_bound_into_production_render_mesh():
    """Objekt-Identität: Eine Kamera, an den Production-RenderMesh gebunden."""
    _, binding, camera = _binding_with_camera()
    assert isinstance(camera, ProductionOrbitCamera)
    assert binding.camera is camera
    assert binding.render.camera is camera  # Gate-7-Vertrag: dieselbe Instanz


def test_camera_change_touches_only_camera_uniforms():
    core_mesh, binding, camera = _binding_with_camera()
    before = dict(binding.render.stats.counters)
    ids_before = dict(binding.render.store.resource_ids())

    camera.orbit(0.1, 0.05)
    binding.apply_camera(aspect=1.6)

    after = binding.render.stats.counters
    assert after.get("camera_updates", 0) == before.get("camera_updates", 0) + 1
    # V0.2-Isolation (Gate 7): Kamera-Änderungen rühren keine Geometrie an.
    assert after.get("geometry_uploads", 0) == before.get("geometry_uploads", 0)
    assert after.get("vertex_updates", 0) == before.get("vertex_updates", 0)
    assert after.get("mesh_rebuilds", 0) == before.get("mesh_rebuilds", 0)
    assert after.get("structural_rebuilds", 0) == before.get(
        "structural_rebuilds", 0
    )
    # GPU-Ressourcen-IDs bleiben stabil.
    assert dict(binding.render.store.resource_ids()) == ids_before


def test_camera_uniforms_content_matches_bound_camera():
    """camera_uniforms (32 floats) == view+proj derselben Kamera-Instanz."""
    _, binding, camera = _binding_with_camera()
    binding.apply_camera(aspect=1.6)
    expected = (
        list(camera.build_view_matrix())
        + list(camera.build_projection_matrix(1.6))
    )
    stored = binding.render.store.data("camera_uniforms")
    assert len(stored) == 32
    assert stored == expected


def test_stress_camera_changes_preserve_invariants():
    """100 Kamera-Zyklen: keine Geometrie-Uploads, stabile IDs."""
    _, binding, camera = _binding_with_camera()
    ids_before = dict(binding.render.store.resource_ids())
    geom_before = binding.render.stats.counters.get("geometry_uploads", 0)
    for _ in range(100):
        camera.orbit(0.01, 0.005)
        binding.apply_camera(aspect=1.6)
    assert binding.render.stats.counters.get("geometry_uploads", 0) == geom_before
    assert dict(binding.render.store.resource_ids()) == ids_before


def test_lab_index_map_matches_production_vertex_index():
    """Lab-Index-Map == Production `RenderMesh.vertex_index_of`."""
    core_mesh, binding, _ = _binding_with_camera()
    for vid in core_mesh.all_vertex_ids():
        assert binding.index_map.index(vid) == binding.render.vertex_index_of(vid)


def test_move_is_core_first_and_keeps_resource_identity():
    core_mesh, binding, _ = _binding_with_camera()
    vid = core_mesh.all_vertex_ids()[0]
    ids_before = dict(binding.render.store.resource_ids())
    mesh_rebuilds_before = binding.render.stats.counters.get("mesh_rebuilds", 0)

    binding.move_vertex(vid, (5.0, 6.0, 7.0))

    assert core_mesh.vertex_position(vid) == (5.0, 6.0, 7.0)
    idx = binding.index_map.index(vid)
    assert binding.render.store.data("positions")[idx * 3: idx * 3 + 3] == [
        5.0, 6.0, 7.0,
    ]
    assert binding.render.stats.counters.get("mesh_rebuilds", 0) == (
        mesh_rebuilds_before
    )
    assert dict(binding.render.store.resource_ids()) == ids_before


def test_selection_is_core_only_bookkeeping():
    """Selection existiert nur in der Core-Selection; Overlay-Ressource folgt."""
    core_mesh, binding, _ = _binding_with_camera()
    vid = core_mesh.all_vertex_ids()[1]
    geom_before = binding.render.stats.counters.get("geometry_uploads", 0)

    binding.select_vertex(vid)

    assert vid in binding.selection.vertices  # Core-Selection ist die Wahrheit
    idx = binding.index_map.index(vid)
    flags = binding.render.store.data("highlight_flags")
    assert flags[idx] == 1.0
    # Selection darf die Geometrie NICHT anfassen (Overlay-Kanal separat).
    assert binding.render.stats.counters.get("geometry_uploads", 0) == geom_before

    binding.clear_selection()
    assert len(binding.selection.vertices) == 0
    assert binding.render.store.data("highlight_flags")[idx] == 0.0


def test_no_lab_module_imports_v02_experiment():
    """Akzeptanzkriterium WP-IL-01: keine V0.2-Experiment-Imports mehr."""
    lab_dir = Path(__file__).resolve().parents[1]
    # Needle zusammengesetzt, damit diese Testdatei sich nicht selbst trifft.
    needle = "mirai_bastel_" + "viewport_V02"
    offenders: list[str] = []
    for py_file in lab_dir.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8", errors="ignore")
        if needle in text:
            offenders.append(str(py_file.relative_to(lab_dir)))
    assert offenders == []
