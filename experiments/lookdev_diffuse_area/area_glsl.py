"""GLSL variants of the key's diffuse term, patched into the production skin fragment *inside this experiment's
process only* (2026-11-24). `src/` is not changed: `install(config)` replaces `viewport.lookdev_pass.skin_sources` (the
name the pass calls) with a wrapper that edits the fragment string; `uninstall()` restores it.

Every edit asserts its anchor, so a production change makes the experiment fail loudly instead of comparing the wrong
shader. The eye program is not touched (it builds from `lookdev_shaders.LD_COMMON_SRC`, which stays as it is).

Config (`Variant`):
- `method`   "A" (production: `ld_wrap`), "B" (the quadratic horizon spline), "B2" (the exact sphere irradiance),
             "C" (`samples` directions on the cap). Twins: `area_math.lambert_wrap` / `area_quad` / `area_exact` /
             `area_samples`.
- `samples`  C's direction count (a const array, unrolled by the compiler).
- `excess`   which key visibility the light past Lambert takes (the SHADOW block): "lifted" - the area band joins the
             wrap's excess under production's lifted lookup (AD-039 §16.7: the map read 4 normal offsets further out);
             "split" - the wrap's excess exactly as production, the area band (method minus wrap) under the plain
             lookup like Lambert; "point" - all of it under the plain lookup (for contrast).
- `spec`     False = no specular at all (`direct_specular` and `env_brdf_approx` x 0): the diffuse-only comparison.
- `linear`   True = `lookdev_output` writes exposure x colour, no tone curve and no encode (captured into a float FBO and
             tone-mapped in NumPy with production's twin, so every image goes through the identical curve).
"""

from __future__ import annotations

from dataclasses import dataclass

from area_math import GOLDEN_ANGLE, S_MAX, cap_offsets

ANCHOR_WRAP = "vec3 ld_wrap(float ndl, vec3 w) { return max((vec3(ndl) + w) / (vec3(1.0) + w), vec3(0.0)); }\n"
ANCHOR_DIFFUSE_LOOP = ("for (int i = 0; i < LD_LIGHTS; ++i) light += u_ld_light_color[i] * ld_wrap(dot(n, "
                       "u_ld_light_dir[i]), wrap);")
ANCHOR_SHADOW_WRAP = "(ld_wrap(ndl, u_wrap) - lambert)"
ANCHOR_VIS_WRAP = "(1.0 - vis_wrap) * (ld_wrap"
ANCHOR_OUTPUT = "vec3 lookdev_output(vec3 c) { return srgb_encode(ld_tone(max(c, 0.0) * u_ld_exposure)); }"
ANCHOR_COMMON = "\n// -- LookDev (AD-038 §5.2)"
ANCHOR_DIRECT = "float direct_specular(vec3 n, vec3 v, vec3 l, float roughness, float f0) {"
ANCHOR_ENV_BRDF = "float env_brdf_approx("
ANCHOR_LIFT = "ld_shadow_coord_lifted(p, n, l, LD_SHADOW_WRAP_LIFT)"
#: `lift`: the lifted lookup's distance - "effective" (production: 4 normal offsets of the *effective* map, so it grows
#: with the key's size up to 6x at size 1), "full" (4 offsets of the full-resolution map: a constant world distance),
#: "mid" (the geometric mean: x sqrt(scale)).
LIFTS = {"effective": "LD_SHADOW_WRAP_LIFT", "full": "LD_SHADOW_WRAP_LIFT * u_ld_shadow_scale",
         "mid": "LD_SHADOW_WRAP_LIFT * sqrt(u_ld_shadow_scale)"}


@dataclass(frozen=True)
class Variant:
    method: str = "A"
    samples: int = 16
    excess: str = "lifted"
    spec: bool = True
    linear: bool = False
    s_max: float = S_MAX
    lift: str = "effective"
    #: bench only: `ld_diffuse` evaluates the method this many times (a slightly different normal each time, so the
    #: compiler cannot merge them) - the per-pixel cost difference between two methods x repeat rises above the noise
    repeat: int = 1

    def label(self) -> str:
        m = f"C{self.samples}" if self.method == "C" else self.method
        return (m + ("" if self.repeat <= 1 else f"x{self.repeat}") + ("" if self.excess == "lifted" else f"-{self.excess}") + ("" if self.lift == "effective" else
                f"-lift{self.lift}") + ("" if self.spec else "-diffuse"))


def _replace(text: str, old: str, new: str, count: int | None = None) -> str:
    found = text.count(old)
    if found == 0 or (count is not None and found != count):
        raise AssertionError(f"anchor found {found}x (want {count or '>= 1'}): {old[:70]!r}")
    return text.replace(old, new)


def area_library(v: Variant) -> str:
    """`ldx_diffuse(i, n, wrap)`: light i's diffuse factor (per channel) at world normal n."""
    head = f"// -- experiment lookdev_diffuse_area: method {v.method}\nconst float LDX_S_MAX = {float(v.s_max)!r};\n"
    if v.method == "A":
        body = "vec3 ldx_diffuse(int i, vec3 n, vec3 wrap) { return ld_wrap(dot(n, u_ld_light_dir[i]), wrap); }\n"
    elif v.method == "B":
        body = """// the sphere light's irradiance as the C1 horizon spline, the cosine shifted by the material's wrap
vec3 ldx_diffuse(int i, vec3 n, vec3 wrap) {
    float s = max(u_ld_light_size[i] * LDX_S_MAX, 1e-4);
    vec3 x = vec3(dot(n, u_ld_light_dir[i])) + wrap;
    vec3 t = max(x + s, 0.0);
    vec3 e = mix(t * t / (4.0 * s), x, step(vec3(s), x));
    return e / (vec3(1.0) + wrap);
}
"""
    elif v.method == "B2":
        body = """// the exact irradiance of a uniform sphere light (Snyder; the Frostbite form), the cosine shifted by the wrap
vec3 ldx_diffuse(int i, vec3 n, vec3 wrap) {
    float s = max(u_ld_light_size[i] * LDX_S_MAX, 1e-4);
    float s2 = s * s;
    vec3 x = vec3(dot(n, u_ld_light_dir[i])) + wrap;
    vec3 xc = clamp(x, -1.0, 1.0);
    vec3 sin_t = sqrt(max(1.0 - xc * xc, 1e-12));
    float xx = sqrt(max(1.0 / s2 - 1.0, 0.0));
    vec3 y = clamp(-xx * xc / sin_t, -1.0, 1.0);
    vec3 sty = sin_t * sqrt(max(1.0 - y * y, 0.0));
    vec3 part = max(((xc * acos(y) - xx * sty) * s2 + atan(sty, vec3(xx))) / (PI * s2), 0.0);
    vec3 e = mix(part, x, step(vec3(s), x));
    return e / (vec3(1.0) + wrap);
}
"""
    elif v.method == "C":
        off = cap_offsets(v.samples)
        rows = ",\n    ".join(f"vec3({float(u)!r}, {float(cp)!r}, {float(sp)!r})" for u, cp, sp in off)
        body = f"""// {v.samples} directions on the emitter's cap (Vogel spiral, uniform in solid angle; golden angle {GOLDEN_ANGLE:.6f})
const int LDX_N = {v.samples};
const vec3 LDX_CAP[LDX_N] = vec3[](
    {rows});
vec3 ldx_diffuse(int i, vec3 n, vec3 wrap) {{
    vec3 l = u_ld_light_dir[i];
    float s = u_ld_light_size[i] * LDX_S_MAX;
    float cos_sigma = sqrt(max(1.0 - s * s, 0.0));
    float norm = 2.0 / (1.0 + cos_sigma);  // the cap's mean cosine is c (1 + cos sigma) / 2: the lit side stays Lambert
    vec3 right;
    vec3 up;
    if (i == 0) {{
        right = u_ld_key_right;
        up = u_ld_key_up;
    }} else {{
        vec3 ref = abs(l.y) < 0.999 ? vec3(0.0, 1.0, 0.0) : vec3(1.0, 0.0, 0.0);
        right = normalize(cross(ref, l));
        up = cross(l, right);
    }}
    vec3 sum = vec3(0.0);
    for (int k = 0; k < LDX_N; ++k) {{
        float cos_a = 1.0 - LDX_CAP[k].x * (1.0 - cos_sigma);
        float sin_a = sqrt(max(1.0 - cos_a * cos_a, 0.0));
        vec3 d = l * cos_a + (right * LDX_CAP[k].y + up * LDX_CAP[k].z) * sin_a;
        sum += max((vec3(dot(n, d) * norm) + wrap) / (vec3(1.0) + wrap), 0.0);
    }}
    return sum / float(LDX_N);
}}
"""
    else:
        raise ValueError(v.method)
    return head + body


def patch_fragment(fragment: str, v: Variant) -> str:
    out = _replace(fragment, ANCHOR_WRAP, ANCHOR_WRAP + area_library(v), 1)
    if v.repeat <= 1:
        loop = "for (int i = 0; i < LD_LIGHTS; ++i) light += u_ld_light_color[i] * ldx_diffuse(i, n, wrap);"
    else:
        loop = (f"for (int i = 0; i < LD_LIGHTS; ++i) {{ vec3 acc = vec3(0.0); for (int r = 0; r < {v.repeat}; ++r) "
                "acc += ldx_diffuse(i, normalize(n + float(r) * 1e-4 * u_ld_light_dir[i]), wrap); "
                f"light += u_ld_light_color[i] * acc / {float(v.repeat)!r}; }}")
    out = _replace(out, ANCHOR_DIFFUSE_LOOP, loop, 1)
    if "#define SHADOW 1" in out:
        if v.excess == "lifted":  # the area band joins the wrap's excess: both take the lifted lookup
            out = _replace(out, ANCHOR_SHADOW_WRAP, "(ldx_diffuse(0, n, u_wrap) - lambert)")
        elif v.excess == "split":  # the wrap's excess as production; the area band takes the plain lookup (as Lambert)
            out = _replace(out, ANCHOR_SHADOW_WRAP, "(ld_wrap(ndl, u_wrap) - lambert) + (1.0 - vis) * "
                                                    "(ldx_diffuse(0, n, u_wrap) - ld_wrap(ndl, u_wrap))")
        elif v.excess == "point":  # everything past Lambert (wrap included) takes the plain lookup - for contrast
            out = _replace(out, ANCHOR_VIS_WRAP, "(1.0 - vis) * (ld_wrap")
            out = _replace(out, ANCHOR_SHADOW_WRAP, "(ldx_diffuse(0, n, u_wrap) - lambert)")
        else:
            raise ValueError(v.excess)
        if v.lift != "effective":
            out = _replace(out, ANCHOR_LIFT, f"ld_shadow_coord_lifted(p, n, l, {LIFTS[v.lift]})", 1)
    if not v.spec:
        out = _replace(out, ANCHOR_DIRECT, "float direct_specular_ldx(vec3 n, vec3 v, vec3 l, float roughness, float f0) {", 1)
        out = _replace(out, ANCHOR_ENV_BRDF, "float env_brdf_approx_ldx(", 1)
        out = _replace(out, ANCHOR_COMMON,
                       "\nfloat direct_specular(vec3 n, vec3 v, vec3 l, float roughness, float f0) { return 0.0; }\n"
                       "float env_brdf_approx(float f0, float roughness, float nv) { return 0.0; }\n"
                       + ANCHOR_COMMON, 1)
    if v.linear:
        out = _replace(out, ANCHOR_OUTPUT,
                       "vec3 lookdev_output(vec3 c) { return max(c, 0.0) * u_ld_exposure; }", 1)
    return out


_ORIGINAL = None
CURRENT = Variant()


def install(variant: Variant) -> None:
    """From now on the skin programs the pass compiles are `variant`'s (call `reset_programs` to drop cached ones)."""
    global _ORIGINAL, CURRENT
    from viewport import lookdev_pass

    if _ORIGINAL is None:
        _ORIGINAL = lookdev_pass.skin_sources
    CURRENT = variant

    def patched(locations, *key, **kw):
        sources = _ORIGINAL(locations, *key, **kw)
        return [(patch_fragment(src, CURRENT) if kind == "fragment" else src, kind) for src, kind in sources]

    lookdev_pass.skin_sources = patched


def uninstall() -> None:
    global _ORIGINAL
    from viewport import lookdev_pass

    if _ORIGINAL is not None:
        lookdev_pass.skin_sources = _ORIGINAL
        _ORIGINAL = None


def reset_programs(app) -> int:
    """Drop the LookDev pass's cached skin programs (the next frame compiles the installed variant). Returns how many."""
    programs = app.viewport.lookdev_pass.programs
    n = len(programs)
    for program in programs.values():
        try:
            program.delete()
        except Exception:  # noqa: BLE001 - a program already gone
            pass
    programs.clear()
    return n
