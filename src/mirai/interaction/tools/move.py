"""MoveTool: Referenz-Tool der Produktions-Application.

Pfad:

    Command.Move
        ↓
    MoveTool
        ↓
    Core-MoveOperation (src/core)
        ↓
    Mesh / History

Verantwortlichkeiten (INPUT_COMMAND_TOOL_CONTRACT.md §2):

- MoveTool besitzt temporären Interaktionszustand (Anchor-Vertex, laufende
  MoveOperation, Menge der betroffenen Vertex-IDs, optionale Achsen-/
  Ebenen-Maske, optional normal für "space='normal'"-Constraint).
- Die eigentliche persistente Domain-Mutation macht die bestehende
  `MoveOperation` aus `src.core` — es wird bewusst KEINE zweite
  Move-Mutationslogik gebaut.
- Selection ist kein Tool: Sie bleibt Core-Domain-State. Die Auflösung
  Selection → betroffene Vertex-IDs übernimmt die reine Hilfsfunktion
  `resolve_selection_vertices()`.

begin(vertex_ids=..., space=None, pivot=None, derived_geometry=None) (AD-009, analog Rotate/Scale):

    space=None          → frei auf der Bildebene der Kamera (bisheriges Verhalten).
    space="x"/"y"/"z"   → Bewegung nur entlang dieser Weltachse.
    space="xy"/"yz"/"xz" → Bewegung in dieser Weltebene (die jeweils dritte
                          Komponente bleibt gesperrt).
    space="normal"      → Bewegung entlang der aus der Selection abgeleiteten Normal.

Constraint-Mechanik: Das ohnehin über die Bildebene berechnete Welt-Delta
wird komponentenweise mit der Achsen-/Ebenenmaske multipliziert (identisches
Prinzip wie bei `ScaleTool.axes_mask` — siehe `transform.py::_WORLD_AXES`),
statt eine zweite, unabhängige Constraint-Mathematik einzuführen.

Produktions-Design (WP-04): parameterloser `__init__`; `scene`, `camera`
und `vertex_ids` kommen über den Interaktions-Kontext in
`_on_begin(scene=..., camera=..., vertex_ids=...)` (Pattern A/B).

Bewusst pyglet-frei und ohne physische Key-/Button-Konstanten: Pointer-
Bewegung wird als semantisches Pixel-Delta übergeben und erst hier mit der
Kamera-Hilfsfunktion in ein Welt-Delta übersetzt.

Soft Selection (WP-SOFT-01 S2a, AD-020, `PROVISIONAL`): `begin(soft=SoftSettings)` (nur wenn
die Einstellung an ist - sonst fehlt der Parameter und nichts ändert sich) berechnet aus den
Seeds (`vertex_ids`) die Influence-Map und startet statt der `MoveOperation` die
`SoftMoveOperation` (`params["influence"]`). `.moves` berichtet dann die beeinflusste
Menge; der Anchor bleibt ein Seed (`min(vertex_ids)`), die Bildebenen-Abbildung ist die
des normalen Move. Unter Symmetrie (AD-SYM-04 SS2) kommen Gewichte und Kategorien aus
`soft_selection.symmetric_influence` (ein Gewicht pro Spiegelpaar).

Symmetrisches Move (AD-SYM-02 §2.4, WP-SYM-01 Slice 2): Ist eine Symmetry
Definition aktiv, löst `_on_begin()` die gespiegelten Partner-Vertices der
Artist-Auswahl auf (`mirai.symmetry.mirrored_selection()`) - analog zu
`resolve_selection_vertices()` - und klassifiziert die Seam-Vertices unter
den selektierten. Beide Mengen reisen über
`OperationContext.params["symmetry"]` in die bestehende `MoveOperation`
(AD-SYM-02 §2.2: kein neues Feld an `OperationContext`, keine
MirrorResult-Struktur). Die eigentliche Spiegel-/Projektions-Mechanik lebt
in `core.operations.move.MoveOperation`, nicht hier - MoveTool löst nur auf,
was betroffen ist, es rechnet nicht selbst.
"""

from __future__ import annotations

from typing import Any

from core import (
    MoveOperation,
    OperationContext,
    VertexId,
)

from ...mask import mask_symmetric_influence, mask_weights, unblocked
from ...soft_selection import SoftMoveOperation, compute_influence, symmetric_influence
from ...symmetry import CorrespondenceState, mirrored_selection, vertex_correspondence
from ..tool import Tool, ToolStateError
from .selection_helpers import _VertexSelectionView
from .transform import _resolve_space, world_masked_delta


class MoveTool(Tool):
    """Modal-interaktives Move-Tool auf Basis der bestehenden MoveOperation.

    Lifecycle-Zustellung (ToolManager):

        activate()  → Tool bereit (keine Interaktion)
        begin(scene=..., camera=..., vertex_ids=...) → MoveOperation.begin()
        update(dx, dy, width, height)* → MoveOperation.update(delta=…)
        commit()    → MoveOperation.commit()  (genau eine History-Grenze)
        cancel()    → MoveOperation.cancel()  (exakter Vorzustand, keine History)
        deactivate()→ Rückkehr nach IDLE, ohne die History zu berühren
    """

    def __init__(self) -> None:
        super().__init__()
        self._scene = None
        self._camera = None
        self._operation: MoveOperation | None = None
        self._mask: dict = {}
        self._vertex_ids: set[VertexId] = set()
        self._anchor_vertex: VertexId | None = None
        self._axes_mask: tuple[float, float, float] = (1.0, 1.0, 1.0)
        self._normal: tuple[float, float, float] | None = None  # Für space="normal" single-axis
        self._plane_exclude: tuple[float, float, float] | None = None  # Für space="normal" plane (WP-03D)
        # Symmetric Soft with seeds only on the seam (AD-SYM-04 SS2): the step stays parallel to
        # the mirror plane, so both sides move alike (`SymmetricInfluence.in_plane_only`).
        self._in_plane_normal: tuple[float, float, float] | None = None
        # The seeds of a running Soft gesture (None without Soft) and the sum of the deltas handed to
        # the op since begin(): what `reweight()` re-begins from and replays.
        self._soft_seeds: frozenset[VertexId] | None = None
        self._total_delta: tuple[float, float, float] = (0.0, 0.0, 0.0)

    # -- Beobachtbarkeit für Tests/Integration ------------------------------

    @property
    def operation(self) -> MoveOperation | None:
        return self._operation

    @property
    def moves(self) -> set[VertexId]:
        """Von dieser Interaktion betroffene Vertex-IDs (Live-Daten)."""
        return set(self._vertex_ids)

    @property
    def axes_mask(self) -> tuple[float, float, float]:
        """Achsen-/Ebenenmaske dieser Interaktion (1.0 = frei, AD-009)."""
        return self._axes_mask

    @property
    def is_soft_gesture(self) -> bool:
        """A begun Soft gesture is running: `reweight()` applies."""
        return self.is_interacting and self._soft_seeds is not None

    @property
    def soft_seeds(self) -> frozenset[VertexId]:
        """The seeds of the running Soft gesture (empty without one)."""
        return self._soft_seeds or frozenset()

    def reweight(self, soft) -> set[VertexId]:
        """Live Soft radius / flow balance, as `TransformTool.reweight`: cancel (exact start geometry, no History),
        begin again from the same seeds with `soft`, replay the summed delta as one step. Returns the
        vertices whose position may have changed (old ∪ new influenced set)."""
        if not self.is_soft_gesture:
            raise ToolStateError("reweight() needs a running Soft gesture.")
        touched = set(self._vertex_ids)
        self._operation.cancel()
        self._operation = None
        self._begin_operation(set(self._soft_seeds), soft)
        if self._total_delta != (0.0, 0.0, 0.0):
            self._operation.update(delta=self._total_delta)
        return touched | self._vertex_ids

    # -- Hooks -----------------------------------------------------------------

    def _on_begin(
        self, scene=None, camera=None, vertex_ids=None, space=None, axis=None, derived_geometry=None,
        soft=None, mask=None, **params: Any
    ) -> None:
        self._mask = mask or {}  # Mask Geometry: `mirai.mask`; fixed for the gesture
        vertex_ids = unblocked(vertex_ids or (), self._mask)
        if not vertex_ids:
            raise ValueError("MoveTool.begin() benötigt mindestens einen Vertex.")
        self._scene = scene
        self._camera = camera
        self._vertex_ids = vertex_ids
        self._anchor_vertex = min(vertex_ids)
        self._normal = None
        self._plane_exclude = None
        self._in_plane_normal = None

        # WP-03C: axis is now an explicit parameter (separate from space)
        # Backward compatibility: if old API passes axis as space parameter
        if space is None and axis is not None and not isinstance(axis, str):
            # axis passed as vector — treat as space
            space = axis
            axis = None
        elif space is None and axis is not None:
            # axis passed as string (old flat API like axis="normal")
            # Let _resolve_space figure it out
            space = axis
            axis = None

        if space is None:
            self._axes_mask = (1.0, 1.0, 1.0)
        elif isinstance(space, str):
            space_lower = space.lower()
            # Achsen und Ebenen via _resolve_space (for_rotation=False → gibt Maske zurück)
            if space_lower in ("x", "y", "z", "xy", "yz", "xz"):
                axis_or_mask = _resolve_space(
                    space,
                    derived_geometry=derived_geometry,
                    mesh=self._scene.mesh if self._scene else None,
                    selection=self._scene.selection if self._scene else None,
                    axis=axis,  # Pass through new axis parameter (WP-03C)
                    for_rotation=False,
                )
                # Verwende die Maske direkt (axis/plane aus _WORLD_AXES)
                self._axes_mask = axis_or_mask
            elif space_lower == "normal":
                axis_lower_check = axis.lower() if isinstance(axis, str) else None
                if axis_lower_check in ("xy", "yz", "xz"):
                    # WP-03D: plane constraint — subtract the excluded direction from delta
                    self._plane_exclude = _resolve_space(
                        space,
                        derived_geometry=derived_geometry,
                        mesh=self._scene.mesh if self._scene else None,
                        selection=self._scene.selection if self._scene else None,
                        axis=axis,
                        for_rotation=False,
                    )
                    self._normal = None
                else:
                    # WP-03C: single-axis — project delta onto this direction
                    self._normal = _resolve_space(
                        space,
                        derived_geometry=derived_geometry,
                        mesh=self._scene.mesh if self._scene else None,
                        selection=self._scene.selection if self._scene else None,
                        axis=axis,
                        for_rotation=False,
                    )
                    self._plane_exclude = None
                self._axes_mask = (1.0, 1.0, 1.0)  # Dummy-Maske, wird nicht verwendet
            else:
                raise ValueError(
                    f"Unbekannter Move-Space {space!r} — erlaubt: "
                    "'x', 'y', 'z', 'xy', 'yz', 'xz', 'normal'."
                ) from None
        else:
            raise ValueError(f"MoveTool.begin(): space-Parameter muss String oder None sein, nicht {type(space).__name__}.")

        self._total_delta = (0.0, 0.0, 0.0)
        self._soft_seeds = None
        self._begin_operation(vertex_ids, soft)
        if soft is not None:
            self._soft_seeds = frozenset(vertex_ids)

    def _begin_operation(self, vertex_ids: set[VertexId], soft) -> None:
        mesh = self._scene.mesh
        self._in_plane_normal = None
        affected_vertex_ids = set(vertex_ids)
        operation_params: dict[str, Any] = {}
        definition = mesh.symmetry_definition
        if definition is not None and soft is not None:
            # Symmetric Soft (AD-SYM-04 SS2, `PROVISIONAL`): weights and the four step
            # categories from `symmetric_influence`, which refuses (`SoftSymmetryRefusal`)
            # before anything moves; falloff seam vertices slide in the plane (P-a).
            field = symmetric_influence(
                mesh, vertex_ids, soft.world_radius, metric=soft.metric, curve=soft.curve,
                curve_power=soft.curve_power, flow_ratio=soft.flow_ratio,
            )
            field = mask_symmetric_influence(field, self._mask)
            if not field.weights:
                raise ValueError("MoveTool.begin() benötigt mindestens einen gültigen Vertex.")
            operation_params["symmetry"] = field.symmetry_params(mesh)
            operation_params["influence"] = field.weights
            affected_vertex_ids = set(field.weights)
            if field.in_plane_only:
                self._in_plane_normal = definition.plane_normal
        elif definition is not None:
            mirrored_vertex_ids = mirrored_selection(mesh, vertex_ids)
            correspondence = vertex_correspondence(mesh)
            seam_vertex_ids = {
                vid
                for vid in vertex_ids
                if correspondence.get(vid) is not None
                and correspondence[vid].state is CorrespondenceState.SEAM
            }
            affected_vertex_ids |= mirrored_vertex_ids
            operation_params["symmetry"] = {
                "plane_normal": definition.plane_normal,
                "mirrored_vertex_ids": mirrored_vertex_ids,
                "seam_vertex_ids": seam_vertex_ids,
            }
        if soft is not None and definition is None:
            # AD-020 §4.1: the tool computes the influence at begin(), from the seeds and
            # the current (= start) positions.
            influence = compute_influence(
                mesh, vertex_ids, soft.world_radius, metric=soft.metric, curve=soft.curve,
                curve_power=soft.curve_power, flow_ratio=soft.flow_ratio,
            )
            influence = mask_weights(influence, vertex_ids, self._mask)
            if not influence:
                raise ValueError("MoveTool.begin() benötigt mindestens einen gültigen Vertex.")
            operation_params["influence"] = influence
            affected_vertex_ids = set(influence)
        # .moves (Beobachtbarkeit) berichtet die tatsächlich betroffene Menge,
        # inklusive gespiegelter Partner bzw. der Soft-Influence — nicht nur die Artist-Auswahl.
        self._vertex_ids = affected_vertex_ids

        context = OperationContext(
            target=mesh,
            selection=_VertexSelectionView(affected_vertex_ids),
            history=self._scene.history,
            params=operation_params,
        )
        operation = SoftMoveOperation(context) if soft is not None else MoveOperation(context)
        operation.begin()
        self._operation = operation

    def _on_update(self, dx: float, dy: float, width: int, height: int) -> None:
        # Anchor ist ein Referenz-Punkt der bewegten Auswahl: Das Pixel-Delta
        # wird auf der Bildebene der Kamera durch diesen Punkt in ein Welt-Delta
        # übersetzt.
        anchor_pos = self._scene.mesh.vertex_position(self._anchor_vertex)
        world_delta = self._camera.screen_delta_to_world(
            anchor_pos, dx, dy, width, height
        )

        # Constraint anwenden: plane-exclude, Normal-Projektion oder Achsen-Maske.
        if self._plane_exclude is not None:
            # WP-03D: subtract the excluded component (non-axis-aligned plane constraint).
            ex = self._plane_exclude
            dot = world_delta[0] * ex[0] + world_delta[1] * ex[1] + world_delta[2] * ex[2]
            world_delta = (
                world_delta[0] - dot * ex[0],
                world_delta[1] - dot * ex[1],
                world_delta[2] - dot * ex[2],
            )
        elif self._normal is not None:
            # Projekt world_delta auf die Normal-Richtung: (delta · normal) * normal
            dot = (
                world_delta[0] * self._normal[0] +
                world_delta[1] * self._normal[1] +
                world_delta[2] * self._normal[2]
            )
            world_delta = (
                dot * self._normal[0],
                dot * self._normal[1],
                dot * self._normal[2],
            )
        elif self._axes_mask != (1.0, 1.0, 1.0):
            # AD-009: Achsen-/Ebenen-Constraint — komponentenweise Maske auf das
            # ohnehin berechnete Bildebenen-Delta (kein zweiter Mechanismus). AD-021 M2-1:
            # die Maske meint Weltachsen; bei einem platzierten Objekt in Welt angewendet.
            world_delta = world_masked_delta(self._camera, world_delta, self._axes_mask)

        if self._in_plane_normal is not None:
            # Same projection as the Core's seam step (`_project_onto_plane`): exact for E1 axes.
            n = self._in_plane_normal
            dot = world_delta[0] * n[0] + world_delta[1] * n[1] + world_delta[2] * n[2]
            world_delta = (
                world_delta[0] - dot * n[0],
                world_delta[1] - dot * n[1],
                world_delta[2] - dot * n[2],
            )

        self._operation.update(delta=world_delta)
        t = self._total_delta
        self._total_delta = (t[0] + world_delta[0], t[1] + world_delta[1], t[2] + world_delta[2])

    def _on_commit(self) -> Any:
        command = self._operation.commit()
        self._operation = None
        self._soft_seeds = None
        return command

    def _on_cancel(self) -> None:
        self._operation.cancel()
        self._operation = None
        self._soft_seeds = None

    def _on_deactivate(self) -> None:
        self._anchor_vertex = None
        self._scene = None
        self._camera = None
        self._axes_mask = (1.0, 1.0, 1.0)
        self._normal = None
        self._in_plane_normal = None
        self._plane_exclude = None