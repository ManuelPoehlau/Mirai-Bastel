"""Transform-Foundation: wiederverwendbare Vertex-Transformationen (WP-03, WP-A).

Bezug: ROADMAP.md §5 WP-03 (Transform Foundation), V1_SPEC.md §4 (Transform).

Rotate, Scale, und Move folgen alle demselben interaktiven Lifecycle-Vertrag
(AD-003): begin() → update()* → commit() | cancel(). Gemeinsame Basis
VertexTransformOperation eliminates duplication. MoveOperation was the first
WP-02 prototype before Rotate/Scale existed; consolidated onto this base
in WP-A (Move Unification).

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
- Symmetrie (AD-SYM-02 §2.4): `_on_update()` reicht die gerade verarbeitete
  `VertexId` als `vertex_id=` an `_transform_position()` durch (WP-SYM-01
  Slice 2, für Move). Rotate/Scale (WP-SYM-LAB-02 S2) lesen den Symmetriekontext
  aus `OperationContext.params["symmetry"]` (derselbe Kanal und dieselbe Form wie
  bei Move: `plane_normal`, `mirrored_vertex_ids`, `seam_vertex_ids`; zusätzlich
  `plane_point`, weil ein Pivot eine *Position* ist und sich nur mit Ebenenpunkt
  spiegeln lässt). Siehe `_PivotTransformOperation`.
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


#: Absolute Toleranz (Mesh-Einheiten bzw. Einheitsvektor-Komponenten), mit der der
#: Seam-Vertrag prüft, ob ein Pivot auf der Ebene liegt und eine Achse/Skalierung
#: die Ebene erhält. Agent-Annahme (WP-SYM-LAB-02 S2): Pivots entstehen als
#: Zentroid über gespiegelte Paare und tragen Rundungsreste (~1e-17); `mirai.symmetry`
#: selbst vergleicht exakt (AR-1). Innerhalb der Toleranz wird das Seam-Ergebnis exakt
#: auf die Ebene projiziert, damit es nie als VIOLATED erscheint.
SEAM_TOLERANCE = 1e-9


class SeamConstraintError(ValueError):
    """Die Transformation könnte einen Seam-Vertex von der Symmetrieebene lösen (INV-2/INV-8).

    Wird von der Operation als Rückhalt geworfen und von den Tools beim Scharfschalten
    VOR der ersten Bewegung als sichtbare Ablehnung ausgelöst - nie stilles Driften."""


def _signed_distance(point: Position, plane_point: Position, normal: Position) -> float:
    return sum((p - o) * n for p, o, n in zip(point, plane_point, normal))


def mirror_point(point: Position, plane_point: Position, normal: Position) -> Position:
    """Spiegelt eine *Position* an der Ebene. Rechenweg bewusst identisch zu
    `mirai.symmetry.mirror_position` (der Core importiert nicht aus `mirai`), damit
    das Ergebnis bitgleich ist - die Correspondence-Ableitung vergleicht exakt."""
    distance = _signed_distance(point, plane_point, normal)
    return tuple(p - 2.0 * distance * n for p, n in zip(point, normal))


def _project_to_plane(point: Position, plane_point: Position, normal: Position) -> Position:
    distance = _signed_distance(point, plane_point, normal)
    return tuple(p - distance * n for p, n in zip(point, normal))


def pivot_on_plane(
    pivot: Position, plane_point: Position, normal: Position, tol: float = SEAM_TOLERANCE
) -> bool:
    return abs(_signed_distance(pivot, plane_point, normal)) <= tol


def rotation_keeps_plane(axis: Position, normal: Position, tol: float = SEAM_TOLERANCE) -> bool:
    """Rotation um `axis` (durch einen Pivot auf der Ebene) erhält die Ebene genau dann,
    wenn die Achse parallel zur Ebenennormale liegt."""
    length = _length(axis)
    if length < 1e-12:
        return False
    return _length(_cross(_scale(axis, 1.0 / length), normal)) <= tol


def scale_keeps_plane(
    factor: "float | Iterable[float]",
    basis: "tuple[Position, Position, Position] | None",
    normal: Position,
    tol: float = SEAM_TOLERANCE,
) -> bool:
    """Skalierung um einen Pivot auf der Ebene erhält die Ebene genau dann, wenn die
    Normale Eigenvektor von A = sum(f_i * b_i b_i^T) ist (uniform, oder eine Basisachse
    liegt auf der Normalen)."""
    f = _as_triple(factor)
    b = basis if basis is not None else ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    an = (0.0, 0.0, 0.0)
    for fi, bi in zip(f, b):
        an = _add(an, _scale(bi, fi * _dot(bi, normal)))
    perpendicular = _sub(an, _scale(normal, _dot(an, normal)))
    return _length(perpendicular) <= tol * max(1.0, *(abs(v) for v in f))


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
            new = self._transform_position(pos, vertex_id=vid, **kwargs)
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


class _PivotTransformOperation(VertexTransformOperation):
    """Rotate/Scale unter Symmetrie (AD-SYM-02 §2.4, WP-SYM-LAB-02 S2).

    `params["symmetry"]` wie bei Move: `plane_normal`, `mirrored_vertex_ids`,
    `seam_vertex_ids` (+ `plane_point`, Default Ursprung). Drei Vertexkategorien:

    - Direkt gewählte Vertices: die gewöhnliche Transformation um den Pivot.
    - Gespiegelte Partner (`mirrored_vertex_ids`): die *konjugierte Absicht* - Rotation
      um spiegel(Pivot) um spiegel(Achse) mit -Winkel, bzw. Skalierung um spiegel(Pivot)
      mit Faktor je Basisachse b_i entlang spiegel(b_i) (Spiegelung kehrt die
      Händigkeit um). Berechnet wird sie als spiegel(T(spiegel(p))): mathematisch
      identisch, aber T läuft mit denselben Eingaben wie auf der Quellseite, das
      Ergebnis ist also die exakte Spiegelung der Quellposition (bitgleich bei
      achsenparallelen Ebenen). Das ist nötig, weil `mirai.symmetry` Partner per exakter
      Positionsgleichheit findet - eine Näherung würde das Paar zu UNPAIRED machen.
    - Seam-Vertices: gewöhnliche Transformation, danach exakt auf die Ebene projiziert.
      Nur zulässig, wenn der Pivot auf der Ebene liegt UND die Transformation die Ebene
      erhält (siehe `rotation_keeps_plane`/`scale_keeps_plane`); sonst `SeamConstraintError`
      (Pivot-Prüfung in begin(), Achse/Faktor vor dem ersten Schritt eines update()).

    Der Pivot ist EINMAL gesetzt (Default oder `params["pivot"]`) und wird für Partner
    gespiegelt - kein fest verdrahteter Zentroid in der Operation. Auswahl
    UND Partner liefert der Aufrufer (Tool) in `context.selection`.
    """

    supports_symmetry = True

    def _on_begin(self, context: OperationContext) -> None:
        super()._on_begin(context)
        symmetry = context.params.get("symmetry")
        self._mirrored_vertex_ids: frozenset[VertexId] = frozenset()
        self._seam_vertex_ids: frozenset[VertexId] = frozenset()
        self._plane_normal: Position | None = None
        self._plane_point: Position = (0.0, 0.0, 0.0)
        if symmetry is None:
            return
        self._mirrored_vertex_ids = frozenset(symmetry.get("mirrored_vertex_ids", ()))
        self._seam_vertex_ids = frozenset(symmetry.get("seam_vertex_ids", ()))
        self._plane_normal = symmetry["plane_normal"]
        self._plane_point = tuple(symmetry.get("plane_point", (0.0, 0.0, 0.0)))
        if self._seam_vertex_ids and not pivot_on_plane(
            self._pivot, self._plane_point, self._plane_normal
        ):
            raise SeamConstraintError("Pivot liegt nicht auf der Symmetrieebene")

    def _on_update(self, **kwargs) -> None:
        if self._seam_vertex_ids:
            self._check_seam_step(**kwargs)
        super()._on_update(**kwargs)

    def _transform_position(
        self, pos: Position, vertex_id: VertexId | None = None, **kwargs
    ) -> Position:
        if vertex_id in self._mirrored_vertex_ids:
            mirrored = mirror_point(pos, self._plane_point, self._plane_normal)
            return mirror_point(
                self._apply(mirrored, **kwargs), self._plane_point, self._plane_normal
            )
        new = self._apply(pos, **kwargs)
        if vertex_id in self._seam_vertex_ids:
            new = _project_to_plane(new, self._plane_point, self._plane_normal)
        return new

    def _apply(self, pos: Position, **kwargs) -> Position:
        raise NotImplementedError

    def _check_seam_step(self, **kwargs) -> None:
        raise NotImplementedError


class RotateOperation(_PivotTransformOperation):
    """Rotiert die betroffenen Vertices inkrementell um eine feste Achse.

    update(axis=..., angle=...): `axis` ist eine (beliebig skalierte)
    Rotationsachse durch den fixen Pivot (wird normalisiert; Nullvektor
    ungültig), `angle` der inkrementelle Winkel in Radiant. Winkel mehrerer
    update()-Aufrufe akkumulieren sich (inkrementeller Core-Vertrag).
    """

    description = "Rotate Vertices"

    def _apply(self, pos: Position, axis: Position, angle: float, **_) -> Position:
        return rotate_around_axis(pos, self._pivot, axis, angle)

    def _check_seam_step(self, axis: Position, **_) -> None:
        if not rotation_keeps_plane(axis, self._plane_normal):
            raise SeamConstraintError(
                "Rotation um diese Achse würde den Seam-Vertex von der Ebene lösen "
                "(nur Achse parallel zur Ebenennormale)"
            )


class ScaleOperation(_PivotTransformOperation):
    """Skaliert die betroffenen Vertices inkrementell um den fixen Pivot.

    update(factor=..., basis=None): `factor` ist ein float (uniform) oder
    ein 3-Tupel (per Achse). Faktoren mehrerer update()-Aufrufe multiplizieren
    sich (inkrementeller Core-Vertrag): zwei updates mit 2.0 erzeugen 4x.

    `basis` ist ein optionales Tupel aus drei orthonormalen Vektoren (b0, b1,
    b2). Wenn angegeben, wird `factor` gegen diese Basis dekomponiert statt
    gegen die impliziten Weltachsen:

        q = pos - pivot
        c0, c1, c2 = dot(q,b0), dot(q,b1), dot(q,b2)
        result = pivot + f0*c0*b0 + f1*c1*b1 + f2*c2*b2

    `basis=None` (Standard) erhält das exakte heutige Verhalten — die
    Weltachsen-Diagonalformel. Inkrementeller Vertrag gilt für beide Pfade.
    """

    description = "Scale Vertices"

    def _check_seam_step(self, factor, basis=None, **_) -> None:
        if not scale_keeps_plane(factor, basis, self._plane_normal):
            raise SeamConstraintError(
                "Skalierung würde den Seam-Vertex von der Ebene lösen "
                "(nur uniform oder an der Ebenennormale ausgerichtet)"
            )

    def _apply(
        self,
        pos: Position,
        factor: "float | Iterable[float]",
        basis: "tuple[Position, Position, Position] | None" = None,
        **_,
    ) -> Position:
        f = _as_triple(factor)
        q = _sub(pos, self._pivot)
        if basis is None:
            return _add(self._pivot, (f[0] * q[0], f[1] * q[1], f[2] * q[2]))
        b0, b1, b2 = basis
        c0, c1, c2 = _dot(q, b0), _dot(q, b1), _dot(q, b2)
        scaled = _add(
            _add(_scale(b0, f[0] * c0), _scale(b1, f[1] * c1)),
            _scale(b2, f[2] * c2),
        )
        return _add(self._pivot, scaled)
