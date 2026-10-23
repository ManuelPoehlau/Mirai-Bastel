"""SubD (uniform Catmull-Clark) preview of the edit mesh in the Production app — since 2026-10-23.

Promoted from the SubD Lab (`experiments/subdivision_lab/`, WP-SUBD-LAB-01/02) on Manu's approval
("SubD gehört in den Production-Modeller"). The control mesh stays authoritative; the smooth
surface is derived display geometry drawn through the Viewport's replacement-surface hook
(AD-013 H7) with the app's light, Flat/Smooth and placement.

- `catmull_clark` — the evaluator (topology + stencils + provenance, GL-free); the evaluator boundary.
- `preview` — provider (H7), line presentation (H1), view state and the provisional `subd` keys.
- `gl_lines` — the GL sink of the line presentation (pyglet only when drawing).

`Application` owns one `SubdivisionPreview` (`app.subdivision`). Usage, status, limits and
measurements: `README.md` in this folder.
"""

from .catmull_clark import (
    KIND_EDGE,
    KIND_FACE,
    KIND_VERTEX,
    ControlTopology,
    SubdLevel,
    SubdSurface,
    SubdUnsupportedError,
    extract_control,
    predicted_face_count,
)
from .preview import (
    CYCLE_VIEW,
    DEFAULT_LEVEL,
    LEVEL_COMMANDS,
    LEVELS,
    MAX_DERIVED_FACES,
    MAX_LEVEL,
    SUBD_COMMANDS,
    SUBD_CONTEXT,
    SUBD_KEYS,
    TOGGLE_CAGE_DEPTH,
    VIEW_CAGE,
    VIEW_ISO,
    VIEW_LABELS,
    VIEW_OFF,
    VIEW_ORDER,
    SubdBindingConflict,
    SubdivisionPreview,
    SubdLinePresentation,
    SubdSurfaceProvider,
    assert_subd_keys_free,
    install_subd_bindings,
)

__all__ = [
    "CYCLE_VIEW",
    "ControlTopology",
    "DEFAULT_LEVEL",
    "KIND_EDGE",
    "KIND_FACE",
    "KIND_VERTEX",
    "LEVELS",
    "LEVEL_COMMANDS",
    "MAX_DERIVED_FACES",
    "MAX_LEVEL",
    "SUBD_COMMANDS",
    "SUBD_CONTEXT",
    "SUBD_KEYS",
    "SubdBindingConflict",
    "SubdLevel",
    "SubdLinePresentation",
    "SubdSurface",
    "SubdSurfaceProvider",
    "SubdUnsupportedError",
    "SubdivisionPreview",
    "TOGGLE_CAGE_DEPTH",
    "VIEW_CAGE",
    "VIEW_ISO",
    "VIEW_LABELS",
    "VIEW_OFF",
    "VIEW_ORDER",
    "assert_subd_keys_free",
    "extract_control",
    "install_subd_bindings",
    "predicted_face_count",
]
