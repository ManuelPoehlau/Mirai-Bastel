"""Compatibility shim: the ExtrudeTool now lives in `mirai.topology.extrude`.

Moved (not copied) in WP-06 Slice B9; Production and the Playground share that
one implementation. This module only keeps the legacy `ExtrudeTool(scene,
camera)` constructor for callers outside the Production Tool contract
(`playground/command_handler.py`, the head-topology / symmetry probes under
`experiments/`), which still pass the context at construction. New code uses
`mirai.topology.extrude.ExtrudeTool` directly: parameterless `__init__`,
`scene`/`camera`/`face_ids` through `begin()` (as `playground/window.py` does).
"""

from __future__ import annotations

from typing import Any

from mirai.topology.connect_per_face import TopologyToolError  # noqa: F401  (re-export)
from mirai.topology.extrude import (  # noqa: F401  (re-export)
    ExtrudeTool as _ProductionExtrudeTool,
    _compute_face_normal,
    _connected_components,
)


class ExtrudeTool(_ProductionExtrudeTool):
    """Legacy-signature adapter: context at construction, `begin(face_ids=...)`."""

    def __init__(self, scene, camera) -> None:
        super().__init__()
        self._legacy_scene = scene
        self._legacy_camera = camera

    def _on_begin(self, face_ids, **params: Any) -> None:
        params.setdefault("scene", self._legacy_scene)
        params.setdefault("camera", self._legacy_camera)
        super()._on_begin(face_ids=face_ids, **params)
