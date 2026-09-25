"""Lab-Dispatcher: aufgelöstes Command → Lab-Aktion (GL- und pyglet-frei).

Pfad: pyglet-Event → `mirai.pyglet_input` → `app.bindings.command_for(input,
SYMMETRY_LAB_CONTEXT)` → dieser Dispatcher. Das Fenster übersetzt nur Events
und reicht `Input` + Pixelkoordinaten durch; alles Weitere passiert hier,
damit es ohne GL-Kontext testbar ist. Was sich sichtbar geändert hat, sammelt
der Dispatcher als `Change`-Flags; das Fenster holt sie nach jedem Event mit
`take_changes()` ab und baut entsprechend neu auf.

Drag-/Klick-Semantik ist bewusst Lab-lokal (AD-013 A3 bleibt offen):

- Press löst das Command auf. `Orbit`/`Pan` halten diesen Zustand bis zum
  Release derselben Maustaste; Drag-Deltas gehen an die Kamera. Modifier, die
  während des Drags wechseln, ändern die Geste nicht.
- `Select` merkt sich den Press und wird bei Release ausgeführt, wenn die
  Bewegung unter `CLICK_THRESHOLD_PX` blieb (sonst verworfen — kein Box-Select).
- Während eine Geste läuft, werden weitere Maus-Presses ignoriert.

Move (Slice 3, Artist A1 + E5/E6; Ziel-Regel Slice 4 A4/E7/E8): Q löst das
Ziel auf — Auswahl nicht leer → Auswahl; sonst Hover-Vertex → dieser; beides
leer → abgelehnt (Statuszeile, nichts wird scharf). Das Ziel wird beim
Q-Druck einmal festgelegt (E7) und bis Commit/Cancel unverändert an
`begin_current_interaction({..., "vertex_ids": ...})` übergeben — ein
späteres Wegbewegen der Maus ändert es nicht. Ein Hover-Ziel berührt
`scene.selection` nicht (E8): nach Commit/Cancel ist die Auswahl unverändert.
Solange scharf, startet nur LMB ohne Modifier den Move
(`begin_current_interaction`); Alt+LMB, Shift+LMB, MMB und Wheel navigieren
weiter, eine Auswahl per Klick findet nicht statt. Drag →
`update(dx, dy, width, height)` (inkrementell). Release unter der
Klick-Schwelle → `cancel()`, sonst `commit()`; danach immer `deactivate()`
(one-shot). Die Symmetrie liest `MoveTool` selbst aus dem Mesh.

Hover (Slice 4, E9): `motion()` löst per `pick_nearest_vertex` den Vertex
unter dem Cursor auf und hält ihn als reinen Anzeige-Zustand (`hover_vertex`,
GL-frei, testbar) — getrennt von `scene.selection`. Aktualisiert wird nur im
Leerlauf und bei scharfem, aber noch nicht ziehendem Move (`self._gesture is
None`); während einer laufenden Geste (Kamera, Select, Move-Drag) bleibt der
Hover unverändert.

Tasten (`key`): `SymmetryCycle`, `Move`, `ReSymmetrize`, `Cancel`,
`Undo`/`Redo`. Während ein Move-Drag läuft, besitzt die Geste den Input — nur
ESC (Abbruch) wirkt. Jedes andere Command ist ein No-op und gilt als „nicht
behandelt".

Re-Symmetrize (Slice 5, Artist A6/A7, E12–E15): M öffnet die Vorschau —
abgelehnt (nur Statuszeile, kein Zustand), wenn ein Move scharf ist oder
läuft, die Symmetrie aus ist, keine Auswahl besteht, ein Seam-Vertex gewählt
ist oder die Seam das Mesh nicht in genau zwei Teile teilt. Sonst hält der
Dispatcher den `ResymPlan` (`resym_plan`) als Vorschau-Zustand. M erneut →
`apply_plan` (ein Undo-Schritt; bei „0 Änderungen" keiner), ESC → Vorschau
endet ohne Änderung. Während der Vorschau sind nur Orbit/Pan/Zoom erlaubt;
Select, Q, Shift+S, Undo/Redo werden mit Hinweis ignoriert, und der Hover
ist pausiert (ausgeblendet, keine Aktualisierung) — so kann sich das Mesh
zwischen Anzeige und Ausführung des Plans nicht ändern.

Knife (Slice 7, Artist A8/A12/A13, E23–E30): C startet eine Knife-Session
(`LabKnifeTool` aus Slice 6, Klick-Semantik unverändert) — abgelehnt, wenn
ein Move scharf ist oder läuft, bereits eine Session läuft oder `begin`
`KnifeRejected` wirft (E20); während der Re-Symmetrize-Vorschau greift deren
Hinweis. Während der Session: Orbit/Pan/Zoom erlaubt, jedes andere Command
wird mit `KNIFE_HINT` ignoriert (auch Enter bleibt unbelegt, A13). Plain LMB
ist eine eigene Klick-Geste mit derselben Schwelle wie Select; bei Release
unter der Schwelle löst `knife_pick` das Ziel auf (E25): `"vertex"`/`"edge"`
→ `knife.click`, `"outside"` → Commit und Session-Ende, `"face"` → No-op
(A12). ESC → `knife.cancel()`, Mesh wie vor C. `motion()` hält statt des
Vertex-Hovers den Dry-Run des Ziels unter dem Cursor (`knife_hover`, E26/E28)
und meldet ihn über `Change.HOVER`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, Flag, auto
from typing import Optional

from core import VertexId
from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.input import Input
from mirai.viewport.picking import pick_nearest_vertex

from .lab_bindings import KNIFE, RESYMMETRIZE, SYMMETRY_CYCLE, SYMMETRY_LAB_CONTEXT
from .lab_knife import KnifeRejected, LabKnifeTool
from .lab_knife_pick import knife_pick
from .lab_knife_preview import KnifeHoverPreview, knife_hover_preview
from .lab_resymmetrize import ResymmetrizeRejected, ResymPlan, apply_plan, plan_resymmetrize
from .lab_symmetry import cycle_symmetry

#: Wert und Messart (Manhattan-Summe der Drag-Deltas) wie
#: `playground/selector.py::CLICK_THRESHOLD` (Stand `47f821b`).
CLICK_THRESHOLD_PX = 5.0
#: Wie `playground/window.py::_camera_navigate` / `on_mouse_scroll`.
ORBIT_RAD_PER_PX = 0.005
ZOOM_IN_FACTOR = 0.9
ZOOM_OUT_FACTOR = 1.1
#: Hinweis, wenn während der Re-Symmetrize-Vorschau ein anderes Command kommt (E15).
PREVIEW_HINT = "Vorschau aktiv — Befehl ignoriert"
#: Hinweis, wenn während einer Knife-Session ein anderes Command kommt (E24).
KNIFE_HINT = "Knife aktiv — Befehl ignoriert"


class Change(Flag):
    """Was das Fenster nach einem Event neu aufbauen muss."""

    NONE = 0
    STATUS = auto()
    SELECTION = auto()  # Auswahl-Highlight + gespiegelte Vorschau
    HOVER = auto()  # Hover-Highlight + gespiegelte Vorschau (Slice 4), Knife-Marker (Slice 7)
    MESH = auto()  # Mesh-VBOs + Symmetrie-Overlays (Positionen oder Definition)
    PREVIEW = auto()  # Re-Symmetrize-Vorschau (Slice 5)


class MoveState(Enum):
    READY = "bereit"
    ARMED = "scharf"
    DRAGGING = "zieht"


@dataclass
class _Gesture:
    command: str
    button: str
    moved: float = 0.0


class LabDispatcher:
    def __init__(self, app: Application, width: int = 1, height: int = 1) -> None:
        self.app = app
        self.width = width
        self.height = height
        self._gesture: Optional[_Gesture] = None
        self._move_armed = False
        #: Beim Q-Druck festgelegtes Ziel (E7); bleibt bis Commit/Cancel unverändert.
        self._move_target: Optional[frozenset] = None
        #: Anzeige-Label des Ziels ("Auswahl" / "Hover v<id>"), für die Statuszeile.
        self._move_target_label: Optional[str] = None
        #: Vertex unter dem Cursor (Slice 4, E9) — reiner Anzeige-Zustand.
        self._hover_vertex: Optional[VertexId] = None
        #: Re-Symmetrize-Vorschau (Slice 5, E15); None = keine Vorschau aktiv.
        self._resym_plan: Optional[ResymPlan] = None
        #: Knife-Session (Slice 7, E24); None = keine Session.
        self._knife: Optional[LabKnifeTool] = None
        #: Dry-Run des Ziels unter dem Cursor während der Session (E26/E28).
        self._knife_hover: Optional[KnifeHoverPreview] = None
        self._changes = Change.NONE
        #: Letzte Rückmeldung an den Artist (Statuszeile), z. B. „Move: keine Auswahl".
        self.message = ""

    @property
    def active_command(self) -> Optional[str]:
        """Command der laufenden Maus-Geste (`Orbit`/`Pan`/`Select`/`Move`/`Knife`) oder None."""
        return self._gesture.command if self._gesture is not None else None

    @property
    def move_state(self) -> MoveState:
        if self.active_command == cmd.MOVE:
            return MoveState.DRAGGING
        return MoveState.ARMED if self._move_armed else MoveState.READY

    @property
    def move_target_label(self) -> Optional[str]:
        """"Auswahl" / "Hover v<id>", solange Move scharf oder ziehend ist; sonst None."""
        return self._move_target_label

    @property
    def hover_vertex(self) -> Optional[VertexId]:
        return self._hover_vertex

    @property
    def resym_plan(self) -> Optional[ResymPlan]:
        """Plan der aktiven Re-Symmetrize-Vorschau, sonst None."""
        return self._resym_plan

    @property
    def knife(self) -> Optional[LabKnifeTool]:
        """Laufende Knife-Session, sonst None (nur lesen: `start`, `partner()`, …)."""
        return self._knife

    @property
    def knife_active(self) -> bool:
        return self._knife is not None

    @property
    def knife_hover(self) -> Optional[KnifeHoverPreview]:
        """Dry-Run des Ziels unter dem Cursor; None außerhalb der Session oder ohne Ziel."""
        return self._knife_hover

    def take_changes(self) -> Change:
        changes, self._changes = self._changes, Change.NONE
        return changes

    def _mark(self, change: Change, message: Optional[str] = None) -> None:
        self._changes |= change | Change.STATUS
        if message is not None:
            self.message = message

    def resize(self, width: int, height: int) -> None:
        self.width = width
        self.height = height

    def resolve(self, inp: Input) -> Optional[str]:
        return self.app.bindings.command_for(inp, SYMMETRY_LAB_CONTEXT)

    # -- Tastatur -----------------------------------------------------------

    def key(self, inp: Optional[Input]) -> bool:
        """Führt das Tasten-Command aus. False = nicht behandelt (Fenster-Default)."""
        if inp is None or inp.kind != "key":
            return False
        command = self.resolve(inp)
        if self._resym_plan is not None:
            return self._preview_key(command)
        if self._knife is not None:
            return self._knife_key(command)
        if command == cmd.CANCEL:
            return self._cancel()
        if command == RESYMMETRIZE:
            self._open_preview()
            return True
        if command == KNIFE:
            self._start_knife()
            return True
        if command not in (SYMMETRY_CYCLE, cmd.MOVE, cmd.UNDO, cmd.REDO):
            return False
        if self.move_state is MoveState.DRAGGING:
            return True  # die laufende Geste besitzt den Input
        if command == SYMMETRY_CYCLE:
            axis = cycle_symmetry(self.app.scene)
            self._mark(Change.MESH | Change.SELECTION, f"Symmetrie: {axis or 'aus'}")
        elif command == cmd.MOVE:
            self._arm_move()
        else:
            self._undo_redo(command)
        return True

    def _cancel(self) -> bool:
        if self._knife is not None:
            # Snapshot-Restore kann Positionen, Topologie und Seam ändern.
            self._knife.cancel()
            self._end_knife()
            self._mark(Change.MESH | Change.HOVER, "Knife abgebrochen")
            return True
        state = self.move_state
        if state is MoveState.DRAGGING:
            self.app.tool_manager.cancel()
            self._gesture = None
            self._disarm_move()
            self._mark(Change.MESH | Change.SELECTION, "Move abgebrochen")
            return True
        if state is MoveState.ARMED:
            self._disarm_move()
            self._mark(Change.STATUS, "Move entschärft")
            return True
        return False

    def _undo_redo(self, command: str) -> None:
        self.app.dispatch_command(command)
        # Wie Playground: nach Undo/Redo Auswahl leeren — ein Snapshot-Load
        # kann Vertex-IDs ungültig machen. Ohne Auswahl ist ein scharfer Move
        # sinnlos, also mit entschärfen.
        self.app.scene.selection.clear()
        self._disarm_move()
        self._mark(Change.MESH | Change.SELECTION, command)

    # -- Re-Symmetrize (Slice 5) ----------------------------------------------

    def _open_preview(self) -> None:
        """E15: Vorschau öffnen oder mit Grund in der Statuszeile ablehnen."""
        if self.move_state is not MoveState.READY:
            self._mark(Change.STATUS, f"Re-Symmetrize: nicht während Move ({self.move_state.value})")
            return
        selected = self.app.scene.selection.vertices
        mesh = self.app.scene.mesh
        try:
            if mesh.symmetry_definition is None:
                raise ResymmetrizeRejected("Symmetrie aus")
            if not selected:
                raise ResymmetrizeRejected("keine Auswahl")
            if len(selected) != 1:
                raise ResymmetrizeRejected("genau einen Vertex auswählen")
            plan = plan_resymmetrize(mesh, next(iter(selected)))
        except ResymmetrizeRejected as exc:
            self._mark(Change.STATUS, f"Re-Symmetrize: {exc}")
            return
        self._resym_plan = plan
        self._hover_vertex = None  # Hover pausiert während der Vorschau
        self._mark(Change.PREVIEW | Change.HOVER, "")

    def _preview_key(self, command: Optional[str]) -> bool:
        """Tasten während der Vorschau: M führt aus, ESC bricht ab, Rest ignoriert."""
        if command == RESYMMETRIZE:
            plan = self._resym_plan
            self._resym_plan = None
            if apply_plan(self.app.scene, plan):
                message = f"Re-Symmetrize ausgeführt: {len(plan.changes)} Änderungen"
                self._mark(Change.MESH | Change.SELECTION | Change.PREVIEW, message)
            else:
                self._mark(Change.PREVIEW, "Re-Symmetrize: 0 Änderungen — kein Schritt")
            return True
        if command == cmd.CANCEL:
            self._resym_plan = None
            self._mark(Change.PREVIEW, "Re-Symmetrize abgebrochen")
            return True
        if command is None:
            return False
        self._mark(Change.STATUS, PREVIEW_HINT)
        return True

    # -- Knife (Slice 7) ------------------------------------------------------

    def _start_knife(self) -> None:
        """E24: Session starten oder mit Grund in der Statuszeile ablehnen."""
        if self.move_state is not MoveState.READY:
            self._mark(Change.STATUS, f"Knife: nicht während Move ({self.move_state.value})")
            return
        scene = self.app.scene
        knife = LabKnifeTool()
        knife.activate()
        try:
            knife.begin(mesh=scene.mesh, scene=scene)
        except KnifeRejected as exc:
            knife.deactivate()
            self._mark(Change.STATUS, str(exc))
            return
        self._knife = knife
        self._knife_hover = None
        self._hover_vertex = None  # Vertex-Hover pausiert, Knife-Hover übernimmt (E26)
        self._mark(Change.HOVER, "Knife gestartet")

    def _end_knife(self) -> None:
        self._knife.deactivate()
        self._knife = None
        self._knife_hover = None
        if self._gesture is not None and self._gesture.command == KNIFE:
            self._gesture = None

    def _knife_key(self, command: Optional[str]) -> bool:
        """Tasten während der Session: ESC bricht ab, Rest ignoriert (E24, A13)."""
        if command == cmd.CANCEL:
            return self._cancel()
        if command is None:
            return False
        if command == KNIFE:
            self._mark(Change.STATUS, "Knife: läuft bereits")
        else:
            self._mark(Change.STATUS, KNIFE_HINT)
        return True

    def _knife_press(self, inp: Input) -> None:
        """E29: plain LMB = Knife-Klick-Geste; Orbit/Pan erlaubt; Rest ignoriert."""
        if inp.value == "LEFT" and not inp.modifiers:
            self._gesture = _Gesture(KNIFE, "LEFT")
            return
        command = self.resolve(inp)
        if command in (cmd.ORBIT, cmd.PAN):
            self._gesture = _Gesture(command, inp.value)
        elif command is not None:
            self._mark(Change.STATUS, KNIFE_HINT)

    def _pick_knife_target(self, x: float, y: float) -> dict:
        return knife_pick(self.app.camera, self.app.scene.mesh, x, y, self.width, self.height)

    def _knife_click_at(self, x: float, y: float) -> None:
        """E25: Vertex/Edge → Schnitt, Hintergrund → Commit, Face → No-op (A12)."""
        knife = self._knife
        target = self._pick_knife_target(x, y)
        kind = target["kind"]
        if kind == "face":
            return
        if kind == "outside":
            command = knife.commit()
            self._end_knife()
            message = "Knife committet" if command is not None else "Knife — keine Schnitte"
            # Slice 6 mutiert pro Klick: der Mesh-Zustand kann schon der Nachher-Zustand sein.
            self._mark(Change.MESH | Change.HOVER, message)
            return
        validation_before = knife.last_validation
        if knife.click(target):
            message = "Knife: Schritt angenommen"
        else:
            message = knife.last_message or "Knife abgelehnt"
            validation = knife.last_validation
            # Nur ein Ergebnis dieses Klicks nennen, kein altes (A11).
            if validation is not None and validation is not validation_before and not validation.ok:
                summary = validation.summary()
                if summary not in message:
                    message = f"{message} — {summary}"
        # Das Mesh hat sich ggf. geändert: Vorschau für dieselbe Cursor-Position neu.
        self._knife_hover = knife_hover_preview(knife, self._pick_knife_target(x, y))
        self._mark(Change.MESH | Change.HOVER, message)

    def _update_knife_hover(self, x: float, y: float) -> None:
        preview = knife_hover_preview(self._knife, self._pick_knife_target(x, y))
        if preview != self._knife_hover:
            self._knife_hover = preview
            self._mark(Change.HOVER)

    # -- Move ---------------------------------------------------------------

    def _arm_move(self) -> None:
        """A4/E7: Ziel-Regel — Auswahl nicht leer → Auswahl; sonst Hover; beides
        leer → ablehnen. Das Ziel wird hier einmal festgelegt (E7) und ändert
        sich bis Commit/Cancel nicht mehr, auch wenn sich Auswahl oder Hover
        danach ändern."""
        selection = self.app.scene.selection
        if not selection.is_empty():
            target = frozenset(selection.vertices)
            label = "Auswahl"
        elif self._hover_vertex is not None:
            target = frozenset({self._hover_vertex})
            label = f"Hover v{int(self._hover_vertex)}"
        else:
            self._mark(Change.STATUS, "Move: keine Auswahl, kein Hover — nichts zu bewegen")
            return
        self.app.dispatch_command(cmd.MOVE)
        self._move_armed = True
        self._move_target = target
        self._move_target_label = label
        self._mark(Change.STATUS, "Move scharf — LMB ziehen")

    def _disarm_move(self) -> None:
        if self._move_armed:
            self.app.tool_manager.deactivate()
        self._move_armed = False
        self._move_target = None
        self._move_target_label = None

    def _begin_move(self) -> None:
        app = self.app
        app.tool_manager.begin_current_interaction(
            {
                "scene": app.scene,
                "camera": app.camera,
                # E8: das bei Q festgelegte Ziel, nicht die (ggf. leere) Auswahl —
                # MoveTool liest die Symmetrie selbst aus dem Mesh.
                "vertex_ids": set(self._move_target),
            }
        )
        self._gesture = _Gesture(cmd.MOVE, "LEFT")
        self._mark(Change.STATUS, "")

    def _end_move(self, gesture: _Gesture) -> None:
        manager = self.app.tool_manager
        if gesture.moved < CLICK_THRESHOLD_PX:
            manager.cancel()
            message = "Move: nicht gezogen — kein Schritt"
        else:
            manager.commit()
            message = "Move übernommen"
        self._disarm_move()
        self._mark(Change.MESH | Change.SELECTION, message)

    # -- Maus -------------------------------------------------------------

    def press(self, inp: Input) -> None:
        if inp.kind != "mouse" or self._gesture is not None:
            return
        if self._move_armed and inp.value == "LEFT" and not inp.modifiers:
            self._begin_move()
            return
        if self._knife is not None:
            self._knife_press(inp)
            return
        command = self.resolve(inp)
        if self._resym_plan is not None and command not in (cmd.ORBIT, cmd.PAN):
            if command is not None:
                self._mark(Change.STATUS, PREVIEW_HINT)
            return
        allowed = (cmd.ORBIT, cmd.PAN) if self._move_armed else (cmd.ORBIT, cmd.PAN, cmd.SELECT)
        if command in allowed:
            self._gesture = _Gesture(command, inp.value)

    def drag(self, dx: float, dy: float) -> None:
        gesture = self._gesture
        if gesture is None:
            return
        gesture.moved += abs(dx) + abs(dy)
        if gesture.command == cmd.ORBIT:
            self.app.camera.orbit(-dx * ORBIT_RAD_PER_PX, -dy * ORBIT_RAD_PER_PX)
        elif gesture.command == cmd.PAN:
            self.app.camera.pan(dx, dy, self.width, self.height)
        elif gesture.command == cmd.MOVE:
            self.app.tool_manager.update(dx=dx, dy=dy, width=self.width, height=self.height)
            self._mark(Change.MESH | Change.SELECTION)

    def release(self, button: str, x: float, y: float) -> bool:
        """Beendet die Geste von `button`. True, wenn sich die Auswahl geändert hat."""
        gesture = self._gesture
        if gesture is None or gesture.button != button:
            return False
        self._gesture = None
        if gesture.command == cmd.MOVE:
            self._end_move(gesture)
            return False
        if gesture.command == KNIFE:
            if gesture.moved < CLICK_THRESHOLD_PX and self._knife is not None:
                self._knife_click_at(x, y)
            return False
        if gesture.command == cmd.SELECT and gesture.moved < CLICK_THRESHOLD_PX:
            if self._resym_plan is not None:
                # LMB wurde vor dem M gedrückt: keine Auswahl während der Vorschau (E15).
                self._mark(Change.STATUS, PREVIEW_HINT)
                return False
            return self.select_at(x, y)
        return False

    def motion(self, x: float, y: float) -> None:
        """E9: aktualisiert das Hover-Ziel im Leerlauf und bei scharfem (aber
        noch nicht ziehendem) Move. No-op während einer laufenden Geste
        (Kamera, Select, Move-Drag) — die Geste besitzt den Input — und während
        der Re-Symmetrize-Vorschau (Hover pausiert, E15). Während einer
        Knife-Session: Knife-Hover statt Vertex-Hover (E26)."""
        if self._gesture is not None or self._resym_plan is not None:
            return
        if self._knife is not None:
            self._update_knife_hover(x, y)
            return
        vid = pick_nearest_vertex(
            self.app.camera, self.app.scene.mesh, x, y, self.width, self.height
        )
        if vid != self._hover_vertex:
            self._hover_vertex = vid
            self._mark(Change.HOVER)

    def scroll(self, inp: Optional[Input]) -> None:
        if inp is None or inp.kind != "wheel":
            return
        if self.resolve(inp) == cmd.ZOOM:
            self.app.camera.dolly(ZOOM_IN_FACTOR if inp.value == "UP" else ZOOM_OUT_FACTOR)

    # -- Auswahl ----------------------------------------------------------

    def select_at(self, x: float, y: float) -> bool:
        """Ersetzt die Vertex-Auswahl durch den nächsten Vertex, oder leert sie."""
        selection = self.app.scene.selection
        before = set(selection.vertices)
        vid = pick_nearest_vertex(
            self.app.camera, self.app.scene.mesh, x, y, self.width, self.height
        )
        if vid is None:
            selection.clear()
        else:
            selection.set({vid})
        changed = set(selection.vertices) != before
        if changed:
            self._mark(Change.SELECTION, "")
        return changed
