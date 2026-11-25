"""The LookDev panel's logic (AD-038 §7; AD-030: pure logic headless, `lookdev_panel` only draws).

The panel reads the room's state (`state(app)`) and calls `Application` (`set_lookdev_studio_preset`,
`set_lookdev_studio`, `set_lookdev_light`, `set_lookdev_material`, `set_lookdev_material_values`, `frame_lookdev`,
`close_lookdev`, `preview_lookdev_material_values`, `reset_lookdev_material`, `save_lookdev_image`,
`set_lookdev_effect`, AD-039 S7 `set_lookdev_map`, S6 `set_lookdev_area` / `move_lookdev_region`, AD-040
`set_lookdev_quality`); it holds no document state. AD-040 §8.1: the block „Qualität“ (`QualityRow`) - a machine setting,
not the scene's. AD-039 S6: the material block edits a „Bereich“ - „Ganzes Objekt“ or one face region of the targets
(`AreaRow`; its own material saved on the object, the maps stay the object's). Since LD-2 (AD-038 §18) the material
is document data (`SceneObject.look`, saved, one Undo step per change: a
held slider or colour previews, the release commits - `MaterialEdit`); the studio is view state saved in
`view.lookdev` (no Undo). About 15 controls are visible; the rest sits under "Mehr". Labels German, every layout choice
`PROVISIONAL` (proposal §3).
"""

from __future__ import annotations

from dataclasses import dataclass

from mirai import look_maps
from mirai.lookdev_material import PRESET_NAMES as MATERIAL_PRESETS
from mirai.lookdev_presets import PRESET_NAMES as STUDIO_PRESETS

#: The window's title and the SPACE menu row (no key, D-L9).
TITLE = "LookDev"
MENU_OPEN = "LookDev öffnen"
MENU_CLOSE = "LookDev schließen"
SAVED = "Material und Studio werden mit der Szene gespeichert"
SAVE_IMAGE = "Bild speichern"
SAVE_IMAGE_HINT = "PNG der LookDev-Ansicht ohne Overlays (Fenstergröße) - kein Render-Export"
RESET = "Zurücksetzen"
RESET_HINT = "kein LookDev-Material: das Objekt zeigt wieder Neutral"
EYE_NOTE = "Auge - Werte im Panel „Auge“"
LIGHTS = ("key", "fill", "rim")
LIGHT_LABELS = {"key": "Key", "fill": "Fill", "rim": "Rim"}
TONE_LABELS = {"reinhard": "Neutral", "clamp": "Clamp (Diagnose)"}
#: Front / ¾ / Profil: (yaw, pitch) in degrees after framing the edit object.
VIEWS = {"Front": (0.0, 5.0), "¾": (35.0, 8.0), "Profil": (90.0, 5.0)}


@dataclass(frozen=True)
class LightRow:
    name: str
    label: str
    on: bool
    intensity: float
    azimuth: float
    elevation: float
    kelvin: float
    size: float


#: AD-039 §2.1: the block „Effekte“ - one checkbox per built P3 effect, in slice order.
EFFECTS_TITLE = "Effekte"
EFFECT_LABELS = {"shadow": "Schatten", "eye_shadow": "Augen-Schatten", "dual_lobe": "Doppel-Glanz",
                 "thickness": "Durchleuchtung", "cube": "Umgebungs-Cube", "regions": "Region-Materialien",
                 "maps": "Maps", "area_diffuse": "Weiches Licht", "soft_shadow": "Weicher Schatten"}
EFFECT_HINTS = {"shadow": "Schatten des Key auf Haut und Zähnen (wird nur bei Pose-, Form- oder Key-Änderung neu "
                          "gerechnet); „Weichheit“ des Key macht die Kante weicher",
                "eye_shadow": "Lider, Brauen und Nase werfen den Schatten des Key auf die Augen (braucht "
                              "„Schatten“); die Lid-Abdunklung im Panel „Auge“ bleibt",
                "dual_lobe": "Glanz der Haut aus zwei Anteilen: eine schärfere Spitze und ein weicher Saum (Lichter "
                             "Key, Fill, Rim; mit „Umgebungs-Cube“ auch die Studio-Spiegelung)",
                "thickness": "Licht des Key scheint durch dünne Stellen (Ohren, Nasenflügel), wenn der Key von hinten "
                             "kommt; Stärke und Farbe aus „Backscatter“ des Materials (braucht „Schatten“)",
                "cube": "Spiegelung des Studios auf der Haut aus einer vorgefilterten Umgebung (genauer bei rauen "
                        "Materialien, schneller); wird nur bei einem Studio-Wechsel neu berechnet. Die Augen bleiben "
                        "beim analytischen Studio",
                "regions": "Eigene Materialien für Regionen (Polygroups) des Objekts, z. B. Mundinneres (wählen unter "
                           "„Bereich“ im Block Material); aus = ein Material je Objekt",
                "maps": "Rauheit-, Normal- und Durchscheinen-Maps der Materialien (laden unter „Mehr“ im Block "
                        "Material); aus = die Materialien ohne ihre Maps",
                "area_diffuse": "„Weichheit“ des Lichts macht auch den Übergang ins Dunkle weicher",
                "soft_shadow": "Schlagschatten des Key werden mit dem Abstand zum Werfer weicher (am besten zusammen "
                               "mit „Weiches Licht“; braucht Schatten; kostet Bildrate)"}

#: AD-040 §8.1 (LD-3a): the block „Qualität“ below „Effekte“ - a machine setting (`~/.mirai_bastel`), no keys.
QUALITY_TITLE = "Qualität"
QUALITY_TIER = "Qualität (beim Arbeiten)"
QUALITY_REFINE = "In Ruhe verfeinern"
QUALITY_IDLE_TIER = "Ruhe-Qualität"
QUALITY_WAIT = "Wartezeit"
QUALITY_DRAG = "Schatten beim Ziehen"
QUALITY_HINTS = {
    "tier": "Was beim Drehen, Posen und Morphen gezeichnet wird. Auto misst die Grafikkarte und geht nur beim Arbeiten "
            "eine Stufe herunter (Ziel 12 ms); ein ruhiges Bild wird nie wegen der Zeitmessung schlechter. "
            "Entwurf: ohne Schatten, Doppel-Glanz, Durchleuchtung und Weiches Licht; Mittel: ohne Weicher Schatten",
    "refine": "Nach der Wartezeit ohne Änderung zeichnet der Raum die Ruhe-Qualität (Weicher Schatten nur dann). "
              "Wird auf diesem Rechner gespeichert, nicht in der Szene",
    "idle_tier": "Hoch: wie beim Arbeiten plus Weicher Schatten. Maximal: dazu Schattenkarte 2048² und eine genauer "
                 "gefilterte Umgebung (256 Samples) - kostet einen kurzen Moment beim ersten Mal",
    "wait": "So lange muss das Bild unverändert sein, bevor die Ruhe beginnt",
    "drag": "Schattenkarte, während eine Pose, ein Morph oder ein Sculpt-Strich das Modell ändert (Q-LD3-1, offen bis "
            "zum Referenz-PC-Lauf): eingefroren holt den Schatten beim Loslassen nach",
}
QUALITY_TIER_CHOICES = ("auto", "hoch", "mittel", "entwurf")
QUALITY_IDLE_CHOICES = ("hoch", "maximal")
QUALITY_TIER_LABELS = {"auto": "Auto", "hoch": "Hoch", "mittel": "Mittel", "entwurf": "Entwurf", "maximal": "Maximal"}
QUALITY_DRAG_CHOICES = ("every", "every_2nd", "frozen")
QUALITY_DRAG_LABELS = {"every": "jedes Frame", "every_2nd": "jedes 2. Frame", "frozen": "eingefroren"}


@dataclass(frozen=True)
class QualityRow:
    """The block „Qualität“: the machine setting's values and the status line („Interaktiv – Mittel (Auto: …)“)."""

    tier: str
    refine: bool
    idle_tier: str
    wait: float
    drag_updates: str
    status: str


#: AD-039 §10 (S7): the material's maps under „Mehr“ - one row per map: its file, „Laden …“, „Entfernen“.
MAPS_TITLE = "Maps (gespeichert)"
MAP_LABELS = look_maps.LABELS
MAP_LOAD = "Laden …"
MAP_REMOVE = "Entfernen"
MAPS_HINT = ("Bilder in den UVs des Objekts (z. B. aus ZBrush): Rauheit und Durchscheinen grau (weiß = Wert des "
             "Materials), Normal-Map im Tangentenraum. Höchstens 4096²; beim Speichern neben die Szene kopiert.")
NORMAL_STRENGTH = "Normal-Stärke"
NORMAL_GREEN_DOWN = "Grün unten (DirectX)"


#: AD-039 §9 (S6): the material block's „Bereich“ - the whole object or one face region of the targets.
AREA = "Bereich"
AREA_WHOLE = "Ganzes Objekt"
AREA_OWN = "eigenes Material"
AREA_MISSING = "Region fehlt"
AREA_UP = "nach oben"
AREA_DOWN = "nach unten"
AREA_HINT = ("Material für eine Region (Polygroup) des Objekts: Vorlage oder Werte wählen legt es an (höchstens 4 je "
             "Objekt). Bei Überlappung gewinnt die untere in der Liste. Maps gelten für das ganze Objekt.")
AREA_ORDER_HINT = "Reihenfolge der Region-Materialien: bei Überlappung gewinnt die untere"
AREA_RESET_HINT = "die Region zeigt wieder das Material des ganzen Objekts"


@dataclass(frozen=True)
class AreaRow:
    """One region the „Bereich“ offers: its name, whether a target has its own material for it (`own`) and whether no
    target's mesh has the region any more (`missing`: the entry is kept, not drawn)."""

    name: str
    own: bool
    missing: bool

    @property
    def label(self) -> str:
        notes = [note for note, on in ((AREA_OWN, self.own), (AREA_MISSING, self.missing)) if on]
        return self.name + (f" ({', '.join(notes)})" if notes else "")


@dataclass(frozen=True)
class MapRow:
    """One map of the first target's material: its kind, label, path (None = none) and the text the panel shows."""

    kind: str
    label: str
    path: str | None
    text: str


@dataclass(frozen=True)
class EffectRow:
    """One P3 effect: switched on, and why it is greyed (None = available)."""

    name: str
    label: str
    on: bool
    reason: str | None
    hint: str
    #: AD-040 §8.1: the quality configuration in force holds it back - where it is drawn („aktiv in: Hoch, Maximal“)
    held_back: str | None = None

    @property
    def available(self) -> bool:
        return self.reason is None

    @property
    def tooltip(self) -> str:
        if not self.available:
            return self.reason
        return self.hint + (f" – gerade zurückgehalten, {self.held_back}" if self.held_back else "")


@dataclass(frozen=True)
class MaterialRow:
    """The material section: the targets' names and the first target's material (None = no organic target)."""

    targets: tuple[str, ...]
    preset: str | None
    adjusted: bool
    base_color: tuple[float, float, float]
    albedo_source: str
    albedo_label: str
    roughness: float
    specular: float
    wrap: float
    backscatter: float
    backscatter_color: tuple[float, float, float]
    #: a selected eye: its values stay in the panel "Auge"
    eye_selected: bool
    #: a target has its own look (`SceneObject.look`); False = all draw the Neutral fallback ("Zurücksetzen" has nothing)
    has_look: bool = False
    #: AD-039 S7: the first target's maps (one row per kind) and the normal map's values
    maps: tuple[MapRow, ...] = ()
    normal_strength: float = 1.0
    normal_green_down: bool = False
    #: the first target has no UVs: maps are kept but not drawn
    no_uvs: bool = False
    #: AD-039 S6: the „Bereich“ (None = „Ganzes Objekt“; then `has_look` = the object's look, else the region's entry)
    area: str | None = None
    areas: tuple[AreaRow, ...] = ()


@dataclass(frozen=True)
class LookdevPanelState:
    open: bool
    preparing: bool
    studio_preset: str
    rotation: float
    env_intensity: float
    exposure: float
    tone_curve: str
    follow_camera: bool
    background: tuple[tuple[float, float, float], tuple[float, float, float]]
    background_gradient: bool
    lights: tuple[LightRow, ...]
    material: MaterialRow | None
    wire: bool
    eye_preview: bool
    status: str
    effects: tuple[EffectRow, ...] = ()
    quality: QualityRow | None = None


def _albedo_label(app, obj) -> str:
    if app.paint_display.shows(obj):
        return "Bemalung"
    return "Textur" if obj.texture is not None else "Textur (keine)"


def _material(app) -> MaterialRow | None:
    room = app.lookdev
    targets = app.lookdev_material_targets()
    eye_selected = app.lookdev_eye_selected()
    if not targets:
        return None if not eye_selected else MaterialRow((), None, False, (0.5, 0.5, 0.5), "color", "", 0.0, 0.0,
                                                         0.0, 0.0, (1.0, 1.0, 1.0), True)
    area = room.area
    areas = tuple(AreaRow(*choice) for choice in app.lookdev_area_choices())
    if area is not None and area not in [a.name for a in areas]:
        areas += (AreaRow(area, False, True),)
    if area is not None:  # AD-039 §9: the targets of the region (the first of them shows its values)
        targets = [obj for obj in targets if room.has_region(obj, area) or room.region_entry(obj, area) is not None] \
            or targets
    first = targets[0]
    m = room.area_material(first)
    maps = room.material(first).maps  # the maps are the object's (one UV layout), shown in „Ganzes Objekt“
    rows = tuple(MapRow(kind, MAP_LABELS[kind], getattr(maps, kind) if maps else None,
                        look_maps.status_text(getattr(maps, kind) if maps else None)) for kind in look_maps.KINDS)
    has_look = any(obj.look is not None for obj in targets) if area is None else \
        any(room.region_entry(obj, area) is not None for obj in targets)
    return MaterialRow(tuple(obj.name for obj in targets), m.preset, m.adjusted, m.base_color, m.albedo_source,
                       _albedo_label(app, first), m.roughness, m.specular, m.wrap, m.backscatter, m.backscatter_color,
                       eye_selected, has_look, rows if area is None else (),
                       maps.normal_strength if maps else 1.0, maps.normal_green_down if maps else False,
                       not first.mesh.has_face_uvs(), area, areas)


def _effects(app, s) -> tuple[EffectRow, ...]:
    reasons = app.lookdev_effect_reasons()
    held = app.lookdev_effect_tiers()
    return tuple(EffectRow(name, EFFECT_LABELS.get(name, name), bool(on), reasons.get(name), EFFECT_HINTS.get(name, ""),
                           held.get(name))
                 for name, on in s.effects.as_dict().items())


def _quality(app) -> QualityRow:
    q = app.lookdev_quality
    return QualityRow(q.tier, q.refine, q.idle_tier, q.wait, q.drag_updates, app.lookdev_quality_status())


def state(app) -> LookdevPanelState:
    room = app.lookdev
    s = room.studio
    lights = tuple(LightRow(name, LIGHT_LABELS[name], light.on, light.intensity, light.azimuth, light.elevation,
                            light.kelvin, light.size) for name, light in zip(LIGHTS, s.lights()))
    return LookdevPanelState(
        open=app.lookdev_open, preparing=bool(room.preparing), studio_preset=s.preset, rotation=s.rotation,
        env_intensity=s.env_intensity, exposure=s.exposure, tone_curve=s.tone_curve, follow_camera=s.follow_camera,
        background=s.background, background_gradient=s.background_gradient, lights=lights,
        material=_material(app) if app.lookdev_open else None, wire=app.display.wireframe_overlay,
        eye_preview=app.display.eye_preview,
        status="Shader werden vorbereitet …" if room.preparing else SAVED, effects=_effects(app, s),
        quality=_quality(app),
    )


class MaterialEdit:
    """A held material control (AD-038 §7 / §18): `hold` previews the values (no Undo step), `release` commits them all
    as one step. The panel releases when no control is active and the mouse is up, so a slider drag and a colour
    picker's drag are each one step. A preview the application already ended (the room closed, a preset was picked)
    is dropped, never committed late."""

    def __init__(self) -> None:
        self.values: dict = {}

    @property
    def held(self) -> bool:
        return bool(self.values)

    def hold(self, app, **values) -> bool:
        self.values.update(values)
        return app.preview_lookdev_material_values(**self.values)

    def release(self, app) -> bool:
        values, self.values = self.values, {}
        if not values or not app.lookdev.preview:
            return False
        return app.set_lookdev_material_values(**values)

    def drop(self, app) -> None:
        if self.values:
            self.values = {}
            app.end_lookdev_material_preview()


def load_map(app, kind: str, text: str | None) -> bool:
    """AD-039 S7: a picked (or typed) image path becomes the targets' `kind` map (quotes and blanks stripped; empty =
    nothing); None removes it. One Undo step; refused with the reason in the status line."""
    if text is None:
        return app.set_lookdev_map(kind, None)
    path = str(text).strip().strip('"').strip()
    if not path:
        app.set_status(f"LookDev {MAP_LABELS.get(kind, kind)}: erst einen Pfad wählen")
        return False
    return app.set_lookdev_map(kind, path)


def menu_label(app) -> str:
    """The SPACE menu row: LookDev can open on any state (it shows pose, morph and SubD as they are, R-1)."""
    return MENU_CLOSE if app.lookdev_open else MENU_OPEN


def toggle(app) -> bool:
    return app.close_lookdev() if app.lookdev_open else app.open_lookdev()


def preset_label(st: LookdevPanelState) -> str:
    return st.studio_preset


def material_label(row: MaterialRow) -> str:
    if row.preset is None:
        return "-"
    return row.preset + (" (angepasst)" if row.adjusted else "")


def area_label(row: MaterialRow) -> str:
    """The „Bereich“ combo's text: „Ganzes Objekt“ or the region with its notes."""
    if row.area is None:
        return AREA_WHOLE
    return next((a.label for a in row.areas if a.name == row.area), row.area)


def targets_label(row: MaterialRow) -> str:
    if not row.targets:
        return EYE_NOTE
    names = ", ".join(row.targets[:3]) + (f" +{len(row.targets) - 3}" if len(row.targets) > 3 else "")
    return names + (f"  ({EYE_NOTE})" if row.eye_selected else "")


__all__ = ["QUALITY_DRAG", "QUALITY_DRAG_CHOICES", "QUALITY_DRAG_LABELS", "QUALITY_HINTS", "QUALITY_IDLE_CHOICES",
           "QUALITY_IDLE_TIER", "QUALITY_REFINE", "QUALITY_TIER", "QUALITY_TIER_CHOICES", "QUALITY_TIER_LABELS",
           "QUALITY_TITLE", "QUALITY_WAIT", "QualityRow", "AREA", "AREA_DOWN", "AREA_HINT", "AREA_MISSING", "AREA_ORDER_HINT", "AREA_OWN", "AREA_RESET_HINT",
           "AREA_UP", "AREA_WHOLE", "AreaRow", "area_label", "EFFECTS_TITLE", "EFFECT_HINTS", "EFFECT_LABELS", "EYE_NOTE", "EffectRow", "LIGHTS", "MAPS_HINT", "MAPS_TITLE",
           "MAP_LABELS", "MAP_LOAD", "MAP_REMOVE", "MapRow", "NORMAL_GREEN_DOWN", "NORMAL_STRENGTH", "load_map",
           "LIGHT_LABELS", "MATERIAL_PRESETS", "MENU_CLOSE", "MENU_OPEN", "RESET", "RESET_HINT",
           "SAVED", "SAVE_IMAGE", "SAVE_IMAGE_HINT", "STUDIO_PRESETS", "TITLE", "TONE_LABELS", "VIEWS", "LightRow",
           "LookdevPanelState", "MaterialEdit", "MaterialRow", "material_label", "menu_label", "preset_label", "state",
           "targets_label", "toggle"]
