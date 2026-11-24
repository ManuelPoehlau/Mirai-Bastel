"""PCSS for the key's shadow map, patched into the production skin fragment *inside this experiment's process only*
(2026-11-24, LookDev P3, AD-039 §23.6 / Q-S8-3). `src/` is not changed.

What `install(area, pcss)` does in this process:
- the skin fragment: `area_glsl.patch_fragment(fragment, area)` (the diffuse-only / linear-output levers of the
  diffuse-area experiment), then - with a `Pcss` - the two lookups of the SHADOW block (`ld_key_visibility` for the
  key's Lambert part and highlight, `ld_key_visibility_lifted` for the wrap's / the area band's excess) replaced by
  `ldx_key_shadow`: a blocker search in the raw depth (unit 7, S4's sampler without compare) and a PCF whose radius is
  the penumbra of a disc light of angular radius sigma, (receiver depth - mean blocker depth) x tan sigma;
- `full = True`: the map at full resolution for every key size (`lookdev_optics.shadow_resolution` replaced; the eye
  pass reads the same map, so its lookup is the size-0 one then - measured, see the README);
- the raw sampler bound on unit 7 for every skin draw with the shadow (production binds it only with the thickness).

The eye's sources are not touched (they come from `eye_shaders.shell_sources`, not `skin_sources`).

Every anchor is asserted, so a production change fails loudly.

Geometry: the key's map is orthographic over a sphere of radius R, its UV spans 2R and its depth [0, 1] spans 2R too
(`shadow_view_projection`), so a depth difference in map units *is* a UV distance: penumbra radius (UV) =
(z_receiver - z_blocker) x tan sigma, no further uniform. sin sigma = size x sin 40° (the S8 mapping,
`lookdev_shaders.AREA_SIN_MAX`), so shadow, terminator band and the 32-key reference share one sigma.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import area_glsl as ag

GOLDEN = math.pi * (3.0 - math.sqrt(5.0))

ANCHOR_SHADOW_END = """float ld_key_visibility_lifted(vec3 p, vec3 n, vec3 l) {
    vec3 sp = ld_shadow_coord_lifted(p, n, l, LD_SHADOW_WRAP_LIFT);
    return ld_shadow_pcf(sp, ld_shadow_slope(sp));
}
"""
ANCHOR_THICKNESS_DEPTH = "uniform sampler2D u_ld_shadow_depth;\nuniform float u_ld_shadow_range;"
CALLS = {
    "n": ("float vis = ld_key_visibility(v_world_pos, n, u_ld_light_dir[0]);\n"
          "        float vis_wrap = ld_key_visibility_lifted(v_world_pos, n, u_ld_light_dir[0]);"),
    "n_geo": ("float vis = ld_key_visibility(v_world_pos, n_geo, u_ld_light_dir[0]);\n"
              "        float vis_wrap = ld_key_visibility_lifted(v_world_pos, n_geo, u_ld_light_dir[0]);"),
}


def pattern(kind: str, count: int) -> list[tuple[float, float]]:
    """Unit-square / unit-disc offsets: "grid" a k x k grid over [-1, 1]² (k² = count), "disc" a Vogel spiral in the
    unit disc (sqrt((i + 0.5) / n), golden angle: an even, fixed, noise-free Poisson-like set)."""
    if kind == "grid":
        k = int(round(math.sqrt(count)))
        if k * k != count:
            raise ValueError(f"grid needs a square count, not {count}")
        steps = [(-1.0 + 2.0 * i / (k - 1)) if k > 1 else 0.0 for i in range(k)]
        return [(x, y) for y in steps for x in steps]
    if kind == "centre":  # a Vogel spiral with the radius linear in i: denser near the centre (thin contact blockers)
        return [((i + 0.5) / count * math.cos(i * GOLDEN), (i + 0.5) / count * math.sin(i * GOLDEN))
                for i in range(count)]
    if kind == "disc":
        return [(math.sqrt((i + 0.5) / count) * math.cos(i * GOLDEN), math.sqrt((i + 0.5) / count) * math.sin(i * GOLDEN))
                for i in range(count)]
    raise ValueError(kind)


@dataclass(frozen=True)
class Pcss:
    blocker: int = 16          # blocker-search fetches (raw depth)
    pcf: int = 16              # PCF fetches (each a hardware 2 x 2 bilinear compare)
    kind: str = "disc"         # "disc" (Vogel) or "grid", both patterns
    full: bool = True          # the map at full resolution for every key size
    #: the blocker search's reach in map depth units (2R): a blocker up to this far above the receiver is found.
    #: Gollum: 2R ~ 2 WE ~ 42 cm, so 0.15 ~ 6 cm (the nose over the cheek is 2-4 cm)
    search: float = 0.15
    #: the PCF radius's floor in texels of the map in use: 1 = production's 3 x 3 one texel apart (size 0 = today's)
    min_texels: float = 1.0
    #: the PCF / search radius's cap in texels of the full map (the fetches stay a usable density)
    max_texels: float = 48.0
    #: "shared": one search at the surface point, its penumbra for both lookups; "each": each lookup searches itself
    search_at: str = "shared"
    #: early out: no blocker in the search -> lit without the PCF (a branch; derivatives are taken before it)
    early: bool = True
    #: "pcss" (this experiment) or "production" (production's 3 x 3 lookup unchanged - with `full`: only the map's
    #: resolution changes, the row "F")
    filter: str = "pcss"
    #: the receiver plane: "deriv" = production's (screen derivatives of the map point: per triangle constant),
    #: "normal" = from the shading normal in the map's frame (smooth across triangles)
    plane: str = "deriv"
    #: the slope's clamp (production: `SHADOW_SLOPE_MAX` = 10)
    slope_max: float = 10.0
    #: the blocker search's test: "plane" (the receiver plane, as the PCF) or "cone" (no plane: a fetch is a blocker
    #: when it lies more than |o| x `cone` above the receiver - the receiver's own surface up to that steepness is not)
    #: or "both" (above the cone and above the receiver plane)
    search_test: str = "plane"
    cone: float = 1.0          # 0 = the light's own cone: 1 / tan sigma
    #: behind the terminator (n.l < 0: a facet turned away from the key, its plane lies behind the lit front) the
    #: receiver plane is meaningless: True = compare flat there (slope 0)
    back_flat: bool = False
    #: the PCF's comparison: "plane" (the receiver plane, production's) or "level" (no plane: a fetch is shadowed by a
    #: surface more than `level` x (the receiver's depth - the mean blocker depth) above the receiver, so the receiver's
    #: own surface is not a blocker while the found blockers are) or "min" (lit if either says lit)
    pcf_test: str = "plane"
    #: the lifted lookup's lift grows with the band: + `band_lift` x R x s² world units (R the map's radius, s = sin
    #: sigma; a convex surface of radius rho needs ~ rho s² / 2 to leave its own shadow at the band's edge n.l = -s)
    band_lift: float = 0.0
    band_power: float = 2.0    # the band lift's exponent on s
    #: fade the PCF in over the first `fade` blockers found (0 = off): a search that finds one or two fetches at its
    #: cone's edge (the receiver's own surface, the outer penumbra) does not switch the PCF on at full weight - the
    #: early out's edge stays continuous
    fade: float = 0.0
    #: near the centre the receiver plane, farther out the cone / level test: per fetch the plane's weight is
    #: 1 - smoothstep(near, 2.5 near, |o| in texels) (0 = off: the cone / level test everywhere). Small kernels (a hard
    #: key, a contact shadow) then compare as production does (AD-039 §16.6: the plane is right over a few texels),
    #: wide ones without the per-triangle plane
    near: float = 0.0
    #: the lifted lookup's lift from the measured chord (shared search only): + `chord` x (receiver - mean blocker
    #: depth, world) x max(-n.l, 0) / 4. On a convex surface of radius rho a point at n.l = -x lies 2 rho x behind its
    #: own lit front and needs ~ rho x² / 2 = chord x / 4 to leave its own shadow; in a crease (a nostril) the wall is
    #: close and the lift stays small
    chord: float = 0.0
    #: the blocker search's radius floor in texels (production's 3 x 3 bilinear PCF reaches 2 texels: a smaller search
    #: misses the edge of a hard / contact shadow and the early out lights it)
    search_min: float = 1.0
    #: the blocker search's pattern ("" = `kind`; "centre" = denser near the centre)
    search_kind: str = ""
    #: cost diagnostics (bench only, 2026-11-24 after the reference-PC run): "" = the lookup; "nofetch" = every fetch
    #: replaced by a cheap data-dependent ALU term (the cost without the texture unit); "search" = the blocker search
    #: alone (no PCF); "pcf" = the two PCFs alone at the search radius (no search, no branch)
    probe: str = ""
    #: NVIDIA loop pragma: "" (driver default), "all" or "none" (`#pragma optionNV(unroll ...)`)
    unroll: str = ""
    #: fewer ALU per fetch: the plane / level blend and the cone length per fragment from the radius, the taps'
    #: lengths as constants, no per-tap smoothstep / length
    lean: bool = False
    level: float = 0.5

    def label(self) -> str:
        if self.filter == "production":
            return "F" if self.full else "P"
        return (f"S{self.blocker}P{self.pcf}{'g' if self.kind == 'grid' else 'd'}" + ("" if self.full else "-eff")
                + ("" if self.search_at == "shared" else "-each") + ("" if self.early else "-nb")
                + ("" if self.search == 0.15 else f"-r{self.search:g}")
                + ("" if self.plane == "deriv" else "-nrm") + ("" if self.search_test == "plane" else f"-{self.search_test}{self.cone:g}")
                + ("-bf" if self.back_flat else "")
                + ("" if self.pcf_test == "plane" else f"-{self.pcf_test}{self.level:g}")
                + ("" if not self.band_lift else f"-bl{self.band_lift:g}")
                + ("" if self.band_power == 2.0 else f"^{self.band_power:g}")
                + ("" if self.slope_max == 10.0 else f"-k{self.slope_max:g}")
                + ("" if not self.fade else f"-f{self.fade:g}") + ("" if not self.near else f"-n{self.near:g}")
                + ("" if not self.chord else f"-ch{self.chord:g}")
                + ("" if self.search_min == 1.0 else f"-sm{self.search_min:g}")
                + ("" if not self.search_kind else f"-{self.search_kind}")
                + ("" if not self.probe else f"-{self.probe}") + ("" if not self.unroll else f"-u{self.unroll}")
                + ("-lean" if self.lean else ""))


def _array(name: str, points) -> str:
    rows = ",\n    ".join(f"vec2({x!r}, {y!r})" for x, y in points)
    return f"const vec2 {name}[{len(points)}] = vec2[](\n    {rows});\n"


def _floats(name: str, values) -> str:
    rows = ", ".join(f"{float(v)!r}" for v in values)
    return f"const float {name}[{len(values)}] = float[]({rows});\n"


def library(p: Pcss) -> str:
    from viewport.lookdev_shaders import AREA_SIN_MAX

    if p.search_at == "shared":  # one search at the surface point; its penumbra for both lookups
        body = """    vec2 found = ldx_blockers(sp, slope, rs);
""" + ("""    if (found.y < 0.5) return vec2(1.0);
""" if p.early else "") + ("""    float chord = found.y > 0.5 ? max(sp.z - found.x / found.y, 0.0) * 2.0 * radius : 0.0;  // world units
    spl = ld_shadow_coord_lifted(p, n, l, LD_SHADOW_WRAP_LIFT
                                 + LDX_CHORD * chord * max(-dot(n, l), 0.0) * 0.25 / max(u_ld_shadow_offset, 1e-9));
    slope_l = slope;  // the lifted plane is parallel to the receiver's
""" if p.chord else "") + """    float r = ldx_penumbra(sp.z, found, rmin);
    float lv = ldx_level(sp.z, found);
    float w = LDX_FADE > 0.0 ? min(found.y / LDX_FADE, 1.0) : 1.0;
    return vec2(1.0) - w * (vec2(1.0) - vec2(ldx_pcf(sp, slope, r, lv), ldx_pcf(spl, slope_l, r, lv)));"""
    elif p.search_at == "each":  # each lookup searches for itself
        if p.early:
            body = """    vec2 found = ldx_blockers(sp, slope, rs);
    vec2 found_l = ldx_blockers(spl, slope_l, rs);
    float v = found.y < 0.5 ? 1.0 : ldx_pcf(sp, slope, ldx_penumbra(sp.z, found, rmin), ldx_level(sp.z, found));
    float v_l = found_l.y < 0.5 ? 1.0 : ldx_pcf(spl, slope_l, ldx_penumbra(spl.z, found_l, rmin),
                                               ldx_level(spl.z, found_l));
    return vec2(v, v_l);"""
        else:
            body = """    vec2 found = ldx_blockers(sp, slope, rs);
    vec2 found_l = ldx_blockers(spl, slope_l, rs);
    return vec2(ldx_pcf(sp, slope, ldx_penumbra(sp.z, found, rmin), ldx_level(sp.z, found)),
                ldx_pcf(spl, slope_l, ldx_penumbra(spl.z, found_l, rmin), ldx_level(spl.z, found_l)));"""
    else:
        raise ValueError(p.search_at)
    if p.probe == "search":
        body = """    vec2 found = ldx_blockers(sp, slope, rs);
    return vec2(1.0 - found.y / float(LDX_NB), clamp(found.x, 0.0, 1.0));"""
    elif p.probe == "pcf":
        body = """    float lv = 0.01 * sp.z;
    return vec2(ldx_pcf(sp, slope, rs, lv), ldx_pcf(spl, slope_l, rs, lv));"""
    elif p.probe not in ("", "nofetch"):
        raise ValueError(p.probe)
    fetch = ("#define LDX_RAW(uv) fract(dot(uv, vec2(12.9898, 78.233)) * 43.75)\n"
             "#define LDX_CMP(c) step(0.5, fract(dot(c, vec3(12.9898, 78.233, 37.719)) * 43.75))\n"
             if p.probe == "nofetch" else
             "#define LDX_RAW(uv) textureLod(u_ld_shadow_depth, uv, 0.0).r\n"
             "#define LDX_CMP(c) textureLod(u_ld_shadow, c, 0.0)\n")
    pragma = f"#pragma optionNV(unroll {p.unroll})\n" if p.unroll else ""
    lengths = (_floats("LDX_BL", [math.hypot(x, y) for x, y in pattern(p.search_kind or p.kind, p.blocker)])
               if p.lean else "")
    plane = (("#define LDX_PLANE_NORMAL 1\n" if p.plane == "normal" else "")
             + ("#define LDX_SEARCH_CONE 1\n" if p.search_test == "cone" else "")
             + ("#define LDX_SEARCH_BOTH 1\n" if p.search_test == "both" else "")
             + ("#define LDX_BACK_FLAT 1\n" if p.back_flat else "")
             + ("#define LDX_NEAR_ON 1\n" if p.near else "")
             + {"plane": "", "level": "#define LDX_PCF_LEVEL 1\n", "min": "#define LDX_PCF_MIN 1\n"}[p.pcf_test]
             + ("#define LDX_LEAN 1\n" if p.lean else "") + pragma + fetch)
    return f"""
// -- experiment lookdev_pcss: {p.label()} - blocker search + PCF with the penumbra of a disc light (AD-039 §23.6)
uniform sampler2D u_ld_shadow_depth;  // S4's raw depth (unit 7); with THICKNESS its own declaration is removed
const float LDX_SIN_MAX = {AREA_SIN_MAX!r};
{plane}const float LDX_SEARCH = {float(p.search)!r};
const float LDX_SLOPE_MAX = {float(p.slope_max)!r};
const float LDX_CONE = {float(p.cone)!r};
const float LDX_LEVEL = {float(p.level)!r};
const float LDX_BAND_LIFT = {float(p.band_lift)!r};
const float LDX_FADE = {float(p.fade)!r};
const float LDX_BAND_POWER = {float(p.band_power)!r};
const float LDX_NEAR = {float(p.near)!r};
const float LDX_CHORD = {float(p.chord)!r};
const float LDX_SEARCH_MIN = {float(p.search_min)!r};
const float LDX_MIN_TEXELS = {float(p.min_texels)!r};
const float LDX_MAX_TEXELS = {float(p.max_texels)!r};
const int LDX_NB = {p.blocker};
const int LDX_NP = {p.pcf};
{_array("LDX_B", pattern(p.search_kind or p.kind, p.blocker))}{_array("LDX_P", pattern(p.kind, p.pcf))}{lengths}
float ldx_tan_sigma() {{
    float s = u_ld_light_size[0] * LDX_SIN_MAX;
    return s / sqrt(max(1.0 - s * s, 1e-6));
}}
float ldx_cone() {{
    return LDX_CONE > 0.0 ? LDX_CONE : 1.0 / max(ldx_tan_sigma(), 1e-3);
}}
// 0 near the map point (the receiver plane decides), 1 from 2.5 x LDX_NEAR texels out (the cone / level decides)
float ldx_far(vec2 o) {{
    return smoothstep(LDX_NEAR, 2.5 * LDX_NEAR, length(o) * u_ld_shadow_scale / u_ld_shadow_radius);
}}
// x: the summed depth of the blockers around sp within radius r (map UV), y: how many; a blocker is nearer to the
// key than the receiver's own plane at the fetch (the receiver-plane bias of the PCF)
vec2 ldx_blockers(vec3 sp, vec2 slope, float r) {{
    vec2 acc = vec2(0.0);
#if defined(LDX_LEAN)
    float rc = r * ldx_cone();
    float fw = smoothstep(LDX_NEAR, 2.5 * LDX_NEAR, 0.5 * r * u_ld_shadow_scale / u_ld_shadow_radius);
#endif
    for (int k = 0; k < LDX_NB; ++k) {{
        vec2 o = LDX_B[k] * r;
        float d = LDX_RAW((sp.xy + o) * u_ld_shadow_scale);
#if defined(LDX_LEAN)
        float b = step(d, sp.z - 2.0 * LD_SHADOW_BIAS + mix(dot(slope, o), -LDX_BL[k] * rc, fw));
#elif defined(LDX_NEAR_ON)
        float b = step(d, sp.z - 2.0 * LD_SHADOW_BIAS + mix(dot(slope, o), -length(o) * ldx_cone(), ldx_far(o)));
#elif defined(LDX_SEARCH_BOTH)
        float b = step(d, sp.z - 2.0 * LD_SHADOW_BIAS + min(dot(slope, o), -length(o) * ldx_cone()));
#elif defined(LDX_SEARCH_CONE)
        float b = step(d, sp.z - 2.0 * LD_SHADOW_BIAS - length(o) * ldx_cone());
#else
        float b = step(d, sp.z - LD_SHADOW_BIAS + dot(slope, o) - LD_SHADOW_BIAS);
#endif
        acc += vec2(d * b, b);
    }}
    return acc;
}}
// the PCF's level: how far above the receiver a fetch must lie to shadow it (LDX_PCF_LEVEL / _MIN)
float ldx_level(float z, vec2 found) {{
    return found.y > 0.5 ? LDX_LEVEL * max(z - found.x / found.y, 0.0) : 0.0;
}}
// the PCF radius (map UV): the penumbra (z - mean blocker) x tan sigma, between the floor and the cap
float ldx_penumbra(float z, vec2 found, float rmin) {{
    float zb = found.y > 0.5 ? found.x / found.y : z;
    return clamp(max(z - zb, 0.0) * ldx_tan_sigma(), rmin, LDX_MAX_TEXELS * u_ld_shadow_radius);
}}
float ldx_pcf(vec3 sp, vec2 slope, float r, float lift) {{
    float sum = 0.0;
#if defined(LDX_LEAN)
    float fw = smoothstep(LDX_NEAR, 2.5 * LDX_NEAR, 0.5 * r * u_ld_shadow_scale / u_ld_shadow_radius);
#endif
    for (int k = 0; k < LDX_NP; ++k) {{
        vec2 o = LDX_P[k] * r;
#if defined(LDX_LEAN)
        float ref = sp.z - LD_SHADOW_BIAS + mix(dot(slope, o), -lift, fw);
#elif defined(LDX_NEAR_ON)
        float ref = sp.z - LD_SHADOW_BIAS + mix(dot(slope, o), -lift, ldx_far(o));
#elif defined(LDX_PCF_LEVEL)
        float ref = sp.z - LD_SHADOW_BIAS - lift;
#elif defined(LDX_PCF_MIN)
        float ref = sp.z - LD_SHADOW_BIAS + min(dot(slope, o), -lift);
#else
        float ref = sp.z - LD_SHADOW_BIAS + dot(slope, o);
#endif
        sum += LDX_CMP(vec3((sp.xy + o) * u_ld_shadow_scale, ref));
    }}
    float inside = float(all(greaterThanEqual(sp, vec3(0.0))) && all(lessThanEqual(sp, vec3(1.0))));
    return mix(1.0, sum / float(LDX_NP), inside);
}}
// the receiver's slope (d depth / d uv) of the plane through the map point with world normal n: the map is
// orthographic, its rows map world to (u, v, depth) with one scale, so slope = (n.right, n.up) / (n.toward key)
vec2 ldx_normal_slope(vec3 n) {{
    vec3 ru = vec3(u_ld_shadow_vp[0][0], u_ld_shadow_vp[1][0], u_ld_shadow_vp[2][0]);
    vec3 rv = vec3(u_ld_shadow_vp[0][1], u_ld_shadow_vp[1][1], u_ld_shadow_vp[2][1]);
    vec3 rz = vec3(u_ld_shadow_vp[0][2], u_ld_shadow_vp[1][2], u_ld_shadow_vp[2][2]);
    float nl = max(-dot(n, rz), 1e-6);
    return clamp(vec2(dot(n, ru), dot(n, rv)) / nl, -LDX_SLOPE_MAX, LDX_SLOPE_MAX);
}}
vec2 ldx_slope(vec3 sp, vec3 n) {{
#ifdef LDX_PLANE_NORMAL
    return ldx_normal_slope(n);
#else
    vec3 dx = dFdx(sp);
    vec3 dy = dFdy(sp);
    float det = dx.x * dy.y - dx.y * dy.x;
    vec2 slope = abs(det) > 1e-14 ? vec2(dy.y * dx.z - dx.y * dy.z, dx.x * dy.z - dy.x * dx.z) / det : vec2(0.0);
    return clamp(slope, -LDX_SLOPE_MAX, LDX_SLOPE_MAX);
#endif
}}
// (the key's visibility, the lifted lookup's visibility): ld_key_visibility / ld_key_visibility_lifted with PCSS
vec2 ldx_key_shadow(vec3 p, vec3 n, vec3 l) {{
    vec3 sp = ld_shadow_coord(p, n, l);
    float sb = u_ld_light_size[0] * LDX_SIN_MAX;
    float radius = 1.0 / length(vec3(u_ld_shadow_vp[0][0], u_ld_shadow_vp[1][0], u_ld_shadow_vp[2][0]));
    vec3 spl = ld_shadow_coord_lifted(p, n, l, LD_SHADOW_WRAP_LIFT
                                      + LDX_BAND_LIFT * radius * pow(sb, LDX_BAND_POWER) / max(u_ld_shadow_offset, 1e-9));
    vec2 slope = ldx_slope(sp, n);         // the derivatives first: uniform control flow
    vec2 slope_l = ldx_slope(spl, n);
#ifdef LDX_BACK_FLAT
    float front = step(0.0, dot(n, l));
    slope *= front;
    slope_l *= front;
#endif
    float texel = u_ld_shadow_radius / u_ld_shadow_scale;
    float rmin = LDX_MIN_TEXELS * texel;
    float rs = clamp(LDX_SEARCH * ldx_tan_sigma(), LDX_SEARCH_MIN * texel, LDX_MAX_TEXELS * u_ld_shadow_radius);
{body}
}}
"""


def patch_shadow(fragment: str, p: Pcss) -> str:
    if "#define SHADOW 1" not in fragment or p.filter == "production":
        return fragment
    out = ag._replace(fragment, ANCHOR_SHADOW_END, ANCHOR_SHADOW_END + library(p), 1)
    if "#define THICKNESS 1" in fragment:  # LD_THICKNESS_SRC (after this library) declares the raw depth too
        out = ag._replace(out, ANCHOR_THICKNESS_DEPTH, ANCHOR_THICKNESS_DEPTH.split("\n", 1)[1], 1)
    for normal, calls in CALLS.items():
        if normal == "n_geo" and "#define NORMAL_MAP 1" not in fragment:
            continue
        out = ag._replace(out, calls, f"vec2 ldx_v = ldx_key_shadow(v_world_pos, {normal}, u_ld_light_dir[0]);\n"
                                      "        float vis = ldx_v.x;\n        float vis_wrap = ldx_v.y;", 1)
    return out


# -- install -------------------------------------------------------------------------------------------------------

_ORIGINAL: dict = {}
CURRENT: tuple = (ag.Variant(), None)


def install(area: ag.Variant, pcss: Pcss | None) -> None:
    """From now on the skin programs are `area`'s patch plus `pcss`'s (None = production's shadow lookup, the map at
    its effective resolution). Call `area_glsl.reset_programs(app)` to drop cached programs."""
    global CURRENT
    from viewport import lookdev_optics, lookdev_pass

    if not _ORIGINAL:
        _ORIGINAL["skin_sources"] = lookdev_pass.skin_sources
        _ORIGINAL["shadow_resolution"] = lookdev_optics.shadow_resolution
        _ORIGINAL["draw"] = lookdev_pass.LookdevPass.draw
        original = _ORIGINAL["skin_sources"]
        original_res = _ORIGINAL["shadow_resolution"]
        original_draw = _ORIGINAL["draw"]

        def patched(locations, *key, **kw):
            a, p = CURRENT
            sources = original(locations, *key, **kw)
            out = []
            for src, kind in sources:
                if kind == "fragment":
                    src = ag.patch_fragment(src, a)
                    if p is not None:
                        src = patch_shadow(src, p)
                out.append((src, kind))
            return out

        def resolution(size, map_size=lookdev_optics.SHADOW_SIZE):
            p = CURRENT[1]
            return int(map_size) if p is not None and p.full else original_res(size, map_size)

        def draw(self, render_mesh, look, frame, shadow=None, *args, **kw):
            raw = CURRENT[1] is not None and shadow is not None and shadow.ready
            if raw:
                from viewport.lookdev_shaders import SHADOW_RAW_UNIT

                shadow.bind_raw(SHADOW_RAW_UNIT)
            try:
                return original_draw(self, render_mesh, look, frame, shadow, *args, **kw)
            finally:
                if raw:
                    shadow.unbind_raw(SHADOW_RAW_UNIT)

        lookdev_pass.skin_sources = patched
        lookdev_optics.shadow_resolution = resolution
        lookdev_pass.LookdevPass.draw = draw
    CURRENT = (area, pcss)


def uninstall() -> None:
    from viewport import lookdev_optics, lookdev_pass

    if _ORIGINAL:
        lookdev_pass.skin_sources = _ORIGINAL.pop("skin_sources")
        lookdev_optics.shadow_resolution = _ORIGINAL.pop("shadow_resolution")
        lookdev_pass.LookdevPass.draw = _ORIGINAL.pop("draw")
