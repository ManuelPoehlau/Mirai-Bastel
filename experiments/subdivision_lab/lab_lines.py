"""Lab-owned line overlay: cage and isolines (handoff §3.3, stop condition 2).

`GLLineOverlay` has class-level `LAYERS`/`LAYER_STYLES`/`NO_DEPTH_LAYERS`, so
the lab subclasses it (same pattern as `ShadingLabStore` in the shading lab)
instead of touching production. What the subclass changes: two lab layers
with lab-owned colors, and the cage depth behavior as an *instance* switch —
`NO_DEPTH_LAYERS` is read through `self` in `FlatColorLayers.draw()`, so a
property can decide per instance whether the cage is depth-tested.

Colors (lab-owned, PROVISIONAL, within the production palette family of dark
greys): cage = production wire grey; isolines = a cooler, slightly lighter
slate so the two are distinguishable if both are ever shown together.

Shader: the parent's flat-color program is reused unchanged, so no own
`_program` is needed (the E2 pitfall of the shading lab only bites when a
subclass compiles a *different* shader).
"""

from __future__ import annotations

from viewport.gl_line_overlay import EDGE_COLOR, EDGE_LINE_WIDTH, GLLineOverlay

CAGE_LAYER = "cage"
ISO_LAYER = "iso"

CAGE_COLOR = EDGE_COLOR
ISO_COLOR = (0.22, 0.34, 0.52, 1.0)


class LabLineOverlay(GLLineOverlay):
    LAYERS = (CAGE_LAYER, ISO_LAYER)
    LAYER_STYLES = {
        CAGE_LAYER: (CAGE_COLOR, EDGE_LINE_WIDTH),
        ISO_LAYER: (ISO_COLOR, EDGE_LINE_WIDTH),
    }

    def __init__(self) -> None:
        super().__init__()
        #: True: the cage is depth-tested (hidden where the surface is in front);
        #: False: drawn on top of everything ("immer sichtbar").
        self.cage_depth_test = True

    @property
    def NO_DEPTH_LAYERS(self) -> frozenset:  # noqa: N802 - mirrors the parent's class attribute
        return frozenset() if self.cage_depth_test else frozenset({CAGE_LAYER})

    def set_cage(self, segments) -> None:
        self._set(CAGE_LAYER, segments)

    def set_iso(self, segments) -> None:
        self._set(ISO_LAYER, segments)

    def segment_count(self, layer: str = CAGE_LAYER) -> int:
        return self._count(layer)

    def vertex_list(self, layer: str = CAGE_LAYER):
        return self._vertex_lists.get(layer)

    def draw(self, camera_uniforms, layers=(CAGE_LAYER,)) -> None:
        # Skip GLLineOverlay.draw (its `layers` default is the production wire layer).
        super(GLLineOverlay, self).draw(camera_uniforms, layers)
