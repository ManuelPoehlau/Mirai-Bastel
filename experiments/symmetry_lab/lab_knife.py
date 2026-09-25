"""Gespiegelter Knife — **Lab-Experiment**, keine Capability. Headless, GL-frei.

Handoff WP-SYM-LAB-01 Slice 6, §2 A8–A11 / E16–E22
(`docs/architecture/WP-SYM-LAB-01_SLICE6_CLAUDE_CODE_HANDOFF.md`).
Interaktionsmodell und Session-History aus AD-017
(`docs/architecture/AD-017_FINAL_DECISIONS_2026-09-22.md` §6–§8): Klick =
nächster Schnitt, In-Session-Undo = letzter Schnitt, Cancel = alles
verwerfen, Commit = ein History-Eintrag. Eine symmetrische Operation ist
eine Operation-Instanz, nicht zwei (AD-SYM-02 §2.1): beide Seiten eines
Klicks liegen in *einem* Session-Schritt, die ganze Session in *einem*
`MeshStateCommand`.

Herkunft (E16, Präzedenz AD-010 wie die Draw-Stücke): kopiert und adaptiert
— nicht importiert — aus `playground/topology_tools/knife.py` (`KnifeTool`)
und `connect_in_shared_face` aus `playground/topology_tools/topology_points.py`,
Stand `1825b44`. Das Playground-Original bleibt unverändert. Abweichungen
von der Vorlage:

- `connect_in_shared_face` gibt zusätzlich die benutzte Face und ihre
  Boundary zurück (`Connection`), damit die Spiegel-Face als Partnerbild
  dieser Face bestimmt werden kann statt über „niedrigste FaceId".
- Kein Auswahl-Residue beim Commit (E22): das Lab hat keinen Edge-Modus,
  der Knife berührt `scene.selection` nicht.
- Ein Split, der wirft, rollt den Schritt zurück und lehnt ab, statt die
  Ausnahme weiterzureichen (A11).

Spiegelziel (A9, E17): Primär ist der Operationskontext — der Knife weiß,
welche Vertices er in dieser Session paarweise erzeugt hat (`intent_pairs`,
INV-6: Gegenseite aus der Absicht). Für bestehende Geometrie, die der Knife
nicht erzeugt hat, gilt die gespeicherte Seam (INV-4) und danach die
Capability-Korrespondenz. Nicht auflösbar → Schritt abgelehnt, nie auf einen
unbekannten Partner spiegeln (INV-5). Position (`mirai.symmetry`) und
Topologie (`lab_topology`) sind danach *unabhängige Validierung* jedes
Schritts (E19), keine Quelle. Das ist nur die Regel dieses Experiments, keine
Architekturentscheidung über eine künftige Capability.

Keine Toleranz (A5): der Spiegelpunkt wird über `mirror_position` gesetzt,
nicht über ein gespiegeltes `t` (Befund P3 in der README).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from core import EdgeId, FaceId, Mesh, SymmetryDefinition, VertexId
from core.operations.topology import MeshStateCommand
from mirai.interaction.tool import Tool
from mirai.symmetry import (
    CorrespondenceState,
    SymmetryState,
    mirror_position,
    symmetry_state,
    vertex_correspondence,
)

from .lab_topology import topological_pairing, topological_sides

#: Namen der Prüfungen aus E19 — so erscheinen sie in Meldungen und `failed`.
CHECK_POSITION = "Position"
CHECK_TOPOLOGY = "Topologie"
CHECK_SEAM_SIDES = "Seam/Seiten"


class KnifeRejected(ValueError):
    """`begin` abgelehnt (E20); `str(exc)` ist die Meldung für die Statuszeile."""


# -- Lab-Kopie von `connect_in_shared_face` (E16) ----------------------------------


@dataclass(frozen=True)
class Connection:
    edge: EdgeId
    #: Die geteilte Face — nach dem Connect ungültig (`connect_vertices` ersetzt sie).
    face: FaceId
    #: Ihre Boundary vor dem Connect.
    boundary: tuple[VertexId, ...]


def connect_in_shared_face(
    mesh: Mesh, a: VertexId, b: VertexId, faces: Optional[list[FaceId]] = None
) -> Optional[Connection]:
    """Verbindet `a` und `b` über die niedrigste gemeinsame FaceId, in der sie
    nicht benachbart sind (wie die Vorlage). `faces` schränkt die Kandidaten
    ein — so wird der Spiegel-Connect auf die Partner-Face festgelegt.
    `None`, wenn keine Face passt.
    """
    candidates = mesh.all_face_ids() if faces is None else faces
    for fid in sorted(candidates, key=int):
        boundary = mesh.face_vertices(fid)
        if a not in boundary or b not in boundary:
            continue
        n = len(boundary)
        dist = (boundary.index(b) - boundary.index(a)) % n
        if dist == 1 or dist == n - 1:
            continue  # benachbart
        try:
            new_edge, _, _ = mesh.connect_vertices(fid, a, b)
        except Exception:
            continue
        return Connection(new_edge, fid, tuple(boundary))
    return None


def edge_between(mesh: Mesh, a: VertexId, b: VertexId) -> Optional[EdgeId]:
    for eid in mesh.vertex_edges(a):
        if b in mesh.edge_vertices(eid):
            return eid
    return None


# -- Validierung (E19) — reine Funktion, auch für Tests und Slice 7 -----------------


@dataclass(frozen=True)
class KnifeValidation:
    """Ergebnis von E19 für einen Mesh-Zustand und eine Absichts-Paarung."""

    position_ok: bool
    topology_ok: bool
    seam_sides_ok: bool
    state: SymmetryState
    component_count: int
    topology_conflicts: int
    face_pair_conflicts: int
    #: Absichts-Paare, die die jeweilige Prüfung nicht bestätigt.
    position_mismatches: frozenset[VertexId] = frozenset()
    topology_mismatches: frozenset[VertexId] = frozenset()

    @property
    def ok(self) -> bool:
        return self.position_ok and self.topology_ok and self.seam_sides_ok

    @property
    def failed(self) -> tuple[str, ...]:
        names = (
            (CHECK_POSITION, self.position_ok),
            (CHECK_TOPOLOGY, self.topology_ok),
            (CHECK_SEAM_SIDES, self.seam_sides_ok),
        )
        return tuple(name for name, ok in names if not ok)

    def summary(self) -> str:
        if self.ok:
            return "Validierung ok"
        parts = []
        if not self.position_ok:
            parts.append(f"{CHECK_POSITION} ({len(self.position_mismatches)} Paare)")
        if not self.topology_ok:
            parts.append(f"{CHECK_TOPOLOGY} ({len(self.topology_mismatches)} Paare)")
        if not self.seam_sides_ok:
            parts.append(
                f"{CHECK_SEAM_SIDES} (Zustand {self.state.value}, {self.component_count} Seiten, "
                f"{self.topology_conflicts}+{self.face_pair_conflicts} Konflikte)"
            )
        return "Validierung gescheitert: " + ", ".join(parts)


def validate_step(mesh: Mesh, intent_pairs: dict[VertexId, VertexId]) -> KnifeValidation:
    """E19: bestätigen Position und Topologie jedes Absichts-Paar, und ist das
    Ganze `valid` mit genau zwei Seiten und ohne Konflikte?"""
    correspondence = vertex_correspondence(mesh)
    pairing = topological_pairing(mesh)
    sides = topological_sides(mesh)

    position_mismatches: set[VertexId] = set()
    topology_mismatches: set[VertexId] = set()
    for x, y in intent_pairs.items():
        corr = correspondence.get(x)
        if x == y:
            position_confirms = corr is not None and corr.state is CorrespondenceState.SEAM
        else:
            position_confirms = (
                corr is not None and corr.state is CorrespondenceState.PAIRED and corr.partner == y
            )
        if not position_confirms:
            position_mismatches.add(x)
        if pairing.partners.get(x) != y:
            topology_mismatches.add(x)

    state = symmetry_state(mesh)
    seam_sides_ok = (
        state is SymmetryState.VALID
        and sides.component_count == 2
        and not pairing.conflicts
        and pairing.face_pair_conflicts == 0
    )
    return KnifeValidation(
        position_ok=not position_mismatches,
        topology_ok=not topology_mismatches,
        seam_sides_ok=seam_sides_ok,
        state=state,
        component_count=sides.component_count,
        topology_conflicts=len(pairing.conflicts),
        face_pair_conflicts=pairing.face_pair_conflicts,
        position_mismatches=frozenset(position_mismatches),
        topology_mismatches=frozenset(topology_mismatches),
    )


# -- Session ----------------------------------------------------------------------


@dataclass
class _KnifeStep:
    state_before: Any
    start_before: Optional[VertexId]
    path_edges_before: list[EdgeId]
    intent_pairs_before: dict[VertexId, VertexId] = field(default_factory=dict)


class _StepRejected(Exception):
    """Interner Abbruch eines Klicks; wird in `click` zurückgerollt und gemeldet."""


class LabKnifeTool(Tool):
    """Knife-Session mit Spiegelung (Symmetrie an) bzw. wie im Playground (aus).

    Lebenszyklus wie `playground/topology_tools/knife.py`:
      knife.activate(); knife.begin(mesh=..., scene=...)   # KnifeRejected bei E20
      knife.click(target) / knife.undo_step() / knife.redo_step()
      knife.commit()  # → MeshStateCommand | None
      knife.cancel()

    `last_message` ist die letzte Meldung (Ablehnung oder Erfolg),
    `last_validation` das letzte E19-Ergebnis (auch bei Ablehnung).
    """

    def _on_activate(self) -> None:
        self._mesh: Optional[Mesh] = None
        self._scene = None
        self._session_before: Any = None
        self._mirrored = False
        self._start: Optional[VertexId] = None
        self._path_edges: list[EdgeId] = []
        self._intent_pairs: dict[VertexId, VertexId] = {}
        self._step_stack: list[_KnifeStep] = []
        self._redo_stack: list[tuple[_KnifeStep, _KnifeStep]] = []
        self._correspondence: dict = {}
        self.last_message: Optional[str] = None
        self.last_validation: Optional[KnifeValidation] = None

    # -- öffentlich lesend -----------------------------------------------------

    @property
    def mirrored(self) -> bool:
        return self._mirrored

    @property
    def start(self) -> Optional[VertexId]:
        return self._start

    @property
    def path_edges(self) -> list[EdgeId]:
        return list(self._path_edges)

    @property
    def intent_pairs(self) -> dict[VertexId, VertexId]:
        return dict(self._intent_pairs)

    # -- Lifecycle -------------------------------------------------------------

    def _on_begin(self, mesh=None, scene=None, **_) -> None:
        """E20: Symmetrie aus → ungespiegelt; an → nur bei `valid` und 2 Seiten."""
        mirrored = mesh.symmetry_definition is not None
        if mirrored:
            state = symmetry_state(mesh)
            sides = topological_sides(mesh).component_count
            if state is not SymmetryState.VALID or sides != 2:
                self.last_message = (
                    f"Knife nicht gestartet: Symmetrie {state.value}, {sides} Seiten "
                    "(nötig: valid und 2 Seiten)"
                )
                raise KnifeRejected(self.last_message)
        self._mesh = mesh
        self._scene = scene
        self._mirrored = mirrored
        self._session_before = mesh.export_state()
        self._start = None
        self._path_edges = []
        self._intent_pairs = {}
        self._step_stack = []
        self._redo_stack = []
        self.last_message = None
        self.last_validation = None

    def _on_update(self, **kwargs) -> None:
        pass

    def _on_commit(self) -> Optional[MeshStateCommand]:
        """E21: genau ein `MeshStateCommand`; unverändert → keiner. Kein Residue (E22)."""
        current = self._mesh.export_state()
        self._redo_stack.clear()
        if current == self._session_before:
            return None
        cmd = MeshStateCommand(
            mesh=self._mesh,
            before_state=self._session_before,
            after_state=current,
            description="Knife (symmetrisch)" if self._mirrored else "Knife",
        )
        self._scene.history.push(cmd)
        return cmd

    def _on_cancel(self) -> None:
        self._mesh.load_state(self._session_before)
        self._step_stack.clear()
        self._redo_stack.clear()
        self._path_edges = []
        self._intent_pairs = {}
        self._start = None

    # -- Vorschau (Vorlage, unverändert; Spiegelziele erst in Slice 7) -----------

    def hover(self, target: dict) -> dict:
        kind = target.get("kind") if target else None
        if kind == "vertex":
            return {"valid": True, "target": target, "start": self._start}
        if kind == "edge":
            eid = target.get("edge_id")
            t = target.get("t", 0.5)
            if eid is not None and self._mesh.is_valid_edge(eid) and 0.0 < t < 1.0:
                if self._start is not None and self._start in self._mesh.edge_vertices(eid):
                    return {"valid": False, "target": target, "start": self._start}
                return {"valid": True, "target": target, "start": self._start}
        return {"valid": False, "target": target, "start": self._start}

    # -- Klick (E18) -------------------------------------------------------------

    def click(self, target: dict) -> bool:
        """Ein Klick = ein Schritt mit beiden Seiten. True = angenommen."""
        kind = target.get("kind") if target else None
        try:
            if kind == "vertex":
                self._check_vertex_target(target.get("vertex_id"))
            elif kind == "edge":
                self._check_edge_target(target.get("edge_id"), target.get("t", 0.5))
            else:
                raise _StepRejected(f"Ziel {kind!r} nicht unterstützt (kein Schnitt)")
        except _StepRejected as exc:
            return self._reject(str(exc))

        # Ab hier wird gemutiert: Snapshot VOR der Mutation, damit Rollback und
        # In-Session-Undo beide Seiten (inkl. intent_pairs und Seam) zurücknehmen.
        self._push_step()
        self._correspondence = vertex_correspondence(self._mesh) if self._mirrored else {}
        try:
            if kind == "vertex":
                self._apply_vertex_click(target["vertex_id"])
            else:
                self._apply_edge_click(target["edge_id"], target.get("t", 0.5))
            if self._mirrored:
                self.last_validation = validate_step(self._mesh, self._intent_pairs)
                if not self.last_validation.ok:
                    raise _StepRejected(self.last_validation.summary())
        except _StepRejected as exc:
            self._rollback()
            return self._reject(str(exc))
        finally:
            # Nur für die Dauer eines Klicks gültig (bestehende Geometrie, E17 Stufe 3).
            self._correspondence = {}
        self._redo_stack.clear()
        self.last_message = None
        return True

    def _check_vertex_target(self, vid) -> None:
        mesh = self._mesh
        if vid is None or not mesh.is_valid_vertex(vid):
            raise _StepRejected(f"kein gültiger Vertex ({vid!r})")
        if self._start is None:
            return
        if vid == self._start:
            raise _StepRejected("Ziel ist der Start-Vertex")
        if self._mirrored:
            seam = self._seam_vertices()
            if self._start in seam and vid in seam:
                raise _StepRejected("Schnitt entlang der Seam nicht unterstützt")
        if edge_between(mesh, self._start, vid) is not None:
            raise _StepRejected(
                f"Verbindung v{int(self._start)}–v{int(vid)} existiert bereits"
            )

    def _check_edge_target(self, eid, t) -> None:
        mesh = self._mesh
        if eid is None or not mesh.is_valid_edge(eid):
            raise _StepRejected(f"keine gültige Edge ({eid!r})")
        if not (0.0 < t < 1.0):
            raise _StepRejected(f"t={t!r} nicht in (0, 1)")
        if self._start is None:
            return
        if self._start in mesh.edge_vertices(eid):
            raise _StepRejected(f"Edge e{int(eid)} hängt am Start-Vertex")
        start_faces = {f for e in mesh.vertex_edges(self._start) for f in mesh.edge_faces(e)}
        if not start_faces & set(mesh.edge_faces(eid)):
            raise _StepRejected(f"Edge e{int(eid)} teilt keine Face mit dem Start-Vertex")
        if self._mirrored and self._start in self._seam_vertices() and self._is_seam_edge(eid):
            raise _StepRejected("Schnitt entlang der Seam nicht unterstützt")

    def _apply_vertex_click(self, vid: VertexId) -> None:
        if self._mirrored:
            self._require_partner(vid)
        if self._start is None:
            self._start = vid
            return
        self._connect(vid)

    def _apply_edge_click(self, eid: EdgeId, t: float) -> None:
        new_vertex = self._split(eid, t)
        if self._start is None:
            self._start = new_vertex
            return
        self._connect(new_vertex)

    def _split(self, eid: EdgeId, t: float) -> VertexId:
        """Edge-Split beider Seiten (E18). Gibt den Quell-Vertex zurück."""
        mesh = self._mesh
        if not self._mirrored:
            return self._split_edge(eid, t)[0]

        a, b = mesh.edge_vertices(eid)
        if self._is_seam_edge(eid):
            new_vertex, half_a, half_b = self._split_edge(eid, t)
            definition = mesh.symmetry_definition
            mesh.symmetry_definition = SymmetryDefinition(
                plane_point=definition.plane_point,
                plane_normal=definition.plane_normal,
                seam_edges=(definition.seam_edges - {eid}) | {half_a, half_b},
            )
            # Achsenkomponente != 0.0 → Zustand violated → E19 „Seam/Seiten".
            self._intent_pairs[new_vertex] = new_vertex
            return new_vertex

        mirror_edge = edge_between(mesh, self._require_partner(a), self._require_partner(b))
        if mirror_edge is None:
            raise _StepRejected(f"keine Spiegel-Edge zu e{int(eid)}")
        if mirror_edge == eid:
            # E17: partner_edge(e) == e nur für Seam-Edges; alles andere nicht raten.
            raise _StepRejected(f"e{int(eid)} ist ihr eigenes Spiegelbild, aber keine Seam-Edge")
        new_vertex = self._split_edge(eid, t)[0]
        mirror_vertex = self._split_mirror_edge(mirror_edge, new_vertex)
        self._intent_pairs[new_vertex] = mirror_vertex
        self._intent_pairs[mirror_vertex] = new_vertex
        return new_vertex

    def _split_mirror_edge(self, mirror_edge: EdgeId, source_vertex: VertexId) -> VertexId:
        """Spiegelpunkt über `mirror_position(pos(n))`, nicht über gespiegeltes `t` (P3)."""
        mesh = self._mesh
        definition = mesh.symmetry_definition
        mirror_vertex = self._split_edge(mirror_edge, 0.5)[0]
        mesh.set_vertex_position(
            mirror_vertex,
            mirror_position(
                mesh.vertex_position(source_vertex), definition.plane_point, definition.plane_normal
            ),
        )
        return mirror_vertex

    def _split_edge(self, eid: EdgeId, t: float) -> tuple[VertexId, EdgeId, EdgeId]:
        try:
            return self._mesh.split_edge(eid, t)
        except Exception as exc:
            raise _StepRejected(f"split_edge e{int(eid)} gescheitert: {exc}") from exc

    def _connect(self, target: VertexId) -> None:
        """Connect start → target, gespiegelt in der Partner-Face (E18)."""
        mesh = self._mesh
        start = self._start
        source = connect_in_shared_face(mesh, start, target)
        if source is None:
            raise _StepRejected(
                f"Connect v{int(start)} → v{int(target)} gescheitert "
                "(keine gemeinsame Face, in der sie nicht benachbart sind)"
            )
        self._path_edges.append(source.edge)

        if self._mirrored:
            mirror_start = self._require_partner(start)
            mirror_target = self._require_partner(target)
            if {mirror_start, mirror_target} != {start, target}:
                image = {self._require_partner(v) for v in source.boundary}
                faces = [f for f in mesh.all_face_ids() if set(mesh.face_vertices(f)) == image]
                if not faces:
                    raise _StepRejected(f"keine Spiegel-Face zu f{int(source.face)}")
                mirror = connect_in_shared_face(mesh, mirror_start, mirror_target, faces)
                if mirror is None:
                    raise _StepRejected(
                        f"Spiegel-Connect v{int(mirror_start)} → v{int(mirror_target)} gescheitert"
                    )
                self._path_edges.append(mirror.edge)
        self._start = target

    # -- Partner (E17) -------------------------------------------------------------

    def _seam_edges(self) -> set[EdgeId]:
        definition = self._mesh.symmetry_definition
        return {e for e in definition.seam_edges if self._mesh.is_valid_edge(e)}

    def _is_seam_edge(self, eid: EdgeId) -> bool:
        return eid in self._seam_edges()

    def _seam_vertices(self) -> set[VertexId]:
        return {v for e in self._seam_edges() for v in self._mesh.edge_vertices(e)}

    def partner(self, vid: VertexId) -> Optional[VertexId]:
        """E17: Operationskontext → Seam → Capability-Korrespondenz → `None`."""
        if vid in self._intent_pairs:
            return self._intent_pairs[vid]
        if vid in self._seam_vertices():
            return vid
        corr = self._correspondence.get(vid) or vertex_correspondence(self._mesh).get(vid)
        if corr is not None and corr.state is CorrespondenceState.PAIRED:
            return corr.partner
        return None

    def _require_partner(self, vid: VertexId) -> VertexId:
        p = self.partner(vid)
        if p is None:
            raise _StepRejected(f"kein Spiegelpartner für v{int(vid)} (INV-5)")
        return p

    # -- Schritte, Rollback, Undo/Redo ---------------------------------------------

    def _snapshot(self) -> _KnifeStep:
        return _KnifeStep(
            state_before=self._mesh.export_state(),
            start_before=self._start,
            path_edges_before=list(self._path_edges),
            intent_pairs_before=dict(self._intent_pairs),
        )

    def _restore(self, step: _KnifeStep) -> None:
        self._mesh.load_state(step.state_before)
        self._start = step.start_before
        self._path_edges = list(step.path_edges_before)
        self._intent_pairs = dict(step.intent_pairs_before)

    def _push_step(self) -> None:
        self._step_stack.append(self._snapshot())

    def _rollback(self) -> None:
        """A11: den gerade gepushten Schritt bitgenau zurücknehmen."""
        self._restore(self._step_stack.pop())

    def _reject(self, message: str) -> bool:
        self.last_message = f"Knife abgelehnt: {message}"
        print(f"[LAB-KNIFE] {self.last_message}")
        return False

    def undo_step(self) -> bool:
        if not self._step_stack:
            return False
        step = self._step_stack.pop()
        self._redo_stack.append((step, self._snapshot()))
        self._restore(step)
        return True

    def redo_step(self) -> bool:
        if not self._redo_stack:
            return False
        step, after = self._redo_stack.pop()
        self._restore(after)
        self._step_stack.append(step)
        return True
