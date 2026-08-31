"""Transform-Foundation: wiederverwendbare Vertex-Transformationen (WP-03).

Bezug: ROADMAP.md §5 WP-03 (Transform Foundation), V1_SPEC.md §4 (Transform).

Rotate und Scale folgen demselben interaktiven Lifecycle-Vertrag wie
MoveOperation (AD-003) - hier als gemeinsame Basis umgesetzt, statt drei
unabhängige Features zu implementieren (WP-03-Ziel: ein wiederverwendbares
Transform-Konzept, keine unrelated Einzel-Features).

Verhältnis zu operations/move.py: MoveOperation bleibt bewusst UNANGETASTET
(sie ist die getestete WP-02-Basis). Eine spätere Vereinheitlichung auf diese
Basis ist eine explizite Architekturentscheidung, kein Nebeneffekt von WP-03.

Architekturvertrag (siehe operation.py):

- update() ist INKREMENTELL (Core-Vertrag): jeder Aufruf wendet seinen Schritt
  relativ zum aktuellen Live-Zustand an. Bei Rotation addieren sich die
  Winkel, bei Scale multiplizieren sich die Faktoren. Mehrere update()-Aufrufe
  erzeugen trotzdem genau einen History-Eintrag (entsteht nur in commit()).
- Der Pivot wird EINMAL in begin() festgelegt und bleibt während der gesamten
  Interaktion fix: context.params["pivot"] oder - wenn nicht gesetzt - der
  Zentroid der betroffenen Vertices im begin()-Moment (Selection Center,
  V1_SPEC §4). Der Pivot wird bewusst NICHT pro update() neu berechnet.
- Der History-Eintrag speichert Start- und Endpositionen (kein Delta) und ist
  damit unabhängig von akkumulierten Rundungsfehlern exakt reversibel.
- cancel() stellt die exakten Ausgangspositionen wieder her (kein History).
- Soft-Selection-Platzhalter wie in MoveOperation: alle Gewichte sind V1 auf
  1.0 gesetzt; die Struktur (`self._weights`) hält die Stelle für ein
  späteres Influence-Map-System frei, ohne den Lifecycle zu ändern.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from ..ids import VertexId
from ..mesh import Mesh, Position
from ..operation import Operation, OperationContext


# --- Minimale Vektor-Hilfsfunktionen auf reinen Tupeln ------------------------
# (bewusst lokal und privat wie in operations/move.py _add; der Core importiert
#  keine Viewport-/Experiment-Module - Dependency-Richtung Core <- Viewport.)

def _add(a: Position, b: Position) -> Position:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _sub(a: Position, b: Position) -> Position:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _scale(a: Position, s: float) -> Position:
    return (a[0] * s, a[1] * s, a[2] * s)


def _dot(a: Position, b: Position) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Position, b: Position) -> Position:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _length(a: Position) -> float:
    return math.sqrt(_dot(a, a))


def _as_triple(factor: "float | Iterable[float]") -> Position:
    """Normalisiert einen Scale-Faktor auf ein Tripel.

    float        → uniformer Faktor auf allen drei Achsen
    3-Tuple/List → per-Achsen-Faktor (inkl. negativer Werte = Spiegelung;
                   die semantische Entscheidung darüber trifft der Aufrufer,
                   nicht die Operation)
    """
    if isinstance(factor, (int, float)):
        f = float(factor)
        return (f, f, f)
    values = tuple(float(v) for v in factor)
    if len(values) != 3:
        raise ValueError(
            f"Scale-Faktor erwartet float oder 3 Komponenten, erhalten {values!r}."
        )
    return values


def rotate_around_axis(
    point: Position, pivot: Position, axis: Position, angle: float
) -> Position:
    """Rotiert `point` um `angle` (Radiant) um die Achse `axis` durch `pivot`.

    Rodrigues-Rotationsformel, Rechte-Hand-Regel. `axis` wird defensiv
    normalisiert; ein Nullvektor ist keine gültige Rotationsachse.
    """
    length = _length(axis)
    if length < 1e-12:
        raise ValueError("Rotationsachse darf nicht der Nullvektor sein.")
    k = _scale(axis, 1.0 / length)
    q = _sub(point, pivot)
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    # q' = q·cos + (k×q)·sin + k·(k·q)·(1-cos)
    rotated = _add(
        _add(_scale(q, cos_a), _scale(_cross(k, q), sin_a)),
        _scale(k, _dot(k, q) * (1.0 - cos_a)),
    )
    return _add(pivot, rotated)


@dataclass
class VertexTransformCommand:
    """Reversibler History-Eintrag für eine abgeschlossene Transformation.

    Gleiche Strategie wie MoveVerticesCommand: Start- und Endpositionen
    (kein Delta), damit undo()/redo() unabhängig von Rundungsfehlern exakt
    reproduzierbar bleiben. `description` unterscheidet die Transform-Art
    in der History ("Rotate Vertices", "Scale Vertices", ...).
    """

    mesh: Mesh
    start_positions: dict[VertexId, Position]
    end_positions: dict[VertexId, Position]
    description: str = "Transform Vertices"

    def undo(self) -> None:
        for vid, pos in self.start_positions.items():
            self.mesh.set_vertex_position(vid, pos)

    def redo(self) -> None:
        for vid, pos in self.end_positions.items():
            self.mesh.set_vertex_position(vid, pos)


class VertexTransformOperation(Operation):
    """Gemeinsame Snapshot-/Commit-/Cancel-Maschinerie für Vertex-Transforms.

    Konkrete Transformationen implementieren ausschließlich
    `_transform_position()`: Abbildung einer AKTUELLEN Vertex-Position auf
    die nächste Position für einen inkrementellen update()-Schritt. Der
    update-Vertrag der Basisklasse (operation.py) bleibt erhalten:
    inkrementell relativ zum aktuellen Live-Zustand, nie History in update().
    """

    description = "Transform Vertices"

    def _on_begin(self, context: OperationContext) -> None:
        mesh: Mesh = context.target
        self._mesh = mesh
        self._vertex_ids = set(context.selection.vertices)
        self._weights: dict[VertexId, float] = {vid: 1.0 for vid in self._vertex_ids}
        self._start_positions: dict[VertexId, Position] = {
            vid: mesh.vertex_position(vid) for vid in self._vertex_ids
        }
        pivot = context.params.get("pivot")
        # Pivot ist ab begin() fix (siehe Modul-Docstring). Default:
        # Zentroid der Startpositionen = Selection Center.
        if pivot is not None:
            self._pivot: Position = (float(pivot[0]), float(pivot[1]), float(pivot[2]))
        else:
            self._pivot = self._selection_center()

    def _selection_center(self) -> Position:
        """Zentroid der Startpositionen (Selection Pivot / Center)."""
        positions = list(self._start_positions.values())
        count = len(positions)
        if count == 0:
            # Leere Auswahl ist ein No-op; der Pivot ist dann bedeutungslos.
            return (0.0, 0.0, 0.0)
        return (
            sum(p[0] for p in positions) / count,
            sum(p[1] for p in positions) / count,
            sum(p[2] for p in positions) / count,
        )

    @property
    def pivot(self) -> Position:
        """Fixer Transform-Pivot dieser Interaktion (seit begin())."""
        return self._pivot

    @property
    def vertex_ids(self) -> set[VertexId]:
        return set(self._vertex_ids)

    def _on_update(self, **kwargs) -> None:
        for vid in self._vertex_ids:
            pos = self._mesh.vertex_position(vid)
            new = self._transform_position(pos, **kwargs)
            weight = self._weights[vid]
            if weight != 1.0:
                # Soft-Selection-Platzhalter: Interpolation zwischen aktueller
                # Position und transformierter Position (Gewicht 1.0 = voll).
                new = _add(pos, _scale(_sub(new, pos), weight))
            self._mesh.set_vertex_position(vid, new)

    def _on_commit(self) -> VertexTransformCommand | None:
        end_positions = {
            vid: self._mesh.vertex_position(vid) for vid in self._vertex_ids
        }
        if end_positions == self._start_positions:
            return None
        return VertexTransformCommand(
            mesh=self._mesh,
            start_positions=dict(self._start_positions),
            end_positions=end_positions,
            description=self.description,
        )

    def _on_cancel(self) -> None:
        for vid, pos in self._start_positions.items():
            self._mesh.set_vertex_position(vid, pos)

    # ------------------------------------------------------------------
    # Von konkreten Transformationen zu implementieren
    # ------------------------------------------------------------------

    def _transform_position(self, pos: Position, **kwargs) -> Position:
        """Abbildung einer aktuellen Position für einen update()-Schritt."""
        raise NotImplementedError


class RotateOperation(VertexTransformOperation):
    """Rotiert die betroffenen Vertices inkrementell um eine feste Achse.

    update(axis=..., angle=...): `axis` ist eine (beliebig skalierte)
    Rotationsachse durch den fixen Pivot (wird normalisiert; Nullvektor
    ungültig), `angle` der inkrementelle Winkel in Radiant. Winkel mehrerer
    update()-Aufrufe akkumulieren sich (inkrementeller Core-Vertrag).
    """

    description = "Rotate Vertices"

    def _transform_position(
        self, pos: Position, axis: Position, angle: float, **_
    ) -> Position:
        return rotate_around_axis(pos, self._pivot, axis, angle)


class ScaleOperation(VertexTransformOperation):
    """Skaliert die betroffenen Vertices inkrementell um den fixen Pivot.

    update(factor=...): `factor` ist ein float (uniform) oder ein 3-Tupel
    (per Achse). Faktoren mehrerer update()-Aufrufe multiplizieren sich
    (inkrementeller Core-Vertrag): zwei updates mit 2.0 erzeugen 4x.
    """

    description = "Scale Vertices"

    def _transform_position(
        self, pos: Position, factor: "float | Iterable[float]", **_
    ) -> Position:
        f = _as_triple(factor)
        q = _sub(pos, self._pivot)
        return _add(self._pivot, (f[0] * q[0], f[1] * q[1], f[2] * q[2]))
