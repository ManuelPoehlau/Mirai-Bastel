"""Objekt-Ebene der Application (AD-021 M1): Scene-Reset, Objekt-Commands, Referenz-Look.

AD-021 §4.6 / §5.4: die Objekt-Commands sind einfache `Command`-Implementierungen außerhalb
von `HistoryStack` (Core unverändert, M0 liefert alles). Jeder hält seine Ziel-Instanz
selbst, so dass Objekt- und Mesh-Schritte auf dem einen Stack der Scene korrekt
ineinandergreifen (AD-021 F-4, Probe P-1). Namen und Texte sind `PROVISIONAL`.

Nichts aus M2: kein Transform, keine Model-Matrix, kein Wechsel des Edit-Objekts.
"""

from __future__ import annotations

from core import Mesh, ObjectState, Scene, SceneObject

#: AD-021 Q-11 (Manu 2026-10-15: "Das gedämpfte Blau ist gut"): eine Referenz ist schattiert wie
#: jedes Mesh, ohne Selection-Overlays, in diesem gedämpften Blau, deutlich dunkler als das Grau
#: des Edit-Objekts (`gl_render_store.DEFAULT_BASE_COLOR`). Ghost und Wireframe: §7.3, M2-0.
REFERENCE_BASE_COLOR = (0.38, 0.47, 0.62)

#: AD-021 M2-0 (§7.3 RD-1, Q-11 bestätigt; Wert `PROVISIONAL`): Deckkraft einer Referenz im Ghost.
REFERENCE_GHOST_ALPHA = 0.3


def object_base_color(obj: SceneObject) -> tuple[float, float, float] | None:
    """Grundfarbe des Render-Eintrags eines Nicht-Edit-Objekts (None = Standardfarbe)."""
    return REFERENCE_BASE_COLOR if obj.state is ObjectState.REFERENCE else None


def reset_scene(scene: Scene, mesh: Mesh, name: str) -> SceneObject:
    """Scene-Reset beim Laden (AD-021 §5.2, review R-4): alle Objekte werden durch genau ein
    neues, bearbeitbares Objekt ersetzt, das Edit-Objekt wird.

    Ersetzt die frühere Zuweisung `scene.mesh = ...` in `Application.init_scene`; der
    Setter bedeutet ab M1 nur noch "Mesh dieses Objekts tauschen". Die Scene-Instanz
    bleibt dieselbe (Selection/History hängen daran); ObjectIds laufen weiter, keine wird
    wiederverwendet (AD-001). Nur über die M0-API, kein Core-Change."""
    obj = scene.add_object(mesh, name=name)
    scene.edit_object_id = obj.id
    for object_id in [oid for oid in scene.objects if oid != obj.id]:
        scene.remove_object(object_id)
    return obj


class AddObjectCommand:
    """"Objekt hinzufügen" als ein Undo-Schritt (AD-021 §4.6, Q-3 = ja).

    Wird nach `scene.add_object(...)` gepusht. Undo entfernt, Redo setzt **dieselbe**
    Instanz mit derselben ID wieder ein (AD-001: eine ID wird nie neu vergeben)."""

    def __init__(self, scene: Scene, obj: SceneObject) -> None:
        self.scene = scene
        self.obj = obj
        self.description = f"Add object {obj.name!r}"

    def undo(self) -> None:
        self.scene.remove_object(self.obj.id)

    def redo(self) -> None:
        self.scene.restore_object(self.obj)


class ObjectStateCommand:
    """Zustandswechsel Normal <-> Referenz als ein Undo-Schritt (AD-021 §4.6, Q-3 = ja)."""

    def __init__(self, obj: SceneObject, before: ObjectState, after: ObjectState) -> None:
        self.obj = obj
        self.before = before
        self.after = after
        self.description = f"Object {obj.name!r}: {after.value}"

    def undo(self) -> None:
        self.obj.state = self.before

    def redo(self) -> None:
        self.obj.state = self.after
