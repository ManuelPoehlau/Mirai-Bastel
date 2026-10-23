"""Uniform Catmull-Clark subdivision — now the Production evaluator (2026-10-23).

The implementation moved to `src/mirai/subdivision/catmull_clark.py` (SubD in Production); this module
only re-exports it, so the standalone window (`run_standalone.py`, `lab_scene.py`), the bench and
other readers keep working against the one implementation. Its tests are Production tests now
(`tests/test_subdivision_evaluator.py`).
"""

from __future__ import annotations

from mirai.subdivision.catmull_clark import (  # noqa: F401
    KIND_EDGE,
    KIND_FACE,
    KIND_NAMES,
    KIND_VERTEX,
    ControlTopology,
    Stencil,
    SubdLevel,
    SubdSurface,
    SubdUnsupportedError,
    Vec3,
    extract_control,
    predicted_face_count,
)
