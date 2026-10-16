"""SubD Lab on the app path — lab context, keys, view state, HUD text (GL-free).

WP-SUBD-LAB-02. Same pattern as the Symmetry Lab (`experiments/symmetry_lab/lab_app.py`, AD-013
Addendum H2): the lab is not a second input layer. Navigation, selection, W/E/R, Tweak, Soft, C,
Knife, Extrude, loops, symmetry, Undo/Redo, display modes and the worklight all run unchanged
through `Application`. The lab only adds

- its own keys in the context `subd_lab` (`LAB_KEYS`), resolved through the one `app.bindings`
  before `Application` (`lab_key_press`), with a start-up check that none of them is bound in a
  context the app resolves (`LabBindingConflict`);
- the replacement surface (`lab_surface.SubdSurfaceProvider`, AD-013 H7) and the cage/isoline
  overlay (`lab_surface.SubdLineOverlay`, H1);
- one HUD line built from public state only.

The lab keys only change view state (no mesh change, no History, no Undo step), so the lab needs
neither `command_gate` nor `apply_mesh_change`. While an `Application` interaction owns the keys
(`interaction_owner`, H2-R2) a lab key is refused visibly, like in the Symmetry Lab.

The keys are a proposal for this lab, not an Artist decision. `1`/`2`/`3` (the lab's levels until
WP-SUBD-LAB-01) are the app's component modes, `X` its constraint, so levels are Ctrl+1/2/3 and the
cage depth test is Shift+V.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Optional

from mirai.application import Application
from mirai.interaction.input import KNIFE_CONTEXT, TOPOLOGY_CONTEXT, BindingSet, Input

from .lab_state import DEFAULT_LEVEL, LEVELS, VIEW_BOTH, VIEW_CAGE, VIEW_LABELS, VIEW_ORDER
from .lab_surface import SubdLineOverlay, SubdSurfaceProvider

SUBD_LAB_CONTEXT = "subd_lab"

CYCLE_VIEW = "SubdCycleView"
TOGGLE_AB = "SubdToggleAB"
TOGGLE_CAGE_DEPTH = "SubdToggleCageDepth"
LEVEL_COMMANDS = {f"SubdLevel{n}": n for n in LEVELS}


@dataclass(frozen=True)
class LabKey:
    input: Input
    command: str
    label: str

    def describe(self) -> str:
        return f"{key_label(self.input):<10} {self.command:<20} {self.label}"


def key_label(input: Input) -> str:
    mods = "+".join(m.capitalize() for m in sorted(input.modifiers))
    value = input.value.upper()
    return f"{mods}+{value}" if mods else value


#: The single source of the lab keys (printed at start, mirrored in the README).
LAB_KEYS: tuple[LabKey, ...] = (
    LabKey(Input("key", "v"), CYCLE_VIEW, "Ansicht: Käfig → glatte Fläche + Käfig → glatte Fläche + Isolinien"),
    *(
        LabKey(Input("key", str(n), frozenset({"ctrl"})), command, f"Stufe {n}")
        for command, n in LEVEL_COMMANDS.items()
    ),
    LabKey(Input("key", "b"), TOGGLE_AB, "A/B: Käfig-Ansicht an/aus (Umschalter, Ansicht und Stufe bleiben)"),
    LabKey(Input("key", "v", frozenset({"shift"})), TOGGLE_CAGE_DEPTH, "Käfig-Tiefentest an / immer sichtbar"),
)
LAB_COMMANDS = frozenset(entry.command for entry in LAB_KEYS)

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
        bindings.set_default(entry.input, entry.command, context=SUBD_LAB_CONTEXT)


class SubdAppLab:
    """View state of the lab and its two Viewport attachments (provider H7, overlay H1)."""

    def __init__(self, app: Application, line_sink=None) -> None:
        self.app = app
        self.view = VIEW_CAGE
        self.ab_active = False
        self.cage_depth_test = True
        self.provider = SubdSurfaceProvider(level=DEFAULT_LEVEL)
        self.provider.on_message = app.set_status
        self.lines = SubdLineOverlay(self.provider, sink=line_sink)
        self._apply()

    def attach(self, viewport) -> None:
        viewport.set_surface_provider(self.provider)
        viewport.add_overlay(self.lines)

    @property
    def level(self) -> int:
        return self.provider.level

    def effective_view(self) -> str:
        return VIEW_CAGE if self.ab_active else self.view

    def _apply(self) -> None:
        view = self.effective_view()
        self.provider.set_enabled(view != VIEW_CAGE)
        self.lines.set_view(view, self.cage_depth_test)

    def run_command(self, command: str) -> bool:
        owner = self.app.interaction_owner
        if owner is not None:
            self.app.set_status(f"SubD: {command} ignoriert — {owner} läuft")
            return False
        if command == CYCLE_VIEW:
            self.view = VIEW_ORDER[(VIEW_ORDER.index(self.view) + 1) % len(VIEW_ORDER)]
            self.ab_active = False
            self._apply()
            self.app.set_status(f"SubD: {VIEW_LABELS[self.view]}")
        elif command == TOGGLE_AB:
            self.ab_active = not self.ab_active
            self._apply()
            self.app.set_status(
                "SubD: A/B — Käfig" if self.ab_active else f"SubD: {VIEW_LABELS[self.view]}"
            )
        elif command == TOGGLE_CAGE_DEPTH:
            self.cage_depth_test = not self.cage_depth_test
            self._apply()
            self.app.set_status(
                "SubD: Käfig-Tiefentest an" if self.cage_depth_test else "SubD: Käfig immer sichtbar"
            )
        elif command in LEVEL_COMMANDS:
            refusal = self.provider.set_level(LEVEL_COMMANDS[command])
            self.app.set_status(refusal if refusal is not None else f"SubD: Stufe {self.level}")
            if refusal is not None:
                return False
        else:
            return False
        return True


def start_lab(app: Application, line_sink=None) -> SubdAppLab:
    """Checks and installs the lab keys; the caller attaches the lab after `init_scene`."""
    install_lab_bindings(app.bindings)
    return SubdAppLab(app, line_sink=line_sink)


def lab_key_press(
    app: Application,
    lab: SubdAppLab,
    input: Input,
    *,
    forward: Optional[Callable[[Input], object]] = None,
) -> bool:
    """One key press on the lab path, pyglet-free: a lab command runs in the lab, everything else
    goes to `Application` (`forward`, default `app.key_press`; the window passes the handler from
    `src/main.py` so its side effects stay)."""
    command = app.bindings.command_for(input, SUBD_LAB_CONTEXT)
    if command in LAB_COMMANDS:
        return lab.run_command(command)
    return bool((forward or app.key_press)(input))


def startup_listing() -> list[str]:
    lines = [f"Lab-Kontext {SUBD_LAB_CONTEXT!r} (Vorschlag, keine Artist-Entscheidung):"]
    lines.extend(f"  {entry.describe()}" for entry in LAB_KEYS)
    lines.append("Alles andere ist die Bedienung von src/main.py (W/E/R, C, Undo, D, Ctrl+D, …).")
    return lines


def _ms(value: Optional[float]) -> str:
    return "–" if value is None else f"{value:.1f} ms"


def hud_text(lab: SubdAppLab, asset_name: str, frame_ms: Optional[float] = None) -> str:
    provider = lab.provider
    mesh = lab.app.viewport.mesh if lab.app.viewport is not None else None
    parts = [f"SubD Lab · {asset_name}"]
    view = lab.effective_view()
    parts.append(VIEW_LABELS[view] + (" (A/B)" if lab.ab_active else ""))
    parts.append(f"Stufe {lab.level}")
    if mesh is not None:
        parts.append(f"Käfig {len(mesh.all_vertex_ids())} V / {len(mesh.all_face_ids())} F")
    counts = provider.derived_counts
    if counts is not None:
        parts.append(f"Fläche {counts[0]} V / {counts[1]} F")
    if view == VIEW_BOTH:
        parts.append("Tiefentest an" if lab.cage_depth_test else "Käfig immer sichtbar")
    parts.append(f"Aufbau {_ms(provider.last_build_ms)}")
    parts.append(f"Update {_ms(provider.last_update_ms)}")
    if frame_ms is not None:
        parts.append(f"Frame {frame_ms:.1f} ms")
    if provider.enabled and provider.message:
        parts.append(provider.message)
    return " · ".join(parts)
