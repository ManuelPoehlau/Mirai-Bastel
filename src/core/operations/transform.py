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
- Gewichte (Soft Selection, AD-SYM-05 SS1): `params["influence"]` ist eine
  Abbildung VertexId -> Gewicht in (0, 1], Schlüssel = genau die Vertex-Menge der
  Operation. Ohne den Schlüssel läuft byte-identisch der ungewichtete Pfad. Mit ihm
  gewichtet jede Operation ihren eigenen Parameter (Move `w·Δ`, Rotate `w·θ`, Scale
  `1 + w(F − 1)`), danach greift die Symmetrie-Kategorie; `w == 1.0` nimmt die
  ungewichtete Arithmetik auf der Live-Position. Rotate/Scale brauchen mit Gewichten
  `params["pivot"]` (der Default wäre der Zentroid der *beeinflussten* Menge).
- **Sichtbare Abweichung vom inkrementellen Vertrag (operation.py, AD-SYM-05 §4.4):**
  mit `params["influence"]` werden Scale-Vertices mit `w < 1` und die
  Falloff-Seam-Vertices von Rotate/Scale ABSOLUT aus dem begin()-Snapshot
  (`_start_positions`) mit dem seit begin() akkumulierten Faktor `F` bzw. Winkel `Θ`
  ausgewertet: `1 + w(F − 1)` ist nicht multiplikativ, und Drehen-dann-Projizieren
  hängt von der Zerlegung des Drags in Schritte ab. Alles andere bleibt inkrementell.
  Dafür fixiert ein gewichtetes Scale die Basis für die ganze Geste, ein gewichtetes
  Rotate mit Falloff-Seam-Vertices die Achse; ungewichtet wird nichts akkumuliert und
  nichts fixiert.
- Symmetrie (AD-SYM-02 §2.4): `_on_update()` reicht die gerade verarbeitete
  `VertexId` als `vertex_id=` an `_transform_position()` durch (WP-SYM-01
  Slice 2, für Move). Rotate/Scale (WP-SYM-LAB-02 S2) lesen den Symmetriekontext
  aus `OperationContext.params["symmetry"]` (derselbe Kanal und dieselbe Form wie
  bei Move: `plane_normal`, `mirrored_vertex_ids`, `seam_vertex_ids`; zusätzlich
  `plane_point`, weil ein Pivot eine *Position* ist und sich nur mit Ebenenpunkt
  spiegeln lässt). Siehe `_PivotTransformOperation`. Nur mit Gewichten kommt eine
  vierte Kategorie dazu, `falloff_seam_vertex_ids` (AD-SYM-05 §4.3, P-a): Seam-Vertices,
  die nur der Falloff erreicht - gewichteter Schritt, exakt auf die Ebene projiziert,
  von BEIDEN Seam-Prüfungen ausgenommen (die gelten weiter nur für `seam_vertex_ids`).
  Dass die beiden Partner eines Paars dasselbe Gewicht und entgegengesetzte Kategorien
  tragen, ist Vorbedingung des Aufrufers; der Core leitet keine Correspondence ab.
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

    Konkrete Transformationen implementieren `_transform_position()`: Abbildung
    einer AKTUELLEN Vertex-Position auf die nächste Position für einen
    inkrementellen update()-Schritt. Der update-Vertrag der Basisklasse
    (operation.py) bleibt erhalten: inkrementell relativ zum aktuellen
    Live-Zustand, nie History in update().

    Gewichtet (`params["influence"]`, Modul-Docstring) ruft die Schleife statt
    dessen `_weighted_position()` mit dem Gewicht des Vertex; eine Operation ohne
    diesen Haken lehnt `params["influence"]` in begin() ab.
    """

    description = "Transform Vertices"
    #: Mit Gewichten ist `params["pivot"]` Pflicht (AD-SYM-05 §4.1, AD-020 E7).
    _weighted_needs_pivot = False

    def _on_begin(self, context: OperationContext) -> None:
        mesh: Mesh = context.target
        vertex_ids = set(context.selection.vertices)
        influence = context.params.get("influence")
        # Erst prüfen, dann speichern (AD-SYM-05 §4.1); ohne Schlüssel der heutige Pfad.
        weights = (
            None if influence is None
            else self._validated_influence(context.params, influence, vertex_ids)
        )
        self._mesh = mesh
        self._vertex_ids = vertex_ids
        self._weighted = weights is not None
        self._weights: dict[VertexId, float] = (
            weights if weights is not None else {vid: 1.0 for vid in self._vertex_ids}
        )
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

    def _validated_influence(
        self, params: dict, influence, vertex_ids: set[VertexId]
    ) -> dict[VertexId, float]:
        name = type(self).__name__
        if type(self)._weighted_position is VertexTransformOperation._weighted_position:
            raise ValueError(f"{name} does not support params['influence'].")
        if self._weighted_needs_pivot and params.get("pivot") is None:
            raise ValueError(
                f"{name} needs params['pivot'] with params['influence']; the default "
                "would be the centroid of the influenced set."
            )
        weights: dict[VertexId, float] = {}
        for vid, w in influence.items():
            w = float(w)
            if not (0.0 < w <= 1.0):  # NaN fails the comparison as well
                raise ValueError(f"Influence weight for {vid!r} must be in (0, 1], got {w!r}.")
            weights[vid] = w
        if set(weights) != vertex_ids:
            raise ValueError(
                "The selection must be exactly the influenced vertex set "
                f"({len(vertex_ids)} selected, {len(weights)} weighted)."
            )
        return weights

    def _read_falloff_seam(
        self,
        symmetry: dict,
        seam_vertex_ids: frozenset[VertexId],
        mirrored_vertex_ids: frozenset[VertexId],
    ) -> frozenset[VertexId]:
        """`falloff_seam_vertex_ids` (AD-SYM-05 §4.3) prüfen und zurückgeben.

        Ein gewählter Seam-Vertex ist ein Seed, der nach heutigen Regeln läuft: mit
        Gewichten muss er genau 1.0 tragen (review R-7)."""
        falloff = frozenset(symmetry.get("falloff_seam_vertex_ids", ()))
        if falloff and not self._weighted:
            raise ValueError("falloff_seam_vertex_ids needs params['influence'].")
        if falloff & seam_vertex_ids or falloff & mirrored_vertex_ids:
            raise ValueError(
                "falloff_seam_vertex_ids must be disjoint from seam_vertex_ids and "
                "mirrored_vertex_ids."
            )
        if self._weighted:
            for vid in seam_vertex_ids:
                w = self._weights.get(vid)
                if w is not None and w != 1.0:
                    raise ValueError(
                        f"Selected seam vertex {vid!r} needs weight 1.0, got {w!r}."
                    )
        return falloff

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
        if self._weighted:
            weights = self._weights
            for vid in self._vertex_ids:
                pos = self._mesh.vertex_position(vid)
                new = self._weighted_position(pos, weights[vid], vertex_id=vid, **kwargs)
                self._mesh.set_vertex_position(vid, new)
            return
        for vid in self._vertex_ids:
            pos = self._mesh.vertex_position(vid)
            new = self._transform_position(pos, vertex_id=vid, **kwargs)
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

    def _weighted_position(self, pos: Position, weight: float, **kwargs) -> Position:
        """Gewichteter Schritt (nur mit `params["influence"]`, AD-SYM-05 §4.2)."""
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

    Mit Gewichten zusätzlich `falloff_seam_vertex_ids` (P-a, AD-SYM-05 §4.3): absolut aus
    dem Start ausgewertet, dann projiziert; keine der beiden Seam-Prüfungen. Reihenfolge
    eines gewichteten update(): prüfen (Basis/Achse fix, Faktor/Winkel endlich, Seam-Schritt
    für `seam_vertex_ids`) → akkumulieren → Schleife; eine Ablehnung lässt Positionen und
    Summen unverändert.

    Der Pivot ist EINMAL gesetzt (Default oder `params["pivot"]`) und wird für Partner
    gespiegelt - kein fest verdrahteter Zentroid in der Operation. Auswahl
    UND Partner liefert der Aufrufer (Tool) in `context.selection`.
    """

    supports_symmetry = True
    _weighted_needs_pivot = True

    def _on_begin(self, context: OperationContext) -> None:
        super()._on_begin(context)
        symmetry = context.params.get("symmetry")
        self._mirrored_vertex_ids: frozenset[VertexId] = frozenset()
        self._seam_vertex_ids: frozenset[VertexId] = frozenset()
        self._falloff_seam_vertex_ids: frozenset[VertexId] = frozenset()
        self._plane_normal: Position | None = None
        self._plane_point: Position = (0.0, 0.0, 0.0)
        if symmetry is None:
            return
        self._mirrored_vertex_ids = frozenset(symmetry.get("mirrored_vertex_ids", ()))
        self._seam_vertex_ids = frozenset(symmetry.get("seam_vertex_ids", ()))
        self._plane_normal = symmetry["plane_normal"]
        self._plane_point = tuple(symmetry.get("plane_point", (0.0, 0.0, 0.0)))
        self._falloff_seam_vertex_ids = self._read_falloff_seam(
            symmetry, self._seam_vertex_ids, self._mirrored_vertex_ids
        )
        if self._seam_vertex_ids and not pivot_on_plane(
            self._pivot, self._plane_point, self._plane_normal
        ):
            raise SeamConstraintError("Pivot liegt nicht auf der Symmetrieebene")

    def _on_update(self, **kwargs) -> None:
        if self._weighted:
            self._check_weighted_step(**kwargs)
        if self._seam_vertex_ids:
            self._check_seam_step(**kwargs)
        if self._weighted:
            self._accumulate(**kwargs)
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

    def _check_weighted_step(self, **kwargs) -> None:
        raise NotImplementedError

    def _accumulate(self, **kwargs) -> None:
        raise NotImplementedError


class RotateOperation(_PivotTransformOperation):
    """Rotiert die betroffenen Vertices inkrementell um eine feste Achse.

    update(axis=..., angle=...): `axis` ist eine (beliebig skalierte)
    Rotationsachse durch den fixen Pivot (wird normalisiert; Nullvektor
    ungültig), `angle` der inkrementelle Winkel in Radiant. Winkel mehrerer
    update()-Aufrufe akkumulieren sich (inkrementeller Core-Vertrag).

    Gewichtet: Rotation um `w·angle`, inkrementell (Drehungen um eine Achse addieren
    sich). Nur mit Falloff-Seam-Vertices wird `Θ` akkumuliert, die Achse für die Geste
    fixiert und ein nicht-endlicher Winkel abgelehnt (AD-SYM-05 §4.4, review R-1): ohne
    sie nimmt ein gewichtetes Rotate wie bisher je update() eine neue Achse an.
    """

    description = "Rotate Vertices"

    def _on_begin(self, context: OperationContext) -> None:
        super()._on_begin(context)
        self._total_angle = 0.0
        self._fixed_axis: Position | None = None

    def _apply(self, pos: Position, axis: Position, angle: float, **_) -> Position:
        return rotate_around_axis(pos, self._pivot, axis, angle)

    def _check_seam_step(self, axis: Position, **_) -> None:
        if not rotation_keeps_plane(axis, self._plane_normal):
            raise SeamConstraintError(
                "Rotation um diese Achse würde den Seam-Vertex von der Ebene lösen "
                "(nur Achse parallel zur Ebenennormale)"
            )

    def _check_weighted_step(self, axis: Position, angle: float, **_) -> None:
        if not self._falloff_seam_vertex_ids:
            return
        a = (float(axis[0]), float(axis[1]), float(axis[2]))
        if self._fixed_axis is not None and a != self._fixed_axis:
            raise ValueError(
                "RotateOperation with falloff seam vertices needs the same axis for the "
                "whole gesture."
            )
        if _length(a) < 1e-12:
            raise ValueError("Rotationsachse darf nicht der Nullvektor sein.")
        if not math.isfinite(angle):
            raise ValueError(f"Rotation angle must be finite, got {angle!r}.")

    def _accumulate(self, axis: Position, angle: float, **_) -> None:
        if not self._falloff_seam_vertex_ids:
            return
        if self._fixed_axis is None:
            self._fixed_axis = (float(axis[0]), float(axis[1]), float(axis[2]))
        self._total_angle += angle

    def _weighted_position(
        self, pos: Position, weight: float, vertex_id: VertexId | None = None, *,
        axis: Position, angle: float, **kwargs,
    ) -> Position:
        if vertex_id in self._falloff_seam_vertex_ids:
            # Absolut: Drehen-dann-Projizieren hängt sonst von der Zerlegung des Drags ab.
            new = rotate_around_axis(
                self._start_positions[vertex_id], self._pivot, self._fixed_axis,
                weight * self._total_angle,
            )
            return _project_to_plane(new, self._plane_point, self._plane_normal)
        return self._transform_position(
            pos, vertex_id=vertex_id, axis=axis,
            angle=angle if weight == 1.0 else weight * angle, **kwargs,
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

    Gewichtet: je Basisachse `1 + w(F − 1)` mit `F` dem seit begin() akkumulierten
    Faktor, für `w < 1` absolut aus dem Start (der Ausdruck ist nicht multiplikativ, kein
    inkrementeller Weg ist pfadunabhängig); `w == 1` inkrementell wie ungewichtet. Die
    Basis gilt dann für die ganze Geste, ein Faktor muss endlich sein (AD-SYM-05 §4.4).
    """

    description = "Scale Vertices"

    def _on_begin(self, context: OperationContext) -> None:
        super()._on_begin(context)
        self._total_factor: Position = (1.0, 1.0, 1.0)
        self._basis_fixed = False
        self._fixed_basis: "tuple[Position, Position, Position] | None" = None

    def _check_seam_step(self, factor, basis=None, **_) -> None:
        if not scale_keeps_plane(factor, basis, self._plane_normal):
            raise SeamConstraintError(
                "Skalierung würde den Seam-Vertex von der Ebene lösen "
                "(nur uniform oder an der Ebenennormale ausgerichtet)"
            )

    def _check_weighted_step(self, factor, basis=None, **_) -> None:
        f = _as_triple(factor)
        if not all(math.isfinite(v) for v in f):
            raise ValueError(f"Scale factor must be finite, got {f!r}.")
        if self._basis_fixed and basis != self._fixed_basis:
            raise ValueError(
                f"{type(self).__name__} needs the same basis for the whole gesture."
            )

    def _accumulate(self, factor, basis=None, **_) -> None:
        f = _as_triple(factor)
        t = self._total_factor
        self._total_factor = (t[0] * f[0], t[1] * f[1], t[2] * f[2])
        self._basis_fixed = True
        self._fixed_basis = basis

    def _weighted_factor(self, weight: float) -> Position:
        t = self._total_factor
        return (1.0 + weight * (t[0] - 1.0), 1.0 + weight * (t[1] - 1.0), 1.0 + weight * (t[2] - 1.0))

    def _weighted_position(
        self, pos: Position, weight: float, vertex_id: VertexId | None = None, *,
        factor: "float | Iterable[float]",
        basis: "tuple[Position, Position, Position] | None" = None, **kwargs,
    ) -> Position:
        if vertex_id in self._falloff_seam_vertex_ids:
            # Absolut auch bei w == 1: gedrehte Basis und Projektion kommutieren nicht.
            new = self._apply(
                self._start_positions[vertex_id], factor=self._weighted_factor(weight),
                basis=basis,
            )
            return _project_to_plane(new, self._plane_point, self._plane_normal)
        if weight == 1.0:
            return self._transform_position(
                pos, vertex_id=vertex_id, factor=factor, basis=basis, **kwargs
            )
        return self._transform_position(
            self._start_positions[vertex_id], vertex_id=vertex_id,
            factor=self._weighted_factor(weight), basis=basis, **kwargs,
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
