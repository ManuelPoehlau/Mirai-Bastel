"""LookdevRoom (AD-038 §2): the LookDev room's session state - a configuration of the same window, like the Paint Room,
but **without** an interaction session (LookDev changes no gesture, LD-D1 / LD-D2).

It holds:
- `saved_view` - the display values the room changed (`mode`, `wire`, `regions`, `tier`), None while closed;
- `studio` - the session studio (`viewport.lookdev_optics.LookdevState`; Portrait by default, kept across closing and
  opening in one session);
- `preview` - the materials a held slider shows `{ObjectId: LookMaterial}` (§18, LD-2). The material itself is
  document data since LD-2: `SceneObject.look` (Core, saved as v15, one Undo step per change through
  `ObjectLookCommand`), so it travels with Duplicate, mirror copy, Detach and the scene file. The preview is drawn
  instead of `obj.look` until the release commits (or ends) it; a scene load / reset drops it, a deleted object loses
  its row (`prune`). An object without a look is Neutral (§15 Q3);
- `last_image` - the path the last "Bild speichern" wrote (§18.4), None before;
- `preparing` - True between `open_lookdev` and the first LookDev frame while the room's programs are compiled behind
  the status line (§9).

R-1 (§2.2) by construction: opening and closing write only these and the display fields in `saved_view`.
`look_draw` resolves an object's `LookDraw` from the object (never from the Worklight packet: no selection tint,
independent of the texture toggle, §3.3).
"""

from __future__ import annotations

from ..lookdev_material import LookMaterial, fallback, wrap_rgb
from ..lookdev_presets import DEFAULT_PRESET, preset as studio_preset


class LookdevRoom:
    def __init__(self, services) -> None:
        self.services = services
        self.saved_view: dict | None = None
        self.studio = studio_preset(DEFAULT_PRESET)
        self.preview: dict = {}
        self.last_image = None  # the last "Bild speichern" file (§18.4)
        self.preparing = False

    @property
    def open(self) -> bool:
        return self.saved_view is not None

    def start(self, saved_view: dict) -> None:
        self.saved_view = dict(saved_view)

    def stop(self) -> dict:
        saved, self.saved_view = self.saved_view, None
        self.preparing = False
        return saved

    def clear(self) -> None:
        """A scene load / reset: every object is new, a held preview goes (the studio stays unless the file has
        `view.lookdev`)."""
        self.preview.clear()

    def prune(self) -> None:
        objects = self.services.scene.objects
        for oid in [oid for oid in self.preview if oid not in objects]:
            del self.preview[oid]

    def committed(self, obj) -> LookMaterial:
        """The object's look (`SceneObject.look`), or Neutral with its `ObjectMaterial.base_color` as the colour."""
        from viewport.gl_render_store import DEFAULT_BASE_COLOR

        if obj.look is not None:
            return obj.look
        return fallback(obj.material.base_color if obj.material is not None else None, DEFAULT_BASE_COLOR)

    def material(self, obj) -> LookMaterial:
        """What the room draws for `obj`: a held slider's preview, else `committed(obj)`."""
        row = self.preview.get(obj.id)
        return row if row is not None else self.committed(obj)

    def albedo_source(self, obj):
        """The albedo map of `obj`: its paint composite while painted, else its texture path; None without UVs."""
        if not obj.mesh.has_face_uvs():
            return None
        paint = self.services.paint_display
        if paint.shows(obj):
            return paint.texture(obj)
        return obj.texture

    def look_draw(self, obj):
        from viewport.lookdev_pass import LookDraw

        material = self.material(obj)
        albedo = self.albedo_source(obj) if material.albedo_source == "texture" else None
        return LookDraw(base_color=material.base_color, roughness=material.roughness, specular=material.specular,
                        wrap_rgb=wrap_rgb(material), backscatter=material.backscatter,
                        backscatter_color=material.backscatter_color, albedo=albedo)
