"""The eye pass (AD-033 §5): draws an eye entry's VertexList with the eye program instead of the Worklight's
`GLRenderStore.draw()` - a foreign pass on the store's buffers, like `GpuPicker` (audit §4.2, option B). The Worklight
code is untouched; with no eye in the scene nothing here runs.

`EyeDraw` is what the viewport needs per eye (the app resolves it: `mirai.controllers.objects`); `EyeDisplay` the view
state (preview on / off, reflection, refraction, tier - not saved, no Undo, Q-E3). GL state: opaque, depth test + write,
no blending, back faces culled, the store's polygon offset (the wire overlay keeps drawing over it); restored after.

Eye LookDev phase 3: an eye whose `EyeSpec.look` has an amount above 0 is drawn with the `LOOK` program in the "full"
tier (`uses_look`); "fast" and every eye without a look draw with the program before phase 3, at its cost.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import eye_optics as eo
from . import eye_shaders as es
from .material import SurfaceFinish

#: The iris texture's unit (any unit the Worklight's face data does not use while the pass runs).
IRIS_UNIT = 1
#: The irregularity texture's unit (phase 3).
NOISE_UNIT = 2
#: P1b's pupil colour (sRGB, display-referred like every albedo here).
PUPIL_ALBEDO = (0.012, 0.012, 0.012)
REFLECTIONS = tuple(es.REFLECTIONS)
REFRACTIONS = tuple(es.VARIANT_IDS)
#: The quality tier (assessment 2026-11-16 §D change 3): "fast" in the modelling view, "full" while the Eye Lab window
#: is open. "fast" draws without the look (phase 3), so it draws and costs what it did before phase 3.
TIERS = ("fast", "full")


@dataclass(frozen=True)
class EyeDraw:
    """One eye entry: its values (`core.EyeSpec`), its iris image (None = the procedural iris), the sclera colour (the
    object's resolved base colour, selection tint included) and finish, and how many leading triangles of its shell are
    the corneal cap."""

    spec: object
    texture: str | None
    sclera_colour: tuple[float, float, float]
    finish: SurfaceFinish
    cornea_triangles: int
    #: Phase 3: the eye's own placement without the gaze (column-major 4x4; None = as drawn). The lid shadow and band
    #: stay with the head in this rest frame while the eye turns.
    rest_matrix: tuple | None = None
    #: Phase 3: which part of the irregularity texture this eye reads (the app passes the object's id).
    variation: int = 0


@dataclass(frozen=True)
class EyeDisplay:
    preview: bool = True
    reflection: str = "studio"  # Q-E4: the studio by default; "key" = the Worklight key highlight only
    refraction: str = "V2"  # P1b V2 is the baseline (Manu 2026-11-14); V3 selectable
    tier: str = "fast"

    def __post_init__(self) -> None:
        if self.reflection not in REFLECTIONS or self.refraction not in REFRACTIONS or self.tier not in TIERS:
            raise ValueError(f"EyeDisplay: reflection {REFLECTIONS}, refraction {REFRACTIONS}, tier {TIERS}")


def _inverse(model: list[float]) -> tuple[float, ...]:
    m = np.asarray(model, dtype=np.float64).reshape(4, 4).T  # column-major -> row-major
    return tuple(np.linalg.inv(m).T.ravel())


def eye_uniforms(draw: EyeDraw) -> dict:
    """The eye's geometry, limbus and fit uniforms (GL-free)."""
    spec = draw.spec
    g = eo.EyeGeometry.from_values(spec)
    angle = g.angle
    values = {
        "u_ant_centre_z": g.anterior_centre_z, "u_ant_radius": g.cornea_radius,
        "u_post_centre_z": g.posterior_centre_z, "u_post_radius": eo.POSTERIOR_RADIUS, "u_cap_z": g.limbus_z,
        "u_angle": angle, "u_iris_a": g.iris_a, "u_iris_b": g.iris_b, "u_iris_radius": g.iris_radius,
        "u_pupil_radius": g.pupil_radius, "u_limbus_radius": g.limbus_radius,
        "u_theta_ring": float(np.arcsin(g.limbus_radius)), "u_u0": eo.limbus_u0(g),
        "u_band": spec.band_mm * eo.MM, "u_strength": spec.strength, "u_normal_w": spec.normal_mm * eo.MM,
        "u_falloff": spec.falloff, "u_asym": eo.ASYM_MM * eo.MM if spec.asymmetry else 0.0,
        "u_overlap": spec.overlap_mm * eo.MM,
        "u_sclera_albedo": tuple(draw.sclera_colour), "u_limbus_albedo": tuple(spec.limbal_colour),
        "u_pupil_albedo": PUPIL_ALBEDO, "u_cornea_triangles": int(draw.cornea_triangles),
        "u_specular": draw.finish.specular, "u_spec_exponent": draw.finish.exponent,
        "u_fill_specular": draw.finish.fill_specular, "u_cornea_f0": eo.CORNEA_F0,
        "u_cornea_roughness": eo.CORNEA_ROUGHNESS, "u_key_irradiance": eo.KEY_IRRADIANCE,
    }
    knots = eo.fit_knots(spec, g)
    if knots is not None:
        values["u_fit_lab"], values["u_fit_img"] = knots
    return values


def uses_look(draw: EyeDraw, display: EyeDisplay) -> bool:
    """Phase 3: draw `draw` with its look (the "full" tier and a look with an amount above 0)."""
    return display.tier == "full" and eo.look_active(getattr(draw.spec, "look", None))


def rest_rotation(draw: EyeDraw, model) -> tuple[float, ...]:
    """The 3x3 rotation (column-major) from the eye's drawn local frame to its rest frame: inverse(rest) * model."""
    if draw.rest_matrix is None:
        return (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
    rest = np.asarray(draw.rest_matrix, dtype=np.float64).reshape(4, 4).T
    drawn = np.asarray(model, dtype=np.float64).reshape(4, 4).T
    m = np.linalg.solve(rest[:3, :3], drawn[:3, :3])
    return tuple(float(v) for v in m.T.ravel())


def look_uniforms(draw: EyeDraw) -> dict:
    """The look's uniforms (GL-free; `eye_optics.look_values`); the rest frame is added by the draw."""
    look = draw.spec.look
    v = eo.look_values(look, draw.variation)
    return {
        "u_wet": look.wet_sclera, "u_sclera_roughness": look.sclera_roughness, "u_lid_shadow": look.lid_shadow,
        "u_lid_band": look.lid_band, "u_tilt": v["tilt"], "u_rough_s": v["rough_s"], "u_noise_scale": v["noise_scale"],
        "u_noise_offset": v["noise_offset"], "u_lid": v["lid"], "u_soft_half": v["soft_half"],
        "u_soft_radiance": v["soft_radiance"],
    }


class EyePass:
    """Programs (per variant), the procedural iris texture and the draw. Created by the viewport on the first eye."""

    def __init__(self) -> None:
        self.programs: dict = {}
        self._procedural: dict = {}
        self._ring_colours: dict = {}
        self._noise = None
        #: Test hook: draw the ray classes (red iris, green pupil, blue limbal tissue, yellow sclera).
        self.debug_kind = False
        #: Test hook: in the "full" tier, draw an eye with any look (also one at amount 0) with the LOOK program - the
        #: check that every term is neutral at 0.
        self.force_look = False

    def program(self, display: EyeDisplay, level: int, fit: bool, look: bool = False):
        from pyglet.graphics.shader import Shader, ShaderProgram

        from .gl_render_store import GLRenderStore

        key = (display.refraction, int(level), display.reflection, bool(fit), self.debug_kind, bool(look))
        program = self.programs.get(key)
        if program is None:
            attributes = GLRenderStore.program().attributes
            locations = {"position": attributes["position"]["location"], "normal": attributes["normal"]["location"]}
            sources = es.shell_sources(locations, display.refraction, level, display.reflection, fit, self.debug_kind,
                                       look)
            program = ShaderProgram(*(Shader(src, kind) for src, kind in sources))
            self.programs[key] = program
        return program

    def procedural_texture(self, spec):
        """The procedural iris of this eye's anatomy (an eye without its own image), built once per anatomy."""
        from pyglet import gl, image

        g = eo.EyeGeometry.from_values(spec)
        key = (g.pupil_radius, g.limbus_radius, g.iris_root_z)
        texture = self._procedural.get(key)
        if texture is None:
            rgb = eo.procedural_iris(g, 512)
            data = (np.clip(rgb[::-1], 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)  # pyglet rows run bottom-up
            texture = image.ImageData(512, 512, "RGB", data.tobytes(), pitch=512 * 3).get_texture()
            gl.glBindTexture(texture.target, texture.id)
            gl.glGenerateMipmap(texture.target)
            gl.glTexParameteri(texture.target, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR_MIPMAP_LINEAR)
            gl.glBindTexture(texture.target, 0)
            self._procedural[key] = texture
        return texture

    def noise_texture(self):
        """The irregularity texture (`eye_optics.film_noise`), built once: repeating, mip-mapped, so the irregularity
        fades with distance instead of shimmering (there is no MSAA)."""
        from pyglet import gl, image

        if self._noise is None:
            data = eo.film_noise()
            size = data.shape[0]
            texture = image.ImageData(size, size, "RGB", data.tobytes(), pitch=size * 3).get_texture()
            gl.glBindTexture(texture.target, texture.id)
            gl.glTexParameteri(texture.target, gl.GL_TEXTURE_WRAP_S, gl.GL_REPEAT)
            gl.glTexParameteri(texture.target, gl.GL_TEXTURE_WRAP_T, gl.GL_REPEAT)
            gl.glGenerateMipmap(texture.target)
            gl.glTexParameteri(texture.target, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR_MIPMAP_LINEAR)
            gl.glTexParameteri(texture.target, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
            gl.glBindTexture(texture.target, 0)
            self._noise = texture
        return self._noise

    def limbal_colour(self, draw: EyeDraw) -> tuple[float, float, float]:
        """The limbal colour: the eye's own (`colour_source` "shader"), or the iris image's outer ring ("image"; the
        procedural iris without an image). Cached per image file (path + modification time) and ring edge; an image
        that cannot be read falls back to the eye's own colour."""
        spec = draw.spec
        if spec.colour_source != "image":
            return tuple(spec.limbal_colour)
        g = eo.EyeGeometry.from_values(spec)
        edge = spec.fit_limbus if spec.fit_pupil is not None else g.limbus_radius / g.iris_radius
        stamp = None
        if draw.texture:
            import os

            try:
                stamp = os.stat(draw.texture).st_mtime_ns
            except OSError:
                return tuple(spec.limbal_colour)
        key = (draw.texture, stamp, edge, None if draw.texture else (g.pupil_radius, g.limbus_radius, g.iris_root_z))
        if key not in self._ring_colours:
            colour = None
            try:
                if draw.texture:
                    from pyglet import image

                    data = image.load(draw.texture).get_image_data()
                    raw = np.frombuffer(data.get_data("RGB", data.width * 3), dtype=np.uint8)
                    rgb = raw.reshape(data.height, data.width, 3) / 255.0
                else:
                    rgb = eo.procedural_iris(g, 256)
                colour = eo.image_ring_colour(rgb, edge)
            except Exception:  # noqa: BLE001 - an unreadable image keeps the eye's own colour
                colour = None
            self._ring_colours[key] = colour
        colour = self._ring_colours[key]
        return tuple(spec.limbal_colour) if colour is None else colour

    def draw(self, render_mesh, draw: EyeDraw, light: dict, display: EyeDisplay) -> bool:
        """Draw one eye entry. False = nothing drawn (no VertexList / camera yet): the caller draws it as usual."""
        from pyglet import gl

        from .gl_render_store import GLRenderStore

        store = render_mesh.store
        vlist = store.vertex_list() if hasattr(store, "vertex_list") else None
        camera = store.uniform_data("camera_uniforms") if vlist is not None else []
        if vlist is None or len(camera) != 32:
            return False
        texture = GLRenderStore.texture(draw.texture) if draw.texture else None
        if texture is None:
            texture = self.procedural_texture(draw.spec)
        values = eye_uniforms(draw)
        values["u_limbus_albedo"] = self.limbal_colour(draw)
        look = uses_look(draw, display) or (self.force_look and display.tier == "full" and draw.spec.look is not None)
        program = self.program(display, draw.spec.limbus_level, "u_fit_lab" in values, look)
        model = store.uniform_data("model_uniforms")
        model = list(model) if len(model) == 16 else [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0]
        values.update(light)
        values.update({"u_view": camera[0:16], "u_proj": camera[16:32], "u_model": model,
                       "u_model_inv": _inverse(model), "u_iris_texture": IRIS_UNIT})
        noise = None
        if look:
            noise = self.noise_texture()
            values.update(look_uniforms(draw))
            values.update({"u_rest": rest_rotation(draw, model), "u_noise_texture": NOISE_UNIT})
        program.use()
        active = program.uniforms  # pyglet builds this dict on every access: once per draw, not once per value
        for name, value in values.items():
            if name in active:
                program[name] = value
        gl.glActiveTexture(gl.GL_TEXTURE0 + IRIS_UNIT)
        gl.glBindTexture(texture.target, texture.id)
        if noise is not None:
            gl.glActiveTexture(gl.GL_TEXTURE0 + NOISE_UNIT)
            gl.glBindTexture(noise.target, noise.id)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_TRUE)
        gl.glDisable(gl.GL_BLEND)
        gl.glEnable(gl.GL_CULL_FACE)
        gl.glCullFace(gl.GL_BACK)
        offset = bool(getattr(store, "polygon_offset", False))
        if offset:
            gl.glEnable(gl.GL_POLYGON_OFFSET_FILL)
            gl.glPolygonOffset(1.0, 1.0)
        vlist.draw(gl.GL_TRIANGLES)
        if offset:
            gl.glDisable(gl.GL_POLYGON_OFFSET_FILL)
        gl.glDisable(gl.GL_CULL_FACE)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glActiveTexture(gl.GL_TEXTURE0 + IRIS_UNIT)
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        if noise is not None:
            gl.glActiveTexture(gl.GL_TEXTURE0 + NOISE_UNIT)
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        program.stop()
        return True

    def release(self) -> None:
        for program in self.programs.values():
            program.delete()
        self.programs.clear()
        for texture in self._procedural.values():
            texture.delete()
        self._procedural.clear()
        if self._noise is not None:
            self._noise.delete()
            self._noise = None
