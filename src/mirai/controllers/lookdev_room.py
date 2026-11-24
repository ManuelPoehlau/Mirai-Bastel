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
  the status line (§9);
- `area` - AD-039 §9 (S6): the panel's „Bereich“ the material controls edit, None = „Ganzes Objekt“ (`SceneObject.look`),
  else a region name (that region's entry in `SceneObject.look_regions`). View state of the session, like the studio;
  the held preview belongs to it (a new area drops the preview).

R-1 (§2.2) by construction: opening and closing write only these and the display fields in `saved_view`.
`look_draw` resolves an object's `LookDraw` from the object (never from the Worklight packet: no selection tint,
independent of the texture toggle, §3.3). AD-039 S7: with the material's maps that pass `look_maps.drawable` - on an
object with UVs only. AD-039 S6: with the object's region materials whose region exists in its mesh (a missing region is
skipped: drawn as the object's material), in their order, each with its region's faces.
"""

from __future__ import annotations

from ..lookdev_material import LookMaterial, fallback, region_material, with_region, wrap_rgb
from ..lookdev_presets import DEFAULT_PRESET, preset as studio_preset


class LookdevRoom:
    def __init__(self, services) -> None:
        self.services = services
        self.saved_view: dict | None = None
        self.studio = studio_preset(DEFAULT_PRESET)
        self.preview: dict = {}
        self.last_image = None  # the last "Bild speichern" file (§18.4)
        self.preparing = False
        self.area: str | None = None  # AD-039 §9: the panel's „Bereich“ (None = „Ganzes Objekt“)

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
        `view.lookdev`). AD-039 §9: the „Bereich“ goes back to „Ganzes Objekt“."""
        self.preview.clear()
        self.area = None

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
        """What the room draws for `obj` as a whole: a held slider's preview (in „Ganzes Objekt“), else
        `committed(obj)`."""
        row = self.preview.get(obj.id) if self.area is None else None
        return row if row is not None else self.committed(obj)

    @staticmethod
    def region_entry(obj, name: str):
        """AD-039 §9: `obj`'s `RegionLook` for region `name`, or None."""
        return next((entry for entry in obj.look_regions if entry.region == name), None)

    @staticmethod
    def has_region(obj, name: str) -> bool:
        regions = obj.mesh.face_regions
        return regions is not None and regions.get(name) is not None

    def committed_area(self, obj, area: str | None = None) -> LookMaterial:
        """The committed material of `area` (None = the object's, `committed`): the region's entry, or - before it has
        one - the object's material without its maps (a new region starts from what it shows now)."""
        if area is None:
            return self.committed(obj)
        entry = self.region_entry(obj, area)
        return entry.look if entry is not None else region_material(self.committed(obj))

    def area_material(self, obj) -> LookMaterial:
        """What the panel shows for `obj` in the current area: the held preview, else `committed_area`."""
        row = self.preview.get(obj.id)
        return row if row is not None else self.committed_area(obj, self.area)

    def drawn_regions(self, obj) -> tuple:
        """`obj`'s region entries as the room draws them: `look_regions` with a held preview of the current area in
        its place (or last, while it has no entry yet and a slot is free)."""
        entries = obj.look_regions
        row = self.preview.get(obj.id) if self.area is not None else None
        if row is not None:
            try:
                entries = with_region(entries, self.area, row)
            except ValueError:  # a fifth region: not drawn (its commit is refused with the reason)
                pass
        return entries

    def albedo_source(self, obj):
        """The albedo map of `obj`: its paint composite while painted, else its texture path; None without UVs."""
        if not obj.mesh.has_face_uvs():
            return None
        paint = self.services.paint_display
        if paint.shows(obj):
            return paint.texture(obj)
        return obj.texture

    def look_draw(self, obj):
        from .. import look_maps

        material = self.material(obj)
        maps = material.maps if material.maps is not None and obj.mesh.has_face_uvs() else None
        extra = {}
        if maps is not None:
            extra = dict(roughness_map=look_maps.drawable(maps.roughness), normal_map=look_maps.drawable(maps.normal),
                         translucency_map=look_maps.drawable(maps.translucency),
                         normal_strength=maps.normal_strength, normal_green_down=maps.normal_green_down)
        regions, faces = [], []
        mesh_regions = obj.mesh.face_regions
        for entry in self.drawn_regions(obj):
            region = mesh_regions.get(entry.region) if mesh_regions is not None else None
            if region is not None:  # AD-039 §9: a missing region is ignored
                regions.append(self._draw(obj, entry.look))
                faces.append(region.faces)
        return self._draw(obj, material, regions=tuple(regions), region_faces=tuple(faces), **extra)

    def _draw(self, obj, material: LookMaterial, **extra):
        from viewport.lookdev_pass import LookDraw

        albedo = self.albedo_source(obj) if material.albedo_source == "texture" else None
        return LookDraw(base_color=material.base_color, roughness=material.roughness, specular=material.specular,
                        wrap_rgb=wrap_rgb(material), backscatter=material.backscatter,
                        backscatter_color=material.backscatter_color, albedo=albedo, **extra)
