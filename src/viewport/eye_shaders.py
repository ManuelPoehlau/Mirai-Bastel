"""GLSL of the eye pass (AD-033 §5): the eye shell drawn with the Eye-Lab shading in the Worklight.

Promoted from `experiments/lookdev_eye_lab/` (`shaders.LIB_SRC`, `refraction_shaders`, `iris_fit`, `limbus_shaders`;
Manu's go 2026-11-15). Every function of `EYE_LIB_SRC` has a NumPy twin in `eye_optics` (GPU parity:
`tests/test_gl_eye_pass.py`); the lab stays frozen as the oracle.

**The shell program** (`shell_sources`; variants by `#define`: `VARIANT` 2 / 3 = refraction V2 / V3, `LIMBUS_LEVEL`
0–3, `REFLECTION` 0 = the Worklight key highlight only / 1 = + the analytic studio (lab T-D), `IRIS_FIT`, `DEBUG_KIND`):
- one draw of the eye's VertexList. The shell's first `u_cornea_triangles` triangles are the corneal cap
  (`mirai.eye_object.shell_mesh` builds it first), so `gl_PrimitiveID` decides cornea or sclera **per triangle** - the
  same branch for every fragment of a 2×2 quad, so texture derivatives stay defined;
- all geometry in eye-local space (`u_model_inv`; 1 = the sclera radius, the eye looks down +Z), normals and
  reflections back to world / view space for the light;
- **diffuse light is the Worklight's own** (ambient + key and fill with wrap, `gl_render_store.FRAGMENT_SRC`) on the
  display-referred albedos, so an eye's sclera reads like any Worklight object of its colour; the sclera highlight is
  the Worklight's Blinn–Phong with the eye's finish; only the cornea's wet reflection (GGX key + the studio, Schlick
  F with IOR 1.376) is computed in linear light and added Reinhard + sRGB encoded, as P1's C2 shell did;
- cornea: P1b's ray (V2 / V3) to the analytic iris / pupil / limbal tissue, P1c's L1–L3 and the overlap /
  asymmetry; sclera: P1c's colour band, normal blend and translucent band (with the L3 fast path and its 2-pixel
  margin).
"""

from __future__ import annotations

from . import eye_optics as eo

VARIANT_IDS = {"V2": 2, "V3": 3}
REFLECTIONS = {"key": 0, "studio": 1}


def _frames_src() -> str:
    frames = eo.studio_frames()
    vec = lambda v: f"vec3({float(v[0])!r}, {float(v[1])!r}, {float(v[2])!r})"  # noqa: E731
    lines = [f"const int STUDIO_LIGHTS = {len(frames)};"]
    for name, index in (("centre", 0), ("right", 1), ("up", 2)):
        lines.append(f"const vec3 STUDIO_{name.upper()}[{len(frames)}] = vec3[]("
                     + ", ".join(vec(f[index]) for f in frames) + ");")
    lines.append(f"const vec2 STUDIO_HALF[{len(frames)}] = vec2[]("
                 + ", ".join(f"vec2({float(f[3][0])!r}, {float(f[3][1])!r})" for f in frames) + ");")
    lines.append(f"const vec3 STUDIO_RADIANCE[{len(frames)}] = vec3[](" + ", ".join(vec(f[4]) for f in frames) + ");")
    return "\n".join(lines)


EYE_LIB_SRC = f"""
const float PI = 3.14159265358979;
const float N_AIR = {eo.N_AIR!r};
const float N_CORNEA = {eo.N_CORNEA!r};
const float N_AQUEOUS = {eo.N_AQUEOUS!r};
const float N_EFFECTIVE = {eo.N_EFFECTIVE!r};
const float RAY_EPS = {eo.EPS!r};
const int KIND_MISS = {eo.MISS};
const int KIND_IRIS = {eo.IRIS};
const int KIND_PUPIL = {eo.PUPIL};
const int KIND_LIMBUS = {eo.LIMBUS};
const float MIN_DIRECT_ROUGHNESS = {eo.MIN_DIRECT_ROUGHNESS!r};
const float TD_SIGMA_SCALE = {eo.TD_SIGMA_SCALE!r};
const float TD_SIGMA_POWER = {eo.TD_SIGMA_POWER!r};
const vec3 STUDIO_ZENITH = vec3{eo.STUDIO_ZENITH!r};
const vec3 STUDIO_HORIZON = vec3{eo.STUDIO_HORIZON!r};
const vec3 STUDIO_FLOOR = vec3{eo.STUDIO_FLOOR!r};
const float STUDIO_HORIZON_WIDTH = {eo.STUDIO_HORIZON_WIDTH!r};
const float STUDIO_EDGE_SIGMA = {eo.STUDIO_EDGE_SIGMA!r};
{_frames_src()}
const float COVER_FADE = {eo.COVER_FADE!r};

// The eye's geometry (eye_optics.EyeGeometry), eye-local.
uniform float u_ant_centre_z;
uniform float u_ant_radius;
uniform float u_post_centre_z;
uniform float u_post_radius;
uniform float u_cap_z;
uniform vec2 u_angle;
uniform float u_iris_a;
uniform float u_iris_b;
uniform float u_iris_radius;
uniform float u_pupil_radius;
uniform float u_limbus_radius;
uniform float u_theta_ring;
uniform float u_u0;
// The limbus settings (eye_optics, lab limbus_model).
uniform float u_band;
uniform float u_strength;
uniform float u_normal_w;
uniform float u_falloff;
uniform float u_asym;
uniform float u_overlap;
// The radial fit (eye_optics.fit_knots).
uniform vec2 u_fit_lab;
uniform vec3 u_fit_img;
// The Worklight's light (gl_render_store.FRAGMENT_SRC, Viewport.light_uniforms).
uniform vec3 u_key_dir;
uniform vec3 u_key_color;
uniform float u_key_wrap;
uniform vec3 u_fill_dir;
uniform vec3 u_fill_color;
uniform float u_fill_wrap;
uniform float u_ambient;

// -- colour (lab eye_math) and BRDF (lab shaders.LIB_SRC)
vec3 srgb_encode(vec3 c) {{
    c = clamp(c, 0.0, 1.0);
    return mix(1.055 * pow(c, vec3(1.0 / 2.4)) - 0.055, 12.92 * c, vec3(lessThanEqual(c, vec3(0.0031308))));
}}
vec3 display_add(vec3 linear_rgb) {{
    vec3 x = max(linear_rgb, 0.0);
    return srgb_encode(x / (1.0 + x));
}}
float ggx_d(float n_dot_h, float alpha) {{
    float a2 = alpha * alpha;
    float d = n_dot_h * n_dot_h * (a2 - 1.0) + 1.0;
    return a2 / (PI * d * d);
}}
float smith_vis(float n_dot_l, float n_dot_v, float alpha) {{
    float a2 = alpha * alpha;
    float gv = n_dot_l * sqrt(n_dot_v * n_dot_v * (1.0 - a2) + a2);
    float gl = n_dot_v * sqrt(n_dot_l * n_dot_l * (1.0 - a2) + a2);
    return 0.5 / max(gv + gl, 1e-12);
}}
float schlick_scalar(float f0, float cos_theta) {{
    float m = 1.0 - clamp(cos_theta, 0.0, 1.0);
    return f0 + (1.0 - f0) * (m * m * m * m * m);
}}
float direct_specular(vec3 n, vec3 v, vec3 l, float roughness, float f0) {{
    vec3 h = normalize(v + l);
    float nl = dot(n, l);
    if (nl <= 0.0) return 0.0;
    float nv = max(dot(n, v), 1e-4);
    float r = max(roughness, MIN_DIRECT_ROUGHNESS);
    float a = r * r;
    return ggx_d(max(dot(n, h), 0.0), a) * smith_vis(nl, nv, a) * nl * schlick_scalar(f0, max(dot(v, h), 0.0));
}}
float env_brdf_approx(float f0, float roughness, float n_dot_v) {{
    const vec4 c0 = vec4(-1.0, -0.0275, -0.572, 0.022);
    const vec4 c1 = vec4(1.0, 0.0425, 1.04, -0.04);
    vec4 q = roughness * c0 + c1;
    float a004 = min(q.x * q.x, exp2(-9.28 * n_dot_v)) * q.x + q.y;
    return f0 * (-1.04 * a004 + q.z) + 1.04 * a004 + q.w;
}}

// -- the studio (eye_optics.td_env), view space
float erf_approx(float x) {{
    float s = sign(x);
    float a = abs(x);
    float t = 1.0 / (1.0 + 0.3275911 * a);
    float poly = ((((1.061405429 * t - 1.453152027) * t + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t;
    return s * (1.0 - poly * exp(-a * a));
}}
float box_profile(float x, float half_width, float sigma) {{
    float k = 1.0 / (1.4142135623730951 * sigma);
    return 0.5 * (erf_approx((x + half_width) * k) - erf_approx((x - half_width) * k));
}}
vec3 td_env(vec3 d, float roughness) {{
    float lobe = TD_SIGMA_SCALE * pow(roughness * roughness, TD_SIGMA_POWER);
    float sigma = sqrt(STUDIO_EDGE_SIGMA * STUDIO_EDGE_SIGMA + lobe * lobe);
    float width = sqrt(STUDIO_HORIZON_WIDTH * STUDIO_HORIZON_WIDTH + lobe * lobe);
    vec3 sky = STUDIO_HORIZON + (STUDIO_ZENITH - STUDIO_HORIZON) * clamp(d.y, 0.0, 1.0);
    vec3 value = STUDIO_FLOOR + (sky - STUDIO_FLOOR) * smoothstep(-width, width, d.y);
    for (int i = 0; i < STUDIO_LIGHTS; ++i) {{
        float dc = dot(d, STUDIO_CENTRE[i]);
        float x = atan(dot(d, STUDIO_RIGHT[i]), dc + 1e-12);
        float y = atan(dot(d, STUDIO_UP[i]), dc + 1e-12);
        value += box_profile(x, STUDIO_HALF[i].x, sigma) * box_profile(y, STUDIO_HALF[i].y, sigma)
               * smoothstep(0.0, 0.25, dc) * STUDIO_RADIANCE[i];
    }}
    return value;
}}

// -- the Worklight's diffuse light (eye_optics.worklight_light), world normals
float wrap_light(float ndl, float w) {{ return max((ndl + w) / (1.0 + w), 0.0); }}
vec3 worklight_light(vec3 n) {{
    return vec3(u_ambient) + u_key_color * wrap_light(dot(n, u_key_dir), u_key_wrap)
         + u_fill_color * wrap_light(dot(n, u_fill_dir), u_fill_wrap);
}}

// -- rays (eye_optics), eye-local
bool sphere_entry(vec3 o, vec3 d, vec3 c, float radius, out float t) {{
    vec3 oc = o - c;
    float b = dot(oc, d);
    float cc = dot(oc, oc) - radius * radius;
    float disc = b * b - cc;
    float s = sqrt(max(disc, 0.0));
    float t0 = -b - s;
    t = t0 > RAY_EPS ? t0 : -b + s;
    return disc >= 0.0 && t > RAY_EPS;
}}
bool iris_cone_hit(vec3 o, vec3 d, out float t, out float r) {{
    float a = u_iris_a;
    float b = u_iris_b;
    float q0 = o.z - a;
    float A = d.z * d.z - b * b * (d.x * d.x + d.y * d.y);
    float B = 2.0 * (q0 * d.z - b * b * (o.x * d.x + o.y * d.y));
    float C = q0 * q0 - b * b * (o.x * o.x + o.y * o.y);
    float disc = B * B - 4.0 * A * C;
    float s = sqrt(max(disc, 0.0));
    bool quadratic = abs(A) > 1e-12;
    float safe = quadratic ? A : 1.0;
    float r1 = (-B - s) / (2.0 * safe);
    float r2 = (-B + s) / (2.0 * safe);
    float lin = abs(B) > 1e-12 ? -C / B : -1.0;
    float lo = quadratic ? min(r1, r2) : lin;
    float hi = quadratic ? max(r1, r2) : lin;
    bool ok_disc = disc >= 0.0 || !quadratic;
    bool lo_ok = lo > RAY_EPS && q0 + lo * d.z >= -1e-9 && ok_disc;
    bool hi_ok = hi > RAY_EPS && q0 + hi * d.z >= -1e-9 && ok_disc;
    t = lo_ok ? lo : (hi_ok ? hi : -1.0);
    vec3 p = o + max(t, 0.0) * d;
    r = length(p.xy);
    return t > RAY_EPS;
}}
int trace_cornea(vec3 eye, vec3 d, int variant, out vec3 entry, out vec3 normal, out vec3 hit,
                 out float transmit_inner) {{
    d = normalize(d);
    transmit_inner = 1.0;
    vec3 ant = vec3(0.0, 0.0, u_ant_centre_z);
    float ta;
    bool hit_a = sphere_entry(eye, d, ant, u_ant_radius, ta);
    entry = eye + ta * d;
    normal = normalize(entry - ant);
    hit = entry;
    if (!hit_a || entry.z < u_cap_z - 1e-9) return KIND_MISS;
    float eta = N_AIR / (variant == 2 ? N_EFFECTIVE : N_CORNEA);
    vec3 t_dir = normalize(refract(d, normal, eta));
    float tp;
    bool hit_p = sphere_entry(entry, t_dir, vec3(0.0, 0.0, u_post_centre_z), u_post_radius, tp);
    vec3 pp = entry + tp * t_dir;
    if (!hit_p || pp.z < u_angle.y) return KIND_LIMBUS;
    vec3 start = entry;
    if (variant == 3) {{
        vec3 np = normalize(pp - vec3(0.0, 0.0, u_post_centre_z));
        vec3 inner = refract(t_dir, np, N_CORNEA / N_AQUEOUS);
        if (length(inner) < 0.5) return KIND_LIMBUS;
        float f0 = (N_AQUEOUS - N_CORNEA) / (N_AQUEOUS + N_CORNEA);
        transmit_inner = 1.0 - schlick_scalar(f0 * f0, clamp(-dot(np, t_dir), 0.0, 1.0));
        t_dir = normalize(inner);
        start = pp;
    }}
    float ti;
    float ri;
    bool hit_i = iris_cone_hit(start, t_dir, ti, ri);
    if (!hit_i || ri > u_iris_radius) {{
        transmit_inner = 1.0;
        return KIND_LIMBUS;
    }}
    hit = start + ti * t_dir;
    return ri < u_pupil_radius ? KIND_PUPIL : KIND_IRIS;
}}
float limbus_weight(float r_entry) {{
    return smoothstep(0.0, 1.0, clamp((r_entry - u_angle.x) / (u_limbus_radius - u_angle.x), 0.0, 1.0));
}}

// -- the radial fit (eye_optics.share_map / iris_uv)
float iris_fit_share(float s) {{
    float inner = s * (u_fit_img.x / u_fit_lab.x);
    float middle = u_fit_img.x + (s - u_fit_lab.x) * ((u_fit_img.y - u_fit_img.x) / (u_fit_lab.y - u_fit_lab.x));
    float outer = u_fit_img.y + (s - u_fit_lab.y) * ((u_fit_img.z - u_fit_img.y) / (1.0 - u_fit_lab.y));
    return s < u_fit_lab.x ? inner : (s < u_fit_lab.y ? middle : outer);
}}
vec2 iris_st(vec2 p) {{
#ifdef IRIS_FIT
    float s = length(p) / u_iris_radius;
    float scale = s > 1e-6 ? iris_fit_share(s) / s : u_fit_img.x / u_fit_lab.x;
    return vec2(0.5) + 0.5 * p / u_iris_radius * scale;
#else
    return vec2(0.5) + p / (2.0 * u_iris_radius);
#endif
}}

// -- the soft limbus (eye_optics)
float limbus_smooth(float t) {{
    t = clamp(t, 0.0, 1.0);
    return t * t * (3.0 - 2.0 * t);
}}
float sclera_u(vec3 p) {{ return atan(length(p.xy), p.z) - u_theta_ring; }}
float cornea_u(vec3 p) {{ return length(p.xy) - u_limbus_radius; }}
float asym_shift(vec3 p) {{ return u_overlap + u_asym * p.y * p.y / max(dot(p.xy, p.xy), 1e-12); }}
float colour_weight(float u) {{ return limbus_smooth((u - u_u0) / (u_band - u_u0)); }}
vec3 limbus_tint(float w, vec3 limbal, vec3 sclera) {{ return mix(sclera, mix(limbal, sclera, w), u_strength); }}
float iris_cover(float u, float shift) {{
    float amount = u_overlap + u_asym;
    if (amount <= 0.0) return 0.0;
    float ramp = limbus_smooth((u - (u_u0 - shift)) / max(shift, 1e-9));
    return ramp * limbus_smooth(shift / (COVER_FADE * amount));
}}
vec3 normal_blend(vec3 n_cornea, vec3 n_sclera, float u) {{
    float b = limbus_smooth((u + u_normal_w) / (2.0 * u_normal_w));
    return normalize(mix(n_cornea, n_sclera, b));
}}
float transmission(float u) {{
    float t = clamp((u - u_u0) / (u_band - u_u0), 0.0, 1.0);
    return pow(1.0 - t, u_falloff);
}}
bool sclera_through(vec3 p, vec3 d, vec3 n_sclera, out vec3 point) {{
    vec3 t_dir = normalize(refract(d, n_sclera, N_AIR / N_CORNEA));
    float t;
    float r;
    bool hit = iris_cone_hit(p, t_dir, t, r);
    point = p + max(t, 0.0) * t_dir;
    return hit && r <= u_iris_radius;
}}
vec3 iris_cone_normal(vec3 hit) {{
    float r = max(length(hit.xy), 1e-6);
    return normalize(vec3(-u_iris_b * hit.xy / r, 1.0));
}}
"""

SHELL_VERTEX_SRC = """#version 330 core
layout(location = {position}) in vec3 position;
layout(location = {normal}) in vec3 normal;
uniform mat4 u_view;
uniform mat4 u_proj;
uniform mat4 u_model;
out vec3 v_world_pos;
void main() {{
    vec4 world = u_model * vec4(position, 1.0);
    gl_Position = u_proj * u_view * world;
    v_world_pos = world.xyz;
}}
"""

SHELL_FRAGMENT_BODY = """
in vec3 v_world_pos;
uniform mat4 u_view;
uniform mat4 u_proj;
uniform mat4 u_model;
uniform mat4 u_model_inv;
uniform int u_cornea_triangles;
uniform sampler2D u_iris_texture;
uniform vec3 u_sclera_albedo;
uniform vec3 u_limbus_albedo;
uniform vec3 u_pupil_albedo;
uniform float u_specular;
uniform float u_spec_exponent;
uniform float u_fill_specular;
uniform float u_cornea_f0;
uniform float u_cornea_roughness;
uniform float u_key_irradiance;
out vec4 out_color;

const vec3 LUMA = vec3(0.2126, 0.7152, 0.0722);

vec3 to_world(vec3 n_local) { return normalize(mat3(u_model) * n_local); }

vec3 lit(vec3 albedo, vec3 n_local) { return albedo * worklight_light(to_world(n_local)); }

float blinn_phong(vec3 n, vec3 l, vec3 v, float e) {
    if (dot(n, l) <= 0.0) return 0.0;
    return pow(max(dot(n, normalize(l + v)), 0.0), e);
}

// The cornea's wet reflection in linear light (world n / v): GGX key highlight + the studio.
vec3 cornea_reflection(vec3 n, vec3 v) {
    vec3 key = u_key_color * (u_key_irradiance * direct_specular(n, v, u_key_dir, u_cornea_roughness, u_cornea_f0));
#if REFLECTION == 1
    vec3 r_view = mat3(u_view) * reflect(-v, n);
    float nv = max(dot(n, v), 1e-4);
    key += td_env(r_view, u_cornea_roughness) * env_brdf_approx(u_cornea_f0, u_cornea_roughness, nv);
#endif
    return key;
}

void main() {
    vec3 camera = -transpose(mat3(u_view)) * u_view[3].xyz;
    vec3 dir_world = normalize(v_world_pos - camera);
    vec3 eye_world = camera;
    if (u_proj[3][3] == 1.0) {
        // Ortho: parallel rays along the view axis, started in front of the eye.
        dir_world = normalize(transpose(mat3(u_view)) * vec3(0.0, 0.0, -1.0));
        eye_world = v_world_pos - dir_world * 4.0 * length(mat3(u_model) * vec3(1.0, 0.0, 0.0));
    }
    vec3 eye = (u_model_inv * vec4(eye_world, 1.0)).xyz;
    vec3 p = (u_model_inv * vec4(v_world_pos, 1.0)).xyz;
    vec3 dir = normalize(p - eye);
    vec3 v = -dir;
    vec3 v_world = -dir_world;
    bool cornea = gl_PrimitiveID < u_cornea_triangles;  // per triangle: the same branch for a whole quad
    vec3 colour;
    if (cornea) {
        vec3 entry;
        vec3 n;
        vec3 hit;
        float transmit_inner;
        int kind = trace_cornea(eye, dir, VARIANT, entry, n, hit, transmit_inner);
        if (kind == KIND_MISS) {
            entry = p;
            n = normalize(p - vec3(0.0, 0.0, u_ant_centre_z));
            kind = KIND_LIMBUS;
        }
#if LIMBUS_LEVEL >= 3
        // The ray behind the limbal tissue (fast path: tissue rays only in V2; V3 traces every fragment, as the lab).
        vec3 deep_hit = hit;
        bool deep = false;
        if (VARIANT == 3 || kind == KIND_LIMBUS) {
            vec3 deep_dir = normalize(refract(dir, n, N_AIR / (VARIANT == 2 ? N_EFFECTIVE : N_CORNEA)));
            float deep_t;
            float deep_r;
            deep = iris_cone_hit(entry, deep_dir, deep_t, deep_r) && deep_r <= u_iris_radius;
            deep_hit = entry + max(deep_t, 0.0) * deep_dir;
        }
        vec3 deep_albedo = texture(u_iris_texture, iris_st(deep_hit.xy)).rgb;
#endif
        vec3 iris_albedo = texture(u_iris_texture, iris_st(hit.xy)).rgb;
#ifdef DEBUG_KIND
        out_color = vec4(kind == KIND_IRIS ? 1.0 : 0.0, kind == KIND_PUPIL ? 1.0 : 0.0,
                         kind == KIND_LIMBUS ? 1.0 : 0.0, 1.0);
        return;
#endif
        float u = cornea_u(entry);
        float shift = asym_shift(entry);
        float us = u + shift;
#if LIMBUS_LEVEL >= 2
        vec3 ns = normal_blend(n, normalize(entry), u);
#else
        vec3 ns = n;
#endif
#if LIMBUS_LEVEL >= 1
        vec3 tissue = lit(limbus_tint(colour_weight(us), u_limbus_albedo, u_sclera_albedo), ns);
#else
        vec3 tissue = lit(mix(u_limbus_albedo, u_sclera_albedo, limbus_weight(length(entry.xy))), ns);
#endif
        vec3 inside;
        if (kind == KIND_LIMBUS) {
            inside = tissue;
#if LIMBUS_LEVEL >= 3
            vec3 behind = deep ? lit(deep_albedo, iris_cone_normal(deep_hit)) : lit(u_limbus_albedo, ns);
            inside = mix(tissue, behind, transmission(us));
#endif
        } else {
            inside = lit(kind == KIND_PUPIL ? u_pupil_albedo : iris_albedo, iris_cone_normal(hit));
#if LIMBUS_LEVEL >= 1
#if LIMBUS_LEVEL >= 3
            vec3 cover = mix(tissue, inside, transmission(us));
#else
            vec3 cover = tissue;
#endif
            inside = mix(inside, cover, iris_cover(u, shift));
#endif
        }
        vec3 n_world = to_world(ns);
        float fresnel = schlick_scalar(u_cornea_f0, max(dot(n_world, v_world), 0.0));
        colour = (1.0 - fresnel) * transmit_inner * inside + display_add(cornea_reflection(n_world, v_world));
    } else {
#ifdef DEBUG_KIND
        out_color = vec4(1.0, 1.0, 0.0, 1.0);
        return;
#endif
        vec3 n_s = normalize(p);
        float u = sclera_u(p);
        float us = u + asym_shift(p);
#if LIMBUS_LEVEL >= 3
        vec3 through_hit = vec3(0.0);
        bool through = false;
        // Fast path (P1c): only where the band transmits, plus a 2-pixel margin so every quad at the band's edge is
        // traced completely (its mip level then matches the full trace).
        if (us - 2.0 * fwidth(us) < u_band) {
            through = sclera_through(p, dir, n_s, through_hit);
        }
        vec3 through_albedo = texture(u_iris_texture, iris_st(through_hit.xy)).rgb;
#endif
#if LIMBUS_LEVEL >= 2
        vec3 n = normal_blend(normalize(p - vec3(0.0, 0.0, u_ant_centre_z)), n_s, u);
#else
        vec3 n = n_s;
#endif
#if LIMBUS_LEVEL >= 1
        vec3 albedo = limbus_tint(colour_weight(us), u_limbus_albedo, u_sclera_albedo);
#else
        vec3 albedo = u_sclera_albedo;
#endif
        colour = lit(albedo, n);
#if LIMBUS_LEVEL >= 3
        vec3 behind = through ? lit(through_albedo, iris_cone_normal(through_hit)) : lit(u_limbus_albedo, n);
        colour = mix(colour, behind, transmission(us));
#endif
        // The Worklight's own highlight (non-local viewer), with the eye's finish.
        vec3 n_world = to_world(n);
        vec3 view_axis = normalize(transpose(mat3(u_view)) * vec3(0.0, 0.0, 1.0));
        colour += vec3(u_specular * dot(u_key_color, LUMA) * blinn_phong(n_world, u_key_dir, view_axis, u_spec_exponent)
                     + u_fill_specular * dot(u_fill_color, LUMA) * blinn_phong(n_world, u_fill_dir, view_axis,
                                                                               u_spec_exponent));
    }
    out_color = vec4(colour, 1.0);
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
        vec3 entry;
        vec3 n;
        vec3 hit;
        float tin;
        int kind = trace_cornea(a.xyz, b.xyz, int(c.x + 0.5), entry, n, hit, tin);
        o = vec4(hit, float(kind));
    } else if (u_func == 1) {
        vec3 entry;
        vec3 n;
        vec3 hit;
        float tin;
        int kind = trace_cornea(a.xyz, b.xyz, int(c.x + 0.5), entry, n, hit, tin);
        o = vec4(entry, tin);
    } else if (u_func == 2) {
        o.xy = iris_st(a.xy);
    } else if (u_func == 3) {
        o.xyz = vec3(sclera_u(a.xyz), cornea_u(a.xyz), asym_shift(a.xyz));
    } else if (u_func == 4) {
        o.xyz = vec3(colour_weight(a.x), iris_cover(a.y, a.z), transmission(a.w));
    } else if (u_func == 5) {
        o.xyz = normal_blend(normalize(a.xyz), normalize(b.xyz), c.x);
    } else if (u_func == 6) {
        vec3 point;
        bool h = sclera_through(a.xyz, normalize(b.xyz), normalize(c.xyz), point);
        o = vec4(point, h ? 1.0 : 0.0);
    } else if (u_func == 7) {
        o.xyz = td_env(normalize(a.xyz), a.w);
    } else if (u_func == 8) {
        o.xyz = worklight_light(normalize(a.xyz));
    }
    out_value = o;
}
"""

PARITY_FUNCS = {"trace_hit": 0, "trace_entry": 1, "iris_st": 2, "coords": 3, "weights": 4, "normal_blend": 5,
                "sclera_through": 6, "td_env": 7, "worklight_light": 8}

FULLSCREEN_VERTEX_SRC = """#version 330 core
layout(location = 0) in vec2 a_position;
void main() {
    gl_Position = vec4(a_position, 0.0, 1.0);
}
"""


def _header(**defines) -> str:
    return "#version 330 core\n" + "".join(f"#define {k} {v}\n" for k, v in defines.items() if v is not None)


def shell_sources(locations: dict[str, int], variant: str, level: int, reflection: str, fit: bool,
                  debug_kind: bool = False) -> list[tuple[str, str]]:
    header = _header(VARIANT=VARIANT_IDS[variant], LIMBUS_LEVEL=int(level), REFLECTION=REFLECTIONS[reflection],
                     IRIS_FIT=1 if fit else None, DEBUG_KIND=1 if debug_kind else None)
    return [(SHELL_VERTEX_SRC.format(**locations), "vertex"), (header + EYE_LIB_SRC + SHELL_FRAGMENT_BODY, "fragment")]


def parity_sources(fit: bool) -> list[tuple[str, str]]:
    return [(FULLSCREEN_VERTEX_SRC, "vertex"),
            (_header(IRIS_FIT=1 if fit else None) + EYE_LIB_SRC + PARITY_FRAGMENT_BODY, "fragment")]
