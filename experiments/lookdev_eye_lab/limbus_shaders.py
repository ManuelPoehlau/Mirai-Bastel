"""P1c GLSL: the soft limbus (2026-11-14). P1's `shaders.py` and P1b's `refraction_shaders.py` are used as they are.

`LIMBUS_LIB_SRC` holds the twins of `limbus_model.py` (compared on the GPU by `tests/test_gl_limbus.py`).

Two programs, both only for L1 ... L3 (L0 is P1b's own code, untouched), `LIMBUS_LEVEL` 1 / 2 / 3 by `#define`:
- **cornea** (`CORNEA_FRAGMENT_BODY`): P1b's refractive cornea pass with the limbus terms. The ray classes and the
  refraction are P1b's (the true anterior surface); L1 re-grades the limbal tissue colour, L2 shades with the blended
  normal (Fresnel, specular, tissue lighting), L3 lets the tissue transmit the iris behind it (the anterior refraction
  continued past the posterior boundary; for V3 the posterior refraction is not applied to these tissue rays).
- **sclera** (`SCLERA_FRAGMENT_BODY`): P1's sclera shading (same terms as `shaders.SURFACE_FRAGMENT_BODY`) with the
  colour band (L1), the blended normal (L2) and the translucent band (L3, `sclera_through` + the iris image).
Textures are sampled before any branch (implicit derivatives need uniform control flow).
"""

from __future__ import annotations

from . import iris_fit
from . import limbus_model as lm
from . import refraction_shaders as rs
from . import shaders

LIMBUS_LIB_SRC = f"""
const float LIMBUS_RING_RADIUS = {lm.RING_RADIUS!r};
const float LIMBUS_THETA_RING = {lm.THETA_RING!r};
const float LIMBUS_U0 = {lm.U0!r};
const float LIMBUS_COVER_FADE = {lm.COVER_FADE!r};
const float SCLERA_R = {1.0!r};
uniform float u_band;
uniform float u_strength;
uniform float u_normal_w;
uniform float u_falloff;
uniform float u_asym;

float limbus_smooth(float t) {{
    t = clamp(t, 0.0, 1.0);
    return t * t * (3.0 - 2.0 * t);
}}
// limbus_model.sclera_u
float sclera_u(vec3 p) {{
    return (atan(length(p.xy), p.z) - LIMBUS_THETA_RING) * SCLERA_R;
}}
// limbus_model.cornea_u
float cornea_u(vec3 p) {{
    return length(p.xy) - LIMBUS_RING_RADIUS;
}}
// limbus_model.asym_shift
float asym_shift(vec3 p) {{
    return u_asym * p.y * p.y / max(dot(p.xy, p.xy), 1e-12);
}}
// limbus_model.colour_weight
float colour_weight(float u) {{
    return limbus_smooth((u - LIMBUS_U0) / (u_band - LIMBUS_U0));
}}
// limbus_model.tint
vec3 limbus_tint(float w, vec3 limbal, vec3 sclera) {{
    return mix(sclera, mix(limbal, sclera, w), u_strength);
}}
// limbus_model.iris_cover
float iris_cover(float u, float shift) {{
    if (u_asym <= 0.0) return 0.0;  // uniform: no divergence
    float ramp = limbus_smooth((u - (LIMBUS_U0 - shift)) / max(shift, 1e-9));
    return ramp * limbus_smooth(shift / (LIMBUS_COVER_FADE * u_asym));
}}
// limbus_model.normal_blend
vec3 normal_blend(vec3 n_cornea, vec3 n_sclera, float u) {{
    float b = limbus_smooth((u + u_normal_w) / (2.0 * u_normal_w));
    return normalize(mix(n_cornea, n_sclera, b));
}}
// limbus_model.transmission
float transmission(float u) {{
    float t = clamp((u - LIMBUS_U0) / (u_band - LIMBUS_U0), 0.0, 1.0);
    return pow(1.0 - t, u_falloff);
}}
// limbus_model.sclera_through (iris_cone_hit from refraction_shaders)
bool sclera_through(vec3 p, vec3 d, vec3 n_sclera, out vec3 point) {{
    vec3 t_dir = normalize(refract(d, n_sclera, N_AIR / N_CORNEA));
    float t;
    float r;
    bool hit = iris_cone_hit(p, t_dir, t, r);
    point = p + max(t, 0.0) * t_dir;
    return hit && r <= u_iris_radius;
}}
// limbus_model.iris_cone_normal
vec3 iris_cone_normal(vec3 hit) {{
    float r = max(length(hit.xy), 1e-6);
    return normalize(vec3(-u_iris_b * hit.xy / r, 1.0));
}}
"""

_SHARED = """
in vec3 v_normal;
in vec3 v_world_pos;
uniform vec3 u_eye;
uniform vec3 u_f0;
uniform float u_roughness;
uniform vec3 u_key_dir;
uniform vec3 u_key_irradiance;
uniform vec3 u_sky;
uniform vec3 u_ground;
uniform float u_env_intensity;
uniform mat3 u_env_rot;
uniform float u_exposure;
uniform int u_tonemap;
uniform sampler2D u_iris_texture;
uniform vec3 u_sclera_albedo;
uniform vec3 u_limbus_albedo;
uniform vec3 u_pupil_albedo;
#if TECH == 2
uniform samplerCube u_env;
uniform float u_env_last;
uniform int u_lod_mode;
uniform int u_env_rgbm;
uniform float u_rgbm_range;
#endif
out vec4 out_color;

// As in refraction_shaders.CORNEA_FRAGMENT_BODY (P1's surface terms).
vec3 env_specular(vec3 n, vec3 v, float roughness, vec3 f0) {
#if TECH == 1
    return vec3(0.0);
#else
    vec3 d = u_env_rot * reflect(-v, n);
    float nv = max(dot(n, v), 1e-4);
#if TECH == 2
    vec4 texel = textureLod(u_env, d, roughness_to_lod(roughness, u_lod_mode, u_env_last));
    vec3 radiance = u_env_rgbm != 0 ? texel.rgb * texel.a * u_rgbm_range : texel.rgb;
#else
    vec3 radiance = td_env(d, roughness);
#endif
    return radiance * u_env_intensity * env_brdf_approx(f0, roughness, nv);
#endif
}

vec3 specular(vec3 n, vec3 v, float roughness, vec3 f0) {
    return direct_specular(n, v, u_key_dir, roughness, f0) * u_key_irradiance + env_specular(n, v, roughness, f0);
}

vec3 lit(vec3 albedo, vec3 n) {
    return albedo * (u_key_irradiance * (max(dot(n, u_key_dir), 0.0) / PI) + mix(u_ground, u_sky, 0.5 + 0.5 * n.y));
}

vec2 iris_st(vec2 p) {
#ifdef IRIS_FIT
    return iris_fit_uv(p);
#else
    return vec2(0.5) + p / (2.0 * u_iris_radius);
#endif
}
"""

CORNEA_FRAGMENT_BODY = _SHARED + """
void main() {
    vec3 dir = normalize(v_world_pos - u_eye);
    vec3 entry;
    vec3 n;
    vec3 hit;
    float transmit_inner;
    int kind = trace_cornea(u_eye, dir, VARIANT, entry, n, hit, transmit_inner);
    if (kind == KIND_MISS) {
        entry = v_world_pos;
        n = normalize(v_world_pos - u_ant_centre);
        kind = KIND_LIMBUS;
    }
#if LIMBUS_LEVEL >= 3
    // Behind the limbal tissue: the anterior refraction continued to the iris (P1c L3).
    vec3 deep_dir = normalize(refract(dir, n, N_AIR / (VARIANT == 2 ? N_EFFECTIVE : N_CORNEA)));
    float deep_t;
    float deep_r;
    bool deep = iris_cone_hit(entry, deep_dir, deep_t, deep_r) && deep_r <= u_iris_radius;
    vec3 deep_hit = entry + max(deep_t, 0.0) * deep_dir;
    vec3 deep_albedo = srgb_decode(texture(u_iris_texture, iris_st(deep_hit.xy)).rgb);
#endif
    vec3 iris_albedo = srgb_decode(texture(u_iris_texture, iris_st(hit.xy)).rgb);
    vec3 v = -dir;
    float u = cornea_u(entry);
    float shift = asym_shift(entry);
    float us = u + shift;
#if LIMBUS_LEVEL >= 2
    vec3 ns = normal_blend(n, normalize(entry), u);
#else
    vec3 ns = n;
#endif
    vec3 tissue = lit(limbus_tint(colour_weight(us), u_limbus_albedo, u_sclera_albedo), ns);
    vec3 inside;
    if (kind == KIND_LIMBUS) {
        inside = tissue;
#if LIMBUS_LEVEL >= 3
        vec3 behind = deep ? lit(deep_albedo, iris_cone_normal(deep_hit)) : lit(u_limbus_albedo, ns);
        inside = mix(tissue, behind, transmission(us));
#endif
    } else {
        vec3 cone_n = iris_cone_normal(hit);
        inside = lit(kind == KIND_PUPIL ? u_pupil_albedo : iris_albedo, cone_n);
#if LIMBUS_LEVEL >= 3
        vec3 cover = mix(tissue, inside, transmission(us));
#else
        vec3 cover = tissue;
#endif
        inside = mix(inside, cover, iris_cover(u, shift));
    }
    float fresnel = schlick(u_f0, max(dot(ns, v), 0.0)).x;
    vec3 colour = (1.0 - fresnel) * transmit_inner * inside + specular(ns, v, u_roughness, u_f0);
    out_color = vec4(display(colour, u_exposure, u_tonemap), 1.0);
}
"""

SCLERA_FRAGMENT_BODY = _SHARED + """
uniform float u_spec_weight;
void main() {
    vec3 p = v_world_pos;
    vec3 n_s = normalize(v_normal);
    vec3 v = normalize(u_eye - p);
    float u = sclera_u(p);
    float us = u + asym_shift(p);
#if LIMBUS_LEVEL >= 3
    vec3 through_hit;
    bool through = sclera_through(p, -v, n_s, through_hit);
    vec3 through_albedo = srgb_decode(texture(u_iris_texture, iris_st(through_hit.xy)).rgb);
#endif
#if LIMBUS_LEVEL >= 2
    vec3 n = normal_blend(normalize(p - u_ant_centre), n_s, u);
#else
    vec3 n = n_s;
#endif
    vec3 colour = lit(limbus_tint(colour_weight(us), u_limbus_albedo, u_sclera_albedo), n);
#if LIMBUS_LEVEL >= 3
    vec3 behind = through ? lit(through_albedo, iris_cone_normal(through_hit)) : lit(u_limbus_albedo, n);
    colour = mix(colour, behind, transmission(us));
#endif
    colour += u_spec_weight * specular(n, v, u_roughness, u_f0);
    out_color = vec4(display(colour, u_exposure, u_tonemap), 1.0);
}
"""

PARITY_FRAGMENT_BODY = """
uniform samplerBuffer u_inputs;
uniform int u_width;
uniform int u_count;
uniform int u_func;
layout(location = 0) out vec4 out_value;
void main() {
    int i = int(gl_FragCoord.y) * u_width + int(gl_FragCoord.x);
    if (i >= u_count) {
        out_value = vec4(0.0);
        return;
    }
    vec4 a = texelFetch(u_inputs, 3 * i);
    vec4 b = texelFetch(u_inputs, 3 * i + 1);
    vec4 c = texelFetch(u_inputs, 3 * i + 2);
    vec4 o = vec4(0.0);
    if (u_func == 0) {
        o.xyz = vec3(sclera_u(a.xyz), cornea_u(a.xyz), asym_shift(a.xyz));
    } else if (u_func == 1) {
        o.xyz = vec3(colour_weight(a.x), iris_cover(a.y, a.z), transmission(a.w));
    } else if (u_func == 2) {
        o.xyz = normal_blend(normalize(a.xyz), normalize(b.xyz), c.x);
    } else if (u_func == 3) {
        vec3 point;
        bool h = sclera_through(a.xyz, normalize(b.xyz), normalize(c.xyz), point);
        o = vec4(point, h ? 1.0 : 0.0);
    } else if (u_func == 4) {
        o.xyz = limbus_tint(a.x, b.xyz, c.xyz);
        o.w = iris_cone_normal(vec3(a.yz, 0.8)).x;
    }
    out_value = o;
}
"""

PARITY_FUNCS = {"coords": 0, "weights": 1, "normal_blend": 2, "sclera_through": 3, "tint": 4}


def _lib(tech, variant, level, fit) -> str:
    # IRIS_FIT's source needs u_iris_radius (REFRACTION_LIB_SRC), so the header's fit source goes after it.
    head = "#version 330 core\n" + "".join(f"#define {k} {v}\n" for k, v in
                                          (("TECH", tech), ("VARIANT", variant), ("LIMBUS_LEVEL", level)))
    if fit:
        head += "#define IRIS_FIT 1\n"
    return (head + shaders.LIB_SRC + rs.REFRACTION_LIB_SRC + (iris_fit.GLSL_SRC if fit else "")
            + LIMBUS_LIB_SRC)


def cornea_sources(locations: dict[str, int], tech: int, variant: int, level: int, fit: bool):
    return [(shaders.SURFACE_VERTEX_SRC.format(**locations), "vertex"),
            (_lib(tech, variant, level, fit) + CORNEA_FRAGMENT_BODY, "fragment")]


def sclera_sources(locations: dict[str, int], tech: int, level: int, fit: bool):
    return [(shaders.SURFACE_VERTEX_SRC.format(**locations), "vertex"),
            (_lib(tech, 2, level, fit) + SCLERA_FRAGMENT_BODY, "fragment")]


def parity_sources():
    return [(shaders.FULLSCREEN_VERTEX_SRC, "vertex"),
            ("#version 330 core\n" + shaders.LIB_SRC + rs.REFRACTION_LIB_SRC + LIMBUS_LIB_SRC + PARITY_FRAGMENT_BODY,
             "fragment")]
