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

**The look** (Eye LookDev phase 3, `core.EyeLook`; define `LOOK`, set only in the "full" tier for an eye whose look has
an amount above 0 - otherwise the program is exactly the one before phase 3): the wet film over the sclera, the
irregularity of the film's reflection normal (a mip-mapped noise texture), the lid shadow on the eyeball and the lid
band in the reflection (both in the eye's rest frame, `u_rest`), the soft key highlight. `LOOK_LIB_SRC` holds the
parity-tested functions (NumPy twins in `eye_optics`); every term is neutral at amount 0.

**The iris** (Eye LookDev phase 4, `core.EyeIris`; define `IRIS`, only together with `LOOK` and only for an eye whose
iris values have an amount above 0 - otherwise the program is exactly the one of phase 3): the Worklight key traced back
through the cornea to the iris (refracted direction, the cornea's focusing - the crescent opposite the key - and the
shadow under the scleral rim), the relief from the iris image's height (alpha), the soft pupil edge and its dark margin.
The key's path is traced once per eye into a small table (`IRIS_LIGHT_SRC`, `iris_table_sources`; the pass bakes it when
the key, the gaze or a value changes) and read per pixel: tracing it per pixel cost the reference PC +13 ms in the Eye
Lab view at 1920×1080 (2026-11-16). `IRIS_LIGHT_SRC` and `IRIS_LIB_SRC` hold the parity-tested functions; every term is
neutral at amount 0.
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

LOOK_LIB_SRC = f"""
const float NOISE_GRADIENT_MAX = {eo.NOISE_GRADIENT_MAX!r};
const vec2 IRREGULAR_ROUGHNESS = vec2{tuple(float(v) for v in eo.IRREGULAR_ROUGHNESS)!r};
const vec2 UPPER_LASH = vec2{eo.lash_offset(eo.UPPER_LASH)!r};
const vec2 LOWER_LASH = vec2{eo.lash_offset(eo.LOWER_LASH)!r};
const float LID_BAND_SOFT = {eo.LID_BAND_SOFT!r};

// The look's numbers (eye_optics.look_values).
uniform float u_tilt;
uniform float u_rough_s;
uniform float u_noise_scale;
uniform vec2 u_noise_offset;
uniform vec3 u_lid;
uniform vec2 u_soft_half;
uniform float u_soft_radiance;

// -- the film's irregularity (eye_optics.film_uv / film_frame / film_normal / film_roughness), eye-local
vec2 film_uv(vec3 p) {{
    float rho = length(p.xy);
    float theta = atan(rho, p.z);
    float k = rho > 1e-6 ? theta / rho : 1.0 / max(p.z, 1e-6);
    return p.xy * (k * u_noise_scale) + u_noise_offset;
}}
vec3 film_normal(vec3 n, vec3 p, vec2 g) {{
    vec3 s = normalize(p);
    float rho = length(s.xy);
    float cphi = rho > 1e-9 ? s.x / rho : 1.0;
    float sphi = rho > 1e-9 ? s.y / rho : 0.0;
    vec3 e_t = vec3(s.z * cphi, s.z * sphi, -rho);
    vec3 e_p = vec3(-sphi, cphi, 0.0);
    vec3 tu = cphi * e_t - sphi * e_p;
    vec3 tv = sphi * e_t + cphi * e_p;
    return normalize(n + u_tilt * (g.x * tu + g.y * tv));
}}
float film_roughness(float base, float nb) {{
    return base + u_rough_s * (IRREGULAR_ROUGHNESS.x + IRREGULAR_ROUGHNESS.y * nb);
}}

// -- the lid (eye_optics.lid_shadow_weight / lid_occlusion), the eye's rest frame
float lid_shadow_weight(vec3 p) {{
    return limbus_smooth((p.y - (u_lid.x - u_lid.z)) / u_lid.z);
}}
float lid_margin_z(float x, float y) {{
    float r2 = x * x + y * y;
    float zs = sqrt(max(1.0 - r2, 0.0));
    float zc = u_ant_centre_z + sqrt(max(u_ant_radius * u_ant_radius - r2, 0.0));
    return r2 < u_limbus_radius * u_limbus_radius ? max(zs, zc) : zs;
}}
float elevation(float y, float z) {{ return abs(y) + abs(z) > 1e-6 ? atan(y, z) : 0.0; }}
float lid_occlusion(vec3 p, vec3 r, float roughness) {{
    float lobe = TD_SIGMA_SCALE * pow(roughness * roughness, TD_SIGMA_POWER);
    float soft = sqrt(LID_BAND_SOFT * LID_BAND_SOFT + lobe * lobe);
    float e_r = elevation(r.y, r.z);
    float e_up = atan(u_lid.x + UPPER_LASH.x - p.y, lid_margin_z(p.x, u_lid.x) + UPPER_LASH.y - p.z);
    float e_low = atan(u_lid.y + LOWER_LASH.x - p.y, lid_margin_z(p.x, u_lid.y) + LOWER_LASH.y - p.z);
    float upper = limbus_smooth((e_r - (e_up - soft)) / (2.0 * soft));
    float lower = 1.0 - limbus_smooth((e_r - (e_low - soft)) / (2.0 * soft));
    return max(upper, lower);
}}

// -- the soft key highlight (eye_optics.area_key), world space
float area_key(vec3 r, vec3 c, vec3 up_ref, vec3 right_ref, float roughness) {{
    vec3 right = cross(up_ref, c);
    float len = length(right);
    right = len > 1e-4 ? right / len : right_ref;
    vec3 up = cross(c, right);
    float lobe = TD_SIGMA_SCALE * pow(roughness * roughness, TD_SIGMA_POWER);
    float sigma = sqrt(STUDIO_EDGE_SIGMA * STUDIO_EDGE_SIGMA + lobe * lobe);
    float dc = dot(r, c);
    float x = atan(dot(r, right), dc + 1e-12);
    float y = atan(dot(r, up), dc + 1e-12);
    return u_soft_radiance * box_profile(x, u_soft_half.x, sigma) * box_profile(y, u_soft_half.y, sigma)
         * smoothstep(0.0, 0.25, dc);
}}
"""

IRIS_LIGHT_SRC = f"""
const int IRIS_LIGHT_STEPS = {eo.IRIS_LIGHT_STEPS};
const float IRIS_LIGHT_TOLERANCE = {eo.IRIS_LIGHT_TOLERANCE!r};
const int IRIS_LIGHT_WARM_STEPS = {eo.IRIS_LIGHT_WARM_STEPS};
const float IRIS_LIGHT_WARM_OFFSET = {eo.IRIS_LIGHT_WARM_OFFSET!r};
const float IRIS_LIGHT_DELTA = {eo.IRIS_LIGHT_DELTA!r};
const float CRESCENT_MAX = {eo.CRESCENT_MAX!r};
const float CRESCENT_MIN_COS = {eo.CRESCENT_MIN_COS!r};
const float IRIS_F0 = {eo.CORNEA_F0!r};

// The key's numbers (eye_optics.iris_values) and the key in eye-local space.
uniform vec3 u_key_local;
uniform float u_crescent;
uniform float u_rim_shadow;
uniform float u_rim_width;

// -- the key through the cornea (eye_optics.iris_light_path / iris_key_terms), eye-local
float light_miss(float phi, float hx, float hy) {{
    float c = cos(phi);
    float s = sin(phi);
    float eta = N_AIR / N_EFFECTIVE;
    float m = sqrt(max(1.0 - eta * eta * (1.0 - c * c), 0.0)) - eta * c;
    return (hx - u_ant_radius * c) * (-m * s) - (hy - u_ant_radius * s) * (-eta - m * c);
}}
// `warm`: start from `phi` (a neighbour's solution) instead of the straight path; `phi` returns this point's angle.
bool iris_light_path(vec3 hit, vec3 l, bool warm, inout float phi, out vec3 entry, out vec3 d, out float cos_in,
                     out float aperture) {{
    vec3 ca = vec3(0.0, 0.0, u_ant_centre_z);
    float radius = u_ant_radius;
    float eta = N_AIR / N_EFFECTIVE;
    vec3 q = hit - ca;
    float hx = dot(q, l);
    vec3 w = q - hx * l;
    float hy = length(w);
    vec3 other = abs(l.x) < 0.9 ? vec3(1.0, 0.0, 0.0) : vec3(0.0, 1.0, 0.0);
    vec3 v = hy > 1e-9 ? w / max(hy, 1e-12) : normalize(cross(l, other));
    float p0 = phi;
    float p1 = phi + IRIS_LIGHT_WARM_OFFSET;
    float c;
    float s;
    float m;
    if (!warm) {{
        p0 = atan(hy, sqrt(max(radius * radius - hy * hy, 0.0)));
        c = cos(p0);
        s = sin(p0);
        m = sqrt(max(1.0 - eta * eta * (1.0 - c * c), 0.0)) - eta * c;
        vec2 dir = vec2(eta + m * c, m * s);
        dir /= max(length(dir), 1e-12);
        float b = hx * dir.x + hy * dir.y;
        float t = -b + sqrt(max(b * b - (hx * hx + hy * hy - radius * radius), 0.0));
        p1 = atan(hy + t * dir.y, hx + t * dir.x);
    }}
    float f0 = light_miss(p0, hx, hy);
    float f1 = light_miss(p1, hx, hy);
    int steps = warm ? IRIS_LIGHT_WARM_STEPS : IRIS_LIGHT_STEPS;
    for (int i = 0; i < steps; ++i) {{
        float den = f1 - f0;
        float p2 = abs(den) > 1e-12 ? p1 - f1 * (p1 - p0) / den : p1;
        p0 = p1;
        f0 = f1;
        p1 = p2;
        f1 = light_miss(p2, hx, hy);
    }}
    phi = p1;
    c = cos(p1);
    s = sin(p1);
    vec3 n = c * l + s * v;
    entry = ca + radius * n;
    m = sqrt(max(1.0 - eta * eta * (1.0 - c * c), 0.0)) - eta * c;
    vec3 t_in = -eta * l - m * n;
    d = normalize(entry - hit);
    cos_in = c;
    float s_plane = (u_cap_z - hit.z) / (d.z > 1e-6 ? d.z : 1.0);
    aperture = d.z > 1e-6 ? length(hit.xy + s_plane * d.xy) : 1e3;
    return abs(f1) < IRIS_LIGHT_TOLERANCE && c > 0.0 && dot(hit - entry, t_in) > 0.0;
}}
vec3 cone_point(vec2 xy) {{ return vec3(xy, u_iris_a + u_iris_b * length(xy)); }}
vec3 iris_key_terms(vec3 hit, vec3 l, out vec3 d) {{
    vec3 h0 = cone_point(hit.xy);
    vec3 e0;
    float c0;
    float a0;
    float phi = 0.0;
    bool ok = iris_light_path(h0, l, false, phi, e0, d, c0, a0);
    float trans = ok ? 1.0 - schlick_scalar(IRIS_F0, c0) : 0.0;
    float conc = 1.0;
    if (u_crescent > 0.0) {{
        // the two neighbours' entries (only for the crescent: the costly part)
        vec3 h1 = cone_point(hit.xy + vec2(IRIS_LIGHT_DELTA, 0.0));
        vec3 h2 = cone_point(hit.xy + vec2(0.0, IRIS_LIGHT_DELTA));
        vec3 e1;
        vec3 e2;
        vec3 d1;
        vec3 d2;
        float c1;
        float c2;
        float a1;
        float a2;
        float phi1 = phi;
        float phi2 = phi;
        bool ok1 = iris_light_path(h1, l, true, phi1, e1, d1, c1, a1);
        bool ok2 = iris_light_path(h2, l, true, phi2, e2, d2, c2, a2);
        float beam = abs(dot(cross(e1 - e0, e2 - e0), l));
        float area = length(cross(h1 - h0, h2 - h0));
        float cos_iris = dot(iris_cone_normal(h0), d);
        conc = ok && ok1 && ok2 ? clamp(beam / (area * max(cos_iris, CRESCENT_MIN_COS)), 0.0, CRESCENT_MAX) : 1.0;
    }}
    float shadow = ok ? limbus_smooth((a0 - u_limbus_radius) / u_rim_width + 0.5) : 1.0;
    return vec3(trans, conc, shadow);
}}

// -- the key's table (eye_optics.iris_light_table): one texel per iris point, (d.x, d.y, T, the crescent and rim
// shadow factor); where no path reaches the point d is the key's own direction (T is 0 there).
vec4 iris_table_value(vec2 xy) {{
    vec3 d;
    vec3 terms = iris_key_terms(vec3(xy, 0.0), u_key_local, d);
    d = terms.x > 0.0 ? d : u_key_local;
    return vec4(d.xy, terms.x, mix(1.0, terms.y, u_crescent) * (1.0 - u_rim_shadow * terms.z));
}}
"""

IRIS_LIB_SRC = f"""
// The iris's numbers (eye_optics.iris_values) and the key's table (`IRIS_LIGHT_SRC`, baked per eye by the pass).
uniform float u_iris_key;
uniform float u_iris_light;
uniform float u_relief_depth;
uniform float u_relief_step;
uniform float u_pupil_edge;
uniform float u_pupil_margin;
uniform float u_margin_width;
uniform sampler2D u_iris_table;

// -- relief and pupil (eye_optics.relief_normal / pupil_weights), eye-local
vec3 relief_normal(vec3 hit, vec2 grad) {{
    float r = max(length(hit.xy), 1e-6);
    return normalize(vec3(-u_iris_b * hit.xy / r - grad, 1.0));
}}
vec2 pupil_weights(float r, float width) {{
    float pupil = width > 0.0 ? 1.0 - limbus_smooth((r - u_pupil_radius) / width + 0.5)
                              : (r < u_pupil_radius ? 1.0 : 0.0);
    return vec2(pupil, 1.0 - limbus_smooth((r - u_pupil_radius) / u_margin_width));
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
#ifdef LOOK
uniform float u_wet;
uniform float u_sclera_roughness;
uniform float u_lid_shadow;
uniform float u_lid_band;
uniform mat3 u_rest;
uniform sampler2D u_noise_texture;
#endif
out vec4 out_color;

const vec3 LUMA = vec3(0.2126, 0.7152, 0.0722);

vec3 to_world(vec3 n_local) { return normalize(mat3(u_model) * n_local); }

vec3 lit(vec3 albedo, vec3 n_local) { return albedo * worklight_light(to_world(n_local)); }
#ifdef IRIS

// Phase 4: the iris's diffuse light - the Worklight's (`lit`), its key traced through the cornea (roadmap #4): the
// refracted direction (`u_iris_light`), the cornea's focusing and the rim's shadow (the table's factor).
// The path is traced once per eye into a small table (`IRIS_LIGHT_SRC`), read here per pixel (no mip levels).
vec3 iris_lit(vec3 albedo, vec3 hit, vec3 n_local) {
    if (u_iris_key <= 0.0) return lit(albedo, n_local);
    vec3 n_world = to_world(n_local);
    vec4 t = textureLod(u_iris_table, vec2(0.5) + hit.xy / (2.0 * u_iris_radius), 0.0);
    vec3 d = vec3(t.xy, sqrt(max(1.0 - dot(t.xy, t.xy), 0.0)));
    float k = wrap_light(dot(n_world, u_key_dir), u_key_wrap);
    k = mix(k, t.z * wrap_light(dot(n_local, d), u_key_wrap), u_iris_light) * t.w;
    return albedo * (vec3(u_ambient) + u_key_color * k
                     + u_fill_color * wrap_light(dot(n_world, u_fill_dir), u_fill_wrap));
}
#endif

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
#ifdef LOOK

// The irregularity texel at an eye-local surface point: (gradient u, gradient v, roughness noise).
vec3 film_sample(vec3 p) {
    vec3 t = texture(u_noise_texture, film_uv(p)).rgb * 2.0 - 1.0;
    return vec3(t.xy * NOISE_GRADIENT_MAX, t.z);
}

// The key's highlight: the point highlight as before, or (I-8) the soft area highlight of the same energy.
vec3 key_reflection(vec3 n, vec3 v, float roughness) {
    if (u_soft_radiance > 0.0) {
        mat3 view_t = transpose(mat3(u_view));
        float w = area_key(reflect(-v, n), u_key_dir, view_t[1], view_t[0], roughness);
        return u_key_color * (w * env_brdf_approx(u_cornea_f0, roughness, max(dot(n, v), 1e-4)));
    }
    return u_key_color * (u_key_irradiance * direct_specular(n, v, u_key_dir, roughness, u_cornea_f0));
}

// The wet film's reflection (cornea_reflection with the film's normal and roughness), dimmed by the lid band.
vec3 film_reflection(vec3 n, vec3 v, float roughness, float band) {
    vec3 c = key_reflection(n, v, roughness);
#if REFLECTION == 1
    vec3 r_view = mat3(u_view) * reflect(-v, n);
    float nv = max(dot(n, v), 1e-4);
    c += td_env(r_view, roughness) * env_brdf_approx(u_cornea_f0, roughness, nv);
#endif
    return c * (1.0 - band);
}
#endif

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
#ifdef IRIS
        vec2 st = iris_st(hit.xy);
        vec4 iris_texel = texture(u_iris_texture, st);
        vec3 iris_albedo = iris_texel.rgb;
        // Before any per-pixel branch (derivatives): the pupil edge's pixel footprint, the relief's height gradient.
        float r_hit = length(hit.xy);
        float r_aa = fwidth(r_hit);
        vec2 relief_grad = vec2(0.0);
        if (u_relief_depth > 0.0) {
            vec2 st_dx = dFdx(st);
            vec2 st_dy = dFdy(st);
            float h0 = iris_texel.a;
            float hx = textureGrad(u_iris_texture, iris_st(hit.xy + vec2(u_relief_step, 0.0)), st_dx, st_dy).a;
            float hy = textureGrad(u_iris_texture, iris_st(hit.xy + vec2(0.0, u_relief_step)), st_dx, st_dy).a;
            relief_grad = vec2(hx - h0, hy - h0) * (2.0 * u_relief_depth / u_relief_step);
        }
#else
        vec3 iris_albedo = texture(u_iris_texture, iris_st(hit.xy)).rgb;
#endif
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
#ifdef IRIS
            vec3 behind = deep ? iris_lit(deep_albedo, deep_hit, iris_cone_normal(deep_hit)) : lit(u_limbus_albedo, ns);
#else
            vec3 behind = deep ? lit(deep_albedo, iris_cone_normal(deep_hit)) : lit(u_limbus_albedo, ns);
#endif
            inside = mix(tissue, behind, transmission(us));
#endif
        } else {
#ifdef IRIS
            vec3 albedo = kind == KIND_PUPIL ? u_pupil_albedo : iris_albedo;
            if (u_pupil_edge > 0.0 || u_pupil_margin > 0.0) {
                // Roadmap #7: the pupil edge soft over its width plus the pixel footprint, the dark margin outside it.
                float width = u_pupil_edge > 0.0 ? sqrt(u_pupil_edge * u_pupil_edge + r_aa * r_aa) : 0.0;
                vec2 w = pupil_weights(r_hit, width);
                albedo = mix(iris_albedo * (1.0 - u_pupil_margin * w.y), u_pupil_albedo, w.x);
            }
            vec3 n_iris = u_relief_depth > 0.0 && kind == KIND_IRIS ? relief_normal(hit, relief_grad)
                                                                    : iris_cone_normal(hit);
            inside = iris_lit(albedo, hit, n_iris);
#else
            inside = lit(kind == KIND_PUPIL ? u_pupil_albedo : iris_albedo, iris_cone_normal(hit));
#endif
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
#ifdef LOOK
        vec3 p_rest = u_rest * entry;
        inside *= 1.0 - u_lid_shadow * lid_shadow_weight(p_rest);
        vec3 n_film = ns;
        float rough = u_cornea_roughness;
        if (u_tilt > 0.0) {
            vec3 g = film_sample(entry);
            n_film = film_normal(ns, entry, g.xy);
            rough = film_roughness(rough, g.z);
        }
        float band = u_lid_band > 0.0 ? u_lid_band * lid_occlusion(p_rest, u_rest * reflect(dir, n_film), rough) : 0.0;
        colour = (1.0 - fresnel) * transmit_inner * inside
               + display_add(film_reflection(to_world(n_film), v_world, rough, band));
#else
        colour = (1.0 - fresnel) * transmit_inner * inside + display_add(cornea_reflection(n_world, v_world));
#endif
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
#ifdef IRIS
        vec3 behind = through ? iris_lit(through_albedo, through_hit, iris_cone_normal(through_hit))
                              : lit(u_limbus_albedo, n);
#else
        vec3 behind = through ? lit(through_albedo, iris_cone_normal(through_hit)) : lit(u_limbus_albedo, n);
#endif
        colour = mix(colour, behind, transmission(us));
#endif
        // The Worklight's own highlight (non-local viewer), with the eye's finish.
        vec3 n_world = to_world(n);
        vec3 view_axis = normalize(transpose(mat3(u_view)) * vec3(0.0, 0.0, 1.0));
#ifdef LOOK
        vec3 p_rest = u_rest * p;
        colour *= 1.0 - u_lid_shadow * lid_shadow_weight(p_rest);
        vec3 highlight = vec3(u_specular * dot(u_key_color, LUMA) * blinn_phong(n_world, u_key_dir, view_axis,
                                                                               u_spec_exponent)
                              + u_fill_specular * dot(u_fill_color, LUMA) * blinn_phong(n_world, u_fill_dir, view_axis,
                                                                                         u_spec_exponent));
        if (u_wet > 0.0) {
            // The wet film continues over the sclera (one film across the limbus: the cornea's roughness at the ring,
            // the sclera's beyond the normal transition); it replaces the Worklight's plastic highlight by `u_wet`.
            vec3 n_film = n;
            float rough = mix(u_cornea_roughness, u_sclera_roughness, limbus_smooth(u / (2.0 * u_normal_w)));
            if (u_tilt > 0.0) {
                vec3 g = film_sample(p);
                n_film = film_normal(n, p, g.xy);
                rough = film_roughness(rough, g.z);
            }
            vec3 nf_world = to_world(n_film);
            float f = schlick_scalar(u_cornea_f0, max(dot(nf_world, v_world), 0.0));
            float band = u_lid_band > 0.0 ? u_lid_band * lid_occlusion(p_rest, u_rest * reflect(dir, n_film), rough)
                                          : 0.0;
            colour = (1.0 - u_wet * f) * colour + (1.0 - u_wet) * highlight
                   + u_wet * display_add(film_reflection(nf_world, v_world, rough, band));
        } else {
            colour += highlight;
        }
#else
        colour += vec3(u_specular * dot(u_key_color, LUMA) * blinn_phong(n_world, u_key_dir, view_axis, u_spec_exponent)
                     + u_fill_specular * dot(u_fill_color, LUMA) * blinn_phong(n_world, u_fill_dir, view_axis,
                                                                               u_spec_exponent));
#endif
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
    } else if (u_func == 9) {
        o.xy = film_uv(a.xyz);
    } else if (u_func == 10) {
        o.xyz = film_normal(normalize(a.xyz), b.xyz, c.xy);
    } else if (u_func == 11) {
        o.xy = vec2(film_roughness(a.x, a.y), lid_shadow_weight(b.xyz));
    } else if (u_func == 12) {
        o.x = lid_occlusion(a.xyz, normalize(b.xyz), c.x);
    } else if (u_func == 13) {
        o.x = area_key(normalize(a.xyz), normalize(b.xyz), normalize(c.xyz), vec3(1.0, 0.0, 0.0), a.w);
    } else if (u_func == 14) {
        vec3 d;
        o.xyz = iris_key_terms(a.xyz, normalize(b.xyz), d);
    } else if (u_func == 15) {
        vec3 e;
        vec3 d;
        float cos_in;
        float aperture;
        float phi = 0.0;
        bool ok = iris_light_path(a.xyz, normalize(b.xyz), false, phi, e, d, cos_in, aperture);
        o = vec4(d, ok ? aperture : -1.0);
    } else if (u_func == 16) {
        o.xyz = relief_normal(a.xyz, b.xy);
    } else if (u_func == 17) {
        o.xy = pupil_weights(a.x, a.y);
    } else if (u_func == 18) {
        o = iris_table_value(a.xy);
    }
    out_value = o;
}
"""

IRIS_TABLE_VERTEX_SRC = """#version 330 core
void main() {
    vec2 p = vec2(float((gl_VertexID << 1) & 2), float(gl_VertexID & 2));
    gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}
"""

IRIS_TABLE_FRAGMENT_BODY = """
uniform int u_table_size;
layout(location = 0) out vec4 out_value;
void main() {
    vec2 xy = (gl_FragCoord.xy / float(u_table_size) * 2.0 - 1.0) * u_iris_radius;
    out_value = iris_table_value(xy);
}
"""

PARITY_FUNCS = {"trace_hit": 0, "trace_entry": 1, "iris_st": 2, "coords": 3, "weights": 4, "normal_blend": 5,
                "sclera_through": 6, "td_env": 7, "worklight_light": 8, "film_uv": 9, "film_normal": 10,
                "film_roughness_shadow": 11, "lid_occlusion": 12, "area_key": 13, "iris_key_terms": 14,
                "iris_light_path": 15, "relief_normal": 16, "pupil_weights": 17,
                "iris_table_value": 18}

FULLSCREEN_VERTEX_SRC = """#version 330 core
layout(location = 0) in vec2 a_position;
void main() {
    gl_Position = vec4(a_position, 0.0, 1.0);
}
"""


def _header(**defines) -> str:
    return "#version 330 core\n" + "".join(f"#define {k} {v}\n" for k, v in defines.items() if v is not None)


def shell_sources(locations: dict[str, int], variant: str, level: int, reflection: str, fit: bool,
                  debug_kind: bool = False, look: bool = False, iris: bool = False) -> list[tuple[str, str]]:
    """The shell program's sources. Without `look` the fragment source is the one before phase 3, character for
    character (`test_gl_eye_pass.py` pins that), so the "fast" tier and an eye without a look draw and cost as before;
    without `iris` it is the one of phase 3. `iris` needs `look` (the iris values live in the look)."""
    iris = bool(iris and look)
    header = _header(VARIANT=VARIANT_IDS[variant], LIMBUS_LEVEL=int(level), REFLECTION=REFLECTIONS[reflection],
                     IRIS_FIT=1 if fit else None, DEBUG_KIND=1 if debug_kind else None, LOOK=1 if look else None,
                     IRIS=1 if iris else None)
    library = EYE_LIB_SRC + (LOOK_LIB_SRC if look else "") + (IRIS_LIB_SRC if iris else "")
    body = SHELL_FRAGMENT_BODY if iris else _without(SHELL_FRAGMENT_BODY, "IRIS")
    body = body if look else _without(body, "LOOK")
    return [(SHELL_VERTEX_SRC.format(**locations), "vertex"), (header + library + body, "fragment")]


def _without(source: str, name: str) -> str:
    """`source` with its `#ifdef <name>` blocks resolved as the preprocessor would without that define (kept: the
    `#else` part). Nested `#if` inside such a block are carried along; blocks of the same name are not nested."""
    out, state, depth = [], None, 0  # state: None outside, "if" / "else" inside a block
    for line in source.splitlines(keepends=True):
        stripped = line.strip()
        if state is None:
            if stripped == f"#ifdef {name}":
                state, depth = "if", 0
            else:
                out.append(line)
            continue
        if stripped.startswith("#if"):
            depth += 1
        elif depth and stripped == "#endif":
            depth -= 1
        elif not depth and stripped == "#else":
            state = "else"
            continue
        elif not depth and stripped == "#endif":
            state = None
            continue
        if state == "else":
            out.append(line)
    return "".join(out)


def parity_sources(fit: bool) -> list[tuple[str, str]]:
    return [(FULLSCREEN_VERTEX_SRC, "vertex"),
            (_header(IRIS_FIT=1 if fit else None, LOOK=1, IRIS=1) + EYE_LIB_SRC + LOOK_LIB_SRC + IRIS_LIGHT_SRC
             + IRIS_LIB_SRC
             + PARITY_FRAGMENT_BODY,
             "fragment")]


def iris_table_sources() -> list[tuple[str, str]]:
    """Phase 4: the program that bakes an eye's key table (`IRIS_LIGHT_SRC`, one fragment per texel)."""
    return [(IRIS_TABLE_VERTEX_SRC, "vertex"),
            (_header() + EYE_LIB_SRC + IRIS_LIGHT_SRC + IRIS_TABLE_FRAGMENT_BODY, "fragment")]
