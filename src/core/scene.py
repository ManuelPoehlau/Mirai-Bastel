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
- Textur pro Objekt (`SceneObject.texture`; AD-026, CORE_V1_FREEZE §7.1 2026-10-29): reine Daten -
  der Pfad einer Bilddatei (oder `None`), die über die Face-Ecken-UVs des Meshes gezeigt wird. Das
  Bild selbst ist kein Scene-Inhalt; Laden und Anzeigen leben in `src/mirai`/`src/viewport`.
- Rig (`Scene.rig: Rig | None`; AD-028 §3.1, CORE_V1_FREEZE §7.1 2026-11-02): der reservierte Platz
  trägt jetzt einen geprüften, unveränderlichen Wert (`core.rig`) - Knochen mit Ruhelage in Welt-
  koordinaten; `None` = kein Rig. Pose, Auswertung und Commands leben in `src/mirai`.
- Bemalung (`PaintStack`, `PaintLayer`, `SceneObject.paint`; AD-037 §3, CORE_V1_FREEZE §7.1 2026-11-18): reine
  Daten - Ebenen über der Textur des Objekts, je ein Bildpfad, Deckkraft, Sichtbarkeit, Mischmodus. Pixel, Malen und
  Undo der Pinselstriche leben in `src/mirai` (`mirai.paint`).
- LookDev-Material (`LookMaterial`, `SceneObject.look`; AD-038 §18 LD-2, CORE_V1_FREEZE §7.1 2026-11-21): reine
  Daten - das organische Material des LookDev-Raums (Vorlage, Farbe, Albedo-Quelle, Rauheit, Glanz, Weichheit,
  Durchscheinen); unabhängig vom Worklight-`ObjectMaterial`. Zeichnung, Vorlagen und Undo leben in `src/mirai` /
  `src/viewport`.
- Augen (`EyeSpec`, `SceneObject.eye`; AD-033 §4, CORE_V1_FREEZE §7.1 2026-11-15): reine Daten. Seit 2026-11-16
  (Eye LookDev Phase 3, Manu I-5 "Core Change erlaubt") trägt ein Auge optional eine verschachtelte Look-Gruppe
  (`EyeLook`, `EyeSpec.look`; `None` = neutral, wie bisher); Bedeutung und Zeichnung leben in `src/viewport`.
"""

from __future__ import annotations

import math
import numbers
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, fields
from enum import Enum
from types import MappingProxyType

from .history import HistoryStack
from .ids import BoneId, IdAllocator, ObjectId
from .mesh import Mesh
from .rig import Rig
from .selection import Selection

Vec3 = tuple[float, float, float]
Mat3 = tuple[Vec3, Vec3, Vec3]

_IDENTITY_ROTATION: Mat3 = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))

# PROVISIONAL (Agent-Annahme, AD-021 E-1): Toleranz, innerhalb derer eine
# Rotationsmatrix als orthonormal mit det +1 gilt. Gleiche Größenordnung wie
# SEAM_TOLERANCE; serialisierte Matrizen tragen Rundungsreste.
ROTATION_TOLERANCE = 1e-9


class ObjectState(Enum):
    """Rolle eines Objekts in der Scene (AD-021 §4.7); erweiterbar (locked).

    `GROUP` (Outliner, Manu 2026-11-07): ein Container ohne eigene Geometrie und Platzierung - sein
    Mesh ist leer. Andere Objekte hängen über `SceneObject.parent` darin; Auswahl, Transform, Ausblenden,
    Duplizieren und Löschen wirken auf die Mitglieder. Eine Gruppe ist nie Edit-Objekt."""

    NORMAL = "normal"
    REFERENCE = "reference"
    GROUP = "group"


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


#: AD-033 §4.1: the eye's limbus levels and colour sources (names the file stores).
EYE_LIMBUS_LEVELS = (0, 1, 2, 3)
EYE_COLOUR_SOURCES = ("shader", "image")


def _finite(value, what: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{what}: expected a number, got {value!r}") from None
    if isinstance(value, bool) or not math.isfinite(number):
        raise ValueError(f"{what}: expected a finite number, got {value!r}")
    return number


#: Eye LookDev phase 4: where the iris relief's height comes from (`EyeIris.relief_source`).
EYE_RELIEF_SOURCES = ("luminance", "alpha")


@dataclass(frozen=True)
class EyeIris:
    """The iris's optional look values (Eye LookDev phase 4, assessment 2026-11-16 §C roadmap #4, #5, #7; Manu
    2026-11-16 "1 go (v11), 2 go"): the key light through the cornea, the relief, the pupil's edge. Data only,
    validated (`ValueError`); no default numbers in the Core (the app's are `mirai.eye_object.DEFAULT_IRIS`).

    The amounts (`light`, `crescent`, `rim_shadow`, `relief`, `pupil_edge_mm`, `pupil_margin`) are neutral at 0; the
    others only shape a term whose amount is above 0. `crescent` 1 = the cornea's focusing as computed, above 1
    exaggerated. `relief_source` "luminance": the height is derived from the iris image's brightness; "alpha": the
    image's alpha channel holds it. `*_mm` millimetres at the reference eye (sclera radius 12 mm)."""

    light: float
    crescent: float
    rim_shadow: float
    rim_shadow_mm: float
    relief: float
    relief_mm: float
    relief_source: str
    pupil_edge_mm: float
    pupil_margin: float

    def __post_init__(self) -> None:
        put = lambda name, value: object.__setattr__(self, name, value)  # noqa: E731
        for name in ("light", "crescent", "rim_shadow", "rim_shadow_mm", "relief", "relief_mm", "pupil_edge_mm",
                     "pupil_margin"):
            put(name, _finite(getattr(self, name), name))
        for name in ("light", "rim_shadow", "relief", "pupil_margin"):
            if not 0.0 <= getattr(self, name) <= 1.0:
                raise ValueError(f"{name}: needs 0 <= a <= 1, got {getattr(self, name)}")
        if not 0.0 <= self.crescent <= 2.0:
            raise ValueError(f"crescent: needs 0 <= c <= 2, got {self.crescent}")
        if not 0.0 <= self.pupil_edge_mm <= 2.0:
            raise ValueError(f"pupil_edge_mm: needs 0 <= w <= 2, got {self.pupil_edge_mm}")
        if not 0.0 < self.rim_shadow_mm or not 0.0 < self.relief_mm:
            raise ValueError("rim_shadow_mm / relief_mm: need > 0")
        if self.relief_source not in EYE_RELIEF_SOURCES:
            raise ValueError(f"relief_source: one of {EYE_RELIEF_SOURCES}, got {self.relief_source!r}")

    def to_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}

    @classmethod
    def from_dict(cls, raw: dict) -> "EyeIris":
        if not isinstance(raw, dict):
            raise ValueError(f"eye iris: expected an object, got {raw!r}")
        names = [f.name for f in fields(cls)]
        missing = [n for n in names if n not in raw]
        unknown = sorted(set(raw) - set(names))
        if missing or unknown:
            raise ValueError(f"eye iris: missing {missing}, unknown {unknown}")
        return cls(**{n: raw[n] for n in names})


@dataclass(frozen=True)
class EyeLook:
    """The eye's optional look values (Eye LookDev phase 3, assessment 2026-11-16 §D change 1; Manu I-5 "Core Change
    erlaubt", I-8, I-10): the wet film's reflection on cornea and sclera and the lid's effect on the eyeball. Data only,
    validated (`ValueError`); no default numbers in the Core (the app's are `mirai.eye_object.DEFAULT_LOOK`).

    The five amounts (`wet_sclera`, `irregularity_deg`, `highlight_softness`, `lid_shadow`, `lid_band`) are neutral at 0;
    the other values only shape a term whose amount is above 0. Heights are eye-local in the eye's rest frame (1 = the
    sclera radius, +Y up), `*_mm` millimetres at the reference eye (sclera radius 12 mm). `seed` picks the irregularity
    pattern (the app mixes it with the object, so two eyes never share one). `iris` (Eye LookDev phase 4, scene format
    v11) is the optional `EyeIris`; `None` = neutral, the iris as before phase 4."""

    wet_sclera: float
    sclera_roughness: float
    irregularity_deg: float
    irregularity_mm: float
    seed: int
    highlight_softness: float
    lid_shadow: float
    lid_shadow_mm: float
    lid_band: float
    lid_upper: float
    lid_lower: float
    iris: EyeIris | None = None

    def __post_init__(self) -> None:
        put = lambda name, value: object.__setattr__(self, name, value)  # noqa: E731
        if self.iris is not None and not isinstance(self.iris, EyeIris):
            raise ValueError(f"iris: expected an EyeIris or None, got {self.iris!r}")
        for name in ("wet_sclera", "sclera_roughness", "irregularity_deg", "irregularity_mm", "highlight_softness",
                     "lid_shadow", "lid_shadow_mm", "lid_band", "lid_upper", "lid_lower"):
            put(name, _finite(getattr(self, name), name))
        for name in ("wet_sclera", "highlight_softness", "lid_shadow", "lid_band"):
            if not 0.0 <= getattr(self, name) <= 1.0:
                raise ValueError(f"{name}: needs 0 <= a <= 1, got {getattr(self, name)}")
        if not 0.0 < self.sclera_roughness <= 1.0:
            raise ValueError(f"sclera_roughness: needs 0 < r <= 1, got {self.sclera_roughness}")
        if not 0.0 <= self.irregularity_deg <= 10.0:
            raise ValueError(f"irregularity_deg: needs 0 <= d <= 10, got {self.irregularity_deg}")
        if not 0.0 < self.irregularity_mm or not 0.0 < self.lid_shadow_mm:
            raise ValueError("irregularity_mm / lid_shadow_mm: need > 0")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or not 0 <= self.seed < 2 ** 31:
            raise ValueError(f"seed: expected an integer 0 <= s < 2**31, got {self.seed!r}")
        if not -1.0 < self.lid_lower < self.lid_upper < 1.0:
            raise ValueError(f"lid_lower / lid_upper: need -1 < lower < upper < 1, got {self.lid_lower}, {self.lid_upper}")

    def to_dict(self) -> dict:
        out = {f.name: getattr(self, f.name) for f in fields(self) if f.name != "iris"}
        return out | ({} if self.iris is None else {"iris": self.iris.to_dict()})  # absent = neutral: v10 looks stay

    @classmethod
    def from_dict(cls, raw: dict) -> "EyeLook":
        if not isinstance(raw, dict):
            raise ValueError(f"eye look: expected an object, got {raw!r}")
        names = [f.name for f in fields(cls) if f.name != "iris"]
        missing = [n for n in names if n not in raw]
        unknown = sorted(set(raw) - set(names) - {"iris"})
        if missing or unknown:
            raise ValueError(f"eye look: missing {missing}, unknown {unknown}")
        iris = raw.get("iris")
        return cls(**{n: raw[n] for n in names}, iris=None if iris is None else EyeIris.from_dict(iris))


@dataclass(frozen=True)
class EyeSpec:
    """A parametric eye (AD-033 §4.1): the object is an eyeball whose shell mesh `src/mirai` generates from these values
    and which the viewport shades as an eye. Data only, validated (`ValueError`); no default numbers in the Core (the
    app's defaults live in `src/mirai/eye_object.py`), `None` at the object = not an eye.

    Eye-local units: 1 = the sclera radius; the eye looks down +Z. `*_mm` values are millimetres at the reference eye
    (sclera radius 12 mm) and scale with the eye. The iris image is the object's `texture` (AD-026); `fit_pupil` /
    `fit_limbus` say where the image's own pupil edge / iris edge lie (shares of half the image width; both None = the
    planar mapping), `hold_outer_color` holds the iris-edge colour beyond the limbus. `look` (Eye LookDev phase 3, scene
    format v10) is the optional `EyeLook`; `None` = neutral, the eye as before phase 3. `sclera_texture` (AD-035 M1,
    scene format v12) is the optional path of the sclera's colour map - a plain string like `SceneObject.texture`, whose
    meaning (scene-relative on disk, the image's layout) `src/mirai` decides; `None` = no map, the sclera's base colour."""

    cornea_radius: float
    limbus_radius: float
    iris_root_z: float
    iris_concavity: float
    pupil_radius: float
    fit_pupil: float | None
    fit_limbus: float | None
    hold_outer_color: bool
    limbus_level: int
    colour_source: str
    limbal_colour: Vec3
    band_mm: float
    strength: float
    normal_mm: float
    falloff: float
    overlap_mm: float
    asymmetry: bool
    look: EyeLook | None = None
    sclera_texture: str | None = None

    def __post_init__(self) -> None:
        put = lambda name, value: object.__setattr__(self, name, value)  # noqa: E731
        if self.look is not None and not isinstance(self.look, EyeLook):
            raise ValueError(f"look: expected an EyeLook or None, got {self.look!r}")
        if self.sclera_texture is not None and (not isinstance(self.sclera_texture, str)
                                                or not self.sclera_texture.strip() or "\0" in self.sclera_texture):
            raise ValueError(f"sclera_texture: expected a non-empty path or None, got {self.sclera_texture!r}")
        for name in ("cornea_radius", "limbus_radius", "iris_root_z", "iris_concavity", "pupil_radius", "band_mm",
                     "strength", "normal_mm", "falloff", "overlap_mm"):
            put(name, _finite(getattr(self, name), name))
        if not 0.0 < self.limbus_radius < 1.0:
            raise ValueError(f"limbus_radius: needs 0 < r < 1 (the sclera radius), got {self.limbus_radius}")
        if not self.limbus_radius < self.cornea_radius:
            raise ValueError("cornea_radius: the cornea sphere must be larger than the limbus circle")
        limbus_z = math.sqrt(1.0 - self.limbus_radius ** 2)
        if not 0.0 < self.iris_root_z < limbus_z:
            raise ValueError(f"iris_root_z: needs 0 < z < {limbus_z:.6g} (behind the limbus plane), got {self.iris_root_z}")
        iris_radius = math.sqrt(1.0 - self.iris_root_z ** 2)
        if not 0.0 <= self.iris_concavity < self.iris_root_z:
            raise ValueError(f"iris_concavity: needs 0 <= c < iris_root_z, got {self.iris_concavity}")
        if not 0.0 < self.pupil_radius < min(self.limbus_radius, iris_radius):
            raise ValueError(f"pupil_radius: needs 0 < r < the limbus / iris radius, got {self.pupil_radius}")
        if (self.fit_pupil is None) != (self.fit_limbus is None):
            raise ValueError("fit_pupil / fit_limbus: both or neither")
        if self.fit_pupil is not None:
            put("fit_pupil", _finite(self.fit_pupil, "fit_pupil"))
            put("fit_limbus", _finite(self.fit_limbus, "fit_limbus"))
            if not 0.0 < self.fit_pupil < self.fit_limbus <= 1.0:
                raise ValueError("fit_pupil / fit_limbus: needs 0 < pupil < limbus <= 1")
        if not isinstance(self.hold_outer_color, bool) or not isinstance(self.asymmetry, bool):
            raise ValueError("hold_outer_color / asymmetry: expected true or false")
        if isinstance(self.limbus_level, bool) or self.limbus_level not in EYE_LIMBUS_LEVELS:
            raise ValueError(f"limbus_level: one of {EYE_LIMBUS_LEVELS}, got {self.limbus_level!r}")
        if self.colour_source not in EYE_COLOUR_SOURCES:
            raise ValueError(f"colour_source: one of {EYE_COLOUR_SOURCES}, got {self.colour_source!r}")
        colour = _vec3(self.limbal_colour, "limbal_colour")
        put("limbal_colour", tuple(_unit(c, "limbal_colour") for c in colour))
        if not 0.0 < self.band_mm or not 0.0 < self.normal_mm or not 0.0 < self.falloff:
            raise ValueError("band_mm / normal_mm / falloff: need > 0")
        if not 0.0 <= self.strength <= 1.0:
            raise ValueError(f"strength: needs 0 <= s <= 1, got {self.strength}")
        if not 0.0 <= self.overlap_mm:
            raise ValueError(f"overlap_mm: needs >= 0, got {self.overlap_mm}")

    def to_dict(self) -> dict:
        return {
            "cornea_radius": self.cornea_radius, "limbus_radius": self.limbus_radius, "iris_root_z": self.iris_root_z,
            "iris_concavity": self.iris_concavity, "pupil_radius": self.pupil_radius, "fit_pupil": self.fit_pupil,
            "fit_limbus": self.fit_limbus, "hold_outer_color": self.hold_outer_color,
            "limbus_level": self.limbus_level, "colour_source": self.colour_source,
            "limbal_colour": list(self.limbal_colour), "band_mm": self.band_mm, "strength": self.strength,
            "normal_mm": self.normal_mm, "falloff": self.falloff, "overlap_mm": self.overlap_mm,
            "asymmetry": self.asymmetry,
        } | ({} if self.look is None else {"look": self.look.to_dict()}) | (  # absent = neutral: v9 eyes as they were
            {} if self.sclera_texture is None else {"sclera_texture": self.sclera_texture})  # absent = none (v9-v11)

    #: The optional keys (absent in a file = None): the look (v10) and the sclera map (v12).
    _OPTIONAL = ("look", "sclera_texture")

    @classmethod
    def from_dict(cls, raw: dict) -> "EyeSpec":
        if not isinstance(raw, dict):
            raise ValueError(f"eye: expected an object, got {raw!r}")
        names = [f.name for f in fields(cls) if f.name not in cls._OPTIONAL]
        missing = [n for n in names if n not in raw]
        unknown = sorted(set(raw) - set(names) - set(cls._OPTIONAL))
        if missing or unknown:
            raise ValueError(f"eye: missing {missing}, unknown {unknown}")
        look = raw.get("look")
        return cls(**{n: raw[n] for n in names}, look=None if look is None else EyeLook.from_dict(look),
                   sclera_texture=raw.get("sclera_texture"))


#: AD-037 §3: the blend modes a paint layer may name (the file stores the name). Phase 1: Normal only; Phase 3 adds
#: Multiply (P-12, Manu 2026-11-19: "Normal + Multiply"). A build that knows fewer modes refuses a file naming another.
PAINT_BLEND_MODES = ("normal", "multiply")
#: AD-037 §3: the largest paint-stack side in pixels (4096² is already "not on the reference PC", audit P-5).
PAINT_MAX_SIZE = 8192


def _clean_text(value: object, what: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\0" in value:
        raise ValueError(f"{what}: expected a non-empty text, got {value!r}")
    return value


@dataclass(frozen=True)
class PaintLayer:
    """One paint layer of an object's paint stack (AD-037 §3): its name, the image that holds its RGBA pixels, how it
    is composited. Data only. `image` is a plain path string like `SceneObject.texture` (its meaning - scene-relative
    on disk, the pixel layout - is `src/mirai`'s); `None` = a fully transparent layer that has no file yet. `opacity`
    in [0, 1]; `blend` one of `PAINT_BLEND_MODES`."""

    name: str
    image: str | None
    opacity: float = 1.0
    visible: bool = True
    blend: str = "normal"

    def __post_init__(self) -> None:
        _clean_text(self.name, "paint layer name")
        if self.image is not None:
            _clean_text(self.image, "paint layer image")
        if isinstance(self.opacity, bool) or not isinstance(self.opacity, (int, float)):
            raise ValueError(f"paint layer opacity: expected a number, got {self.opacity!r}")
        object.__setattr__(self, "opacity", _unit(self.opacity, "paint layer opacity"))
        if not isinstance(self.visible, bool):
            raise ValueError(f"paint layer visible: expected true or false, got {self.visible!r}")
        if self.blend not in PAINT_BLEND_MODES:
            raise ValueError(f"paint layer blend: one of {PAINT_BLEND_MODES}, got {self.blend!r}")

    def to_dict(self) -> dict:
        return {"name": self.name, "image": self.image, "opacity": self.opacity, "visible": self.visible,
                "blend": self.blend}

    @classmethod
    def from_dict(cls, raw: dict) -> "PaintLayer":
        names = [f.name for f in fields(cls)]
        if not isinstance(raw, dict) or set(raw) != set(names):
            raise ValueError(f"paint layer: expected exactly {names}, got {raw!r}")
        return cls(**raw)


@dataclass(frozen=True)
class PaintStack:
    """The paint of one object (AD-037 §3, audit 2026-11-18 P-1 / P-3 / P-4): layers painted in UV space, bottom to
    top, at one resolution (`width` x `height` pixels). The object's own `texture` stays untouched beneath them as the
    base (P-4); without a texture the base is the object's base colour. Data only: no pixels, no defaults - `None` at
    the object = no paint. Layer names are unique; at least one layer."""

    width: int
    height: int
    layers: tuple[PaintLayer, ...]

    def __post_init__(self) -> None:
        for name in ("width", "height"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= PAINT_MAX_SIZE:
                raise ValueError(f"paint {name}: expected an integer in 1..{PAINT_MAX_SIZE}, got {value!r}")
        layers = tuple(self.layers)
        if not layers or not all(isinstance(layer, PaintLayer) for layer in layers):
            raise ValueError(f"paint layers: expected one or more PaintLayer values, got {self.layers!r}")
        if len({layer.name for layer in layers}) != len(layers):
            raise ValueError(f"paint layers: names must be unique, got {[layer.name for layer in layers]}")
        object.__setattr__(self, "layers", layers)

    def to_dict(self) -> dict:
        return {"width": self.width, "height": self.height, "layers": [layer.to_dict() for layer in self.layers]}

    @classmethod
    def from_dict(cls, raw: dict) -> "PaintStack":
        if not isinstance(raw, dict) or set(raw) != {"width", "height", "layers"}:
            raise ValueError(f"paint: expected exactly width, height, layers, got {raw!r}")
        if not isinstance(raw["layers"], list):
            raise ValueError(f"paint layers: expected a list, got {raw['layers']!r}")
        return cls(raw["width"], raw["height"], tuple(PaintLayer.from_dict(layer) for layer in raw["layers"]))


#: AD-038 §18 (LD-2): where a LookDev material takes its albedo - the object's shown texture or paint composite
#: (`texture`), or its colour (`color`). The file stores the name.
LOOK_ALBEDO_SOURCES = ("texture", "color")


def _look_unit(value: object, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise ValueError(f"look {what}: expected a number, got {value!r}")
    return _unit(value, f"look {what}")


def _look_colour(value: object, what: str) -> Vec3:
    if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
        raise ValueError(f"look {what}: expected three numbers, got {value!r}")
    values = tuple(value)
    if len(values) != 3:
        raise ValueError(f"look {what}: expected three numbers, got {value!r}")
    return tuple(_look_unit(c, what) for c in values)  # type: ignore[return-value]


@dataclass(frozen=True)
class LookMaterial:
    """The organic LookDev material of one object (AD-038 §7 / §18, LD-2; proposal §4): data only. `preset` names the
    preset it started from (free text: the presets are `src/mirai`'s data and may be renamed), `base_color` an sRGB
    artist colour, `albedo_source` one of `LOOK_ALBEDO_SOURCES`, `roughness` perceptual, `specular` the level (F0 is
    `src/mirai`'s / `src/viewport`'s business), `wrap` with its per-channel `wrap_tint`, `backscatter` with its colour,
    `adjusted` = a value changed after the preset was picked. Every number in [0, 1]; invalid values are refused, not
    clamped. `None` at the object = no LookDev material (the room draws its Neutral fallback). Independent of
    `ObjectMaterial`, the Worklight material (nothing is mapped between them, proposal §4.3)."""

    preset: str
    base_color: Vec3
    albedo_source: str = "texture"
    roughness: float = 0.6
    specular: float = 0.5
    wrap: float = 0.0
    wrap_tint: Vec3 = (1.0, 1.0, 1.0)
    backscatter: float = 0.0
    backscatter_color: Vec3 = (1.0, 1.0, 1.0)
    adjusted: bool = False

    def __post_init__(self) -> None:
        _clean_text(self.preset, "look preset")
        if self.albedo_source not in LOOK_ALBEDO_SOURCES:
            raise ValueError(f"look albedo_source: one of {LOOK_ALBEDO_SOURCES}, got {self.albedo_source!r}")
        for name in ("roughness", "specular", "wrap", "backscatter"):
            object.__setattr__(self, name, _look_unit(getattr(self, name), name))
        for name in ("base_color", "wrap_tint", "backscatter_color"):
            object.__setattr__(self, name, _look_colour(getattr(self, name), name))
        if not isinstance(self.adjusted, bool):
            raise ValueError(f"look adjusted: expected true or false, got {self.adjusted!r}")

    def to_dict(self) -> dict:
        out = {f.name: getattr(self, f.name) for f in fields(self)}
        for name in ("base_color", "wrap_tint", "backscatter_color"):
            out[name] = list(out[name])
        return out

    @classmethod
    def from_dict(cls, raw: dict) -> "LookMaterial":
        names = [f.name for f in fields(cls)]
        if not isinstance(raw, dict) or set(raw) != set(names):
            raise ValueError(f"look: expected exactly {names}, got {raw!r}")
        for name in ("base_color", "wrap_tint", "backscatter_color"):
            if not isinstance(raw[name], list):
                raise ValueError(f"look {name}: expected a list of three numbers, got {raw[name]!r}")
        return cls(**raw)


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


def _require_link_bone(bone: object) -> BoneId:
    # As `_require_object_id`: a link is never derived from another id kind, hence the type; ids are never negative.
    if not isinstance(bone, BoneId):
        raise TypeError(f"erwartet eine BoneId oder None, nicht {bone!r}")
    if int(bone) < 0:
        raise ValueError(f"BoneId negativ: {int(bone)}")
    return bone


class SceneObject:
    """Scene-Mitglied, das genau ein Mesh besitzt und in der Scene platziert (AD-021 §4.1).

    Das Mesh weiß nichts von seinem Objekt (kein Rückverweis). Mesh-Positionen
    sind Objektraum-Koordinaten. Die ID ist unveränderlich; alles andere sind
    einfache Werte, die künftige Objekt-Commands (M1/M2) ändern.
    """

    __slots__ = ("_id", "mesh", "name", "transform", "pivot", "state", "material", "texture", "hidden", "parent", "eye",
                 "bone", "paint", "look")

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
        texture: str | None = None,
        hidden: bool = False,
        parent: ObjectId | None = None,
        eye: EyeSpec | None = None,
        bone: BoneId | None = None,
        paint: PaintStack | None = None,
        look: LookMaterial | None = None,
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
        # AD-026: Pfad der Textur (None = keine); eine Textur pro Objekt, also pro Mesh.
        if texture is not None and not (isinstance(texture, str) and texture):
            raise TypeError(f"erwartet einen nicht leeren Pfad oder None, nicht {texture!r}")
        self.texture: str | None = texture
        # Outliner (2026-11-07): `hidden` = nicht gezeichnet, nicht pickbar (Ansicht, aber mit der Datei
        # gespeichert); `parent` = die Gruppe, in der das Objekt hängt (None = oberste Ebene). Beides ändern
        # nur Commands in `src/mirai`; `Scene.set_parent` prüft Gruppe und Zyklen.
        self.hidden: bool = bool(hidden)
        self.parent: ObjectId | None = None if parent is None else _require_object_id(parent)
        # AD-033: None = not an eye; else the eye's values (its shell mesh is generated from them in `src/mirai`).
        if eye is not None and not isinstance(eye, EyeSpec):
            raise TypeError(f"erwartet ein EyeSpec oder None, nicht {eye!r}")
        self.eye: EyeSpec | None = eye
        # AD-036 §4.1: the bone this object follows as a rigid part (None = none). Data only: whether the rig has the
        # bone (a dead link follows nothing) and what following means live in `src/mirai` (`mirai.bone_links`).
        self.bone: BoneId | None = None if bone is None else _require_link_bone(bone)
        # AD-037 §3: None = no paint; else the paint layers above `texture` (data only, the pixels live in `src/mirai`).
        if paint is not None and not isinstance(paint, PaintStack):
            raise TypeError(f"erwartet ein PaintStack oder None, nicht {paint!r}")
        self.paint: PaintStack | None = paint
        # AD-038 §18 (LD-2): None = no LookDev material (the room's Neutral fallback); else the object's organic look.
        if look is not None and not isinstance(look, LookMaterial):
            raise TypeError(f"erwartet ein LookMaterial oder None, nicht {look!r}")
        self.look: LookMaterial | None = look

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
        # Implementierung. `rig` ist seit AD-028 ein geprüfter Wert (Property unten).
        self.morph_targets = None
        self._rig: Rig | None = None
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
        _check_hierarchy(loaded, edit_object_id)
        scene._object_ids = IdAllocator(ObjectId, start=object_id_counter)
        scene._objects = dict(sorted(loaded.items()))
        scene._edit_object_id = edit_object_id
        for pair in mirror_pairs:
            scene.add_mirror_pair(pair)
        return scene

    # ------------------------------------------------------------------
    # Rig (AD-028 §3.1)
    # ------------------------------------------------------------------

    @property
    def rig(self) -> Rig | None:
        """Die Knochen der Scene (ein Rig für alle Objekte, AD-021 §4.9) oder None."""
        return self._rig

    @rig.setter
    def rig(self, rig: Rig | None) -> None:
        if rig is not None and not isinstance(rig, Rig):
            raise TypeError(f"erwartet ein Rig oder None, nicht {rig!r}")
        self._rig = rig

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
        texture: str | None = None,
        parent: ObjectId | None = None,
    ) -> SceneObject:
        """Neues Objekt mit frischer, nie wiederverwendeter ObjectId. `parent` = eine Gruppe der Scene."""
        if parent is not None:
            self._require_group(parent)
        obj = SceneObject(self._object_ids.allocate(), mesh, name=name, state=state, texture=texture, parent=parent)
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
        if self.children_of(object_id):
            # Wie das Paar: ein Kind zeigt nie auf eine fehlende Gruppe - erst die Mitglieder entfernen/umhängen.
            raise ValueError(f"Objekt {int(object_id)} hat Mitglieder - erst diese entfernen oder umhängen")
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
    # Gruppen (Outliner, 2026-11-07)
    # ------------------------------------------------------------------

    def _require_group(self, object_id: ObjectId) -> SceneObject:
        group = self._objects.get(_require_object_id(object_id))
        if group is None:
            raise ValueError(f"Gruppe {int(object_id)} ist nicht in der Scene")
        if group.state is not ObjectState.GROUP:
            raise ValueError(f"Objekt {int(object_id)} ist keine Gruppe")
        return group

    def children_of(self, object_id: ObjectId) -> tuple[SceneObject, ...]:
        """Die direkten Mitglieder einer Gruppe, nach ID."""
        return tuple(obj for obj in self._objects.values() if obj.parent == object_id)

    def descendants_of(self, object_id: ObjectId) -> tuple[SceneObject, ...]:
        """Alle Mitglieder, auch verschachtelte; Eltern vor ihren Kindern (Tiefensuche)."""
        found: list[SceneObject] = []
        stack = list(reversed(self.children_of(object_id)))
        while stack:
            obj = stack.pop()
            found.append(obj)
            stack.extend(reversed(self.children_of(obj.id)))
        return tuple(found)

    def ancestors_of(self, object_id: ObjectId) -> tuple[SceneObject, ...]:
        """Die Gruppen über dem Objekt, die nächste zuerst."""
        found: list[SceneObject] = []
        parent = self._objects[object_id].parent
        while parent is not None and parent in self._objects and len(found) <= len(self._objects):
            group = self._objects[parent]
            found.append(group)
            parent = group.parent
        return tuple(found)

    def is_hidden(self, object_id: ObjectId) -> bool:
        """Ausgeblendet: das Objekt selbst oder eine seiner Gruppen."""
        obj = self._objects[object_id]
        return obj.hidden or any(group.hidden for group in self.ancestors_of(object_id))

    def set_parent(self, object_id: ObjectId, parent: ObjectId | None) -> None:
        """Hängt ein Objekt in eine Gruppe (None = oberste Ebene). `ValueError` bei fehlender/Nicht-Gruppe
        und bei einem Zyklus (die Gruppe selbst oder eines ihrer Mitglieder als Ziel). Ändert nur den Verweis;
        Undo ist Sache des Commands."""
        obj = self._objects[_require_object_id(object_id)]
        if parent is not None:
            self._require_group(parent)
            if parent == object_id or any(d.id == parent for d in self.descendants_of(object_id)):
                raise ValueError(f"Zyklus: {int(parent)} liegt in {int(object_id)}")
        obj.parent = parent

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
        if self._objects[object_id].state is ObjectState.GROUP:
            raise ValueError(f"Eine Gruppe ({int(object_id)}) kann nicht Edit-Objekt sein")
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


def _check_hierarchy(objects: Mapping[ObjectId, SceneObject], edit_object_id: ObjectId) -> None:
    """Gruppen-Invarianten einer geladenen Objektmenge: jedes `parent` ist eine Gruppe der Datei, keine Kette
    läuft im Kreis, das Edit-Objekt ist keine Gruppe und nicht ausgeblendet (auch nicht über eine Gruppe)."""
    for obj in objects.values():
        seen = {obj.id}
        parent = obj.parent
        while parent is not None:
            group = objects.get(parent)
            if group is None:
                raise ValueError(f"Objekt {int(obj.id)}: Gruppe {int(parent)} fehlt")
            if group.state is not ObjectState.GROUP:
                raise ValueError(f"Objekt {int(obj.id)}: {int(parent)} ist keine Gruppe")
            if parent in seen:
                raise ValueError(f"Objekt {int(obj.id)}: Gruppen im Kreis")
            seen.add(parent)
            parent = group.parent
    edit = objects[edit_object_id]
    if edit.state is ObjectState.GROUP:
        raise ValueError(f"Edit-Objekt {int(edit_object_id)} ist eine Gruppe")
    chain = [edit]
    parent = edit.parent
    while parent is not None:
        chain.append(objects[parent])
        parent = objects[parent].parent
    if any(obj.hidden for obj in chain):
        raise ValueError(f"Edit-Objekt {int(edit_object_id)} ist ausgeblendet")
