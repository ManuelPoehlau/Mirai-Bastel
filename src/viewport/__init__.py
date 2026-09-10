"""Viewport v0.2 — produktive Rendering-Architektur (Gate 5).

Bezug: `docs/viewport/VIEWPORT_V02_ARCHITECTURE.md` (verbindliche Spec)
sowie das verifizierte Proof-of-Architecture-Experiment
`experiments/mirai_bastel_viewport_V02/` (10/10 Tests + GPU-Live-Check).

Architekturprinzip: **Update only what changed.**

Dieses Paket ist eine reine, standalone Rendering-Schicht:

- Es kennt `src.core.Mesh` als Geometrie-Quelle (read-only Query-API),
  mutiert sie aber NIE selbst — Mutation läuft ausschließlich über
  Core-Operationen (`src.core.operations`) plus History, angestoßen von
  `src.mirai`.
- Es hat KEINE Abhängigkeit auf `src.mirai` (Application/Tools/Interaction).
  Camera-Objekte werden nur duck-typed erwartet (`build_view_matrix()`,
  `build_projection_matrix(aspect)`), damit der Viewport unabhängig von der
  konkreten Interaction-Schicht bleibt und austauschbar ist.
- Kein Fenster-Code hier. Fenster-/Event-Loop-Integration ist Aufgabe eines
  separaten Entry-Points (nicht Teil von Gate 5).

Öffentliche API (Fassade): `Viewport` in `viewport.viewport`.
"""

from __future__ import annotations

from .benchmark import BenchmarkCounters
from .category import (
    ALL_CATEGORIES,
    CAMERA,
    GEOMETRY,
    MATERIAL,
    SELECTION,
    TOPOLOGY,
    DirtyState,
)
from .derived import DerivedGeometry, compute_bounds, triangulate_face
from .overlay import OverlayElementKind, SelectionOverlay
from .render_mesh import RenderMesh
from .resource_store import GpuResource, PygletStore, ResourceStore, TraceStore
from .viewport import Viewport

__all__ = [
    "ALL_CATEGORIES",
    "CAMERA",
    "GEOMETRY",
    "SELECTION",
    "MATERIAL",
    "TOPOLOGY",
    "DirtyState",
    "BenchmarkCounters",
    "DerivedGeometry",
    "compute_bounds",
    "triangulate_face",
    "OverlayElementKind",
    "SelectionOverlay",
    "RenderMesh",
    "GpuResource",
    "ResourceStore",
    "TraceStore",
    "PygletStore",
    "Viewport",
]
