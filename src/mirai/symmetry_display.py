"""Anzeige der Symmetrie in der App: Befund, Ebenen-Umriss, Problem-Marker — GL-frei.

AD-SYM-04 Slice A2 (Q-2 = S-2, Manu 2026-10-14): **verschoben, nicht kopiert** (K-2,
AD-013 I1) aus dem Symmetry Lab — `SymmetryReport`, `symmetry_report` und
`plane_outline_data` aus `experiments/symmetry_lab/lab_symmetry.py` (das Modul ist damit
gelöscht), `geometry_signature`, `only_positions_differ` und `ReportCache` sowie die Ebenen-
und Zustands-Logik der früheren `SymmetryPlaneOverlay`/`SymmetryStateOverlay` aus
`lab_overlays.py`. Das Lab importiert sie von hier; seine Partner-Marker und die
Re-Symmetrize-Vorschau bleiben dort (S-2: keine Partner in der App; die Vorschau gehört zu A3).

Die Symmetrie-*Semantik* (Correspondence, State) kommt unverändert aus `mirai.symmetry`, die
Achse aus `mirai.symmetry_axis` (E1). Hier liegt nur, was angezeigt wird:

- **E4:** keine Toleranz. Vertices knapp neben der Spiegelposition bleiben `UNPAIRED` und
  werden über `SymmetryReport` sichtbar (INV-10).
- `plane_outline_data`: die Ebene als Rechteck-Umriss durch den Ursprung (E1), bemessen auf die
  Mesh-Bounds der beiden Achsen in der Ebene, plus `PLANE_MARGIN`.
- `SymmetryDisplay`: das `Application`-eigene Zusatz-Overlay (Viewport-Vertrag H1:
  `sync(mesh, selection)`, `dirty`, `draw(camera_uniforms)`). Es leitet ab, was zu zeigen ist,
  und schiebt es in eine GL-Senke, die der Host als `symmetry_overlay_type` an
  `Application.init_scene` übergibt (`viewport.gl_symmetry_overlay.GLSymmetryOverlay` über
  `GL_TYPES` in `src/main.py`, Vorbild `soft_overlay_type`). Die Senke kennt keine Symmetrie,
  nur ihre Layer; dieses Modul kennt kein GL.

**Neu berechnet** wird nur, was sich geändert hat (Plan A3 von WP-SYM-LAB-03): Befund und
Umriss hängen an einer billigen Signatur der Geometrie (`geometry_signature`), nicht an Auswahl
oder Hover — eine reine Hover- oder Auswahl-Meldung kostet sie nichts. **Während eines
laufenden Transforms** (`defer()` wahr; `Application`: `interaction_owner == "transform"`) wird
eine reine Positionsänderung nicht neu abgeleitet: Befund und Umriss bleiben die vom
Drag-Start, nur die Marker folgen den bewegten Vertices (eine geänderte Definition, Topologie
oder Seam wird immer sofort abgeleitet). Ein symmetrischer Move erhält die Paarung (Partner
exakt gespiegelt, Seam in der Ebene), die IDs bleiben also gültig. Gemessen im Lab
(Container, `probe_drag_cost.py`): ohne das p95 11,5 ms je Bewegung auf
`man_with_shoes_basemesh`, über der Schwelle von 8 ms. Solange etwas aufgeschoben ist, hält
das Overlay `dirty` gesetzt; der erste `sync()` nach dem Ende (der Commit meldet dem Viewport
nichts) rechnet dann voll.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Optional

from core import Mesh, Selection, VertexId

from .mesh_geometry import mesh_bounds
from .symmetry import (
    CorrespondenceState,
    SymmetryState,
    VertexCorrespondence,
    symmetry_state,
    vertex_correspondence,
)
from .symmetry_axis import AXIS_INDEX, current_axis

#: Umriss ragt um diesen Anteil der größten In-Ebene-Ausdehnung über die Bounds.
PLANE_MARGIN = 0.1


@dataclass(frozen=True)
class SymmetryReport:
    """Was zur aktuellen Definition angezeigt wird (Marker; im Lab auch HUD und Partner)."""

    axis: Optional[str]
    state: SymmetryState
    seam: frozenset[VertexId] = frozenset()
    unpaired: frozenset[VertexId] = frozenset()
    ambiguous: frozenset[VertexId] = frozenset()
    #: Die Zuordnung, aus der der Befund stammt (für Partner-Lookups ohne neue
    #: Ableitung, Plan A3); None bei Symmetrie aus. Nicht Teil des Vergleichs.
    correspondence: Optional[Mapping[VertexId, VertexCorrespondence]] = field(
        default=None, compare=False, repr=False
    )


def symmetry_report(mesh: Mesh) -> SymmetryReport:
    axis = current_axis(mesh)
    if axis is None:
        return SymmetryReport(None, SymmetryState.OFF)
    by_state: dict[CorrespondenceState, set[VertexId]] = {s: set() for s in CorrespondenceState}
    correspondence = vertex_correspondence(mesh)
    for vid, corr in correspondence.items():
        by_state[corr.state].add(vid)
    return SymmetryReport(
        axis=axis,
        state=symmetry_state(mesh),
        seam=frozenset(by_state[CorrespondenceState.SEAM]),
        unpaired=frozenset(by_state[CorrespondenceState.UNPAIRED]),
        ambiguous=frozenset(by_state[CorrespondenceState.AMBIGUOUS]),
        correspondence=correspondence,
    )


def plane_outline_data(mesh: Mesh, axis: Optional[str]) -> list[float]:
    """Linien-Positionen (4 Linien à 2 Punkte, flach) des Ebenen-Umrisses; leer, wenn aus."""
    if axis is None:
        return []
    normal_i = AXIS_INDEX[axis]
    u, w = (i for i in range(3) if i != normal_i)
    lo, hi = mesh_bounds(mesh)
    pad = PLANE_MARGIN * max(hi[u] - lo[u], hi[w] - lo[w], 1e-6)
    corners2d = (
        (lo[u] - pad, lo[w] - pad),
        (hi[u] + pad, lo[w] - pad),
        (hi[u] + pad, hi[w] + pad),
        (lo[u] - pad, hi[w] + pad),
    )
    corners = []
    for cu, cw in corners2d:
        p = [0.0, 0.0, 0.0]
        p[u], p[w] = cu, cw
        corners.append(p)
    positions: list[float] = []
    for a, b in zip(corners, corners[1:] + corners[:1]):
        positions.extend(a)
        positions.extend(b)
    return positions


def geometry_signature(mesh: Mesh) -> tuple:
    """Alles, wovon Ebenen-Umriss und Zustands-Marker abhängen: Definition,
    Vertex-IDs mit Positionen und die Endpunkte der Seam-Edges.

    Der Core hat keinen Änderungszähler (`Mesh` exponiert keinen); das hier kostet
    O(V) Tupel-Zugriffe statt O(V) Spiegelungen + Dict-Lookups des Befunds —
    gemessen (Container) 0,05 ms gegen 4 ms auf `man_with_shoes_basemesh`.
    Bleibt die Reihenfolge von `all_vertex_ids()` nicht gleich, wird nur
    unnötig neu gebaut, nie falsch übersprungen.
    """
    ids = tuple(mesh.all_vertex_ids())
    definition = mesh.symmetry_definition
    seam: tuple = ()
    if definition is not None:
        seam = tuple(
            mesh.edge_vertices(e) if mesh.is_valid_edge(e) else None
            for e in sorted(definition.seam_edges)
        )
    return (definition, ids, tuple(map(mesh.vertex_position, ids)), seam)


def only_positions_differ(old: object, new: tuple) -> bool:
    """Unterscheiden sich zwei Signaturen nur in den Positionen? Nur so eine
    Änderung darf während eines Transforms aufgeschoben werden — eine andere
    Definition, Topologie oder Seam nie (z. B. Shift+S kurz vor W ohne Frame dazwischen)."""
    return (
        isinstance(old, tuple)
        and old[0] == new[0]
        and old[1] == new[1]
        and old[3] == new[3]
    )


def _never() -> bool:
    return False


class ReportCache:
    """Der `SymmetryReport` zur aktuellen Geometrie, neu nur bei geänderter
    `geometry_signature` — eine reine Positionsänderung nicht, solange `defer()`
    wahr ist (laufender Transform, Modul-Docstring)."""

    def __init__(self, defer: Optional[Callable[[], bool]] = None) -> None:
        self.defer = defer or _never
        self._signature: object = None
        self._report: Optional[SymmetryReport] = None
        #: Anzahl der `symmetry_report`-Läufe (Diagnose/Tests, Probe).
        self.recomputes = 0

    def stale(self, signature: tuple) -> bool:
        """Weicht der gelieferte Befund von der Geometrie `signature` ab?"""
        return self._report is None or signature != self._signature

    def current(self, mesh: Mesh, signature: Optional[tuple] = None) -> SymmetryReport:
        """Der Befund genau zur Geometrie `signature`, nie aufgeschoben: für einen Leser, dessen
        Ergebnis zur jetzigen Geometrie passen muss (die Soft-Vorschau der App, AD-SYM-04 SS3,
        deren Gewichte denen des folgenden `begin()` gleichen müssen)."""
        if signature is None:
            signature = geometry_signature(mesh)
        if self.stale(signature):
            self._report = symmetry_report(mesh)
            self._signature = signature
            self.recomputes += 1
        return self._report

    def get(self, mesh: Mesh, signature: Optional[tuple] = None) -> SymmetryReport:
        if signature is None:
            signature = geometry_signature(mesh)
        if self._report is None or (
            signature != self._signature
            and not (only_positions_differ(self._signature, signature) and self.defer())
        ):
            self._report = symmetry_report(mesh)
            self._signature = signature
            self.recomputes += 1
        return self._report


def _positions(mesh: Mesh, ids) -> list:
    return [mesh.vertex_position(v) for v in sorted(ids, key=int)]


def _segments(flat: list[float]) -> list:
    points = [tuple(flat[i:i + 3]) for i in range(0, len(flat), 3)]
    return list(zip(points[0::2], points[1::2]))


class SymmetryDisplay:
    """Ebenen-Umriss und Problem-Marker (Seam, ohne Partner, mehrdeutig) als Zusatz-Overlay
    der App; alles leer bei Symmetrie aus. `Application.init_scene` baut es, wenn der Host
    `symmetry_overlay_type` übergibt, und hängt es an den Viewport (H1).

    `sink` = die GL-Senke (`set_segments(segments)`, `set_markers(seam, unpaired, ambiguous)`
    mit Weltpositionen, `draw(camera_uniforms)`; Layer, Farben und Größen kennt nur sie);
    `defer` = „läuft gerade ein Transform?" (Modul-Docstring); `reports` = ein Befund-Cache, den
    der Besitzer mit anderen Lesern teilt (die App: mit der Soft-Vorschau, AD-SYM-04 SS3) —
    dann gilt dessen `defer`, nicht das übergebene."""

    def __init__(
        self,
        sink,
        defer: Optional[Callable[[], bool]] = None,
        reports: Optional[ReportCache] = None,
    ) -> None:
        self.sink = sink
        self.reports = reports if reports is not None else ReportCache(defer)
        #: Viewport-Vertrag H1: True = beim nächsten Frame `sync()` aufrufen, auch ohne Meldung.
        self.dirty = False
        self._outlined: Optional[SymmetryReport] = None
        #: Anzahl der Umriss-Neuberechnungen (Diagnose/Tests).
        self.plane_recomputes = 0

    @property
    def recomputes(self) -> int:
        """Läufe des Symmetrie-Befunds (die teure Hälfte, Plan A3)."""
        return self.reports.recomputes

    @property
    def report(self) -> Optional[SymmetryReport]:
        """Der zuletzt angezeigte Befund (None vor dem ersten `sync()`)."""
        return self._outlined

    def sync(self, mesh: Mesh, selection: Selection) -> None:
        if (
            mesh.symmetry_definition is None
            and self._outlined is not None
            and self._outlined.axis is None
        ):
            # Symmetrie aus und schon leer: nichts hängt an der Geometrie. Spart jedem Drag
            # ohne Symmetrie die O(V)-Signatur; eine neue Definition ändert die Signatur.
            self.dirty = False
            return
        signature = geometry_signature(mesh)
        report = self.reports.get(mesh, signature)
        # Umriss und Befund hängen an derselben Signatur mit derselben Aufschub-Regel: der
        # Umriss wird genau dann neu gebaut, wenn ein neuer Befund entsteht.
        if report is not self._outlined:
            self._outlined = report
            self.sink.set_segments(_segments(plane_outline_data(mesh, report.axis)))
            self.plane_recomputes += 1
        # Positionen immer aus dem aktuellen Mesh: während eines Transforms wandern die
        # Marker mit, auch wenn ihre IDs vom Drag-Start stammen. Die Senke baut nur neu,
        # wenn sich die Punkte wirklich ändern.
        self.sink.set_markers(
            _positions(mesh, report.seam),
            _positions(mesh, report.unpaired),
            _positions(mesh, report.ambiguous),
        )
        self.dirty = self.reports.defer() and self.reports.stale(signature)

    def draw(self, camera_uniforms) -> None:
        self.sink.draw(camera_uniforms)
