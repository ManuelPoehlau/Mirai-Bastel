"""GLSL 330 sources of the Eye Proof (P1, 2026-11-14).

`LIB_SRC` holds every shading term, each the twin of the same-named function in `eye_math.py` (and the environment
in `studio_env.radiance`); `tests/test_gl_parity.py` checks them on the GPU against the NumPy reference through
`PARITY_FRAGMENT_SRC`, which includes the same `LIB_SRC` the lab draws with.

Programs (all `#version 330 core`):
- **surface** (`surface_sources`): the lab's own shading of a part, drawn from the production `GLRenderStore`'s
  VertexList. Its vertex shader takes the production program's attribute locations (the textured program's and the
  GPU picker's precedent). Variants by `#define`: `TECH` 1 = T-B (GGX key only), 2 = T-C (+ prefiltered cube),
  3 = T-D (+ analytic softbox); `TEXTURED` (iris: production geometry shader + triangle-UV buffer, AD-026);
  `CORNEA_C1` (iris fragments take the cornea's specular at the analytic cornea sphere); `SHELL` 2 / 3 (the cornea
  mesh, additive / Fresnel-alpha). Normals: the interpolated vertex normal, no face data (the bilinear quad normal is
  the Worklight's and costs 13 ms at full frame on the reference PC, RESULTS_REFERENCE_PC §6; D-L6).
- **background**: a full-frame triangle, solid grey or the analytic environment blurred, through the same colour path.
- **parity**: evaluates one function of `LIB_SRC` per fragment for inputs read from a buffer texture.

T-A is not here: it is the production program, unchanged (`EyeLabStore` calls `GLRenderStore.draw`).
"""

from __future__ import annotations

from . import eye_math as em

TECH_IDS = {"T-B": 1, "T-C": 2, "T-D": 3}
SHELL_IDS = {"C2": 2, "C3": 3}
MAX_LIGHTS = 2

LIB_SRC = f"""
const float PI = 3.14159265358979;
const float MIN_DIRECT_ROUGHNESS = {em.MIN_DIRECT_ROUGHNESS!r};
const float TD_SIGMA_SCALE = {em.TD_SIGMA_SCALE!r};
const float TD_SIGMA_POWER = {em.TD_SIGMA_POWER!r};
const int MAX_LIGHTS = {MAX_LIGHTS};

// -- colour path (eye_math.srgb_decode / srgb_encode / tonemap / display)
vec3 srgb_decode(vec3 c) {{
    return mix(pow((c + 0.055) / 1.055, vec3(2.4)), c / 12.92, vec3(lessThanEqual(c, vec3(0.04045))));
}}
vec3 srgb_encode(vec3 c) {{
    c = clamp(c, 0.0, 1.0);
    return mix(1.055 * pow(c, vec3(1.0 / 2.4)) - 0.055, 12.92 * c, vec3(lessThanEqual(c, vec3(0.0031308))));
}}
vec3 tonemap(vec3 x, int mode) {{
    x = max(x, 0.0);
    return mode == 0 ? min(x, 1.0) : x / (1.0 + x);
}}
vec3 display(vec3 linear_rgb, float exposure, int mode) {{
    return srgb_encode(tonemap(linear_rgb * exposure, mode));
}}

// -- BRDF (eye_math.ggx_d / smith_vis / schlick / direct_specular / env_brdf_approx / roughness_to_lod)
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
vec3 schlick(vec3 f0, float v_dot_h) {{
    float m = 1.0 - clamp(v_dot_h, 0.0, 1.0);
    return f0 + (1.0 - f0) * (m * m * m * m * m);
}}
vec3 direct_specular(vec3 n, vec3 v, vec3 l, float roughness, vec3 f0) {{
    n = normalize(n);
    v = normalize(v);
    l = normalize(l);
    vec3 h = normalize(v + l);
    float nl = dot(n, l);
    if (nl <= 0.0) return vec3(0.0);
    float nv = max(dot(n, v), 1e-4);
    float nh = max(dot(n, h), 0.0);
    float vh = max(dot(v, h), 0.0);
    float r = max(roughness, MIN_DIRECT_ROUGHNESS);
    float a = r * r;
    return ggx_d(nh, a) * smith_vis(nl, nv, a) * nl * schlick(f0, vh);
}}
vec3 env_brdf_approx(vec3 f0, float roughness, float n_dot_v) {{
    const vec4 c0 = vec4(-1.0, -0.0275, -0.572, 0.022);
    const vec4 c1 = vec4(1.0, 0.0425, 1.04, -0.04);
    vec4 q = roughness * c0 + c1;
    float a004 = min(q.x * q.x, exp2(-9.28 * n_dot_v)) * q.x + q.y;
    float a = -1.04 * a004 + q.z;
    float b = 1.04 * a004 + q.w;
    return f0 * a + b;
}}
float roughness_to_lod(float roughness, int mode, float last_level) {{
    float r = clamp(roughness, 0.0, 1.0);
    return (mode == 0 ? r : sqrt(r)) * last_level;
}}

// -- the analytic studio (eye_math.erf / box_profile / rect_term / backdrop, studio_env.radiance / td_radiance)
uniform vec3 u_light_centre[MAX_LIGHTS];
uniform vec3 u_light_right[MAX_LIGHTS];
uniform vec3 u_light_up[MAX_LIGHTS];
uniform vec2 u_light_half[MAX_LIGHTS];
uniform vec3 u_light_radiance[MAX_LIGHTS];
uniform int u_light_count;
uniform vec3 u_zenith;
uniform vec3 u_horizon;
uniform vec3 u_floor;
uniform float u_horizon_width;
uniform float u_edge_sigma;

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
float rect_term(vec3 d, vec3 centre, vec3 right, vec3 up, vec2 half_size, float sigma) {{
    float dc = dot(d, centre);
    float x = atan(dot(d, right), dc + 1e-12);
    float y = atan(dot(d, up), dc + 1e-12);
    return box_profile(x, half_size.x, sigma) * box_profile(y, half_size.y, sigma) * smoothstep(0.0, 0.25, dc);
}}
vec3 backdrop(vec3 d, float horizon_width) {{
    vec3 sky = u_horizon + (u_zenith - u_horizon) * clamp(d.y, 0.0, 1.0);
    return u_floor + (sky - u_floor) * smoothstep(-horizon_width, horizon_width, d.y);
}}
vec3 env_radiance(vec3 d, float sigma, float horizon_width) {{
    vec3 value = backdrop(d, horizon_width);
    for (int i = 0; i < MAX_LIGHTS; ++i) {{
        if (i >= u_light_count) break;
        value += rect_term(d, u_light_centre[i], u_light_right[i], u_light_up[i], u_light_half[i], sigma)
               * u_light_radiance[i];
    }}
    return value;
}}
float td_lobe(float roughness) {{
    return TD_SIGMA_SCALE * pow(roughness * roughness, TD_SIGMA_POWER);
}}
vec3 td_env(vec3 d, float roughness) {{
    float lobe = td_lobe(roughness);
    return env_radiance(d, sqrt(u_edge_sigma * u_edge_sigma + lobe * lobe),
                        sqrt(u_horizon_width * u_horizon_width + lobe * lobe));
}}

// -- C1 (eye_math.cornea_hit)
bool cornea_hit(vec3 origin, vec3 dir, vec3 centre, float radius, float limbus_z, float max_t,
                out vec3 p, out vec3 normal) {{
    dir = normalize(dir);
    vec3 oc = origin - centre;
    float b = dot(oc, dir);
    float c = dot(oc, oc) - radius * radius;
    float disc = b * b - c;
    float t = -b - sqrt(max(disc, 0.0));
    p = origin + dir * t;
    normal = (p - centre) / radius;
    return disc >= 0.0 && t > 0.0 && t < max_t && p.z >= limbus_z;
}}
"""

SURFACE_VERTEX_SRC = """#version 330 core
layout(location = {position}) in vec3 position;
layout(location = {normal}) in vec3 normal;
uniform mat4 u_view;
uniform mat4 u_proj;
uniform mat4 u_model;
out vec3 v_normal;
out vec3 v_world_pos;
void main() {{
    vec4 world = u_model * vec4(position, 1.0);
    gl_Position = u_proj * u_view * world;
    v_normal = mat3(u_model) * normal;
    v_world_pos = world.xyz;
}}
"""

SURFACE_FRAGMENT_BODY = """
in vec3 v_normal;
in vec3 v_world_pos;
#ifdef TEXTURED
in vec3 g_bary;
uniform sampler2D u_texture;
uniform samplerBuffer u_triangle_uvs;
#endif

uniform vec3 u_eye;
uniform vec3 u_albedo;
uniform float u_roughness;
uniform vec3 u_f0;
uniform float u_spec_weight;
uniform vec3 u_key_dir;
uniform vec3 u_key_irradiance;
uniform vec3 u_sky;
uniform vec3 u_ground;
uniform float u_env_intensity;
uniform mat3 u_env_rot;
uniform float u_exposure;
uniform int u_tonemap;
#if TECH == 2
uniform samplerCube u_env;
uniform float u_env_last;
uniform int u_lod_mode;
uniform int u_env_rgbm;
uniform float u_rgbm_range;
#endif
#ifdef CORNEA_C1
uniform vec3 u_cornea_centre;
uniform float u_cornea_radius;
uniform float u_limbus_z;
uniform vec3 u_cornea_f0;
uniform float u_cornea_roughness;
#endif

out vec4 out_color;

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

void main() {
    vec3 n = normalize(v_normal);
    vec3 v = normalize(u_eye - v_world_pos);
#ifdef SHELL
    vec3 spec = specular(n, v, u_roughness, u_f0);
#if SHELL == 3
    float alpha = schlick(u_f0, max(dot(n, v), 0.0)).x;
#else
    float alpha = 1.0;
#endif
    out_color = vec4(display(spec, u_exposure, u_tonemap), alpha);
#else
    vec3 albedo = u_albedo;
#ifdef TEXTURED
    {
        int t = gl_PrimitiveID * 3;
        vec2 a = texelFetch(u_triangle_uvs, t).xy;
        if (a.x > -1.0e29) {
            vec2 uv = a * g_bary.x + texelFetch(u_triangle_uvs, t + 1).xy * g_bary.y
                    + texelFetch(u_triangle_uvs, t + 2).xy * g_bary.z;
            albedo = srgb_decode(texture(u_texture, uv).rgb);
        }
    }
#endif
    vec3 colour = albedo * (u_key_irradiance * (max(dot(n, u_key_dir), 0.0) / PI)
                            + mix(u_ground, u_sky, 0.5 + 0.5 * n.y));
    colour += u_spec_weight * specular(n, v, u_roughness, u_f0);
#ifdef CORNEA_C1
    {
        vec3 ray = v_world_pos - u_eye;
        float len = length(ray);
        vec3 p;
        vec3 cn;
        if (cornea_hit(u_eye, ray / len, u_cornea_centre, u_cornea_radius, u_limbus_z, len, p, cn)) {
            vec3 cv = -ray / len;
            float fresnel = schlick(u_cornea_f0, max(dot(cn, cv), 0.0)).x;
            colour = colour * (1.0 - fresnel) + specular(cn, cv, u_cornea_roughness, u_cornea_f0);
        }
    }
#endif
    out_color = vec4(display(colour, u_exposure, u_tonemap), 1.0);
#endif
}
"""

FULLSCREEN_VERTEX_SRC = """#version 330 core
layout(location = 0) in vec2 a_position;
void main() {
    gl_Position = vec4(a_position, 0.0, 1.0);
}
"""

BACKGROUND_FRAGMENT_BODY = """
uniform vec2 u_size;
uniform vec3 u_cam_right;
uniform vec3 u_cam_up;
uniform vec3 u_cam_forward;
uniform float u_tan_half;
uniform mat3 u_env_rot;
uniform float u_env_intensity;
uniform float u_blur;
uniform int u_solid;
uniform vec3 u_solid_colour;
uniform float u_exposure;
uniform int u_tonemap;
out vec4 out_color;
void main() {
    vec2 p = gl_FragCoord.xy / u_size * 2.0 - 1.0;
    vec3 d = normalize(u_cam_forward + u_tan_half * (p.x * u_size.x / u_size.y * u_cam_right + p.y * u_cam_up));
    vec3 radiance = u_solid != 0 ? u_solid_colour : td_env(u_env_rot * d, u_blur) * u_env_intensity;
    out_color = vec4(display(radiance, u_exposure, u_tonemap), 1.0);
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
    if (u_func == 0) o.rgb = srgb_decode(a.rgb);
    else if (u_func == 1) o.rgb = srgb_encode(a.rgb);
    else if (u_func == 2) o.rgb = tonemap(a.rgb, int(a.w + 0.5));
    else if (u_func == 3) o = vec4(ggx_d(a.x, a.y), smith_vis(a.z, a.w, a.y), schlick(vec3(b.x), b.y).x, 0.0);
    else if (u_func == 4) o.rgb = direct_specular(a.xyz, b.xyz, c.xyz, a.w, vec3(b.w));
    else if (u_func == 5) o.rgb = env_brdf_approx(vec3(a.x), a.y, a.z);
    else if (u_func == 6) o = vec4(roughness_to_lod(a.x, int(a.y + 0.5), a.z), erf_approx(a.w),
                                   box_profile(b.x, b.y, b.z), td_lobe(b.w));
    else if (u_func == 7) o.rgb = env_radiance(a.xyz, b.x, b.y);
    else if (u_func == 8) o.rgb = td_env(a.xyz, a.w);
    else if (u_func == 9) {
        vec3 p;
        vec3 n;
        bool hit = cornea_hit(a.xyz, b.xyz, c.xyz, b.w, c.w, a.w, p, n);
        o = vec4(hit ? p : vec3(0.0), hit ? 1.0 : 0.0);
    }
    else if (u_func == 10) o.rgb = display(a.rgb, a.w, int(b.x + 0.5));
    out_value = o;
}
"""

PARITY_FUNCS = {"srgb_decode": 0, "srgb_encode": 1, "tonemap": 2, "ggx_vis_schlick": 3, "direct_specular": 4,
                "env_brdf_approx": 5, "lod_erf_box_lobe": 6, "env_radiance": 7, "td_env": 8, "cornea_hit": 9,
                "display": 10}


def _defines(**flags) -> str:
    return "".join(f"#define {name} {value}\n" for name, value in flags.items() if value is not None)


def surface_sources(locations: dict[str, int], tech: int, textured: bool, cornea_c1: bool,
                    shell: int | None) -> list[tuple[str, str]]:
    """[(source, kind)] of one surface variant, on the production program's attribute `locations`."""
    from viewport.gl_render_store import TEXTURED_GEOMETRY_SRC, TEXTURED_VERTEX_SRC

    header = "#version 330 core\n" + _defines(TECH=tech, TEXTURED=1 if textured else None,
                                              CORNEA_C1=1 if cornea_c1 else None, SHELL=shell)
    fragment = header + LIB_SRC + SURFACE_FRAGMENT_BODY
    if textured:
        # AD-026's own vertex + geometry stage (barycentrics, gl_PrimitiveID passed through), reused unchanged.
        return [(TEXTURED_VERTEX_SRC.format(**locations), "vertex"), (TEXTURED_GEOMETRY_SRC, "geometry"),
                (fragment, "fragment")]
    return [(SURFACE_VERTEX_SRC.format(**locations), "vertex"), (fragment, "fragment")]


def background_sources() -> list[tuple[str, str]]:
    return [(FULLSCREEN_VERTEX_SRC, "vertex"), ("#version 330 core\n" + LIB_SRC + BACKGROUND_FRAGMENT_BODY, "fragment")]


def parity_sources() -> list[tuple[str, str]]:
    return [(FULLSCREEN_VERTEX_SRC, "vertex"), ("#version 330 core\n" + LIB_SRC + PARITY_FRAGMENT_BODY, "fragment")]
