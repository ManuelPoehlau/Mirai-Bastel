"""SubD Lab on the app path — a thin harness around the Production SubD preview (GL-free).

Since 2026-10-23 SubD is a Production capability (`src/mirai/subdivision/`, `Application.subdivision`):
the replacement surface (AD-013 H7), the cage / isoline lines, the view and level keys (`V`,
`Ctrl+1/2/3`, `Shift+V`, `Alt+V`, binding context `subd`) and the unsupported-topology fallback are
the app's, in `python src/main.py` as here. Until WP-SUBD-LAB-02 the lab carried its own provider
and keys; they moved to Production, so there is one implementation.

What the lab still adds on the app path:

- `B` in the lab context `subd_lab` (`LAB_KEYS`): A/B comparison with the cage view (a toggle; the
  preview's view and level are restored). Lab-local, `PROVISIONAL`, checked at start against every
  context the app resolves, including `subd` (`LabBindingConflict`).
- one HUD line from public state (counts, build / update ms, frame time).

The standalone window of WP-SUBD-LAB-01 (`run_standalone.py`) stays as the comparison mode.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Optional

from mirai.application import Application
from mirai.interaction.input import KNIFE_CONTEXT, SUBD_CONTEXT, TOPOLOGY_CONTEXT, BindingSet, Input
from mirai.subdivision import SUBD_KEYS, VIEW_LABELS, VIEW_OFF
from mirai.subdivision.preview import key_label

SUBD_LAB_CONTEXT = "subd_lab"

TOGGLE_AB = "SubdToggleAB"


@dataclass(frozen=True)
class LabKey:
    input: Input
    command: str
    label: str

    def describe(self) -> str:
        return f"{key_label(self.input):<10} {self.command:<20} {self.label}"


#: The single source of the lab keys (printed at start, mirrored in the README).
LAB_KEYS: tuple[LabKey, ...] = (
    LabKey(Input("key", "b"), TOGGLE_AB, "A/B: Käfig-Ansicht an/aus (Umschalter, Ansicht und Stufe bleiben)"),
)
LAB_COMMANDS = frozenset(entry.command for entry in LAB_KEYS)

#: Contexts `Application` resolves keys in; a lab key bound in any of them would shadow it.
APP_CONTEXTS = (None, KNIFE_CONTEXT, TOPOLOGY_CONTEXT, SUBD_CONTEXT)


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
    """The lab's A/B state over `app.subdivision` (the Production preview)."""

    def __init__(self, app: Application) -> None:
        self.app = app
        #: the preview's view while A/B shows the cage (None = A/B off)
        self._ab_view: Optional[str] = None

    @property
    def preview(self):
        return self.app.subdivision

    @property
    def provider(self):
        return self.app.subdivision.provider

    @property
    def level(self) -> int:
        return self.preview.level

    @property
    def ab_active(self) -> bool:
        if self._ab_view is not None and self.preview.view != VIEW_OFF:
            self._ab_view = None  # the view was changed with V meanwhile: A/B is over
        return self._ab_view is not None

    def effective_view(self) -> str:
        return self.preview.view

    def run_command(self, command: str) -> bool:
        owner = self.app.interaction_owner
        if owner is not None:
            self.app.set_status(f"SubD: {command} ignoriert — {owner} läuft")
            return False
        if command != TOGGLE_AB:
            return False
        if self.ab_active:
            view, self._ab_view = self._ab_view, None
            self.preview.set_view(view)
            return True
        if self.preview.view == VIEW_OFF:
            self.app.set_status("SubD: A/B — die Vorschau ist aus, nichts zu vergleichen")
            return False
        self._ab_view = self.preview.view
        self.preview.set_view(VIEW_OFF)
        self.app.set_status("SubD: A/B — Käfig")
        return True


def start_lab(app: Application) -> SubdAppLab:
    """Checks and installs the lab keys (call before `init_scene`; the preview attaches itself)."""
    install_lab_bindings(app.bindings)
    return SubdAppLab(app)


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
    lines = ["SubD-Tasten der App (Kontext 'subd', PROVISIONAL):"]
    lines.extend(f"  {key_label(entry.input):<10} {entry.command:<20} {entry.label}" for entry in SUBD_KEYS)
    lines.append(f"Lab-Kontext {SUBD_LAB_CONTEXT!r} (Vorschlag, keine Artist-Entscheidung):")
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
    parts.append(f"Aufbau {_ms(provider.last_build_ms)}")
    parts.append(f"Update {_ms(provider.last_update_ms)}")
    if frame_ms is not None:
        parts.append(f"Frame {frame_ms:.1f} ms")
    if provider.enabled and provider.message:
        parts.append(provider.message)
    return " · ".join(parts)
