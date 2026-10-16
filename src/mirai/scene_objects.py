"""Objekt-Ebene der Application (AD-021 M1): Scene-Reset, Objekt-Commands, Referenz-Look.

Seit 2026-10-15 auch der Scene-Reset aus einer Szenendatei (`replace_scene`).

AD-021 §4.6 / §5.4: die Objekt-Commands sind einfache `Command`-Implementierungen außerhalb
von `HistoryStack` (Core unverändert, M0 liefert alles). Jeder hält seine Ziel-Instanz
selbst, so dass Objekt- und Mesh-Schritte auf dem einen Stack der Scene korrekt
ineinandergreifen (AD-021 F-4, Probe P-1). Namen und Texte sind `PROVISIONAL`.

AD-021 M2-2 (E-12): `ObjectTransformCommand` - die Platzierung als ein Undo-Schritt; schreibt
nur `transform`, nie ein Mesh (L-1). AD-021 M2-3 (E-13, L-3): `ObjectPivotCommand` und
`CompositeCommand` (der erste Composite des Projekts, §4.6) für "Apply transform";
`apply_placement` / `applied_symmetry_axis` rechnen den Bake.
"""

from __future__ import annotations

from core import Mesh, ObjectState, ObjectTransform, Scene, SceneObject, SymmetryDefinition

from . import object_space
from .symmetry_axis import AXIS_NORMALS, ORIGIN

#: AD-021 Q-11 (Manu 2026-10-15: "Das gedämpfte Blau ist gut"): eine Referenz ist schattiert wie
#: jedes Mesh, ohne Selection-Overlays, in diesem gedämpften Blau, deutlich dunkler als das Grau
#: des Edit-Objekts (`gl_render_store.DEFAULT_BASE_COLOR`). Ghost und Wireframe: §7.3, M2-0.
REFERENCE_BASE_COLOR = (0.38, 0.47, 0.62)

#: AD-021 M2-0 (§7.3 RD-1, Q-11 bestätigt; Wert `PROVISIONAL`): Deckkraft einer Referenz im Ghost.
REFERENCE_GHOST_ALPHA = 0.3


#: Auswahl in Modus `4` sichtbar (Manu 2026-10-16: "man kann nicht wirklich sehen, welches Objekt
#: ausgewählt ist"; Werte `PROVISIONAL`): die Grundfarbe eines ausgewählten Objekts geht zu diesem
#: Anteil in Richtung des Gelbs der Komponenten-Auswahl (`gl_point_overlay.SELECTED_COLOR`). Eine
#: Referenz bleibt dabei erkennbar blau.
SELECTED_TINT = (1.0, 0.82, 0.15)
SELECTED_TINT_SHARE = 0.45
SELECTED_REFERENCE_TINT_SHARE = 0.3


def object_base_color(obj: SceneObject) -> tuple[float, float, float] | None:
    """Grundfarbe des Render-Eintrags eines Nicht-Edit-Objekts (None = Standardfarbe)."""
    return REFERENCE_BASE_COLOR if obj.state is ObjectState.REFERENCE else None


def selected_color(obj: SceneObject, default: tuple[float, float, float]) -> tuple[float, float, float]:
    """Die Farbe eines in Modus `4` ausgewählten Objekts (`default` = Standardfarbe des Viewports)."""
    base = object_base_color(obj) or default
    share = SELECTED_REFERENCE_TINT_SHARE if obj.state is ObjectState.REFERENCE else SELECTED_TINT_SHARE
    return tuple(b + share * (t - b) for b, t in zip(base, SELECTED_TINT))


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


def replace_scene(scene: Scene, loaded: Scene) -> SceneObject:
    """Scene-Reset aus einer Szenendatei: alle Objekte werden durch die Objekte von `loaded`
    ersetzt (Name, Zustand, Transform, Pivot, Mesh samt Symmetrie), das Pendant von dessen
    Edit-Objekt wird Edit-Objekt. Gibt es zurück.

    Wie `reset_scene` bleibt die Scene-Instanz dieselbe (Selection/History hängen daran),
    deshalb bekommen die Objekte hier neue ObjectIds - die IDs der Datei sind sitzungslokal,
    Selection und History werden ohnehin nicht gespeichert. Nur über die M0-API."""
    kept: set = set()
    edit = None
    for source in loaded.objects.values():
        obj = scene.add_object(source.mesh, name=source.name, state=source.state)
        obj.transform = source.transform
        obj.pivot = source.pivot
        kept.add(obj.id)
        if source.id == loaded.edit_object_id:
            edit = obj
    assert edit is not None  # Scene garantiert ein Edit-Objekt unter den Objekten
    scene.edit_object_id = edit.id
    for object_id in [oid for oid in scene.objects if oid not in kept]:
        scene.remove_object(object_id)
    scene.morph_targets = loaded.morph_targets
    scene.rig = loaded.rig
    scene.animation = loaded.animation
    return edit


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


class ObjectTransformCommand:
    """Objekt verschieben/drehen/skalieren als ein Undo-Schritt (AD-021 M2-2, E-12, §4.6).

    `changes` = `(obj, before, after)` je Objekt einer Geste; Undo/Redo setzt nur die
    Transforms (L-1: kein Mesh). Die Ansicht frischt der Aufrufer auf
    (`Application._placement_changed`), wie bei den anderen Objekt-Commands."""

    def __init__(
        self,
        changes: list[tuple[SceneObject, ObjectTransform, ObjectTransform]],
        description: str,
    ) -> None:
        self.changes = list(changes)
        self.description = description

    def undo(self) -> None:
        for obj, before, _ in reversed(self.changes):
            obj.transform = before

    def redo(self) -> None:
        for obj, _, after in self.changes:
            obj.transform = after


class ObjectPivotCommand:
    """Pivot-Änderung eines Objekts (AD-021 §4.6 "transform/pivot change"); heute nur als Teil
    von "Apply transform" (M2-3), ein Pivot-Werkzeug gibt es nicht (Q-13)."""

    def __init__(self, changes: list[tuple[SceneObject, tuple, tuple]]) -> None:
        self.changes = list(changes)
        self.description = "Object pivot"

    def undo(self) -> None:
        for obj, before, _ in reversed(self.changes):
            obj.pivot = before

    def redo(self) -> None:
        for obj, _, after in self.changes:
            obj.pivot = after


class CompositeCommand:
    """Mehrere Commands als ein Undo-Schritt (AD-021 §4.6, E-13): Undo rückwärts, Redo vorwärts.
    `HistoryStack` bleibt unverändert; der Composite ist ein gewöhnliches `Command`."""

    def __init__(self, commands: list, description: str) -> None:
        self.commands = list(commands)
        self.description = description

    def undo(self) -> None:
        for command in reversed(self.commands):
            command.undo()

    def redo(self) -> None:
        for command in self.commands:
            command.redo()


class ApplyRefused(ValueError):
    """"Apply transform" ist für dieses Objekt abgelehnt (Text = Grund, für die Statuszeile)."""


def applied_symmetry_axis(obj: SceneObject) -> str | None:
    """Die E1-Achse, die die Symmetrie-Definition von `obj` nach "Apply transform" hat (None =
    keine Definition), oder `ApplyRefused`.

    AD-021 M2-3 (`PROVISIONAL`): nach dem Bake sind die Mesh-Koordinaten Weltkoordinaten; die
    Definition bleibt nur gültig, wenn die Platzierung die Ebene **exakt** auf eine Achsenebene
    durch den Ursprung abbildet - Rotation achsentreu (Einträge exakt 0/±1), der Pivot liegt auf
    der Ebene und keine Translation entlang der Normale (`t + c` dort exakt 0); `s` beliebig.
    Dann bleiben Paare und Seam bitgleich gespiegelt (gleiches Rechenschema wie
    `object_space.to_world`), sonst würde ein exakt symmetrisches Mesh `partial`."""
    definition = obj.mesh.symmetry_definition
    if definition is None:
        return None
    t = obj.transform
    if any(v not in (0.0, 1.0, -1.0) for row in t.rotation for v in row):
        raise ApplyRefused(
            "the rotation is not a multiple of 90 degrees, so the symmetry plane would not lie on"
            " an axis plane (Clear transform, or Shift+S off first)"
        )
    normal = definition.plane_normal
    i = next(j for j in range(3) if normal[j] != 0.0)
    world_normal = object_space._rotate(t.rotation, normal)
    k = next(j for j in range(3) if world_normal[j] != 0.0)
    c = obj.pivot
    if c[i] != 0.0 or t.translation[k] + c[k] != 0.0:
        raise ApplyRefused(
            "the placement moves the symmetry plane off the origin (a translation along its"
            " normal) - Clear transform, or Shift+S off first"
        )
    return "XYZ"[k]


def apply_placement(obj: SceneObject, axis: str | None) -> None:
    """Bake (L-3): jede Mesh-Position wird ihre Weltposition (`object_space.to_world`, also
    bitgleich zu dem, was Picking und Werkzeuge bisher als Welt gerechnet haben); eine
    Symmetrie-Definition bekommt die Achse `axis` (aus `applied_symmetry_axis`) bei gleicher
    Seam. Schreibt nur das Mesh; Transform und Pivot setzt der Aufrufer (Commands)."""
    mesh = obj.mesh
    for vid in mesh.all_vertex_ids():
        mesh.set_vertex_position(vid, object_space.to_world(obj, mesh.vertex_position(vid)))
    definition = mesh.symmetry_definition
    if definition is not None and axis is not None:
        mesh.symmetry_definition = SymmetryDefinition(
            plane_point=ORIGIN, plane_normal=AXIS_NORMALS[axis], seam_edges=definition.seam_edges
        )
