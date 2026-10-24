"""Scene: Wurzel-Objekt, das Meshes über Objekte in den Systemkontext einbettet.

Bezug: V1_SPEC.md §0, §12, §15 Punkt 7; AD-021 (Object / Component Model).

Architekturvertrag:

- Scene behandelt Mesh NICHT als das gesamte System, sondern als eines
  von mehreren möglichen Kind-Subsystemen. `morph_targets`, `rig` und
  `animation` sind für V1 bewusst `None` - keine Implementierung, aber
  ein fester Platz in der Struktur (§12), damit spätere Subsysteme
  ergänzt statt das Format umgebaut werden muss.
- History und Selection leben auf Scene-Ebene, nicht im Mesh selbst -
  das entspricht §15 Punkt 5/6 (History/Selection nicht mesh-spezifisch
  verankern).
- AD-021 M0: Die Scene hält Objekte (`SceneObject`), jedes besitzt genau
  ein Mesh. Geometrie und alles, was an deren ID-Raum hängt, bleibt im
  Mesh; Platzierung (`transform`, `pivot`), Rolle (`state`) und Name
  liegen am Objekt; welches Objekt bearbeitet wird, weiß die Scene
  (`edit_object_id`, persistiert, kein Modeling-Undo-Schritt). Mesh,
  Operation, OperationContext und HistoryStack kennen keine Objekte.
- `Scene.mesh` ist eine Kompatibilitäts-Zugriffsstelle für "das Mesh des
  Edit-Objekts" (AD-021 §5.2), nie "die Geometrie der Scene".
- Namen sind AD-021-`PROVISIONAL`.
- Spiegelpaare (`MirrorPair`, `Scene.mirror_pairs`; OBJECT_MIRROR_SYMMETRY_PROPOSAL §5.1,
  CORE_V1_FREEZE §7.1): reine Daten wie M0 - welche zwei Objekte über welche Weltebene
  gekoppelt sind. Das Verhalten (Platzierung folgt, Commands, Ablehnungen) lebt in `src/mirai`.
- Material pro Objekt (`ObjectMaterial`, `SceneObject.material`; AD-024, CORE_V1_FREEZE §7.1):
  reine Daten - Grundfarbe, Specular, Glossiness; `None` = der Standard-Look der App. Was die Werte
  bedeuten (Exponent, Fill-Glanz, Auswahl-Tönung, Referenz-Look), entscheiden `src/mirai`/`src/viewport`.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from .history import HistoryStack
from .ids import IdAllocator, ObjectId
from .mesh import Mesh
from .selection import Selection

Vec3 = tuple[float, float, float]
Mat3 = tuple[Vec3, Vec3, Vec3]

_IDENTITY_ROTATION: Mat3 = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))

# PROVISIONAL (Agent-Annahme, AD-021 E-1): Toleranz, innerhalb derer eine
# Rotationsmatrix als orthonormal mit det +1 gilt. Gleiche Größenordnung wie
# SEAM_TOLERANCE; serialisierte Matrizen tragen Rundungsreste.
ROTATION_TOLERANCE = 1e-9


class ObjectState(Enum):
    """Rolle eines Objekts in der Scene (AD-021 §4.7); erweiterbar (hidden, locked)."""

    NORMAL = "normal"
    REFERENCE = "reference"


def _vec3(values: Iterable[float], what: str) -> Vec3:
    vec = tuple(float(v) for v in values)
    if len(vec) != 3 or not all(math.isfinite(v) for v in vec):
        raise ValueError(f"{what} muss drei endliche Zahlen haben: {vec!r}")
    return vec  # type: ignore[return-value]


@dataclass(frozen=True)
class ObjectTransform:
    """Platzierung Objektraum -> Welt: Translation, Rotation, gleichmäßige Skalierung.

    Nur Ähnlichkeitstransformationen sind darstellbar (AD-021 §4.3, Q-4):
    `rotation` ist eine echte Rotationsmatrix (orthonormal, det +1, Zeilen),
    `scale` ein einzelner Faktor > 0. Nicht-gleichmäßige Skalierung, Scherung
    und Spiegelung auf Objektebene sind dadurch strukturell ausgeschlossen.
    Die Kompositionsformel mit dem Pivot ist M2 (AD-021 E-2); M0 speichert nur.
    """

    translation: Vec3 = (0.0, 0.0, 0.0)
    rotation: Mat3 = _IDENTITY_ROTATION
    scale: float = 1.0

    def __post_init__(self) -> None:
        translation = _vec3(self.translation, "translation")
        rows = tuple(self.rotation)
        if len(rows) != 3:
            raise ValueError(f"rotation muss 3x3 sein: {self.rotation!r}")
        rotation = tuple(_vec3(row, "rotation-Zeile") for row in rows)
        for i in range(3):
            for j in range(3):
                dot = sum(rotation[i][k] * rotation[j][k] for k in range(3))
                if abs(dot - (1.0 if i == j else 0.0)) > ROTATION_TOLERANCE:
                    raise ValueError(f"rotation ist nicht orthonormal: {rotation!r}")
        (a, b, c), (d, e, f), (g, h, i_) = rotation
        det = a * (e * i_ - f * h) - b * (d * i_ - f * g) + c * (d * h - e * g)
        if det <= 0.0:
            raise ValueError(f"rotation ist eine Spiegelung (det {det!r}), keine Rotation")
        scale = float(self.scale)
        if not (math.isfinite(scale) and scale > 0.0):
            raise ValueError(f"scale muss endlich und > 0 sein (AD-021 Q-4): {self.scale!r}")
        object.__setattr__(self, "translation", translation)
        object.__setattr__(self, "rotation", rotation)
        object.__setattr__(self, "scale", scale)


IDENTITY_TRANSFORM = ObjectTransform()


def _unit(value: float, what: str) -> float:
    v = float(value)
    if not (math.isfinite(v) and 0.0 <= v <= 1.0):
        raise ValueError(f"{what} muss endlich und in [0, 1] sein: {value!r}")
    return v


@dataclass(frozen=True)
class ObjectMaterial:
    """Oberfläche eines Objekts (AD-024 §2): Grundfarbe (RGB) und der Glanz des Worklights.
    Alle Werte in [0, 1]; ungültige Werte werden abgelehnt, nicht geklemmt (die Setter in
    `src/mirai` klemmen vorher). Keine Standardwerte im Core: "kein Material" ist `None` am Objekt."""

    base_color: Vec3
    specular: float
    glossiness: float

    def __post_init__(self) -> None:
        color = _vec3(self.base_color, "base_color")
        object.__setattr__(self, "base_color", tuple(_unit(c, "base_color") for c in color))
        object.__setattr__(self, "specular", _unit(self.specular, "specular"))
        object.__setattr__(self, "glossiness", _unit(self.glossiness, "glossiness"))


@dataclass(frozen=True)
class MirrorPair:
    """Zwei Objekte, deren Platzierungen über die Weltebene `normal·x = offset` gekoppelt sind
    (OBJECT_MIRROR_SYMMETRY_PROPOSAL §5.1). Nur Daten: die Scene prüft die Invarianten, die
    Kopplung selbst rechnet `src/mirai` (`object_mirror`). `a` war bei der Erzeugung der
    Treiber; danach trägt die Reihenfolge keine Bedeutung. `normal` ist ein Einheitsvektor."""

    a: ObjectId
    b: ObjectId
    normal: Vec3 = (1.0, 0.0, 0.0)
    offset: float = 0.0

    def __post_init__(self) -> None:
        _require_object_id(self.a)
        _require_object_id(self.b)
        if self.a == self.b:
            raise ValueError(f"Spiegelpaar mit sich selbst: Objekt {int(self.a)}")
        normal = _vec3(self.normal, "normal")
        if abs(math.sqrt(sum(v * v for v in normal)) - 1.0) > ROTATION_TOLERANCE:
            raise ValueError(f"normal muss ein Einheitsvektor sein: {normal!r}")
        offset = float(self.offset)
        if not math.isfinite(offset):
            raise ValueError(f"offset muss endlich sein: {self.offset!r}")
        object.__setattr__(self, "normal", normal)
        object.__setattr__(self, "offset", offset)

    def other(self, object_id: ObjectId) -> ObjectId:
        """Der Partner von `object_id` (KeyError, wenn es nicht zu diesem Paar gehört)."""
        if object_id == self.a:
            return self.b
        if object_id == self.b:
            return self.a
        raise KeyError(f"Objekt {int(object_id)} gehört nicht zu diesem Spiegelpaar")


def _require_object_id(object_id: object) -> ObjectId:
    # IDs sind ints: VertexId(0) == ObjectId(0). Ein Objekt wird nie aus einer
    # Element-ID abgeleitet (AD-021 §4.10 N-3), daher hier der Typ.
    if not isinstance(object_id, ObjectId):
        raise TypeError(f"erwartet eine ObjectId, nicht {object_id!r}")
    return object_id


class SceneObject:
    """Scene-Mitglied, das genau ein Mesh besitzt und in der Scene platziert (AD-021 §4.1).

    Das Mesh weiß nichts von seinem Objekt (kein Rückverweis). Mesh-Positionen
    sind Objektraum-Koordinaten. Die ID ist unveränderlich; alles andere sind
    einfache Werte, die künftige Objekt-Commands (M1/M2) ändern.
    """

    __slots__ = ("_id", "mesh", "name", "transform", "pivot", "state", "material")

    def __init__(
        self,
        object_id: ObjectId,
        mesh: Mesh,
        *,
        name: str = "object",
        transform: ObjectTransform = IDENTITY_TRANSFORM,
        pivot: Iterable[float] = (0.0, 0.0, 0.0),
        state: ObjectState = ObjectState.NORMAL,
        material: ObjectMaterial | None = None,
    ) -> None:
        self._id = _require_object_id(object_id)
        self.mesh: Mesh = mesh
        self.name: str = name
        self.transform: ObjectTransform = transform
        # Punkt im Objektraum, um den Objekt-Rotation/-Skalierung wirken (M2).
        self.pivot: Vec3 = _vec3(pivot, "pivot")
        self.state: ObjectState = state
        # AD-024: None = der Standard-Look der App (ein unberührtes Objekt folgt dessen Werten).
        if material is not None and not isinstance(material, ObjectMaterial):
            raise TypeError(f"erwartet ein ObjectMaterial oder None, nicht {material!r}")
        self.material: ObjectMaterial | None = material

    @property
    def id(self) -> ObjectId:
        return self._id

    def __repr__(self) -> str:  # pragma: no cover - reine Debug-Hilfe
        return f"SceneObject({int(self._id)}, {self.name!r}, {self.state.name})"


class Scene:
    def __init__(self) -> None:
        self._object_ids = IdAllocator(ObjectId)
        self._objects: dict[ObjectId, SceneObject] = {}
        # Wie bisher startet eine Scene mit einem leeren, bearbeitbaren Mesh -
        # jetzt als einziges Objekt, das zugleich Edit-Objekt ist.
        self._edit_object_id: ObjectId = self.add_object(Mesh()).id
        self._mirror_pairs: tuple[MirrorPair, ...] = ()

        self.selection: Selection = Selection()
        self.history: HistoryStack = HistoryStack()

        # Bewusst None in V1 - siehe §12/§16. Reservierte Plätze, keine
        # Implementierung.
        self.morph_targets = None
        self.rig = None
        self.animation = None

    @classmethod
    def from_objects(
        cls,
        objects: Iterable[SceneObject],
        *,
        edit_object_id: ObjectId,
        object_id_counter: int,
        mirror_pairs: Iterable[MirrorPair] = (),
    ) -> "Scene":
        """Scene aus bestehenden Objekten (Laden einer Datei, serialization.py).

        `object_id_counter` ist der nächste zu vergebende Rohwert; er muss über
        jeder geladenen ID liegen, sonst würde eine künftige ID eine geladene
        wiederholen (AD-001 auf Objekte erweitert). `mirror_pairs` werden wie
        über `add_mirror_pair` geprüft (ValueError bei einem ungültigen Paar).
        """
        scene = cls()
        loaded: dict[ObjectId, SceneObject] = {}
        for obj in objects:
            if obj.id in loaded:
                raise ValueError(f"ObjectId doppelt: {int(obj.id)}")
            if int(obj.id) >= object_id_counter:
                raise ValueError(
                    f"ObjectId {int(obj.id)} liegt nicht unter object_id_counter {object_id_counter}"
                )
            loaded[obj.id] = obj
        if _require_object_id(edit_object_id) not in loaded:
            raise ValueError(f"Edit-Objekt {int(edit_object_id)} ist nicht unter den Objekten")
        scene._object_ids = IdAllocator(ObjectId, start=object_id_counter)
        scene._objects = dict(sorted(loaded.items()))
        scene._edit_object_id = edit_object_id
        for pair in mirror_pairs:
            scene.add_mirror_pair(pair)
        return scene

    # ------------------------------------------------------------------
    # Objekte (AD-021 §4.1, §4.5, §5.1)
    # ------------------------------------------------------------------

    @property
    def objects(self) -> Mapping[ObjectId, SceneObject]:
        """Nur-Lese-Sicht, nach ID (= Erzeugungsreihenfolge) geordnet.

        Ändern nur über `add_object`/`remove_object`/`restore_object`, damit
        das Edit-Objekt nie aus der Scene verschwindet.
        """
        return MappingProxyType(self._objects)

    @property
    def object_id_counter(self) -> int:
        """Nächster zu vergebender ObjectId-Rohwert - für die Serialisierung."""
        return self._object_ids.peek_next()

    def add_object(
        self,
        mesh: Mesh,
        *,
        name: str = "object",
        state: ObjectState = ObjectState.NORMAL,
    ) -> SceneObject:
        """Neues Objekt mit frischer, nie wiederverwendeter ObjectId."""
        obj = SceneObject(self._object_ids.allocate(), mesh, name=name, state=state)
        self._objects[obj.id] = obj
        return obj

    def remove_object(self, object_id: ObjectId) -> SceneObject:
        """Entfernt ein Objekt und gibt genau diese Instanz zurück (für Undo).

        Das Edit-Objekt wird nicht entfernt: erst ein anderes Objekt zum
        Edit-Objekt machen. Die ID bleibt verbraucht (AD-001).
        """
        if _require_object_id(object_id) == self._edit_object_id:
            raise ValueError(f"Das Edit-Objekt {int(object_id)} kann nicht entfernt werden")
        if self.mirror_pair_of(object_id) is not None:
            # Ein Paar zeigt nie auf ein fehlendes Objekt: erst das Paar lösen (ein Command).
            raise ValueError(f"Objekt {int(object_id)} ist in einem Spiegelpaar - erst das Paar lösen")
        return self._objects.pop(object_id)

    def restore_object(self, obj: SceneObject) -> None:
        """Setzt eine zuvor entfernte Instanz mit ihrer ID wieder ein (Undo/Redo, AD-021 §4.6).

        Nur IDs, die diese Scene schon vergeben hat, und nur, wenn die ID
        gerade frei ist - eine neue oder fremde ID ginge an `add_object` vorbei.
        """
        if obj.id in self._objects:
            raise ValueError(f"ObjectId {int(obj.id)} ist bereits in der Scene")
        if int(obj.id) >= self._object_ids.peek_next():
            raise ValueError(f"ObjectId {int(obj.id)} wurde von dieser Scene nie vergeben")
        self._objects[obj.id] = obj
        # Wieder an seinen Platz in der ID-Reihenfolge, damit Undo auch die
        # Reihenfolge exakt herstellt.
        self._objects = dict(sorted(self._objects.items()))

    # ------------------------------------------------------------------
    # Spiegelpaare (OBJECT_MIRROR_SYMMETRY_PROPOSAL §5.1)
    # ------------------------------------------------------------------

    @property
    def mirror_pairs(self) -> tuple[MirrorPair, ...]:
        """Die Spiegelpaare in Erzeugungsreihenfolge; ändern nur über `add_mirror_pair` /
        `remove_mirror_pair` (Commands in `src/mirai`)."""
        return self._mirror_pairs

    def mirror_pair_of(self, object_id: ObjectId) -> MirrorPair | None:
        """Das Paar, zu dem `object_id` gehört, oder None."""
        for pair in self._mirror_pairs:
            if object_id == pair.a or object_id == pair.b:
                return pair
        return None

    def add_mirror_pair(self, pair: MirrorPair) -> None:
        """Invarianten: beide Objekte sind in der Scene (`a != b` prüft `MirrorPair`), und jedes
        Objekt gehört zu höchstens einem Paar. Ob die Platzierungen gespiegelt sind, prüft die
        Scene nicht - ein Paar kann ungleich geladen werden und wird dann gemeldet, nie repariert."""
        if not isinstance(pair, MirrorPair):
            raise TypeError(f"erwartet ein MirrorPair, nicht {pair!r}")
        for object_id in (pair.a, pair.b):
            if object_id not in self._objects:
                raise ValueError(f"Spiegelpaar: Objekt {int(object_id)} ist nicht in der Scene")
            if self.mirror_pair_of(object_id) is not None:
                raise ValueError(f"Spiegelpaar: Objekt {int(object_id)} ist schon in einem Paar")
        self._mirror_pairs = self._mirror_pairs + (pair,)

    def remove_mirror_pair(self, pair: MirrorPair) -> None:
        if pair not in self._mirror_pairs:
            raise ValueError(f"Spiegelpaar {pair!r} ist nicht in der Scene")
        self._mirror_pairs = tuple(p for p in self._mirror_pairs if p != pair)

    # ------------------------------------------------------------------
    # Edit-Objekt (AD-021 §4.4, review R-3)
    # ------------------------------------------------------------------

    @property
    def edit_object_id(self) -> ObjectId:
        """Das Objekt, dessen Komponenten die Modi 1/2/3 ansprechen."""
        return self._edit_object_id

    @edit_object_id.setter
    def edit_object_id(self, object_id: ObjectId) -> None:
        # Die Komponenten-Sets der Selection gehören zum alten Edit-Objekt;
        # der Aufrufer leert sie nach dem Wechsel (AD-021 §4.4, Reihenfolge Q-5).
        if _require_object_id(object_id) not in self._objects:
            raise KeyError(f"Edit-Objekt {int(object_id)} ist nicht in der Scene")
        self._edit_object_id = object_id

    @property
    def edit_object(self) -> SceneObject:
        try:
            return self._objects[self._edit_object_id]
        except KeyError:
            raise LookupError(
                f"Edit-Objekt {int(self._edit_object_id)} fehlt in Scene.objects"
            ) from None

    @property
    def mesh(self) -> Mesh:
        """Das Mesh des Edit-Objekts - nie "die Geometrie der Scene" (AD-021 §5.2).

        Code, der ein anderes Objekt meint, benennt es: `scene.objects[oid].mesh`.
        """
        return self.edit_object.mesh

    @mesh.setter
    def mesh(self, mesh: Mesh) -> None:
        """Tauscht das Mesh des Edit-Objekts; ID, Name, Transform, Pivot und State bleiben.

        Die heutigen Zuweisungen in App, Factories, Playground und Lab meinen
        "neue Scene laden"; mit genau einem Objekt fallen beide Lesarten
        zusammen. Ab M1 lädt die App über einen expliziten Scene-Reset, und
        dieser Setter bedeutet nur noch "Mesh dieses Objekts tauschen"
        (AD-021 §5.2, review R-4). Die Symmetry Definition stirbt wie bisher
        mit dem alten Mesh (AD-SYM-01).
        """
        self.edit_object.mesh = mesh
