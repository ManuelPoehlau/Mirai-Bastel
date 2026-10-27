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

Spiegelpaare (2026-10-23, OBJECT_MIRROR_SYMMETRY_PROPOSAL §5.5, `PROVISIONAL`): `MirrorPairCommand`
(anlegen / lösen) ist der einzige Weg, `Scene.mirror_pairs` zu ändern; Spiegelkopie, Paaren und
Löschen sind `CompositeCommand`s aus den vorhandenen Commands. Die Mathematik: `object_mirror`.

Material pro Objekt (AD-024, 2026-10-24): `ObjectMaterialCommand` ist der Undo-Schritt einer
Material-Änderung (Core-History unverändert); `object_base_color` / `object_finish` sagen, wie ein
Objekt gezeichnet wird (eine Referenz bleibt im festen Blau, Q-M3), `editable_material`, mit welchen
Werten ein Objekt ohne eigenes Material bearbeitet wird.
"""

from __future__ import annotations

from collections.abc import Iterable

from core import (
    Mesh,
    MirrorPair,
    ObjectId,
    ObjectMaterial,
    ObjectState,
    ObjectTransform,
    Scene,
    SceneObject,
    SymmetryDefinition,
)
from viewport.gl_render_store import DEFAULT_BASE_COLOR
from viewport.material import SurfaceFinish

from . import object_space
from .object_mirror import in_sync, mirror_placement, pair_residual, plane_label
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
    """Grundfarbe, mit der ein Objekt gezeichnet wird (None = Standardfarbe): eine Referenz im
    festen Blau, auch mit eigenem Material (AD-024 Q-M3), sonst die Farbe ihres Materials."""
    if obj.state is ObjectState.REFERENCE:
        return REFERENCE_BASE_COLOR
    return obj.material.base_color if obj.material is not None else None


def object_finish(obj: SceneObject, default: SurfaceFinish) -> SurfaceFinish:
    """Der Glanz, mit dem ein Objekt gezeichnet wird: `default` (der des Worklights, samt
    `fill_specular`) für eine Referenz und ein Objekt ohne Material, sonst dessen Specular und
    Glossiness mit dem `fill_specular` von `default` (AD-024 §4: ein Worklight-Wert)."""
    if obj.state is ObjectState.REFERENCE or obj.material is None:
        return default
    return default.with_(specular=obj.material.specular, glossiness=obj.material.glossiness)


def editable_material(obj: SceneObject, default: SurfaceFinish) -> ObjectMaterial:
    """Die Werte, von denen eine Material-Änderung ausgeht: das Material des Objekts, ohne eines
    der Standard-Look (Standardfarbe, Glanz von `default`)."""
    if obj.material is not None:
        return obj.material
    return ObjectMaterial(DEFAULT_BASE_COLOR, specular=default.specular, glossiness=default.glossiness)


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
    _clear_mirror_pairs(scene)
    for object_id in [oid for oid in scene.objects if oid != obj.id]:
        scene.remove_object(object_id)
    return obj


def replace_scene(scene: Scene, loaded: Scene) -> SceneObject:
    """Scene-Reset aus einer Szenendatei: alle Objekte werden durch die Objekte von `loaded`
    ersetzt (Name, Zustand, Transform, Pivot, Mesh samt Symmetrie), das Pendant von dessen
    Edit-Objekt wird Edit-Objekt. Gibt es zurück.

    Wie `reset_scene` bleibt die Scene-Instanz dieselbe (Selection/History hängen daran),
    deshalb bekommen die Objekte hier neue ObjectIds - die IDs der Datei sind sitzungslokal,
    Selection und History werden ohnehin nicht gespeichert. Nur über die M0-API.

    Spiegelpaare zeigen auf die IDs der Datei: sie werden auf die neuen IDs umgeschrieben
    (OBJECT_MIRROR_SYMMETRY_PROPOSAL §5.1), die Paare der alten Scene fallen mit ihren Objekten."""
    new_ids: dict[ObjectId, ObjectId] = {}
    edit = None
    for source in loaded.objects.values():
        obj = scene.add_object(source.mesh, name=source.name, state=source.state)
        obj.transform = source.transform
        obj.pivot = source.pivot
        obj.material = source.material
        new_ids[source.id] = obj.id
        if source.id == loaded.edit_object_id:
            edit = obj
    assert edit is not None  # Scene garantiert ein Edit-Objekt unter den Objekten
    scene.edit_object_id = edit.id
    _clear_mirror_pairs(scene)
    kept = set(new_ids.values())
    for object_id in [oid for oid in scene.objects if oid not in kept]:
        scene.remove_object(object_id)
    for pair in loaded.mirror_pairs:
        scene.add_mirror_pair(
            MirrorPair(new_ids[pair.a], new_ids[pair.b], normal=pair.normal, offset=pair.offset)
        )
    scene.morph_targets = loaded.morph_targets
    scene.rig = loaded.rig
    scene.animation = loaded.animation
    return edit


def _clear_mirror_pairs(scene: Scene) -> None:
    """Scene-Reset: die alten Paare gehen mit den alten Objekten (kein History-Schritt - ein
    Laden setzt die History ohnehin zurück)."""
    for pair in scene.mirror_pairs:
        scene.remove_mirror_pair(pair)


class AddObjectCommand:
    """"Objekt hinzufügen" als ein Undo-Schritt (AD-021 §4.6, Q-3 = ja).

    Wird nach `scene.add_object(...)` gepusht. Undo entfernt, Redo setzt **dieselbe**
    Instanz mit derselben ID wieder ein (AD-001: eine ID wird nie neu vergeben).

    Edit-Objekt (Track A1, 2026-10-23): `Scene.remove_object` verweigert das Edit-Objekt, und ein
    **Normal**-Objekt kann zwischen Add und Undo Edit-Objekt werden (Modus `4`, anklicken, `1` -
    kein History-Schritt). Der Command trägt deshalb das Edit-Objekt von davor (`edit_before`;
    ohne Angabe das aktuelle der Scene, richtig, wenn der Add es nicht ändert): ist das Objekt im
    Undo das Edit-Objekt, geht die Rolle zuerst dorthin zurück. Hat der Add selbst das neue Objekt
    zum Edit-Objekt gemacht (`edit_before` angegeben, Scene steht schon auf dem neuen), setzt
    Redo es wieder dazu. Nur der Scene-Zustand; die Ansicht (Viewport, Caches) folgt
    `Application._follow_edit_object`."""

    def __init__(
        self, scene: Scene, obj: SceneObject, edit_before: ObjectId | None = None
    ) -> None:
        self.scene = scene
        self.obj = obj
        self.made_edit = edit_before is not None and scene.edit_object_id == obj.id
        self.edit_before = scene.edit_object_id if edit_before is None else edit_before
        if self.edit_before == obj.id:
            raise ValueError("edit_before is the added object itself")
        self.description = f"Add object {obj.name!r}"

    def undo(self) -> None:
        if self.scene.edit_object_id == self.obj.id:
            self.scene.edit_object_id = self.edit_before
        self.scene.remove_object(self.obj.id)

    def redo(self) -> None:
        self.scene.restore_object(self.obj)
        if self.made_edit:
            self.scene.edit_object_id = self.obj.id


class DeleteObjectsCommand:
    """"Objekte löschen" (Modus `4`, Track A2) als ein Undo-Schritt.

    Hält die **Instanzen** (AD-001: dieselbe ID, dasselbe Mesh, Transform, Pivot, Zustand kommen
    im Undo zurück) und das Edit-Objekt davor/danach. Wurde das Edit-Objekt gelöscht, ist
    `edit_after` ein überlebendes Objekt: Redo stellt es *vor* dem Entfernen ein (die Scene
    verweigert das Entfernen des Edit-Objekts), Undo setzt die Objekte ein und danach `edit_before`
    wieder. Nur der Scene-Zustand; Viewport und Caches folgen der Application
    (`_follow_edit_object`, `_sync_object_views`), die Objekt-Auswahl der Selection-Mirror-Stack."""

    def __init__(
        self,
        scene: Scene,
        objects: list[SceneObject],
        edit_before: ObjectId,
        edit_after: ObjectId,
    ) -> None:
        self.scene = scene
        self.objects = list(objects)
        self.edit_before = edit_before
        self.edit_after = edit_after
        names = ", ".join(repr(obj.name) for obj in self.objects)
        self.description = f"Delete object {names}"

    def undo(self) -> None:
        for obj in self.objects:
            self.scene.restore_object(obj)
        self.scene.edit_object_id = self.edit_before

    def redo(self) -> None:
        self.scene.edit_object_id = self.edit_after
        for obj in self.objects:
            self.scene.remove_object(obj.id)


def unique_object_name(scene: Scene, base: str) -> str:
    """`base`, bzw. `base.001`, `base.002`, ... wenn der Name in der Scene schon vorkommt
    (Blender-Schema; Namen sind Anzeige, die Identität ist die ObjectId)."""
    taken = {obj.name for obj in scene.objects.values()}
    if base not in taken:
        return base
    n = 1
    while f"{base}.{n:03d}" in taken:
        n += 1
    return f"{base}.{n:03d}"


class DeleteRefused(ValueError):
    """Objekte löschen ist abgelehnt (Text = Grund, für die Statuszeile)."""


def plan_object_delete(scene: Scene, selected: Iterable[ObjectId]) -> tuple[list[SceneObject], ObjectId]:
    """Was "Objekte löschen" tut, ohne etwas zu ändern: die zu löschenden Objekte (nach ID) und
    das Edit-Objekt danach, oder `DeleteRefused`.

    Scene-Invarianten (`Scene.remove_object`, RF-5): es bleibt immer ein Edit-Objekt, und das ist
    nie eine Referenz. Wird das Edit-Objekt gelöscht, folgt ihm das nächstliegende überlebende
    Normal-Objekt nach ID-Abstand (das davor, bei Gleichstand das danach; `PROVISIONAL`). Gäbe es
    keines - das letzte Objekt, oder nur Referenzen bleiben -, wird abgelehnt: eine leere Scene
    gibt es nicht (Scene und `scene.mesh` setzen ein Edit-Objekt überall voraus), und ein
    Platzhalter oder eine stillschweigend umgeschaltete Referenz wäre ein verstecktes Objekt."""
    doomed_ids = {oid for oid in selected if oid in scene.objects}
    doomed = [scene.objects[oid] for oid in sorted(doomed_ids)]
    edit_id = scene.edit_object_id
    if edit_id not in doomed_ids:
        return doomed, edit_id
    survivors = [obj for obj in scene.objects.values() if obj.id not in doomed_ids]
    if not survivors:
        raise DeleteRefused("the scene needs at least one object - the last one stays")
    editable = [obj for obj in survivors if obj.state is ObjectState.NORMAL]
    if not editable:
        raise DeleteRefused(
            "only References would remain, and the scene needs an editable object"
            " - switch one to Normal (Alt+R) or keep the edit object"
        )
    nearest = min(editable, key=lambda obj: (abs(int(obj.id) - int(edit_id)), int(obj.id)))
    return doomed, nearest.id


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


class ObjectMaterialCommand:
    """Material eines oder mehrerer Objekte als ein Undo-Schritt (AD-024 §7). `changes` =
    `(obj, before, after)` je Objekt (`None` = kein eigenes Material); setzt nur `obj.material`.
    Die Ansicht frischt die Application auf (Material steht in `_object_highlight_signature`)."""

    def __init__(
        self,
        changes: list[tuple[SceneObject, ObjectMaterial | None, ObjectMaterial | None]],
        description: str,
    ) -> None:
        self.changes = list(changes)
        self.description = description

    def undo(self) -> None:
        for obj, before, _ in reversed(self.changes):
            obj.material = before

    def redo(self) -> None:
        for obj, _, after in self.changes:
            obj.material = after


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
    Seam. Schreibt nur das Mesh; Transform und Pivot setzt der Aufrufer (Commands).

    Punkt-Layer (AD-025 §4.3, Phase 3): ein Frame-Wechsel - Vektor-Werte (Morph-Offsets) werden mit
    dem linearen Teil s·R der Platzierung abgebildet (`Mesh.map_vector_layers`, ein Ganz-Layer-Record
    in derselben Aufzeichnung wie die Positionen); die Translation berührt keinen Offset. Danach ist
    die ausgewertete Weltform `b + w·d` dieselbe wie vorher (bis auf Rundung)."""
    mesh = obj.mesh
    for vid in mesh.all_vertex_ids():
        mesh.set_vertex_position(vid, object_space.to_world(obj, mesh.vertex_position(vid)))
    if mesh.has_point_layers() and not object_space.is_identity(obj.transform):
        t = obj.transform
        mesh.map_vector_layers(tuple(tuple(t.scale * c for c in row) for row in t.rotation))
    definition = mesh.symmetry_definition
    if definition is not None and axis is not None:
        mesh.symmetry_definition = SymmetryDefinition(
            plane_point=ORIGIN, plane_normal=AXIS_NORMALS[axis], seam_edges=definition.seam_edges
        )


# -- Spiegelpaare (OBJECT_MIRROR_SYMMETRY_PROPOSAL §5.5, `PROVISIONAL`) -------------------------


class MirrorPairCommand:
    """Ein Spiegelpaar anlegen (`create=True`) oder lösen als ein Undo-Schritt; wird nach der
    Änderung gepusht wie die anderen Objekt-Commands. Nur `Scene.mirror_pairs` - Platzierung und
    Mesh beider Objekte bleiben, wie sie sind (Lösen ist der Weg, ein Objekt frei zu bewegen)."""

    def __init__(self, scene: Scene, pair: MirrorPair, create: bool) -> None:
        self.scene = scene
        self.pair = pair
        self.create = create
        self.description = "Mirror pair" if create else "Break mirror pair"

    def undo(self) -> None:
        if self.create:
            self.scene.remove_mirror_pair(self.pair)
        else:
            self.scene.add_mirror_pair(self.pair)

    def redo(self) -> None:
        if self.create:
            self.scene.add_mirror_pair(self.pair)
        else:
            self.scene.remove_mirror_pair(self.pair)


class MirrorRefused(ValueError):
    """Ein Spiegelpaar-Command ist abgelehnt (Text = Grund, für die Statuszeile)."""


def pair_names(scene: Scene, pair: MirrorPair) -> str:
    return f"{scene.objects[pair.a].name!r} / {scene.objects[pair.b].name!r}"


def check_pairable(scene: Scene, objects: list[SceneObject]) -> None:
    """Die Ablehnungen beim Anlegen (Proposal §5.7): eine Referenz, ein Objekt in einem Paar."""
    for obj in objects:
        if obj.state is ObjectState.REFERENCE:
            raise MirrorRefused(f"{obj.name!r} is a Reference - locked (Alt+R makes it Normal)")
        pair = scene.mirror_pair_of(obj.id)
        if pair is not None:
            partner = scene.objects[pair.other(obj.id)]
            raise MirrorRefused(f"{obj.name!r} already belongs to a pair with {partner.name!r}")


def pair_existing_command(
    scene: Scene, driver: SceneObject, follower: SceneObject, normal, offset: float
) -> CompositeCommand:
    """Zwei vorhandene Objekte paaren (Proposal §5.5): `follower` springt nach F(`driver`)
    (Transform samt Skalierung und Pivot), dann das Paar - ein Undo-Schritt. Ändert die Scene
    und gibt den Command zum Pushen zurück. Die Meshes werden nicht angesehen."""
    if driver.id == follower.id:
        raise MirrorRefused("an object cannot be its own mirror partner")
    check_pairable(scene, [driver, follower])
    transform, pivot = mirror_placement(driver, normal, offset)
    pair = MirrorPair(driver.id, follower.id, normal=normal, offset=offset)
    parts = [
        ObjectTransformCommand([(follower, follower.transform, transform)], "Mirror pair: place"),
        ObjectPivotCommand([(follower, follower.pivot, pivot)]),
        MirrorPairCommand(scene, pair, create=True),
    ]
    follower.transform = transform
    follower.pivot = pivot
    scene.add_mirror_pair(pair)
    return CompositeCommand(parts, f"Mirror pair {driver.name!r} / {follower.name!r}")


def resync_command(scene: Scene, pair: MirrorPair) -> CompositeCommand | None:
    """Re-sync (B folgt A, Proposal §5.7): `pair.b` springt nach F(`pair.a`), ein Undo-Schritt;
    None, wenn das Paar schon synchron ist. Eine Referenz als B wird abgelehnt (gesperrt)."""
    a, b = scene.objects[pair.a], scene.objects[pair.b]
    if in_sync(a, b, pair):
        return None
    if b.state is ObjectState.REFERENCE:
        raise MirrorRefused(f"{b.name!r} (mirror partner of {a.name!r}) is a Reference - locked")
    transform, pivot = mirror_placement(a, pair.normal, pair.offset)
    parts = [
        ObjectTransformCommand([(b, b.transform, transform)], "Re-sync mirror pair"),
        ObjectPivotCommand([(b, b.pivot, pivot)]),
    ]
    b.transform = transform
    b.pivot = pivot
    return CompositeCommand(parts, f"Re-sync mirror pair {a.name!r} / {b.name!r}")


def out_of_sync_text(scene: Scene, pair: MirrorPair) -> str:
    """Die Statuszeile eines ungleichen Paars (Proposal §5.7, Wortlaut `PROVISIONAL`)."""
    a, b = scene.objects[pair.a], scene.objects[pair.b]
    return (
        f"Mirror pair {pair_names(scene, pair)} is out of sync by {pair_residual(a, b, pair):.3g}"
        f" - Re-sync ({b.name!r} follows {a.name!r}) or break it (Shift+M)"
    )


def describe_pair(scene: Scene, pair: MirrorPair) -> str:
    return f"{pair_names(scene, pair)} across {plane_label(pair.normal, pair.offset)}"
