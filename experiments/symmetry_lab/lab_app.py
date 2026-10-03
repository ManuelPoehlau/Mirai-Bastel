"""Symmetry Lab auf dem App-Pfad — Fenster-Schritt, Lab-Kontext, Gate-Tabelle (GL-frei).

WP-SYM-LAB-03 Slice 1b–4. Vertrag: AD-013, Addendum „2026-10-03, WP-SYM-LAB-03 H2"
(DECIDED), § Decision (Lab-Seite) und Regeln H2-R1..R6. Das Lab ist hier keine
zweite Eingabeschicht: Navigation, Auswahl, W/E/R, C, Knife und Undo laufen
unverändert durch `Application`. Das Lab ergänzt nur

- drei eigene Tasten im Kontext `symmetry_lab` (H2-R1): Shift+S → `SymmetryCycle`,
  M → `ReSymmetrize`, Shift+B → `SymmetryGateMode` — aufgelöst über das eine
  `app.bindings`, vor `Application` (`lab_key_press`);
- eine Zeile der Gate-Tabelle in `app.command_gate`, abgeleitet aus
  `mesh.symmetry_definition` (H2-R2, nie gecacht);
- Symmetrie-Wechsel über `app.apply_mesh_change` (H3), Meldungen über
  `app.set_status` (H4);
- (Slice 2) die HUD-Zeile `hud_text`, gebaut nur aus öffentlichem Zustand
  (`selection`, `transform_command`/`transform_interacting`/`transform_target`,
  `axis_constraint`, `status_message`) und dem Symmetrie-Befund;
- (Slice 3) die Re-Symmetrize-Vorschau als einzige modale Lab-Interaktion: M öffnet
  sie (Plan einmal gerechnet), M führt aus (`apply_mesh_change`), Esc schließt sie
  (D1, nur solange sie offen ist). Solange sie offen ist, steht die Vorschau-Zeile
  der Gate-Tabelle (nur Anzeige-Commands, `hover_suspended`), und sie dominiert
  jede andere Zeile (H2-R2, review N2);
- (Slice 4) den E5-Modus MARK/BLOCK (Shift+B, nur Lab-Zustand, AD-SYM-02 §4): bei
  aktiver Symmetrie lehnt BLOCK C und jedes Transform-Command ab, dessen Operation
  `supports_symmetry` nicht erklärt; MARK lässt alles laufen und warnt im HUD
  (`e5_warning_text`), ohne Status zu schreiben, solange eine
  `Application`-Interaktion läuft (H2-R2). Seit Slice 5 ist BLOCK der Default
  (Artist-Verdikt KEEP-BLOCK, Manu, 2026-10-03); MARK bleibt über Shift+B zum
  Vergleich erreichbar.

Erlaubte `Application`-Zugriffe: nur die öffentliche Liste aus H2-R4 (geprüft von
`tests/test_app_lab_boundary.py`, T-R4a/b).

Einstieg: `run.py` (bis Slice 5 `run_app.py`).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from core import MoveOperation, RotateOperation, ScaleOperation
from mirai.application import Application, CommandGate
from mirai.interaction import commands as cmd
from mirai.interaction.input import KNIFE_CONTEXT, BindingSet, Input

from .lab_bindings import (
    LAB_OVERRIDES,
    RESYMMETRIZE,
    SYMMETRY_CYCLE,
    SYMMETRY_GATE_MODE,
    SYMMETRY_LAB_CONTEXT,
    LabOverride,
)
from .lab_overlays import ReportCache
from .lab_resymmetrize import (
    ResymmetrizeRejected,
    ResymPlan,
    plan_description,
    plan_resymmetrize,
    plan_summary,
    set_plan_positions,
)
from .lab_symmetry import SymmetryReport, current_axis, next_axis, set_symmetry_axis

#: Die drei Lab-Commands (H2-R1). Alles andere geht an `Application`.
LAB_COMMANDS = frozenset({SYMMETRY_CYCLE, RESYMMETRIZE, SYMMETRY_GATE_MODE})

#: Die Lab-Kontext-Einträge auf dem App-Pfad: genau die drei Tasten, Eingaben und
#: Begründungen aus `LAB_OVERRIDES` (eine Quelle). Die Navigations- und C-Overrides
#: des alten Labs entfallen hier (H2-R1: keine Pointer-Einträge, Plan §4.3).
LAB_KEY_ENTRIES: tuple[LabOverride, ...] = tuple(
    o for o in LAB_OVERRIDES if o.command in LAB_COMMANDS
)

#: Transform-Commands → (Label, Operation), wie im alten Lab (`lab_dispatch.TRANSFORMS`):
#: nur die Paarung Tool ↔ Operation. Ob ein Command unter Symmetrie spiegelt, liest
#: das Gate bei jeder Ableitung am Klassenattribut `supports_symmetry` der Operation
#: (AD-SYM-02 §2.3) — keine Liste unterstützter oder abgelehnter Tools.
TRANSFORM_OPERATIONS = {
    cmd.MOVE: ("Move", MoveOperation),
    cmd.ROTATE: ("Rotate", RotateOperation),
    cmd.SCALE: ("Scale", ScaleOperation),
}

#: Kontextuelles C (Split/Connect, Knife) hat keine Operation und damit keine
#: Erklärung — es zählt für E5 als nicht unterstützend (Plan Inventar #22).
CONNECT_LABEL = "C"

#: Knife-Session unter Symmetrie (MARK): Warnzeile im HUD, solange sie läuft.
KNIFE_ONE_SIDED_TEXT = "Knife läuft einseitig — Symmetrie aktiv"


class GateMode(Enum):
    """E5-Modus (Lab-Zustand). Default BLOCK seit Slice 5 (Artist-Verdikt KEEP-BLOCK,
    2026-10-03); das alte Lab und Slice 4 starteten in MARK."""

    MARK = "MARK"
    BLOCK = "BLOCK"


def block_text(name: str) -> str:
    """Ablehnungstext von BLOCK, wörtlich wie im alten Lab (`lab_dispatch._arm_move`)."""
    return f"Symmetrie aktiv — {name} spiegelt nicht (BLOCK: {name} nicht gestartet)"


def one_sided_text(name: str) -> str:
    """MARK-Warnung für einen einseitigen Transform, wie im alten Lab."""
    return f"Symmetrie aktiv — {name} spiegelt nicht (läuft einseitig)"


def supports_symmetry(command: str) -> bool:
    """Die Erklärung der Operation hinter einem Transform-Command, live gelesen."""
    return TRANSFORM_OPERATIONS[command][1].supports_symmetry


def unsupported_commands() -> dict[str, str]:
    """Command → Anzeigename aller Commands, die unter Symmetrie nicht spiegeln:
    C (keine Erklärung) und jedes Transform-Command, dessen Operation
    `supports_symmetry` nicht erklärt (heute keines: W/E/R erklären es)."""
    names = {cmd.CONNECT: CONNECT_LABEL}
    for command, (label, _operation) in TRANSFORM_OPERATIONS.items():
        if not supports_symmetry(command):
            names[command] = label
    return names

#: Text der Vorschau-Zeile für jede Ablehnung (App-Gate und Lab), wie im alten Lab
#: (`lab_dispatch.PREVIEW_HINT`; hier kopiert, das alte Modul geht in Slice 5).
PREVIEW_HINT = "Vorschau aktiv — Befehl ignoriert"

#: Was die Vorschau durchlässt (Addendum, Gate-Tabelle „preview open"): nur die
#: Anzeige-Commands. Navigation braucht keinen Eintrag (nie gegatet).
DISPLAY_COMMANDS = frozenset(
    {
        cmd.CYCLE_DISPLAY_MODE,
        cmd.TOGGLE_WIREFRAME_OVERLAY,
        cmd.SET_SHADED,
        cmd.SET_FLAT_SHADED,
        cmd.SET_WIREFRAME,
    }
)

#: D1, H2-R3 (review CLAUDE-002 N8): die kontextuelle Bedeutung von Esc, wörtlich
#: aus dem Addendum, in der Start-Liste.
CANCEL_PREVIEW_LINE = "Cancel (Esc): closes the Re-Symmetrize preview while it is open"

_COMMAND_LABELS = {
    SYMMETRY_CYCLE: "Symmetrie (Shift+S)",
    RESYMMETRIZE: "Re-Symmetrize (M)",
    SYMMETRY_GATE_MODE: "E5-Modus (Shift+B)",
}
_OWNER_LABELS = {"transform": "Transform läuft", "knife": "Knife-Session läuft"}


class LabBindingConflict(RuntimeError):
    """Eine Lab-Taste ist in GLOBAL oder KNIFE belegt (H2-R1, F15/D2)."""


# -- Gate-Tabelle (H2-R2, H2-R3) ----------------------------------------------------


@dataclass(frozen=True)
class GateRow:
    """Eine Zeile der statischen Gate-Tabelle: Lab-Zustand → `command_gate` und
    `hover_suspended` (die beiden Spalten des Addendums)."""

    state: str
    gate: Optional[CommandGate]
    hover_suspended: bool = False

    def describe(self) -> str:
        if self.gate is None:
            text = f"{self.state}: command_gate = None (nichts abgelehnt)"
        else:
            parts = [
                f"{command} abgelehnt — {text!r}" for command, text in sorted(self.gate.refused.items())
            ]
            if self.gate.allowed is not None:
                parts.append(
                    f"nur {', '.join(sorted(self.gate.allowed))} erlaubt — {self.gate.not_allowed_text!r}"
                )
            text = f"{self.state}: " + "; ".join(parts)
        if self.hover_suspended:
            text += "; Hover pausiert (hover_suspended)"
        return text


ROW_SYMMETRY_OFF = GateRow("Symmetrie aus (E5-Modus egal)", None)
#: Slice 4: ersetzt die Slice-1b-Zeile „C abgelehnt". C und W/E/R laufen; ein
#: einseitiger Lauf wird im HUD markiert (`e5_warning_text`).
ROW_MARK = GateRow("Symmetrie an, E5 MARK: C und W/E/R laufen, HUD warnt", None)
_BLOCK_STATE = "Symmetrie an, E5 BLOCK (Default; C und jedes Transform ohne supports_symmetry)"
#: Slice 3: dominiert jede andere Zeile, solange die Vorschau offen ist (H2-R2, N2).
ROW_PREVIEW = GateRow(
    "Re-Symmetrize-Vorschau offen (Slice 3)",
    CommandGate(allowed=DISPLAY_COMMANDS, not_allowed_text=PREVIEW_HINT),
    hover_suspended=True,
)


def block_row() -> GateRow:
    """Die BLOCK-Zeile, bei jedem Aufruf aus den Erklärungen abgeleitet
    (`unsupported_commands`): C plus jedes nicht spiegelnde Transform-Command.
    Gleiche Erklärungen → gleiche (`==`) Zeile; `sync_gate` vergleicht so."""
    refused = {command: block_text(name) for command, name in unsupported_commands().items()}
    return GateRow(_BLOCK_STATE, CommandGate(refused=refused))


def gate_rows() -> tuple[GateRow, ...]:
    """Die Gate-Tabelle (H2-R3, Start-Liste): aus, MARK, BLOCK, Vorschau."""
    return (ROW_SYMMETRY_OFF, ROW_MARK, block_row(), ROW_PREVIEW)


def gate_row_for(axis: Optional[str], mode: GateMode = GateMode.BLOCK) -> GateRow:
    """Zeile zum Lab-Zustand ohne Vorschau (die Vorschau-Zeile setzt `_open_preview`)."""
    if axis is None:
        return ROW_SYMMETRY_OFF
    return ROW_MARK if mode is GateMode.MARK else block_row()


# -- Start-up (H2-R1, H2-R3) ----------------------------------------------------------


def _label(inp: Input) -> str:
    mods = "+".join(m.capitalize() for m in sorted(inp.modifiers))
    return f"{mods}+{inp.value}" if mods else inp.value


def assert_lab_keys_free(bindings: BindingSet) -> None:
    """H2-R1 (F15, D2): jede Lab-Taste löst in GLOBAL und in KNIFE zu `None` auf.

    `command_for` prüft je Kontext User- vor Default-Ebene; KNIFE fällt auf GLOBAL
    zurück. Eine Belegung irgendwo davon würde von der Lab-Taste verdeckt — dann
    bricht der Start laut ab, statt still zu überschatten. Bewusst `raise`, kein
    `assert` (läuft auch unter `python -O`).
    """
    conflicts = []
    for entry in LAB_KEY_ENTRIES:
        for context in (None, KNIFE_CONTEXT):
            bound = bindings.command_for(entry.input, context)
            if bound is not None:
                conflicts.append(
                    f"{_label(entry.input)} ist im Kontext {context or 'global'!r} "
                    f"an {bound!r} gebunden"
                )
    if conflicts:
        raise LabBindingConflict(
            "Lab-Tasten nicht frei (AD-013 H2-R1): " + "; ".join(conflicts)
        )


def install_lab_bindings(bindings: BindingSet) -> None:
    """Prüft (H2-R1) und trägt genau die drei Lab-Tasten im Lab-Kontext ein."""
    assert_lab_keys_free(bindings)
    for entry in LAB_KEY_ENTRIES:
        bindings.set_default(entry.input, entry.command, context=SYMMETRY_LAB_CONTEXT)


def startup_listing() -> list[str]:
    """Konsolen-Liste beim Start (H2-R1, H2-R3, AD-013 I6): Lab-Einträge + Gate-Zeilen."""
    lines = [f"Lab-Kontext {SYMMETRY_LAB_CONTEXT!r} (AD-013 H2-R1, genau drei Tasten):"]
    lines.extend(f"  {entry.describe()}" for entry in LAB_KEY_ENTRIES)
    lines.append(
        "E5-Modus (Shift+B: BLOCK <-> MARK, Default BLOCK; nur Lab-Zustand, kein Undo-Schritt)"
    )
    lines.append("Gate-Tabelle (AD-013 H2-R3, Ablehnungen je Lab-Zustand):")
    lines.extend(f"  {row.describe()}" for row in gate_rows())
    lines.append("Kontextuelle App-Taste (AD-013 D1):")
    lines.append(f"  {CANCEL_PREVIEW_LINE}")
    return lines


# -- Lab-Zustand ----------------------------------------------------------------------


class SymmetryAppLab:
    """Lab-Zustand auf dem App-Pfad. Hält keine Symmetrie-Kopie (H2-R2): die Achse
    wird bei jedem Zugriff aus `mesh.symmetry_definition` gelesen."""

    def __init__(self, app: Application) -> None:
        self.app = app
        #: Overlays mit eigenem `dirty`-Flag (`lab_overlays`); leer = headless ohne Viewport.
        self.overlays: list = []
        #: Befund-Cache, geteilt mit dem Zustands-Overlay (`build_lab_overlays(lab.reports)`);
        #: während eines laufenden Transforms aufgeschoben (Plan A3, `lab_overlays`).
        self.reports = ReportCache(defer=self.transform_running)
        #: Re-Symmetrize-Vorschau (Slice 3): der beim Öffnen einmal gerechnete Plan,
        #: `None` = keine Vorschau. Lab-Zustand, keine Symmetrie-Kopie: während sie
        #: offen ist, lässt das Gate keine Mesh-Änderung zu.
        self.preview: Optional[ResymPlan] = None
        #: E5-Modus (Slice 4, Default BLOCK seit Slice 5): reiner Lab-Zustand, nie
        #: Mesh oder History — Undo/Redo ändert ihn nicht, wohl aber die Symmetrie,
        #: aus der die Zeile folgt.
        self.gate_mode = GateMode.BLOCK

    @property
    def preview_open(self) -> bool:
        return self.preview is not None

    @property
    def axis(self) -> Optional[str]:
        return current_axis(self.app.scene.mesh)

    def transform_running(self) -> bool:
        """W/E/R scharf oder laufend (H2-R2-Prädikat `interaction_owner`): solange
        werden Befund, Ebene und Partner-IDs nicht neu abgeleitet (Plan A3)."""
        return self.app.interaction_owner == "transform"

    @property
    def report(self) -> SymmetryReport:
        """Symmetrie-Befund zur aktuellen Geometrie, neu abgeleitet nur, wenn sich
        Definition, Positionen oder Seam geändert haben und kein Transform läuft
        (Plan A3; der HUD liest ihn pro Frame). Kein
        Symmetrie-Cache im Sinne von H2-R2: die Achse kommt bei jedem Zugriff aus
        `mesh.symmetry_definition` (Teil der Signatur)."""
        return self.reports.get(self.app.scene.mesh)

    def attach_overlays(self, viewport, overlays) -> None:
        """H1: hängt die Lab-Overlays an den Viewport der App (Reihenfolge = Zeichenreihenfolge)."""
        for overlay in overlays:
            viewport.add_overlay(overlay)
            self.overlays.append(overlay)

    def sync_gate(self) -> bool:
        """Installiert die Gate-Zeile zum aktuellen Symmetrie-Zustand, falls sie
        sich geändert hat — nur, solange keine `Application`-Interaktion läuft
        (H2-R2: das Gate bleibt über deren ganze Dauer konstant) und die Vorschau
        zu ist (ihre Zeile dominiert, H2-R2/N2). True = neu installiert."""
        app = self.app
        if app.interaction_owner is not None or self.preview_open:
            return False
        row = gate_row_for(self.axis, self.gate_mode)
        # `==`, nicht `is`: die BLOCK-Zeile wird bei jeder Ableitung neu gebaut.
        if app.command_gate == row.gate and app.hover_suspended == row.hover_suspended:
            return False
        self._install_row(row)
        return True

    def _install_row(self, row: GateRow) -> None:
        """Der einzige Schreiber von `command_gate`/`hover_suspended` (H2-R6).
        Eine andere Zeile als die Vorschau-Zeile bei offener Vorschau ist ein
        Programmierfehler (H2-R2, review N2): sonst könnte W unter der Vorschau
        scharf werden und Esc (D1) die Vorschau statt des Moves beenden. Bewusst
        `raise`, kein `assert` (gilt auch unter `python -O`)."""
        if self.preview_open and row is not ROW_PREVIEW:
            raise AssertionError(
                f"Gate-Zeile {row.state!r} bei offener Re-Symmetrize-Vorschau (AD-013 H2-R2)"
            )
        app = self.app
        app.command_gate = row.gate
        if app.hover_suspended != row.hover_suspended:
            app.hover_suspended = row.hover_suspended

    def mark_overlays_dirty(self) -> None:
        # Eine reine Definitions-Änderung meldet dem Viewport nichts (mutate gibt
        # eine leere Menge zurück, Plan §5 1a) — die Overlays bauen sich selbst neu.
        for overlay in self.overlays:
            overlay.dirty = True

    def run_command(self, command: str) -> bool:
        """Führt ein Lab-Command aus. Abgelehnt (False + Status) während einer
        `Application`-Interaktion (H2-R2) und bei offener Vorschau jedes außer M
        (H2-R2, N2: die Vorschau-Zeile bleibt)."""
        app = self.app
        owner = app.interaction_owner
        if owner is not None:
            app.set_status(f"{_COMMAND_LABELS[command]} abgelehnt — {_OWNER_LABELS[owner]}")
            return False
        if command == RESYMMETRIZE:
            return self._execute_preview() if self.preview_open else self._open_preview()
        if self.preview_open:
            app.set_status(PREVIEW_HINT)
            return False
        if command == SYMMETRY_CYCLE:
            return self._cycle()
        return self._toggle_gate_mode()

    def _toggle_gate_mode(self) -> bool:
        """Shift+B: BLOCK ↔ MARK (wie im alten Lab). Nur
        Lab-Zustand und die daraus folgende Gate-Zeile — kein Mesh, keine History,
        kein Undo-Schritt. Auch bei Symmetrie aus erlaubt (die Zeile bleibt dann
        „aus"); der Modus gilt ab dem nächsten Symmetrie-Wechsel."""
        self.gate_mode = GateMode.BLOCK if self.gate_mode is GateMode.MARK else GateMode.MARK
        self.sync_gate()
        self.app.set_status(f"E5-Modus: {self.gate_mode.value}")
        return True

    # -- Re-Symmetrize (Slice 3; Verhalten = alter Dispatcher, README Slice 5) ----

    def _open_preview(self) -> bool:
        """M ohne Vorschau: Plan einmal rechnen und die Vorschau öffnen, oder mit
        dem Grund des alten Labs ablehnen (README Slice 5, Schritt 12). Die
        Quelle wählt der alte Dispatcher genauso: genau ein ausgewählter Vertex
        (`selection.vertices`)."""
        app = self.app
        mesh = app.scene.mesh
        selected = app.selection.vertices
        try:
            if mesh.symmetry_definition is None:
                raise ResymmetrizeRejected("Symmetrie aus")
            if not selected:
                raise ResymmetrizeRejected("keine Auswahl")
            if len(selected) != 1:
                raise ResymmetrizeRejected("genau einen Vertex auswählen")
            plan = plan_resymmetrize(mesh, next(iter(selected)))
        except ResymmetrizeRejected as exc:
            app.set_status(f"Re-Symmetrize: {exc}")
            return False
        self.preview = plan
        self._install_row(ROW_PREVIEW)
        self.mark_overlays_dirty()
        # Wie das alte Lab: die Statusmeldung wird geleert, die Vorschau-Zeile
        # (`preview_text`) trägt Richtung, Anzahlen und Tasten.
        app.set_status("")
        return True

    def _execute_preview(self) -> bool:
        """M bei offener Vorschau: genau den Plan der Vorschau setzen, ein
        Undo-Schritt über H3; ein leerer Plan erzeugt keinen (E15,
        `apply_mesh_change` gibt dann False zurück). Danach ist die Vorschau zu."""
        plan = self.preview
        mesh = self.app.scene.mesh

        def mutate() -> set:
            return set_plan_positions(mesh, plan)

        changed = self.app.apply_mesh_change(plan_description(plan), mutate)
        if changed:
            message = f"Re-Symmetrize ausgeführt: {len(plan.changes)} Änderungen"
        else:
            message = "Re-Symmetrize: 0 Änderungen — kein Schritt"
        self.end_preview()
        self.app.set_status(message)
        return True

    def cancel_preview(self) -> bool:
        """Esc bei offener Vorschau (D1): schließen, ohne etwas zu ändern."""
        self.end_preview()
        self.app.set_status("Re-Symmetrize abgebrochen")
        return True

    def end_preview(self) -> None:
        """Schließt die Vorschau (M, Esc, Fenster zu): Gate und Hover-Flag zurück
        auf die Zeile des aktuellen Symmetrie-Zustands; das Hover-Flag auf False
        pickt den Hover am Cursor neu (`Application.hover_suspended`). Ohne
        offene Vorschau ein No-op."""
        if not self.preview_open:
            return
        self.preview = None
        self.mark_overlays_dirty()
        self.sync_gate()

    def _cycle(self) -> bool:
        """Shift+S: aus → X → Y → Z → aus, genau ein Undo-Schritt über H3."""
        app = self.app
        mesh = app.scene.mesh
        axis = next_axis(current_axis(mesh))

        def mutate() -> set:
            set_symmetry_axis(mesh, axis)
            return set()  # keine Position bewegt, keine Topologie geändert

        changed = app.apply_mesh_change(f"Symmetry {axis or 'off'}", mutate)
        self.sync_gate()
        self.mark_overlays_dirty()
        app.set_status(f"Shift+S: Symmetrie {axis or 'aus'}")
        return changed


def start_lab(app: Application) -> SymmetryAppLab:
    """Lab-Start auf einer `Application`: Tasten prüfen und eintragen, Gate-Zeile
    zum Start-Zustand installieren. Legt kein zweites `BindingSet` an (T-R1c)."""
    install_lab_bindings(app.bindings)
    lab = SymmetryAppLab(app)
    lab.sync_gate()
    return lab


# -- Fenster-Schritt (Addendum § Decision, N4) ----------------------------------------


def lab_key_press(
    app: Application,
    lab: SymmetryAppLab,
    input: Input,
    *,
    forward: Optional[Callable[[Input], object]] = None,
) -> bool:
    """Ein Tastendruck auf dem Lab-Pfad, pyglet-frei (Addendum-Pseudocode).

    Lab-Command (Kontext `symmetry_lab`, GLOBAL-Fallback) → das Lab führt es aus
    oder lehnt sichtbar ab (bei offener Vorschau alles außer M). Esc (`Cancel`)
    bei offener Vorschau → das Lab schließt sie (D1, True); ohne Vorschau geht Esc
    unverändert an `Application` (T-R2f). Sonst → `Application` (`forward`,
    Default `app.key_press`), danach leitet das Lab Symmetrie-Zustand und
    Gate-Zeile neu ab (H2-R2: Ctrl+Z über einen Zyklus-Schritt stellt die
    Definition wieder her). `forward` existiert nur für den pyglet-Adapter, der
    stattdessen den Handler aus `src/main.py` aufruft (mit dessen Seiteneffekten,
    z. B. Shift-Tracking).
    """
    command = app.bindings.command_for(input, SYMMETRY_LAB_CONTEXT)
    if command in LAB_COMMANDS:
        return lab.run_command(command)
    if lab.preview_open and command == cmd.CANCEL:
        return lab.cancel_preview()
    result = (forward or app.key_press)(input)
    lab.sync_gate()
    return bool(result)


# -- HUD-Zeile (Slice 2, Inventar #27; Vorbild `lab_status.status_text`) ----------------

#: Status-Wörter wie im alten Lab (`lab_dispatch.MoveState`).
TRANSFORM_IDLE = "Transform: bereit"
_TRANSFORM_STATE = {False: "scharf", True: "bewegt"}


def transform_target_label(app: Application) -> Optional[str]:
    """„Auswahl" / „Hover v<id>" für einen scharfen oder laufenden Transform, sonst
    `None` (A4/E7). Das Ziel ist ab dem Tastendruck fix (`transform_target`); kam es
    vom Hover, ist die Auswahl leer (E8) und der Hover schon gelöscht (clear-on-arm),
    also wird es aus dem fixen Ziel gelesen, nicht aus `selection.hovered`."""
    if app.transform_command is None:
        return None
    if not app.selection.is_empty():
        return "Auswahl"
    target = sorted(app.transform_target, key=int)
    if len(target) == 1:
        return f"Hover v{int(target[0])}"
    return f"Hover ({len(target)} V)"


def constraint_label(space: Optional[str]) -> str:
    """Wie im alten Lab (`lab_dispatch.constraint_label`): „X", „XY-Ebene", „frei"."""
    if space is None:
        return "frei"
    return space.upper() if len(space) == 1 else f"{space.upper()}-Ebene"


def hud_text(
    app: Application,
    asset_name: str,
    report: SymmetryReport,
    gate_mode: Optional[GateMode] = None,
) -> str:
    """Die Lab-HUD-Zeile, nur aus öffentlichem `Application`-Zustand und dem
    Symmetrie-Befund (GL-frei). Teile wie `lab_status.status_text`: Asset und
    Vertex-Anzahl, Symmetrie mit Zustand, ohne Partner/mehrdeutig, Transform mit
    Ziel, E5-Modus (Slice 4, nur bei aktiver Symmetrie und wenn `gate_mode`
    übergeben ist), Constraint (nur wenn gesetzt), letzte Statusmeldung. Die
    Vorschau-Zeile (`preview_text`, Slice 3) und die E5-Warnzeile
    (`e5_warning_text`, Slice 4) sind eigene Zeilen darüber.

    `report` kommt aus dem Befund-Cache des Labs (`SymmetryAppLab.report`), damit
    die Zeile pro Frame nichts neu ableitet."""
    vertex_count = len(app.scene.mesh.all_vertex_ids())
    parts = [
        f"{asset_name} | {vertex_count} V",
        f"Symmetrie: {report.axis or 'aus'} ({report.state.value})",
    ]
    if report.axis is not None:
        unpaired = f"ohne Partner: {len(report.unpaired)}"
        if report.ambiguous:
            unpaired += f", mehrdeutig: {len(report.ambiguous)}"
        parts.append(unpaired)
    command = app.transform_command
    if command is None:
        parts.append(TRANSFORM_IDLE)
    else:
        state = _TRANSFORM_STATE[app.transform_interacting]
        parts.append(f"{command}: {state} ({transform_target_label(app)})")
    if report.axis is not None and gate_mode is not None:
        parts.append(f"E5: {gate_mode.value}")
    if app.axis_constraint is not None:
        parts.append(f"Constraint: {constraint_label(app.axis_constraint)}")
    if app.status_message:
        parts.append(app.status_message)
    return " | ".join(parts)


def e5_warning_text(lab: SymmetryAppLab) -> str:
    """E5-Warnzeile (Slice 4) über der HUD-Zeile; leer, wenn nichts einseitig läuft.

    Bei aktiver Symmetrie: eine laufende Knife-Session (`knife_active`) →
    `KNIFE_ONE_SIDED_TEXT`; ein scharfer oder laufender Transform, dessen
    Operation `supports_symmetry` nicht erklärt → die „läuft einseitig"-Meldung
    des alten Labs. Beides nur im HUD, nie über `set_status`: während einer
    `Application`-Interaktion schreibt das Lab nichts (H2-R2). Unter BLOCK
    können beide nicht entstehen (das Gate startet sie nicht, Shift+S und
    Shift+B sind während einer Interaktion abgelehnt) — die Zeile hängt deshalb
    nur an der Symmetrie, nicht am Modus. Ein sofortiges kontextuelles C
    (Split/Connect) ist keine laufende Interaktion; seine Degradation zeigen die
    Zustands-Marker (neuer Vertex ohne Partner, magenta)."""
    if lab.axis is None:
        return ""
    app = lab.app
    if app.knife_active:
        return KNIFE_ONE_SIDED_TEXT
    command = app.transform_command
    if command in TRANSFORM_OPERATIONS and not supports_symmetry(command):
        return one_sided_text(TRANSFORM_OPERATIONS[command][0])
    return ""


def preview_text(lab: SymmetryAppLab) -> str:
    """Die Vorschau-Zeile über der HUD-Zeile (E15, wie `lab_status.preview_text`);
    leer ohne Vorschau."""
    return plan_summary(lab.preview) if lab.preview is not None else ""
