"""`ShadingLabStore` — the production `GLRenderStore` plus the lab's rig hand-over.

Until 2026-10-15 this subclass carried its own Key+Fill fragment shader (handoff WP-SHADE-LAB-01
Slice 1, E2/E4) and its own `draw()`. The rig formula is now production's
(`gl_render_store.FRAGMENT_SRC`, `light_rig`), so the lab draws with the production program and
only passes its rig on as light uniforms. That also fixes the lab's draw, which had stopped
setting `u_model` after AD-021 M2-1 and showed an empty viewport.

The rig is still not a resource (E3): `set_rig_uniforms()` stores a plain dict that `draw()`
pushes as uniforms. Nothing about the rig ever reaches `allocate()`/`update()`, so no rig change
can count as an upload.
"""

from __future__ import annotations

from viewport.gl_render_store import LIGHT_UNIFORM_NAMES, GLRenderStore

from .lab_rig import PRESET_HEUTE, PRESETS, resolve

RIG_UNIFORM_NAMES = LIGHT_UNIFORM_NAMES


class ShadingLabStore(GLRenderStore):
    """Production draw path; the lab supplies the rig."""

    def __init__(self, stats) -> None:
        super().__init__(stats)
        # "Heute" until the window sets something else; world space needs no camera.
        self.set_rig_uniforms(resolve(PRESETS[PRESET_HEUTE]))

    def set_rig_uniforms(self, uniforms: dict) -> None:
        """Stores the resolved rig (`lab_rig.resolve()`) for the next `draw()`.
        Pure CPU state — no resource, no upload."""
        self.set_light_uniforms(uniforms)

    def rig_uniforms(self) -> dict:
        return self.light_uniforms()
