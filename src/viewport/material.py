"""Surface material of the viewport: base colour + the Worklight specular finish (GL-free).

The material is the one `uniform_packet()` a `RenderMesh` uploads as `material_uniforms`
(`bind_material` / `mark_material_dirty` / `material_updates`). A change is a uniform update only:
no geometry, no index or face-data upload.

Packet layout (floats): `[r, g, b, specular, glossiness, fill_specular]`. A 3-float packet (a host
or test material that only knows a colour) is read as that colour with `DEFAULT_FINISH`, so every
surface in the app shades alike.

Specular (2026-10-23, modelling Worklight, not PBR): Blinn-Phong on the key light, neutral white,
`specular * luminance(key) * max(N·H, 0)^exponent`, only where `N·L > 0`, with a non-local viewer
(V = the camera's view axis, the fixed-function default: a Flat polygon stays one colour, and the
highlight follows the normal alone while orbiting under a camera-space light). Not energy-normalised on
purpose: `specular` alone sets the peak, `glossiness` alone the size of the highlight, so the two
parameters stay independent when tuned. The fill light gets its own strength (`fill_specular`, off
by default) so curved forms do not show two highlights unless asked for.

Glossiness → exponent (`gloss_exponent`): logarithmic between `EXPONENT_MIN` and `EXPONENT_MAX`,
`exponent = 4 · 64^g` for `g` in [0, 1] (0 → 4, 0.25 → ≈11.3, 0.5 → 32, 0.75 → ≈90.5, 1 → 256).
Equal glossiness steps are equal ratios of the exponent, roughly equal visual steps of highlight
size, and a value keeps its meaning if the range is retuned only at the ends.

`specular_term` is the pure-Python mirror of the GLSL term in `gl_render_store.FRAGMENT_SRC`;
`light_rig.shade` adds it to the diffuse reference. Change one, change the other.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

Vec3 = tuple[float, float, float]

EXPONENT_MIN = 4.0
EXPONENT_MAX = 256.0
SPECULAR_MAX = 1.0

#: Rec. 709 luminance weights (same as `light_rig.REC709_LUMA`; the highlight is neutral white
#: scaled by the key's luminance, never tinted by the key's temperature).
_LUMA = (0.2126, 0.7152, 0.0722)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def gloss_exponent(glossiness: float) -> float:
    """Blinn-Phong exponent for `glossiness` in [0, 1] (clamped); see the module docstring."""
    return EXPONENT_MIN * (EXPONENT_MAX / EXPONENT_MIN) ** _clamp01(glossiness)


@dataclass(frozen=True)
class SurfaceFinish:
    """The specular part of the material. All values in [0, 1]."""

    specular: float = 0.25
    glossiness: float = 0.5
    fill_specular: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "specular", max(0.0, min(SPECULAR_MAX, float(self.specular))))
        object.__setattr__(self, "glossiness", _clamp01(self.glossiness))
        object.__setattr__(self, "fill_specular", max(0.0, min(SPECULAR_MAX, float(self.fill_specular))))

    @property
    def exponent(self) -> float:
        return gloss_exponent(self.glossiness)

    def with_(self, **changes) -> "SurfaceFinish":
        return replace(self, **changes)


#: PROVISIONAL defaults (agent-set 2026-10-23, no Artist verdict): a soft, mid-size key highlight
#: (peak ≈ +0.15 on the Raitt key of 0.6) that reads curvature, pinching and waviness on a head
#: without changing the diffuse look away from it; fill highlight off.
DEFAULT_FINISH = SurfaceFinish()
#: No highlight at all (the look before 2026-10-23).
MATTE_FINISH = SurfaceFinish(specular=0.0, fill_specular=0.0)


class Material:
    """Base colour + finish (duck-typed `uniform_packet()` for `RenderMesh.bind_material`)."""

    def __init__(self, color: Vec3, finish: SurfaceFinish = DEFAULT_FINISH) -> None:
        self.color = tuple(float(c) for c in color)
        self.finish = finish

    def uniform_packet(self) -> list[float]:
        f = self.finish
        return [*self.color, f.specular, f.glossiness, f.fill_specular]


def read_packet(data, default_color: Vec3) -> tuple[Vec3, SurfaceFinish]:
    """(colour, finish) from a `material_uniforms` packet: 6 floats = full, 3 = colour only
    (`DEFAULT_FINISH`), anything else = `default_color` with `DEFAULT_FINISH`."""
    if len(data) >= 6:
        return (data[0], data[1], data[2]), SurfaceFinish(data[3], data[4], data[5])
    if len(data) == 3:
        return (data[0], data[1], data[2]), DEFAULT_FINISH
    return tuple(default_color), DEFAULT_FINISH


def _dot(a, b) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _normalize(v) -> Vec3:
    length = math.sqrt(_dot(v, v))
    if length == 0.0:
        return (0.0, 0.0, 0.0)
    return (v[0] / length, v[1] / length, v[2] / length)


def specular_term(normal: Vec3, light_dir: Vec3, view_dir: Vec3, exponent: float) -> float:
    """GLSL `blinn_phong()`: `max(N·H, 0)^exponent` where `N·L > 0`, else 0. Unit inputs
    expected for `normal` and `light_dir`; `view_dir` points toward the eye (the shader passes
    the camera's view axis, a non-local viewer)."""
    if _dot(normal, light_dir) <= 0.0:
        return 0.0
    h = _normalize((light_dir[0] + view_dir[0], light_dir[1] + view_dir[1], light_dir[2] + view_dir[2]))
    return max(_dot(normal, h), 0.0) ** exponent


def luminance(rgb: Vec3) -> float:
    return sum(w * c for w, c in zip(_LUMA, rgb))
