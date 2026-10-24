"""Morph Lab on the app path — lab context, weight keys, HUD text (GL-free).

Same pattern as the SubD Lab (`experiments/subdivision_lab/lab_app.py`, AD-013 H2/H7): the lab is
not a second input layer. Navigation, selection, W/E/R, Tweak, Soft, C, Knife, Extrude, loops,
symmetry, Undo/Redo, display modes, the worklight, mode `4` and switching the edit object all run
unchanged through `Application`. The lab only adds

- its own keys in the context `morph_lab` (`LAB_KEYS`), resolved through the one `app.bindings`
  before `Application` (`lab_key_press`), with a start-up check that none of them is bound in a
  context the app resolves (`LabBindingConflict`);
- the replacement surface (`morph.MorphSurfaceProvider`, AD-013 H7, second user — see the H7 note
  "Second user (Morph Lab)" and review CLAUDE-001);
- one HUD line built from public state only.

The weight keys change view state only (no mesh change, no History, not saved); Comma/Period switch the
edit object by running the app's own `4` · select · `1` gesture. So the lab
needs neither `command_gate` nor `apply_mesh_change`. While an `Application` interaction owns the
keys (`interaction_owner`, H2-R2) a lab key is refused visibly. The keys are a proposal
(`PROVISIONAL`), not an Artist decision.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Optional

from core.selection import SelectionMode
from mirai.application import Application
from mirai.interaction.input import KNIFE_CONTEXT, TOPOLOGY_CONTEXT, BindingSet, Input
from mirai.viewport.display import DisplayMode

from .morph import EDITING_BASE, EDITING_OTHER, EDITING_TARGET, MAX_WEIGHT, MIN_WEIGHT, MorphSurfaceProvider

MORPH_LAB_CONTEXT = "morph_lab"

WEIGHT_UP = "MorphWeightUp"
WEIGHT_DOWN = "MorphWeightDown"
WEIGHT_UP_FINE = "MorphWeightUpFine"
WEIGHT_DOWN_FINE = "MorphWeightDownFine"
WEIGHT_FULL = "MorphWeightFull"
WEIGHT_ZERO = "MorphWeightZero"
TOGGLE_AB = "MorphToggleAB"
TOGGLE_RELATIVE = "MorphToggleRelative"
EDIT_BASE = "MorphEditBase"
EDIT_TARGET = "MorphEditTarget"

#: Weight steps in whole percent (`PROVISIONAL`).
STEP, FINE_STEP = 10, 1
STEPS = {WEIGHT_UP: STEP, WEIGHT_DOWN: -STEP, WEIGHT_UP_FINE: FINE_STEP, WEIGHT_DOWN_FINE: -FINE_STEP}


@dataclass(frozen=True)
class LabKey:
    input: Input
    command: str
    label: str

    def describe(self) -> str:
        return f"{key_label(self.input):<12} {self.command:<20} {self.label}"


def key_label(input: Input) -> str:
    names = {"up": "Pfeil hoch", "down": "Pfeil runter", "comma": ",", "period": "."}
    mods = "+".join(m.capitalize() for m in sorted(input.modifiers))
    value = names.get(input.value, input.value.upper())
    return f"{mods}+{value}" if mods else value


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


#: The single source of the lab keys (printed at start, mirrored in the README).
LAB_KEYS: tuple[LabKey, ...] = (
    LabKey(_key("up", "alt"), WEIGHT_UP, f"Gewicht +{STEP} %"),
    LabKey(_key("down", "alt"), WEIGHT_DOWN, f"Gewicht -{STEP} %"),
    LabKey(_key("up", "alt", "shift"), WEIGHT_UP_FINE, f"Gewicht +{FINE_STEP} %"),
    LabKey(_key("down", "alt", "shift"), WEIGHT_DOWN_FINE, f"Gewicht -{FINE_STEP} %"),
    LabKey(_key("up", "ctrl"), WEIGHT_FULL, "Gewicht 100 %"),
    LabKey(_key("down", "ctrl"), WEIGHT_ZERO, "Gewicht 0 %"),
    LabKey(_key("m"), TOGGLE_AB, "A/B: 0 % <-> zuletzt eingestelltes Gewicht"),
    LabKey(_key("b"), TOGGLE_RELATIVE, "Ziel relativ <-> absolut"),
    LabKey(_key("comma"), EDIT_BASE, "Basis bearbeiten"),
    LabKey(_key("period"), EDIT_TARGET, "Ziel 1 bearbeiten"),
)
LAB_COMMANDS = frozenset(entry.command for entry in LAB_KEYS)

#: The key that returns to a component mode after the switch gesture.
COMPONENT_MODE_KEYS = {SelectionMode.VERTEX: "1", SelectionMode.EDGE: "2", SelectionMode.FACE: "3"}

#: Contexts `Application` resolves keys in; a lab key bound in any of them would shadow it.
APP_CONTEXTS = (None, KNIFE_CONTEXT, TOPOLOGY_CONTEXT)


class LabBindingConflict(RuntimeError):
    """A lab key is already bound in a context the app resolves (H2-R1)."""


def assert_lab_keys_free(bindings: BindingSet) -> None:
    conflicts = []
    for entry in LAB_KEYS:
        for context in APP_CONTEXTS:
            bound = bindings.command_for(entry.input, context)
            if bound is not None:
                conflicts.append(
                    f"{key_label(entry.input)} ist im Kontext {context or 'global'!r} an {bound!r} gebunden"
                )
    if conflicts:
        raise LabBindingConflict("Lab-Tasten nicht frei (AD-013 H2-R1): " + "; ".join(conflicts))


def install_lab_bindings(bindings: BindingSet) -> None:
    assert_lab_keys_free(bindings)
    for entry in LAB_KEYS:
        bindings.set_default(entry.input, entry.command, context=MORPH_LAB_CONTEXT)


class MorphAppLab:
    """The weight and the Viewport attachment (provider H7). Built after the lab's scene file is
    loaded, attached to the viewport that load created (review F-5)."""

    def __init__(self, app: Application, base_id, target_id) -> None:
        self.app = app
        self.provider = MorphSurfaceProvider(
            app.scene,
            base_id,
            target_id,
            post=app.set_status,
            serial=lambda: app.status_serial,
        )
        #: the weight the A/B key returns to (the last one above 0 %)
        self.ab_weight = MAX_WEIGHT

    def attach(self, viewport) -> None:
        viewport.set_surface_provider(self.provider)

    @property
    def weight(self) -> int:
        return self.provider.weight

    def set_weight(self, weight: int) -> int:
        weight = self.provider.set_weight(weight)
        if weight > MIN_WEIGHT:
            self.ab_weight = weight
        return weight

    def switch_edit_object(self, object_id) -> bool:
        """Comma/Period: the gesture `4` · select the object · `1`, run through the app's own keys,
        so the switch is the app's (Q-5, E-14: no Undo step, its refusals and status line). The
        lab never calls `_set_edit_object`. Ends in the component mode the artist was in
        (`1` when coming from `4`); the object selection afterwards is the one object."""
        app = self.app
        if app.scene.edit_object_id == object_id:
            app.set_status(f"Morph: {role_name(self, object_id)} wird schon bearbeitet")
            return False
        mode = app.selection.mode
        back = COMPONENT_MODE_KEYS.get(mode, "1")
        app.key_press(Input("key", "4", frozenset()))
        app.selection.objects.clear()
        app.selection.objects.add(object_id)
        app.key_press(Input("key", back, frozenset()))
        return app.scene.edit_object_id == object_id

    def run_command(self, command: str) -> bool:
        owner = self.app.interaction_owner
        if owner is not None:
            self.app.set_status(f"Morph: {command} ignoriert - {owner} läuft")
            return False
        if command == TOGGLE_RELATIVE:
            relative = self.provider.set_relative(not self.provider.relative)
            self.app.set_status(f"Morph: Ziel {'relativ' if relative else 'absolut'}")
            return True
        if command == EDIT_BASE:
            return self.switch_edit_object(self.provider.base_id)
        if command == EDIT_TARGET:
            return self.switch_edit_object(self.provider.target_id)
        before = self.weight
        if command in STEPS:
            self.set_weight(before + STEPS[command])
        elif command == WEIGHT_FULL:
            self.set_weight(MAX_WEIGHT)
        elif command == WEIGHT_ZERO:
            self.set_weight(MIN_WEIGHT)
        elif command == TOGGLE_AB:
            self.provider.set_weight(self.ab_weight if before == MIN_WEIGHT else MIN_WEIGHT)
        else:
            return False
        self.app.set_status(f"Morph: Gewicht {self.weight} %")
        return True


def start_lab(app: Application, base_id, target_id) -> MorphAppLab:
    """Checks and installs the lab keys and builds the lab; the caller attaches it."""
    install_lab_bindings(app.bindings)
    return MorphAppLab(app, base_id, target_id)


def lab_key_press(
    app: Application,
    lab: MorphAppLab,
    input: Input,
    *,
    forward: Optional[Callable[[Input], object]] = None,
) -> bool:
    """One key press on the lab path, pyglet-free: a lab command runs in the lab, everything else
    goes to `Application` (`forward`, default `app.key_press`; the window passes the handler from
    `src/main.py` so its side effects stay)."""
    command = app.bindings.command_for(input, MORPH_LAB_CONTEXT)
    if command in LAB_COMMANDS:
        return lab.run_command(command)
    return bool((forward or app.key_press)(input))


def startup_listing() -> list[str]:
    lines = [f"Lab-Kontext {MORPH_LAB_CONTEXT!r} (Vorschlag, keine Artist-Entscheidung):"]
    lines.extend(f"  {entry.describe()}" for entry in LAB_KEYS)
    lines.append("Alles andere ist die Bedienung von src/main.py (W/E/R, Tweak, Soft, Shift+S, Undo, 4, D, ...).")
    lines.append("Ziel bearbeiten: . (Punkt, oder 4 · Klick aufs Ziel · 1). Zurück zur Basis: , (Komma).")
    lines.append("In 4 ist das ausgewählte Objekt gelblich; Alt+R schaltet es auf Referenz und zurück.")
    return lines


def _ms(value: Optional[float]) -> str:
    return "–" if value is None else f"{value:.1f} ms"


def hints(lab: MorphAppLab) -> list[str]:
    """The `PROVISIONAL` reminders of review F-3, F-7, F-11."""
    app, provider = lab.app, lab.provider
    out = []
    if provider.editing == EDITING_TARGET:
        out.append(
            "Ziel wird bearbeitet - Basis zeigt die Mischung" if lab.weight > MIN_WEIGHT
            else "Ziel wird bearbeitet - Alt+Pfeil hoch zeigt die Mischung an der Basis"
        )
    elif provider.editing == EDITING_BASE and lab.weight > MIN_WEIGHT:
        if app.display.mode is DisplayMode.WIREFRAME:
            out.append("Wireframe: Morph nicht sichtbar")
        elif app.selection.mode is not SelectionMode.OBJECT:
            out.append("Auswahl/Picking = Basis-Ruhelage")
    return out


#: What the HUD calls each selection mode (the app's keys in brackets).
MODE_LABELS = {
    SelectionMode.VERTEX: "Punkte (1)",
    SelectionMode.EDGE: "Kanten (2)",
    SelectionMode.FACE: "Flächen (3)",
    SelectionMode.OBJECT: "Objekte (4)",
}


def role_name(lab: MorphAppLab, object_id) -> str:
    provider = lab.provider
    if object_id == provider.base_id:
        return "Basis"
    if object_id == provider.target_id:
        return "Ziel 1"
    obj = lab.app.scene.objects.get(object_id)
    return repr(obj.name) if obj is not None else "?"


def object_line(lab: MorphAppLab) -> str:
    """Which object `1`/`2`/`3` edit and, in `4`, which are selected (Manu 2026-10-16: "man kann
    nicht wirklich sehen, welches Objekt ausgewählt ist")."""
    app = lab.app
    parts = [f"Bearbeitet: {role_name(lab, app.scene.edit_object_id)}",
             f"Modus: {MODE_LABELS.get(app.selection.mode, app.selection.mode.name)}"]
    if app.selection.mode is SelectionMode.OBJECT:
        selected = sorted(oid for oid in app.selection.objects if oid in app.scene.objects)
        names = ", ".join(role_name(lab, oid) for oid in selected) or "nichts"
        parts.append(f"Ausgewählt: {names}")
    return " · ".join(parts)


def hud_text(lab: MorphAppLab, asset_name: str, frame_ms: Optional[float] = None) -> str:
    """Line 1: lab and weight; line 2: objects; line 3: the app's last status message (in
    `src/main.py` it goes only to the console)."""
    provider = lab.provider
    parts = [
        f"Morph Lab · {asset_name}",
        f"Ziel 1 ({'relativ' if provider.relative else 'absolut'}) · Gewicht {lab.weight} %",
    ]
    if provider.editing != EDITING_OTHER and lab.weight > MIN_WEIGHT:
        parts.append(f"Schritt {_ms(provider.last_update_ms)} ({provider.last_changed} V)")
    if frame_ms is not None:
        parts.append(f"Frame {frame_ms:.1f} ms")
    parts.extend(hints(lab))
    if provider.message and lab.weight > MIN_WEIGHT:
        parts.append(provider.message)
    lines = [" · ".join(parts), object_line(lab)]
    if lab.app.status_message:
        lines.append(f"App: {lab.app.status_message}")
    return "\n".join(lines)
