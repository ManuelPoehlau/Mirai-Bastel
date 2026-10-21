"""GL drawing of the transform gizmo (promoted 2026-10-21, AD-016 D3; Manu "Gizmo nach src/").

`mirai.viewport.gizmo.draw_items` decides what the gizmo looks like (and `Application.gizmo_items()` when it is
shown); this module only draws those line primitives, on top of everything (depth test off), in the same
flat-colour program as the line overlays. The shapes change with the camera distance every frame, so the vertex
lists are made and freed per draw - a handful of tiny lists, only while the gizmo is shown. Needs a GL context;
nothing here runs headless (the pure side is tested in `tests/test_gizmo.py`).
"""

from __future__ import annotations

from .gl_line_overlay import FlatColorLayers


def draw_gizmo(items, camera_uniforms) -> None:
    """Draws `items` (`mirai.viewport.gizmo.DrawItem`) with the camera packet (32 floats: view, projection)."""
    from pyglet import gl

    if not items or len(camera_uniforms) != 32:
        return
    program = FlatColorLayers.program()
    program.use()
    program["u_view"] = tuple(camera_uniforms[0:16])
    program["u_proj"] = tuple(camera_uniforms[16:32])
    blend_was_enabled = gl.glIsEnabled(gl.GL_BLEND)
    gl.glDisable(gl.GL_DEPTH_TEST)
    gl.glEnable(gl.GL_BLEND)
    gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
    for item in items:
        count = len(item.positions) // 3
        if count == 0:
            continue
        primitive = gl.GL_LINE_LOOP if item.primitive == "loop" else gl.GL_LINES
        program["u_color"] = item.color
        gl.glLineWidth(item.width)
        vertex_list = program.vertex_list(count, primitive, position=("f", item.positions))
        vertex_list.draw(primitive)
        vertex_list.delete()
    gl.glLineWidth(1.0)
    if not blend_was_enabled:
        gl.glDisable(gl.GL_BLEND)
    program.stop()
