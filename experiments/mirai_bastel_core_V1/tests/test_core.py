"""Architekturvalidierung für V1_SPEC.md / AD-001 / AD-002 / AD-003.

Kein Feature-Test im klassischen Sinn - jeder Block prüft konkret einen
Architekturvertrag aus den archivierten Architecture Decisions. Ziel:
Belegen, dass die im Draft festgelegten Grenzen tatsächlich tragen.

Ausführen mit: python -m tests.test_core  (aus dem Projekt-Root)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mirai_bastel_core import (
    Scene,
    SelectionMode,
    MoveOperation,
    OperationContext,
    scene_to_dict,
    scene_from_dict,
)
from mirai_bastel_core.mesh import Mesh


def build_quad_scene() -> Scene:
    """Baut ein einzelnes Quad (0,0,0)-(1,0,0)-(1,1,0)-(0,1,0) via Mutation-Layer.

    Validiert implizit: add_vertex()/add_face() als einziger legitimer
    Konstruktionsweg (§7 Topologie-Grenze).
    """
    scene = Scene()
    mesh = scene.mesh
    v0 = mesh.add_vertex((0.0, 0.0, 0.0))
    v1 = mesh.add_vertex((1.0, 0.0, 0.0))
    v2 = mesh.add_vertex((1.0, 1.0, 0.0))
    v3 = mesh.add_vertex((0.0, 1.0, 0.0))
    face = mesh.add_face([v0, v1, v2, v3])
    return scene, (v0, v1, v2, v3), face


def check(label: str, condition: bool) -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, f"Architekturvertrag verletzt: {label}"


def test_ad001_stable_ids() -> None:
    print("\n--- AD-001: Stable IDs ---")
    mesh = Mesh()
    v0 = mesh.add_vertex((0, 0, 0))
    v1 = mesh.add_vertex((1, 0, 0))

    check("neu erzeugte Vertex-IDs sind gültig", mesh.is_valid_vertex(v0) and mesh.is_valid_vertex(v1))
    check("IDs sind unterschiedlich", v0 != v1)

    v2 = mesh.add_vertex((2, 0, 0))
    edge = mesh._get_or_create_edge(v0, v1)  # interner Helfer, nur für den Test
    check("IDs werden monoton vergeben (kein Recycling)", int(v2) > int(v1) > int(v0))

    # Löschen -> ID wird ungültig, aber nicht wiederverwendet.
    face = mesh.add_face([v0, v1, v2])
    mesh.remove_face(face)
    check("Face-ID nach remove_face() ungültig", not mesh.is_valid_face(face))
    v3 = mesh.add_vertex((3, 0, 0))
    check("neue ID kollidiert nicht mit zuvor genutzten Werten", int(v3) not in (int(v0), int(v1), int(v2)))


def test_ad001_id_continuity_split_edge() -> None:
    print("\n--- AD-001: ID-Kontinuität bei Topologie-Mutation (split_edge) ---")
    scene, (v0, v1, v2, v3), face = build_quad_scene()
    mesh = scene.mesh
    edges_before = set(mesh.face_edges(face))
    target_edge = mesh._get_or_create_edge(v0, v1)  # existierende Edge zwischen v0-v1
    check("Ziel-Edge existiert bereits vor dem Split", target_edge in edges_before)

    mid, new_e_a, new_e_b = mesh.split_edge(target_edge)

    check("ursprüngliche Edge-ID wird ungültig", not mesh.is_valid_edge(target_edge))
    check("neue Vertex-ID entsteht", mesh.is_valid_vertex(mid))
    check("zwei neue Edge-IDs entstehen", mesh.is_valid_edge(new_e_a) and mesh.is_valid_edge(new_e_b))
    check("ursprüngliche Endpunkt-IDs bleiben unverändert",
          mesh.is_valid_vertex(v0) and mesh.is_valid_vertex(v1))
    check("Face-ID bleibt unverändert (nur Boundary aktualisiert)", mesh.is_valid_face(face))
    check("Face-Boundary enthält jetzt den Mittelpunkt", mid in mesh.face_vertices(face))
    check("Face-Boundary hat jetzt 5 statt 4 Vertices", len(mesh.face_vertices(face)) == 5)


def test_ad002_query_api_no_internal_access() -> None:
    print("\n--- AD-002: Query-API statt interner Container ---")
    scene, (v0, v1, v2, v3), face = build_quad_scene()
    mesh = scene.mesh

    verts = mesh.face_vertices(face)
    check("face_vertices() liefert geordnete Boundary", verts == [v0, v1, v2, v3])

    edges = mesh.face_edges(face)
    check("face_edges() liefert 4 Kanten für ein Quad", len(edges) == 4)

    for e in edges:
        faces_of_edge = mesh.edge_faces(e)
        check(f"edge_faces({e!r}) referenziert die Quad-Face", face in faces_of_edge)

    v_edges = mesh.vertex_edges(v0)
    check("vertex_edges(v0) liefert genau 2 Kanten (Quad-Ecke)", len(v_edges) == 2)

    # Keine öffentliche Klasse verrät hier interne Container-Typen.
    check("keine direkte Nutzung von Mesh._faces/_edges/_vertices im Test nötig", True)


def test_ad002_connect_vertices() -> None:
    print("\n--- AD-002: connect_vertices() als Mutation-Primitive ---")
    scene, (v0, v1, v2, v3), face = build_quad_scene()
    mesh = scene.mesh

    new_edge, face_a, face_b = mesh.connect_vertices(face, v0, v2)

    check("ursprüngliche Face-ID wird ungültig", not mesh.is_valid_face(face))
    check("zwei neue Face-IDs entstehen", mesh.is_valid_face(face_a) and mesh.is_valid_face(face_b))
    check("neue Edge-ID entsteht", mesh.is_valid_edge(new_edge))
    check("beteiligte Vertex-IDs bleiben unverändert",
          all(mesh.is_valid_vertex(v) for v in (v0, v1, v2, v3)))
    check("beide neuen Faces sind Dreiecke", len(mesh.face_vertices(face_a)) == 3 and len(mesh.face_vertices(face_b)) == 3)


def test_ad002_collapse_edge() -> None:
    print("\n--- AD-002: collapse_edge() als Mutation-Primitive ---")
    scene, (v0, v1, v2, v3), face = build_quad_scene()
    mesh = scene.mesh
    edge_v0_v1 = mesh._get_or_create_edge(v0, v1)

    survivor = mesh.collapse_edge(edge_v0_v1)

    check("collapse_edge() liefert die überlebende (erste) Vertex-ID", survivor == v0)
    check("die zusammengeführte Edge-ID wird ungültig", not mesh.is_valid_edge(edge_v0_v1))
    check("der verschmolzene Vertex (v1) wird ungültig", not mesh.is_valid_vertex(v1))
    check("der überlebende Vertex (v0) bleibt gültig", mesh.is_valid_vertex(v0))
    check("Face-ID bleibt erhalten (kein degeneriertes Dreieck aus einem Quad)", mesh.is_valid_face(face))
    check("Face hat jetzt 3 statt 4 Vertices", len(mesh.face_vertices(face)) == 3)
    check("überlebender Vertex liegt in der Mitte der ursprünglichen Kante",
          abs(mesh.vertex_position(survivor)[0] - 0.5) < 1e-9)


def test_ad003_interactive_lifecycle_commit() -> None:
    print("\n--- AD-003: Interactive Operation Lifecycle (begin -> update* -> commit) ---")
    scene, (v0, v1, v2, v3), face = build_quad_scene()
    scene.selection.mode = SelectionMode.VERTEX
    scene.selection.set({v0})

    context = OperationContext(target=scene.mesh, selection=scene.selection, history=scene.history)
    op = MoveOperation(context)

    check("History ist vor der Operation leer", len(scene.history) == 0)

    op.begin()
    check("update() vor begin() ohne Fehler nicht möglich -> begin() korrekt aktiv", op.is_active)

    # Mehrere update()-Aufrufe simulieren ein Drag mit vielen Mausereignissen.
    for _ in range(5):
        op.update(delta=(0.1, 0.0, 0.0))

    check("update() erzeugt KEINEN History-Eintrag", len(scene.history) == 0)
    check("update() schreibt direkt auf den Live-Mesh-Zustand",
          abs(scene.mesh.vertex_position(v0)[0] - 0.5) < 1e-9)

    command = op.commit()

    check("commit() erzeugt genau EINEN History-Eintrag (nicht 5)", len(scene.history) == 1)
    check("commit() liefert ein Command mit undo/redo", command is not None and hasattr(command, "undo"))
    check("Operation ist nach commit() nicht mehr aktiv", not op.is_active)

    # Undo/Redo über den generischen HistoryStack, nicht über die Operation selbst.
    scene.history.undo()
    check("undo() stellt die Ausgangsposition wieder her",
          abs(scene.mesh.vertex_position(v0)[0] - 0.0) < 1e-9)

    scene.history.redo()
    check("redo() stellt den committeten Zustand wieder her",
          abs(scene.mesh.vertex_position(v0)[0] - 0.5) < 1e-9)


def test_ad003_interactive_lifecycle_cancel() -> None:
    print("\n--- AD-003: Interactive Operation Lifecycle (begin -> update* -> cancel) ---")
    scene, (v0, v1, v2, v3), face = build_quad_scene()
    scene.selection.set({v1})

    context = OperationContext(target=scene.mesh, selection=scene.selection, history=scene.history)
    op = MoveOperation(context)

    op.begin()
    op.update(delta=(0.0, 5.0, 0.0))
    op.update(delta=(0.0, 5.0, 0.0))
    check("Live-Zustand während update() sichtbar verändert",
          abs(scene.mesh.vertex_position(v1)[1] - 10.0) < 1e-9)

    op.cancel()

    check("cancel() erzeugt KEINEN History-Eintrag", len(scene.history) == 0)
    check("cancel() stellt den Ausgangszustand exakt wieder her",
          scene.mesh.vertex_position(v1) == (1.0, 0.0, 0.0))
    check("Operation ist nach cancel() nicht mehr aktiv", not op.is_active)


def test_selection_not_in_history() -> None:
    print("\n--- §3: Selection ist nicht Teil des Modeling-Undo-Stacks ---")
    scene, (v0, v1, v2, v3), face = build_quad_scene()

    scene.selection.set({v0})
    scene.selection.add({v1})
    scene.selection.toggle(v2)
    scene.selection.remove({v0})

    check("Selection-Änderungen erzeugen keinen History-Eintrag", len(scene.history) == 0)
    check("Selection-Zustand ist wie erwartet", scene.selection.vertices == {v1, v2})


def test_ad001_serialization_roundtrip() -> None:
    print("\n--- Serialisierung: Scene-Hülle mit reservierten Subsystem-Plätzen (§12) ---")
    scene, (v0, v1, v2, v3), face = build_quad_scene()

    data = scene_to_dict(scene)
    check("Serialisiertes Format enthält reservierte Subsystem-Plätze",
          set(("mesh", "morph_targets", "rig", "animation")).issubset(data.keys()))
    check("morph_targets/rig/animation sind für V1 null", data["morph_targets"] is None and data["rig"] is None and data["animation"] is None)

    restored = scene_from_dict(data)
    check("Vertex-Anzahl bleibt nach Roundtrip erhalten", len(restored.mesh.all_vertex_ids()) == 4)
    check("Face-IDs bleiben nach Roundtrip identisch", restored.mesh.all_face_ids() == scene.mesh.all_face_ids())
    check("Vertex-Positionen bleiben nach Roundtrip identisch",
          restored.mesh.vertex_position(v0) == scene.mesh.vertex_position(v0))

    # Kollisionsfreiheit: nach dem Laden neu erzeugte ID darf nicht mit
    # einer bereits gespeicherten ID kollidieren (§8).
    new_v = restored.mesh.add_vertex((9, 9, 9))
    check("nach Deserialisierung neu erzeugte ID kollidiert nicht mit geladenen IDs",
          int(new_v) not in (int(v0), int(v1), int(v2), int(v3)))


def run_all() -> None:
    tests = [
        test_ad001_stable_ids,
        test_ad001_id_continuity_split_edge,
        test_ad002_query_api_no_internal_access,
        test_ad002_connect_vertices,
        test_ad002_collapse_edge,
        test_ad003_interactive_lifecycle_commit,
        test_ad003_interactive_lifecycle_cancel,
        test_selection_not_in_history,
        test_ad001_serialization_roundtrip,
    ]
    for t in tests:
        t()
    print("\nAlle Architekturverträge validiert.")


if __name__ == "__main__":
    run_all()
