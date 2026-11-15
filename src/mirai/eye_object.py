"""The parametric eye object (AD-033 §4): the app's default eye values and the shell mesh generated from them.

An eye is an ordinary scene object whose `SceneObject.eye` holds a `core.EyeSpec`; its mesh is the eyeball's outer
shell - the sclera sphere (radius 1, eye-local) open at the limbus circle, closed by the corneal cap that shares the
limbus ring's vertices - built here from the anatomy values, never edited by hand (Q-E5: component editing of an eye
is refused). Iris and pupil have no geometry: the eye pass finds them analytically behind the cornea (P1b).

Size (Q-E6, Manu 2026-11-15: "Einheit cm"): one scene unit = 1 cm, so a new eye is 2.4 units across - eye-local 1
(the sclera radius) = 1.2 units, the object's uniform scale. The eye looks down eye-local +Z.
"""

from __future__ import annotations

import math
from dataclasses import replace

from core import EyeSpec, Mesh, ObjectMaterial, ObjectTransform

from viewport.eye_optics import EyeGeometry

#: Q-E6: 1 unit = 1 cm; a real eye is ~24 mm across, so the sclera radius is 1.2 units.
EYE_SCALE_CM = 1.2
#: Shell tessellation (the lab's: 64 segments, 36 sclera rings, 16 cornea rings; ≈ 3.4 k faces).
SEGMENTS = 64
SCLERA_RINGS = 36
CORNEA_RINGS = 16
#: The lab's sclera colour (sRGB): a new eye's material base colour (AD-024), so it also reads as a sclera with the
#: preview off; specular / glossiness are the Worklight's default finish (`PROVISIONAL`).
SCLERA_COLOUR = (0.86, 0.83, 0.79)
#: P1b's limbal colour (the procedural iris's outer colour), sRGB.
DEFAULT_LIMBAL_COLOUR = (0.10, 0.11, 0.13)

#: The app's default eye (`PROVISIONAL` beyond the lab's anatomy): the lab's eye, planar iris mapping, limbus L0 (P1b as
#: it is - Manu 2026-11-14: "alles erstmal so drin lassen als einstellungen", no default changed).
DEFAULT_EYE = EyeSpec(
    cornea_radius=0.65,
    limbus_radius=0.49,
    iris_root_z=0.80,
    iris_concavity=0.03,
    pupil_radius=0.16,
    fit_pupil=None,
    fit_limbus=None,
    hold_outer_color=False,
    limbus_level=0,
    colour_source="shader",
    limbal_colour=DEFAULT_LIMBAL_COLOUR,
    band_mm=1.0,
    strength=1.0,
    normal_mm=0.5,
    falloff=4.0,
    overlap_mm=0.0,
    asymmetry=False,
)

#: The values whose change rebuilds the shell (the rest only changes the shading).
SHAPE_FIELDS = ("cornea_radius", "limbus_radius")


def eye_material() -> ObjectMaterial:
    from viewport.material import DEFAULT_FINISH

    return ObjectMaterial(SCLERA_COLOUR, specular=DEFAULT_FINISH.specular, glossiness=DEFAULT_FINISH.glossiness)


def cornea_triangles(segments: int = SEGMENTS, cornea_rings: int = CORNEA_RINGS) -> int:
    """How many leading triangles of the shell's VertexList are the corneal cap: the apex fan, then the cap's quads
    (two triangles each) - `shell_mesh` adds them first, and the store keeps the face order of a fresh mesh."""
    return segments + (cornea_rings - 1) * segments * 2


def eye_transform(translation=(0.0, 0.0, 0.0)) -> ObjectTransform:
    return ObjectTransform(translation=tuple(translation), scale=EYE_SCALE_CM)


def _ring(radius: float, z: float, segments: int) -> list[tuple[float, float, float]]:
    return [(radius * math.cos(2.0 * math.pi * k / segments), radius * math.sin(2.0 * math.pi * k / segments), z)
            for k in range(segments)]


def _strip(mesh: Mesh, inner: list, outer: list) -> None:
    """Quads between two rings; `outer` is the next ring away from the front. Counter-clockwise seen from outside."""
    n = len(inner)
    for k in range(n):
        k2 = (k + 1) % n
        mesh.add_face([inner[k], outer[k], outer[k2], inner[k2]])


def shell_mesh(spec: EyeSpec, segments: int = SEGMENTS, sclera_rings: int = SCLERA_RINGS,
               cornea_rings: int = CORNEA_RINGS) -> Mesh:
    """The eyeball's outer shell: corneal cap (apex fan, `cornea_rings` rings) joined at the limbus ring to the sclera
    (from the limbus to a back-pole fan). Closed, outward faces, the limbus ring shared - the lab's sclera and cornea
    meshes (`eye_geometry.sclera_mesh` / `cornea_mesh`) as one."""
    g = EyeGeometry.from_values(spec)
    mesh = Mesh()
    theta_c = math.acos((g.limbus_z - g.anterior_centre_z) / g.cornea_radius)
    apex = mesh.add_vertex((0.0, 0.0, g.apex_z))
    cornea = []
    for r in range(1, cornea_rings + 1):
        theta = theta_c * r / cornea_rings
        cornea.append([mesh.add_vertex(p) for p in _ring(g.cornea_radius * math.sin(theta),
                                                         g.anterior_centre_z + g.cornea_radius * math.cos(theta),
                                                         segments)])
    for k in range(segments):
        mesh.add_face([apex, cornea[0][k], cornea[0][(k + 1) % segments]])
    for r in range(cornea_rings - 1):
        _strip(mesh, cornea[r], cornea[r + 1])
    # The sclera: the limbus ring is the cornea's last ring (same positions), then rings to the back pole.
    theta_l = math.asin(g.limbus_radius)
    rings = [cornea[-1]]
    for r in range(1, sclera_rings + 1):
        theta = theta_l + (math.pi * (1.0 - 1.0 / (sclera_rings + 1)) - theta_l) * r / sclera_rings
        rings.append([mesh.add_vertex(p) for p in _ring(math.sin(theta), math.cos(theta), segments)])
    for r in range(sclera_rings):
        _strip(mesh, rings[r], rings[r + 1])
    pole = mesh.add_vertex((0.0, 0.0, -1.0))
    last = rings[-1]
    for k in range(segments):
        mesh.add_face([last[k], pole, last[(k + 1) % segments]])
    return mesh


def with_changes(spec: EyeSpec, **changes) -> EyeSpec:
    """A validated copy (`ValueError` from `EyeSpec` on an invalid combination)."""
    return replace(spec, **changes)


def shape_changed(before: EyeSpec, after: EyeSpec) -> bool:
    return any(getattr(before, name) != getattr(after, name) for name in SHAPE_FIELDS)


#: The iris image's fit file beside it: same name, `.json` (the eye lab's `iris_custom.json` format).
FIT_KEYS = ("pupil", "limbus")
FIT_OPTIONAL_KEYS = ("hold_outer_color",)


def read_fit_sidecar(image_path) -> tuple[dict | None, str]:
    """The radial fit for an iris image from the JSON beside it with the same name (`iris.png` -> `iris.json`; the
    eye lab's format: `{"pupil": 0.22, "limbus": 0.88, "hold_outer_color": true}` - where the image's own pupil edge and
    iris edge lie, shares of half the image width). Returns (`EyeSpec` field values, "") / (None, "") without a file /
    (None, reason) when it cannot be used. Reads only; accepts UTF-8 with or without a BOM and UTF-16 (Windows tools)."""
    import json
    from pathlib import Path

    path = Path(image_path).with_suffix(".json")
    if not path.exists():
        return None, ""
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8-sig")
        data = json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"{path.name} cannot be read ({exc.__class__.__name__})"
    if not isinstance(data, dict):
        return None, f"{path.name}: not a JSON object"
    unknown = sorted(set(data) - set(FIT_KEYS) - set(FIT_OPTIONAL_KEYS))
    if unknown:
        return None, f"{path.name}: unknown key {unknown[0]!r} (allowed: pupil, limbus, hold_outer_color)"
    if any(k not in data for k in FIT_KEYS):
        return None, f"{path.name}: needs 'pupil' and 'limbus'"
    values = []
    for key in FIT_KEYS:
        value = data[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            return None, f"{path.name}: {key!r} is not a number"
        values.append(float(value))
    pupil, limbus = values
    if not 0.0 < pupil < limbus <= 1.0:
        return None, f"{path.name}: needs 0 < pupil < limbus <= 1"
    hold = data.get("hold_outer_color", False)
    if not isinstance(hold, bool):
        return None, f"{path.name}: 'hold_outer_color' must be true or false"
    return {"fit_pupil": pupil, "fit_limbus": limbus, "hold_outer_color": hold}, ""
