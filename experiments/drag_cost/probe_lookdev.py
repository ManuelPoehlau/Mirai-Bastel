"""LookDev LD-0 probe (AD-038 draft, 2026-11-19): what a LookDev skin pass, the UV request and the P3 render targets cost
on the reference PC, before any `src/` change.

Usage (from the repo root; opens hidden pyglet windows):
    python experiments/drag_cost/probe_lookdev.py                       # 1024x768 (+ extras), then 1920x1080
    python experiments/drag_cost/probe_lookdev.py --draws 5             # container: a function check
    python experiments/drag_cost/probe_lookdev.py --size 1024 768 --skip cube,depth
    python experiments/drag_cost/probe_lookdev.py --png out_dir         # also writes the stand-in frames as PNGs
    python experiments/drag_cost/probe_lookdev.py --p3                  # P3-0 (AD-039 §11.1) instead of the LD-0 rows

Set the NVIDIA driver to "prefer maximum performance" first (as for `probe_shading_gpu.py`). Without `--size` each
size of `--sizes` runs in its own process (a fresh GL context and app); the extras run in the first one only.

The scene: `scenes/Gollum_Head_05.mirai.json` as saved (the painted head is the edit object, the two eyes are drawn by
the eye pass; the teeth and the older head are hidden in that file). Surfaces: `cage` (SubD off) and `subd1` (the SubD
preview at the file's level 1, the head's drawn surface). Views: `framed` (the head framed by
`OrbitCamera.frame_on_bounds` at the ¾ angle) and `close` (front, the face filling the frame).

(a) Frame rows, each the meshes + eyes drawn once, timed with GL_TIME_ELAPSED (`--draws` rounds after 5 unmeasured):
- `worklight`     the Worklight store draw of the meshes (`RenderMesh.render`) + the eyes through the eye pass at the
                  file's eye tier - today's Modelling Room frame without overlays (the LD-D10 floor);
- `wl eyes full`  the same with the eyes in the "full" tier (the tier the LookDev room raises to);
- `ld skin`       the stand-in LookDev skin program on every non-eye mesh, no eyes, no background;
- `ld frame`      the M1 frame stand-in: a gradient background, the skin program (albedo map where the mesh has UVs
                  and a shown texture or paint composite), the eyes in "full" (Worklight variant: the LookDev variant
                  adds a few ALU operations);
- `ld no env`     `ld frame` without the analytic studio specular on skin (the first render-only lever, §12.2);
- `ld no map`     `ld frame` with the base colour instead of the albedo map (what the teeth draw);
- `ld shadow`     P3 stand-in (needs (d)): a 2048² key depth pass + `ld frame` with a 16-tap PCF lookup;
- `app render`    `Viewport.render()` as the app calls it (overlays included), for reference.
  The stand-in skin program is VS + GS + FS like the textured Worklight program (the store's own vertex and geometry
  sources, its attribute locations), with sRGB decode, interpolated normals + specular AA from normal derivatives,
  wrap diffuse from key / fill / rim, GGX / Smith / Schlick from the three lights, SH9 irradiance, the eye's analytic
  studio made parametric (uniform arrays) as environment specular, a backscatter term, exposure, a luminance
  Reinhard curve and one sRGB encode. It is a cost stand-in, not the M1 look.
(b) UV request: the head's UVs inactive (textures hidden: the Worklight has no texture to show), then the stand-in
    request (the instance's `_uv_wanted` answers "the mesh has UVs", `mark_material_dirty`) - the `Viewport.sync()` that
    allocates and fills the triangle UVs (`RenderMesh._sync_uv_resource`), the first draw that uploads them, and the
    request taken back; first cycle and the median of the repeats, cage and SubD 1. Also `_triangle_uvs_flat()` alone.
(c) optional, P3: a 128² RGBA16F cube map with mips down to 2², each face and level rendered through an FBO (a GPU
    prefilter stand-in: N GGX samples of the analytic studio per texel), completeness per attachment, the chain's GPU
    time for 64 and 256 samples, level 0 read back against `eye_optics.td_env`, `textureLod` sampled back.
(d) optional, P3: a 2048² DEPTH_COMPONENT24 texture rendered from the key and sampled with `sampler2DShadow` (the
    `ld shadow` row); completeness, texels written, pixels the lookup darkens.
(compile) first use: the eye shell program of four variants compiled and linked cold (a comment no driver cache has
    seen) and again unchanged (the driver cache), `EyePass.program()` on a fresh pass, the skin stand-in's variants.

`--p3` (P3-0, AD-039 §11.1, 2026-11-22) runs instead: (p3a) the key's depth pass alone at 512² / 1024² / 2048², casters
skin only and skin + eyes (what a pose, morph or key change costs); (p3b) the environment cube prefiltered on the GPU
with and without the corner fix, the corner spread per level; (p3c) frame rows against `ld frame`: `shadow <size>
x<fetches>` (a map rendered once: the lookup of a still pose), `drag` (the map every frame), `thick` (+ the thickness
from the raw depth), `dual direct` / `dual env` (a second GGX lobe), `cube env` / `cube dual env` (the environment
specular from the cube), `p3 all` (the candidate fixed settings together), and the LD-D10 share.

Plain ASCII output; prints the commit and working-tree state (`_paths.source_state`). Reads `src/` (`core`, `mirai`,
`viewport`, `main.GL_TYPES`) only and changes nothing there: the UV request and the triangle-UV binding are stand-ins
built on `RenderMesh` / `GLRenderStore` internals, exactly the two places AD-038 proposes small public interfaces for.
"""

from __future__ import annotations

import argparse
import ctypes
import math
import statistics
import subprocess
import sys
import time
import uuid
from pathlib import Path

_EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
if str(_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS_DIR))

from drag_cost._paths import REPO_ROOT, ensure_paths  # noqa: E402

ensure_paths()

SCENE = REPO_ROOT / "scenes" / "Gollum_Head_05.mirai.json"
WARMUP_ROUNDS = 5
DEFAULT_DRAWS = 30
DEFAULT_SIZES = ((1024, 768), (1920, 1080))
SURFACES = ("cage", "subd1")
VIEWS = ("framed", "close")
EXTRAS = ("uv", "cube", "depth", "compile")
ROWS = ("worklight", "wl eyes full", "ld skin", "ld frame", "ld no env", "ld no map", "ld shadow", "app render")
CLEAR = (0.1, 0.1, 0.11)
#: LD-D10: 30 fps on the reference PC, framed head, 1024x768 - the whole frame's budget in ms.
FRAME_BUDGET_MS = 1000.0 / 30.0
UV_UNIT = 3          # the store's own triangle-UV unit (`gl_render_store._TRIANGLE_UVS_UNIT`)
ALBEDO_UNIT = 4      # the Worklight's texture unit
SHADOW_UNIT = 6       # not one of the units `_flush_face_data` binds (1, 2, 3, 5)
SHADOW_SIZE = 2048
CUBE_SIZE = 128
CUBE_SAMPLES = (64, 256)
# P3-0 (`--p3`, AD-039): the candidates for the P3 fixed settings, measured before any `src/` change.
CUBE_UNIT = 5         # the P3 environment cube (not a unit the skin pass or the store's face data use while it draws)
SHADOW_RAW_UNIT = 7   # the shadow map's raw depth (a second sampler object, no compare) for the thickness
P3_DEPTH_SIZES = (512, 1024, 2048)
P3_SHADOW = ((1024, 2), (1024, 3), (1024, 4), (2048, 3), (2048, 4))   # (map size, PCF grid: grid^2 fetches)
P3_SETTING = (1024, 3)  # the fixed-setting candidate (AD-039 S1): 1024^2, 9 bilinear compare fetches
P3_CUBE_SAMPLES = 64
#: Dual lobe (AD-039 S3, `PROVISIONAL`): roughness x DUAL[0] and x DUAL[1], mixed DUAL[2] / 1 - DUAL[2].
DUAL = (0.75, 1.3, 0.85)
#: Thickness (AD-039 S4, `PROVISIONAL`): the light's transmission falls to 1/e over this many world units (cm).
THICKNESS_SCALE = 0.6
IDENTITY4 = (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0)

# Portrait stand-in (proposal §8.2, `PROVISIONAL`): (azimuth, elevation in degrees, Kelvin, intensity, size), world
# frame (Y up, the model faces +Z, azimuth from +Z toward +X).
PORTRAIT_LIGHTS = ((45.0, 30.0, 5600.0, 1.6, 0.10), (-60.0, 5.0, 6500.0, 0.7, 0.25), (-150.0, 25.0, 7500.0, 1.4, 0.05))
ENV_INTENSITY = 0.08
EXPOSURE = 1.0
BACKGROUND = ((0.05, 0.05, 0.06), (0.20, 0.20, 0.22))   # bottom, top: display values, as picked (LD-D9)
#: Creature Skin stand-in (proposal §4.1): roughness, F0, per-channel wrap, backscatter, backscatter colour.
SKIN = {"u_roughness": 0.5, "u_f0": 0.028, "u_wrap": (0.35, 0.22, 0.18), "u_backscatter": 0.15,
        "u_backscatter_color": (1.0, 0.35, 0.2)}
SPEC_AA_K = 0.5

# -- GLSL -------------------------------------------------------------------------------------------------------------

STUDIO_LIB = """
const float PI = 3.14159265358979;
const float TD_SIGMA_SCALE = {sigma_scale!r};
const float TD_SIGMA_POWER = {sigma_power!r};
const int MAX_STUDIO = 4;
uniform int u_studio_n;
uniform vec3 u_studio_centre[MAX_STUDIO];
uniform vec3 u_studio_right[MAX_STUDIO];
uniform vec3 u_studio_up[MAX_STUDIO];
uniform vec2 u_studio_half[MAX_STUDIO];
uniform vec3 u_studio_radiance[MAX_STUDIO];
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
// eye_shaders.td_env with the studio as uniforms (the parametric studio, proposal section 8.1)
vec3 studio_radiance(vec3 d, float roughness) {{
    float lobe = TD_SIGMA_SCALE * pow(roughness * roughness, TD_SIGMA_POWER);
    float sigma = sqrt(u_edge_sigma * u_edge_sigma + lobe * lobe);
    float width = sqrt(u_horizon_width * u_horizon_width + lobe * lobe);
    vec3 sky = u_horizon + (u_zenith - u_horizon) * clamp(d.y, 0.0, 1.0);
    vec3 value = u_floor + (sky - u_floor) * smoothstep(-width, width, d.y);
    for (int i = 0; i < MAX_STUDIO; ++i) {{
        if (i >= u_studio_n) break;
        float dc = dot(d, u_studio_centre[i]);
        float x = atan(dot(d, u_studio_right[i]), dc + 1e-12);
        float y = atan(dot(d, u_studio_up[i]), dc + 1e-12);
        value += box_profile(x, u_studio_half[i].x, sigma) * box_profile(y, u_studio_half[i].y, sigma)
               * smoothstep(0.0, 0.25, dc) * u_studio_radiance[i];
    }}
    return value;
}}
"""

SKIN_FRAGMENT_BODY = """
in vec3 v_normal;
in vec3 v_world_pos;
in vec3 g_bary;
uniform vec3 u_eye;
uniform vec3 u_base_color;
uniform float u_roughness;
uniform float u_f0;
uniform vec3 u_wrap;
uniform float u_backscatter;
uniform vec3 u_backscatter_color;
uniform vec3 u_light_dir[3];
uniform vec3 u_light_color[3];
uniform float u_light_size[3];
uniform vec3 u_sh[9];
uniform mat3 u_env_rot;
uniform float u_env_intensity;
uniform float u_exposure;
#ifdef ALBEDO_MAP
uniform samplerBuffer u_triangle_uvs;
uniform sampler2D u_albedo;
#endif
#ifdef SHADOW
uniform sampler2DShadow u_shadow;
uniform mat4 u_light_vp;
#ifndef SHADOW_GRID
#define SHADOW_GRID 4
#endif
#endif
#ifdef THICKNESS
uniform sampler2D u_shadow_depth;
uniform float u_light_depth_range;
uniform float u_thickness_scale;
#endif
#ifdef CUBE_ENV
uniform samplerCube u_env_cube;
uniform float u_env_levels;
#endif
out vec4 out_color;

const vec3 LUMA = vec3(0.2126, 0.7152, 0.0722);
#ifdef DUAL_LOBE
// the second specular lobe (P3, AD-039 S3): roughness x 0.75 and x 1.3, mixed 0.85 / 0.15 [PROVISIONAL]
const vec3 DUAL = vec3({dual_a!r}, {dual_b!r}, {dual_mix!r});
#endif
const float SPEC_AA_K = {spec_aa_k!r};

vec3 srgb_decode(vec3 c) {{
    c = clamp(c, 0.0, 1.0);
    return mix(pow((c + 0.055) / 1.055, vec3(2.4)), c / 12.92, vec3(lessThanEqual(c, vec3(0.04045))));
}}
vec3 srgb_encode(vec3 c) {{
    c = clamp(c, 0.0, 1.0);
    return mix(1.055 * pow(c, vec3(1.0 / 2.4)) - 0.055, 12.92 * c, vec3(lessThanEqual(c, vec3(0.0031308))));
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
float env_brdf_approx(float f0, float roughness, float n_dot_v) {{
    const vec4 c0 = vec4(-1.0, -0.0275, -0.572, 0.022);
    const vec4 c1 = vec4(1.0, 0.0425, 1.04, -0.04);
    vec4 q = roughness * c0 + c1;
    float a004 = min(q.x * q.x, exp2(-9.28 * n_dot_v)) * q.x + q.y;
    return f0 * (-1.04 * a004 + q.z) + 1.04 * a004 + q.w;
}}
vec3 wrap3(float ndl, vec3 w) {{ return max((vec3(ndl) + w) / (vec3(1.0) + w), vec3(0.0)); }}
// SH9 irradiance / pi (coefficients already convolved with the clamped cosine and divided by pi on the CPU)
vec3 sh9(vec3 n) {{
    return u_sh[0] * 0.282095
         + u_sh[1] * (0.488603 * n.y) + u_sh[2] * (0.488603 * n.z) + u_sh[3] * (0.488603 * n.x)
         + u_sh[4] * (1.092548 * n.x * n.y) + u_sh[5] * (1.092548 * n.y * n.z)
         + u_sh[6] * (0.315392 * (3.0 * n.z * n.z - 1.0))
         + u_sh[7] * (1.092548 * n.x * n.z) + u_sh[8] * (0.546274 * (n.x * n.x - n.y * n.y));
}}
vec3 lookdev_output(vec3 c) {{
    c *= u_exposure;
    float l = dot(c, LUMA);
    return srgb_encode(c / (1.0 + l));
}}

void main() {{
    vec3 n = normalize(v_normal);
    // derivatives outside any branch (undefined in non-uniform control flow)
    vec3 dndx = dFdx(n);
    vec3 dndy = dFdy(n);
    vec3 v = normalize(u_eye - v_world_pos);
    float nv = max(dot(n, v), 1e-4);
    float alpha = u_roughness * u_roughness;
    alpha = sqrt(clamp(alpha * alpha + SPEC_AA_K * (dot(dndx, dndx) + dot(dndy, dndy)), 1e-6, 1.0));
    float rough = sqrt(alpha);
    vec3 albedo = u_base_color;
#ifdef ALBEDO_MAP
    {{
        int t = gl_PrimitiveID * 3;
        vec2 a = texelFetch(u_triangle_uvs, t).xy;
        if (a.x > -1.0e29) {{
            vec2 uv = a * g_bary.x + texelFetch(u_triangle_uvs, t + 1).xy * g_bary.y
                    + texelFetch(u_triangle_uvs, t + 2).xy * g_bary.z;
            albedo = texture(u_albedo, uv).rgb;
        }}
    }}
#endif
    albedo = srgb_decode(albedo);
    float shadow = 1.0;
#ifdef SHADOW
    vec4 lp = u_light_vp * vec4(v_world_pos, 1.0);
    vec3 sp = lp.xyz / lp.w * 0.5 + 0.5;
    {{
        // SHADOW_GRID^2 fetches, each a hardware 2x2 bilinear compare (sampler2DShadow, GL_LINEAR)
        vec2 texel = 1.0 / vec2(textureSize(u_shadow, 0));
        float sum = 0.0;
        for (int y = 0; y < SHADOW_GRID; ++y)
            for (int x = 0; x < SHADOW_GRID; ++x)
                sum += texture(u_shadow, vec3(sp.xy + (vec2(x, y) - 0.5 * float(SHADOW_GRID - 1)) * texel,
                                              sp.z - 0.0015));
        shadow = sum / float(SHADOW_GRID * SHADOW_GRID);
    }}
#endif
    vec3 diffuse = vec3(0.0);
    vec3 specular = vec3(0.0);
    for (int i = 0; i < 3; ++i) {{
        vec3 l = u_light_dir[i];
        float ndl = dot(n, l);
        float s = i == 0 ? shadow : 1.0;
        diffuse += u_light_color[i] * wrap3(ndl, u_wrap) * s;
        if (ndl > 0.0) {{
            vec3 h = normalize(v + l);
            float nh = max(dot(n, h), 0.0);
#ifdef DUAL_LOBE
            float a0 = clamp(DUAL.x * DUAL.x * alpha + u_light_size[i], 1e-3, 1.0);
            float a1 = clamp(DUAL.y * DUAL.y * alpha + u_light_size[i], 1e-3, 1.0);
            float lobe = mix(ggx_d(nh, a1) * smith_vis(ndl, nv, a1), ggx_d(nh, a0) * smith_vis(ndl, nv, a0), DUAL.z);
#else
            float a = clamp(alpha + u_light_size[i], 1e-3, 1.0);
            float lobe = ggx_d(nh, a) * smith_vis(ndl, nv, a);
#endif
            specular += u_light_color[i] * (lobe * ndl * schlick_scalar(u_f0, max(dot(v, h), 0.0))) * s;
        }}
    }}
    vec3 colour = albedo * (diffuse + u_env_intensity * sh9(u_env_rot * n)) + specular;
#ifdef ENV_SPEC
    vec3 r_env = u_env_rot * reflect(-v, n);
#ifdef CUBE_ENV
#define ENV_AT(rr) textureLod(u_env_cube, r_env, clamp(rr, 0.0, 1.0) * (u_env_levels - 1.0)).rgb
#else
#define ENV_AT(rr) studio_radiance(r_env, rr)
#endif
#ifdef DUAL_LOBE_ENV
    vec3 env = mix(ENV_AT(DUAL.y * rough), ENV_AT(DUAL.x * rough), DUAL.z);
#else
    vec3 env = ENV_AT(rough);
#endif
    colour += u_env_intensity * env * env_brdf_approx(u_f0, rough, nv);
#endif
#ifdef THICKNESS
    // light through thin parts (ears, nostril wings): the key's depth map gives the distance the key light travels
    // inside the mesh to this fragment (translucent shadow maps); no authoring
    float thickness = max(sp.z - texture(u_shadow_depth, sp.xy).r, 0.0) * u_light_depth_range;
    float back = exp(-thickness / u_thickness_scale) * max(-dot(n, u_light_dir[0]), 0.0);
#else
    float back = (1.0 - nv) * (1.0 - nv) * (1.0 - nv) * max(-dot(n, u_light_dir[0]), 0.0);
#endif
    colour += u_backscatter * back * u_backscatter_color * albedo * u_light_color[0];
    out_color = vec4(lookdev_output(colour), 1.0);
}}
"""

FULLSCREEN_VS = """#version 330 core
out vec2 v_uv;
void main() {
    vec2 p = vec2(float((gl_VertexID << 1) & 2), float(gl_VertexID & 2));
    v_uv = p;
    gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}
"""

BACKGROUND_FS = """#version 330 core
in vec2 v_uv;
uniform vec3 u_bottom;
uniform vec3 u_top;
out vec4 out_color;
void main() { out_color = vec4(mix(u_bottom, u_top, clamp(v_uv.y, 0.0, 1.0)), 1.0); }
"""

DEPTH_VS = """#version 330 core
layout(location = {position}) in vec3 position;
uniform mat4 u_light_vp;
uniform mat4 u_model;
void main() {{ gl_Position = u_light_vp * u_model * vec4(position, 1.0); }}
"""

DEPTH_FS = """#version 330 core
void main() {}
"""

CUBE_FS_BODY = """
uniform int u_face;
uniform float u_size;
uniform float u_roughness;
uniform int u_samples;
uniform int u_corner_fix;  // P3 (AD-039 S5): 1 = a corner texel takes the cube corner's direction (equal on 3 faces)
out vec4 out_color;

vec3 face_direction(int face, vec2 uv) {{
    if (face == 0) return vec3(1.0, -uv.y, -uv.x);
    if (face == 1) return vec3(-1.0, -uv.y, uv.x);
    if (face == 2) return vec3(uv.x, 1.0, uv.y);
    if (face == 3) return vec3(uv.x, -1.0, -uv.y);
    if (face == 4) return vec3(uv.x, -uv.y, 1.0);
    return vec3(-uv.x, -uv.y, -1.0);
}}
float radical_inverse(uint bits) {{
    bits = (bits << 16u) | (bits >> 16u);
    bits = ((bits & 0x55555555u) << 1u) | ((bits & 0xAAAAAAAAu) >> 1u);
    bits = ((bits & 0x33333333u) << 2u) | ((bits & 0xCCCCCCCCu) >> 2u);
    bits = ((bits & 0x0F0F0F0Fu) << 4u) | ((bits & 0xF0F0F0F0u) >> 4u);
    bits = ((bits & 0x00FF00FFu) << 8u) | ((bits & 0xFF00FF00u) >> 8u);
    return float(bits) * 2.3283064365386963e-10;
}}
void main() {{
    vec2 uv = gl_FragCoord.xy / u_size * 2.0 - 1.0;
    if (u_corner_fix != 0) {{
        vec2 last = vec2(u_size - 1.0);
        vec2 texel = floor(gl_FragCoord.xy);
        if ((texel.x == 0.0 || texel.x == last.x) && (texel.y == 0.0 || texel.y == last.y)) uv = sign(uv);
    }}
    vec3 n = normalize(face_direction(u_face, uv));
    if (u_samples <= 1) {{
        out_color = vec4(studio_radiance(n, u_roughness), 1.0);
        return;
    }}
    vec3 up = abs(n.y) < 0.999 ? vec3(0.0, 1.0, 0.0) : vec3(1.0, 0.0, 0.0);
    vec3 tx = normalize(cross(up, n));
    vec3 ty = cross(n, tx);
    float a = max(u_roughness * u_roughness, 1e-3);
    vec3 sum = vec3(0.0);
    float weight = 0.0;
    for (int i = 0; i < u_samples; ++i) {{
        vec2 xi = vec2(float(i) / float(u_samples), radical_inverse(uint(i)));
        float phi = 2.0 * PI * xi.x;
        float cos_t = sqrt((1.0 - xi.y) / (1.0 + (a * a - 1.0) * xi.y));
        float sin_t = sqrt(1.0 - cos_t * cos_t);
        vec3 h = tx * (cos(phi) * sin_t) + ty * (sin(phi) * sin_t) + n * cos_t;
        vec3 l = reflect(-n, h);
        float ndl = dot(n, l);
        if (ndl > 0.0) {{
            sum += studio_radiance(l, 0.0) * ndl;
            weight += ndl;
        }}
    }}
    out_color = vec4(sum / max(weight, 1e-6), 1.0);
}}
"""

CUBE_SAMPLE_FS = """#version 330 core
uniform samplerCube u_cube;
uniform float u_lod;
out vec4 out_color;
const vec3 CENTRES[6] = vec3[](vec3(1, 0, 0), vec3(-1, 0, 0), vec3(0, 1, 0), vec3(0, -1, 0), vec3(0, 0, 1),
                               vec3(0, 0, -1));
void main() { out_color = textureLod(u_cube, CENTRES[int(gl_FragCoord.x)], u_lod); }
"""


def skin_sources(locations: dict[str, int], albedo_map: bool, env_spec: bool, shadow: bool,
                 nonce: str | None = None, *, shadow_grid: int = 4, thickness: bool = False, dual: int = 0,
                 cube_env: bool = False) -> list[tuple[str, str]]:
    """The stand-in skin program: the textured Worklight program's vertex and geometry sources (same transform, same
    barycentrics and `gl_PrimitiveID`), the stand-in fragment source. `nonce` = a comment no driver cache has seen.

    P3 variants (`--p3`, AD-039): `shadow_grid` (the PCF grid: grid² bilinear compare fetches; 4 = LD-0's 16 taps),
    `thickness` (the key's raw depth through a second sampler: backscatter by the distance the key light travels in
    the mesh; needs `shadow`), `dual` (1 = a second GGX lobe on the three lights, 2 = also on the environment
    specular), `cube_env` (the environment specular from a prefiltered cube instead of the analytic studio)."""
    from viewport import eye_optics as eo
    from viewport.gl_render_store import TEXTURED_GEOMETRY_SRC, TEXTURED_VERTEX_SRC

    if thickness and not shadow:
        raise ValueError("thickness reads the shadow map: needs shadow")
    if dual not in (0, 1, 2) or not 1 <= shadow_grid <= 8:
        raise ValueError(f"dual {dual!r}, shadow_grid {shadow_grid!r}")
    flags = (("ALBEDO_MAP", albedo_map), ("ENV_SPEC", env_spec), ("SHADOW", shadow), ("THICKNESS", thickness),
             ("DUAL_LOBE", dual > 0), ("DUAL_LOBE_ENV", dual == 2), ("CUBE_ENV", cube_env))
    defines = "".join(f"#define {name} 1\n" for name, on in flags if on)
    if shadow and shadow_grid != 4:
        defines += f"#define SHADOW_GRID {int(shadow_grid)}\n"
    fragment = ("#version 330 core\n" + defines
                + STUDIO_LIB.format(sigma_scale=eo.TD_SIGMA_SCALE, sigma_power=eo.TD_SIGMA_POWER)
                + SKIN_FRAGMENT_BODY.format(spec_aa_k=SPEC_AA_K, dual_a=DUAL[0], dual_b=DUAL[1], dual_mix=DUAL[2])
                + (f"// {nonce}\n" if nonce else ""))
    return [(TEXTURED_VERTEX_SRC.format(**locations), "vertex"), (TEXTURED_GEOMETRY_SRC, "geometry"),
            (fragment, "fragment")]


def cube_sources() -> list[tuple[str, str]]:
    from viewport import eye_optics as eo

    return [(FULLSCREEN_VS, "vertex"),
            ("#version 330 core\n" + STUDIO_LIB.format(sigma_scale=eo.TD_SIGMA_SCALE, sigma_power=eo.TD_SIGMA_POWER)
             + CUBE_FS_BODY.format(), "fragment")]


# -- arguments and small pure helpers (headless, tested) --------------------------------------------------------------


def parse_size(text: str) -> tuple[int, int]:
    w, _, h = text.lower().partition("x")
    size = (int(w), int(h))
    if min(size) < 64:
        raise ValueError(text)
    return size


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--size", nargs=2, type=int, default=None, metavar=("W", "H"),
                   help="one size in this process (default: every size of --sizes, one process each)")
    p.add_argument("--sizes", default="1024x768,1920x1080", help="WxH,WxH (default 1024x768,1920x1080)")
    p.add_argument("--draws", type=int, default=DEFAULT_DRAWS, help=f"measured rounds (default {DEFAULT_DRAWS})")
    p.add_argument("--surfaces", default=",".join(SURFACES), help="cage,subd1")
    p.add_argument("--views", default=",".join(VIEWS), help="framed,close")
    p.add_argument("--skip", default="", help=f"extras to skip, comma separated: {','.join(EXTRAS)}")
    p.add_argument("--no-extras", action="store_true", help="frame rows only (later sizes run with it)")
    p.add_argument("--png", default=None, metavar="DIR", help="write the last round's frames as PNGs into DIR")
    p.add_argument("--p3", action="store_true",
                   help="P3-0 only (AD-039): the depth pass alone and the P3 frame rows (shadow sizes / PCF, thickness, "
                        "dual lobe, environment cube) instead of the LD-0 rows and extras")
    p.add_argument("--p3-rows", default="", help="with --p3: only these frame rows (comma separated names of "
                   "`p3_rows()`, e.g. 'shadow 1k x9,cube env'; `ld frame` always runs)")
    p.add_argument("--p3-no-depth", action="store_true", help="with --p3: skip the depth-pass-alone section")
    return p


def parse_args(argv=None) -> argparse.Namespace:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.sizes = [parse_size(s) for s in args.sizes.split(",") if s.strip()]
    except ValueError:
        parser.error("--sizes: WxH,WxH with sides >= 64")
    args.surfaces = [s.strip() for s in args.surfaces.split(",") if s.strip()]
    args.views = [s.strip() for s in args.views.split(",") if s.strip()]
    args.skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    args.p3_rows = [r.strip() for r in args.p3_rows.split(",") if r.strip()]
    if set(args.p3_rows) - {name for name, _o in p3_rows()}:
        parser.error(f"--p3-rows: from {', '.join(name for name, _o in p3_rows())}")
    if not args.sizes or not args.surfaces or any(s not in SURFACES for s in args.surfaces):
        parser.error(f"--surfaces: from {', '.join(SURFACES)}")
    if not args.views or any(v not in VIEWS for v in args.views):
        parser.error(f"--views: from {', '.join(VIEWS)}")
    if args.skip - set(EXTRAS):
        parser.error(f"--skip: from {', '.join(EXTRAS)}")
    if args.draws < 1 or (args.size is not None and min(args.size) < 64):
        parser.error("--draws >= 1, --size sides >= 64")
    return args


def summary(values) -> tuple[float, float, float]:
    """(p50, min, max)."""
    return statistics.median(values), min(values), max(values)


def direction(azimuth: float, elevation: float) -> tuple[float, float, float]:
    az, el = math.radians(azimuth), math.radians(elevation)
    return (math.sin(az) * math.cos(el), math.sin(el), math.cos(az) * math.cos(el))


def sh9_basis(d):
    """The 9 real SH basis functions at unit directions `d` (..., 3) -> (..., 9), the order `sh9()` reads."""
    import numpy as np

    x, y, z = d[..., 0], d[..., 1], d[..., 2]
    return np.stack([np.full_like(x, 0.282095), 0.488603 * y, 0.488603 * z, 0.488603 * x, 1.092548 * x * y,
                     1.092548 * y * z, 0.315392 * (3.0 * z * z - 1.0), 1.092548 * x * z,
                     0.546274 * (x * x - y * y)], axis=-1)


def fibonacci_directions(count: int):
    import numpy as np

    i = np.arange(count) + 0.5
    z = 1.0 - 2.0 * i / count
    r = np.sqrt(np.maximum(0.0, 1.0 - z * z))
    phi = math.pi * (3.0 - math.sqrt(5.0)) * i
    return np.stack([r * np.cos(phi), r * np.sin(phi), z], axis=-1)


def sh9_project(radiance, count: int = 4096):
    """SH9 irradiance / pi of the radiance function `radiance(d) -> (N, 3)`: projected over `count` Fibonacci
    directions, convolved with the clamped cosine (A0 = pi, A1 = 2pi/3, A2 = pi/4), divided by pi - so a Lambert
    albedo times `sh9(n)` is the diffuse light. (9, 3)."""
    import numpy as np

    d = fibonacci_directions(count)
    basis = sh9_basis(d)
    coeffs = basis.T @ np.asarray(radiance(d), dtype=np.float64) * (4.0 * math.pi / count)
    band = np.array([math.pi] + [2.0 * math.pi / 3.0] * 3 + [math.pi / 4.0] * 5)
    return coeffs * band[:, None] / math.pi


def cube_face_direction(face: int, u: float, v: float) -> tuple[float, float, float]:
    """The GL cube-map direction of face `face` (+X, -X, +Y, -Y, +Z, -Z) at (u, v) in [-1, 1] (GL spec table)."""
    return ((1.0, -v, -u), (-1.0, -v, u), (u, 1.0, v), (u, -1.0, -v), (u, -v, 1.0), (-u, -v, -1.0))[face]


def look_at_ortho(direction_to_light, centre, radius: float) -> list[float]:
    """The column-major view-projection of an orthographic key light: looking from `centre + 2r·dir` at `centre`,
    the box ±r wide and 4r deep (the depth pass of (d))."""
    import numpy as np

    f = -np.asarray(direction_to_light, float)
    f /= np.linalg.norm(f)
    up = np.array([0.0, 1.0, 0.0]) if abs(f[1]) < 0.99 else np.array([1.0, 0.0, 0.0])
    s = np.cross(f, up)
    s /= np.linalg.norm(s)
    u = np.cross(s, f)
    eye = np.asarray(centre, float) - f * 2.0 * radius
    view = np.identity(4)
    view[0, :3], view[1, :3], view[2, :3] = s, u, -f
    view[:3, 3] = -view[:3, :3] @ eye
    near, far = 0.01 * radius, 4.0 * radius
    proj = np.identity(4)
    proj[0, 0] = proj[1, 1] = 1.0 / radius
    proj[2, 2] = -2.0 / (far - near)
    proj[2, 3] = -(far + near) / (far - near)
    return list((proj @ view).T.reshape(-1))


def studio_values() -> dict:
    """The parametric studio's uniforms filled with the eye's studio (`eye_optics.studio_frames`), as world frame."""
    from viewport import eye_optics as eo

    frames = eo.studio_frames()
    pad = 4 - len(frames)
    vec = lambda v: tuple(float(c) for c in v)  # noqa: E731
    return {
        "u_studio_n": len(frames),
        "u_studio_centre": [vec(f[0]) for f in frames] + [(0.0, 0.0, 1.0)] * pad,
        "u_studio_right": [vec(f[1]) for f in frames] + [(1.0, 0.0, 0.0)] * pad,
        "u_studio_up": [vec(f[2]) for f in frames] + [(0.0, 1.0, 0.0)] * pad,
        "u_studio_half": [vec(f[3]) for f in frames] + [(0.1, 0.1)] * pad,
        "u_studio_radiance": [vec(f[4]) for f in frames] + [(0.0, 0.0, 0.0)] * pad,
        "u_zenith": vec(eo.STUDIO_ZENITH), "u_horizon": vec(eo.STUDIO_HORIZON), "u_floor": vec(eo.STUDIO_FLOOR),
        "u_horizon_width": float(eo.STUDIO_HORIZON_WIDTH), "u_edge_sigma": float(eo.STUDIO_EDGE_SIGMA),
    }


def lookdev_values() -> tuple[dict, float]:
    """The skin stand-in's per-frame uniforms (lights, SH9, studio, exposure) and the SH9 projection's CPU ms."""
    from viewport import eye_optics as eo
    from viewport.light_rig import kelvin_to_rgb

    start = time.perf_counter()
    sh = sh9_project(lambda d: eo.td_env(d, 0.1))
    sh_ms = (time.perf_counter() - start) * 1e3
    values = studio_values()
    values.update({
        "u_light_dir": [direction(az, el) for az, el, *_ in PORTRAIT_LIGHTS],
        "u_light_color": [tuple(c * i for c in kelvin_to_rgb(k)) for _az, _el, k, i, _s in PORTRAIT_LIGHTS],
        "u_light_size": [s for *_, s in PORTRAIT_LIGHTS],
        "u_sh": [tuple(float(c) for c in row) for row in sh],
        "u_env_rot": (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0),
        "u_env_intensity": ENV_INTENSITY, "u_exposure": EXPOSURE,
    })
    values.update(SKIN)
    return values, sh_ms


def format_row(name: str, gpu: list[float], cpu: list[float], floor: float | None) -> str:
    p50, lo, hi = summary(gpu)
    versus = f"{p50 - floor:+9.2f}" if floor is not None else f"{'':>9}"
    return f"      {name:<13} {p50:9.2f} {lo:8.2f} {hi:8.2f} {versus} {statistics.median(cpu):9.2f}"


# -- raw GL programs (no pyglet introspection: samplerBuffer / sampler2DShadow, arrays, exact compile timing) ---------


class Program:
    KINDS = {"vertex": 0x8B31, "geometry": 0x8DD9, "fragment": 0x8B30}

    def __init__(self, sources: list[tuple[str, str]]) -> None:
        from pyglet import gl

        start = time.perf_counter()
        self.id = gl.glCreateProgram()
        shaders = []
        for source, kind in sources:
            shader = gl.glCreateShader(self.KINDS[kind])
            data = source.encode("utf-8")
            pointer = ctypes.cast(ctypes.c_char_p(data), ctypes.POINTER(ctypes.c_char))
            length = ctypes.c_int(len(data))
            gl.glShaderSource(shader, 1, ctypes.byref(pointer), ctypes.byref(length))
            gl.glCompileShader(shader)
            status = gl.GLint()
            gl.glGetShaderiv(shader, gl.GL_COMPILE_STATUS, ctypes.byref(status))
            if not status.value:
                raise RuntimeError(f"{kind} shader: {self._log(shader, gl.glGetShaderiv, gl.glGetShaderInfoLog)}")
            gl.glAttachShader(self.id, shader)
            shaders.append(shader)
        gl.glLinkProgram(self.id)
        status = gl.GLint()
        gl.glGetProgramiv(self.id, gl.GL_LINK_STATUS, ctypes.byref(status))
        for shader in shaders:
            gl.glDetachShader(self.id, shader)
            gl.glDeleteShader(shader)
        if not status.value:
            raise RuntimeError(f"link: {self._log(self.id, gl.glGetProgramiv, gl.glGetProgramInfoLog)}")
        gl.glFinish()
        self.compile_ms = (time.perf_counter() - start) * 1e3
        self._locations: dict[str, int] = {}

    @staticmethod
    def _log(name, getter, reader) -> str:
        from pyglet import gl

        size = gl.GLint()
        getter(name, gl.GL_INFO_LOG_LENGTH, ctypes.byref(size))
        buf = ctypes.create_string_buffer(max(size.value, 1))
        reader(name, size, None, buf)
        return buf.value.decode(errors="replace")

    def use(self) -> None:
        from pyglet import gl

        gl.glUseProgram(self.id)

    def location(self, name: str) -> int:
        from pyglet import gl

        if name not in self._locations:
            self._locations[name] = gl.glGetUniformLocation(self.id, ctypes.create_string_buffer(name.encode()))
        return self._locations[name]

    def set(self, name: str, value) -> None:
        """One uniform (the program in use): int / float, vec2 / vec3, mat3 / mat4 (column-major), or a list of
        vec2 / vec3 / floats for an array. Unknown or optimised-out names are skipped."""
        from pyglet import gl

        loc = self.location(name)
        if loc < 0:
            return
        if isinstance(value, (bool, int)):
            gl.glUniform1i(loc, int(value))
        elif isinstance(value, float):
            gl.glUniform1f(loc, value)
        elif isinstance(value, list) and value and isinstance(value[0], (tuple, list)):
            flat = [float(c) for v in value for c in v]
            setter = gl.glUniform3fv if len(value[0]) == 3 else gl.glUniform2fv
            setter(loc, len(value), (gl.GLfloat * len(flat))(*flat))
        elif isinstance(value, list):
            gl.glUniform1fv(loc, len(value), (gl.GLfloat * len(value))(*[float(v) for v in value]))
        elif len(value) == 2:
            gl.glUniform2f(loc, *map(float, value))
        elif len(value) == 3:
            gl.glUniform3f(loc, *map(float, value))
        elif len(value) == 9:
            gl.glUniformMatrix3fv(loc, 1, gl.GL_FALSE, (gl.GLfloat * 9)(*map(float, value)))
        elif len(value) == 16:
            gl.glUniformMatrix4fv(loc, 1, gl.GL_FALSE, (gl.GLfloat * 16)(*map(float, value)))
        else:
            raise ValueError(f"{name}: {value!r}")

    def delete(self) -> None:
        from pyglet import gl

        gl.glDeleteProgram(self.id)


# -- the scene ---------------------------------------------------------------------------------------------------------


def build_app(size):
    import pyglet

    import main as src_main
    from mirai.application import Application

    window = pyglet.window.Window(width=size[0], height=size[1], visible=False)
    app = Application()
    app.init_scene("file", scene_path=str(SCENE), **src_main.GL_TYPES)
    app.set_viewport_size(*size)
    app.update_viewport(0.0)
    return window, app


def set_surface(app, kind: str) -> bool:
    ok = app.subdivision.set_view("off" if kind == "cage" else "cage")
    app.update_viewport(0.0)
    return ok and (kind == "cage") == (app.viewport.surface_render_mesh is None)


def world_bounds(app) -> tuple[tuple[float, float, float], float]:
    """The edit object's bounding sphere in the world (its drawn placement applied: Gollum_Head_05 is scaled)."""
    import numpy as np

    from mirai.mesh_geometry import mesh_center_and_radius

    edit = app.scene.edit_object
    centre, radius = mesh_center_and_radius(edit.mesh)
    model = app._objects.model_matrix(edit)
    if model is None:
        return tuple(centre), radius
    m = np.asarray(model, float).reshape(4, 4).T
    world = m @ np.array([*centre, 1.0])
    scale = max(float(np.linalg.norm(m[:3, i])) for i in range(3))
    return tuple(float(c) for c in world[:3]), radius * scale


def set_view(app, view: str) -> None:
    centre, radius = world_bounds(app)
    cam = app.camera
    if view == "framed":
        cam.set_view(math.radians(35.0), math.radians(8.0))
        cam.frame_on_bounds(centre, radius)
    else:  # the face: front, the camera on the front third of the head, the face filling the frame
        cam.set_view(0.0, math.radians(4.0))
        cam.frame_on_bounds((centre[0], centre[1] + 0.05 * radius, centre[2] + 0.35 * radius), 0.42 * radius, 1.0)
    app.viewport.on_camera_changed()
    app.update_viewport(0.0)


def triangles(rm) -> int:
    return len(getattr(rm, "_triangle_indices", ()))


def albedo_source(app, obj):
    """The LookDev albedo source of `obj` (proposal §6.1): the paint composite or the texture path, independent of the
    Worklight's texture toggle and the selection tint."""
    paint = app.paint_display
    if paint.shows(obj):
        return paint.texture(obj)
    return obj.texture


def bind_triangle_uvs(store) -> bool:
    """STAND-IN for the proposed `GLRenderStore.bind_triangle_uvs(unit)`: flushes the store's face data (which binds
    the triangle UVs on the store's own unit 3, and the other face buffers on theirs) - False = no triangle UVs."""
    names = [n for n, (_f, _u, uniform) in store._face_buffers.items() if uniform == "u_triangle_uvs"]
    if not names or not store._face_cpu.get(names[0]):
        return False
    store._flush_face_data()
    return True


def bind_albedo(source, unit: int) -> bool:
    """STAND-IN for the albedo binding: a path through the shared `GLRenderStore.texture` cache, a `LiveTexture`
    through the store's private upload (`_upload_live`) - the second small interface AD-038 names."""
    from pyglet import gl

    from viewport import gl_render_store as grs

    if source is None:
        return False
    if isinstance(source, str):
        texture = grs.GLRenderStore.texture(source)
        if texture is None:
            return False
        target, name = texture.target, texture.id
    else:
        if source.gl_name is None or source.pending:
            grs._upload_live(source)
        target, name = gl.GL_TEXTURE_2D, source.gl_name
    gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
    gl.glBindTexture(target, name)
    gl.glActiveTexture(gl.GL_TEXTURE0)
    return True


class Frames:
    """The rows of (a) for one app: the Worklight loop, the stand-in LookDev loop, the depth pass of (d)."""

    def __init__(self, window, app, values: dict, depth: bool) -> None:
        import dataclasses

        from pyglet import gl

        from viewport.gl_render_store import GLRenderStore

        self.window, self.app, self.values = window, app, values
        attributes = GLRenderStore.program().attributes
        self.locations = {"position": attributes["position"]["location"], "normal": attributes["normal"]["location"]}
        self.skin: dict = {}
        self.first_use: dict = {}
        self.background = Program([(FULLSCREEN_VS, "vertex"), (BACKGROUND_FS, "fragment")])
        vao = gl.GLuint()
        gl.glGenVertexArrays(1, ctypes.byref(vao))
        self.vao = vao.value
        self.full_tier = dataclasses.replace(app.viewport.eye_display, tier="full")
        self.depth = None
        if depth:
            self.depth = DepthTarget(self.locations)
        self.depth_report: list[str] = []

    def skin_program(self, albedo_map: bool, env_spec: bool, shadow: bool, **p3) -> Program:
        """A stand-in variant, compiled on first use; `p3` = `skin_sources`'s P3 keywords."""
        key = (albedo_map, env_spec, shadow, tuple(sorted(p3.items())))
        if key not in self.skin:
            program = Program(skin_sources(self.locations, albedo_map, env_spec, shadow, nonce=uuid.uuid4().hex, **p3))
            program.use()
            for name, value in self.values.items():
                program.set(name, value)
            program.set("u_triangle_uvs", UV_UNIT)
            program.set("u_albedo", ALBEDO_UNIT)
            program.set("u_shadow", SHADOW_UNIT)
            program.set("u_shadow_depth", SHADOW_RAW_UNIT)
            program.set("u_env_cube", CUBE_UNIT)
            program.set("u_thickness_scale", THICKNESS_SCALE)
            self.skin[key] = program
            self.first_use[key] = program.compile_ms
        return self.skin[key]

    def drawn(self):
        """[(render mesh, object or None, eye draw or None)] in `Viewport.render()`'s order."""
        vp = self.app.viewport
        scene = self.app.scene
        out = [(vp.surface_render_mesh or vp.render_mesh, scene.edit_object, None)] if vp.show_faces else []
        for key in vp._entry_draw_order():
            oid = key[1] if isinstance(key, tuple) else key
            eye = vp._eye_entries.get(key) if vp.eye_display.preview else None
            if eye is not None and key not in vp.entry_surface_render_meshes:
                out.append((vp.object_entries[key], scene.objects.get(oid), eye))
            else:
                out.append((vp.entry_surface_render_meshes.get(key, vp.object_entries[key]), scene.objects.get(oid),
                            None))
        return out

    def worklight(self, eyes_full: bool) -> None:
        vp = self.app.viewport
        light = vp.light_uniforms()
        display = self.full_tier if eyes_full else vp.eye_display
        for rm, _obj, eye in self.drawn():
            set_light = getattr(rm.store, "set_light_uniforms", None)
            if set_light is not None:
                set_light(light)
            if eye is None or not vp.eye_pass.draw(rm, eye, light, display):
                rm.render(vp.render_mesh.camera)

    def draw_background(self) -> None:
        from pyglet import gl

        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        self.background.use()
        self.background.set("u_bottom", BACKGROUND[0])
        self.background.set("u_top", BACKGROUND[1])
        gl.glBindVertexArray(self.vao)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        gl.glBindVertexArray(0)
        gl.glDepthMask(gl.GL_TRUE)
        gl.glUseProgram(0)

    def lookdev(self, *, background: bool, eyes: bool, albedo_map: bool, env_spec: bool, shadow: bool,
                depth: "DepthTarget | None" = None, render_depth: bool = True, cube=None, **p3) -> None:
        """The stand-in LookDev frame. `depth` (P3): the shadow map to read (default the (d) target); `render_depth`
        False reads it as it is (a still pose: the lookup only); `cube` = (texture, levels) for `cube_env`."""
        from pyglet import gl

        vp = self.app.viewport
        light = vp.light_uniforms()
        target = depth if depth is not None else self.depth
        if shadow and render_depth:
            target.render(self.drawn(), self.values["u_light_dir"][0], self.app)
        if background:
            self.draw_background()
        eye_pos = self.eye_position()
        thickness = bool(p3.get("thickness"))
        cube_env = bool(p3.get("cube_env"))
        if cube_env:
            gl.glEnable(gl.GL_TEXTURE_CUBE_MAP_SEAMLESS)
        for rm, obj, eye in self.drawn():
            if eye is not None:
                if eyes:
                    vp.eye_pass.draw(rm, eye, light, self.full_tier)
                continue
            store = rm.store
            vlist = store.vertex_list() if hasattr(store, "vertex_list") else None
            camera = store.uniform_data("camera_uniforms") if vlist is not None else []
            if vlist is None or len(camera) != 32:
                continue
            uvs = albedo_map and bind_triangle_uvs(store)
            mapped = uvs and obj is not None and bind_albedo(albedo_source(self.app, obj), ALBEDO_UNIT)
            program = self.skin_program(bool(mapped), env_spec, shadow, **p3)
            program.use()
            model = store.uniform_data("model_uniforms")
            program.set("u_view", tuple(camera[0:16]))
            program.set("u_proj", tuple(camera[16:32]))
            program.set("u_model", tuple(model) if len(model) == 16 else IDENTITY4)
            program.set("u_eye", eye_pos)
            colour = getattr(rm.material, "color", None) or (0.72, 0.75, 0.82)
            program.set("u_base_color", tuple(float(c) for c in colour))
            if shadow:
                program.set("u_light_vp", tuple(target.light_vp))
                target.bind(SHADOW_UNIT)
            if thickness:
                program.set("u_light_depth_range", float(target.depth_range))
                target.bind_raw(SHADOW_RAW_UNIT)
            if cube_env:
                program.set("u_env_levels", float(cube[1]))
                gl.glActiveTexture(gl.GL_TEXTURE0 + CUBE_UNIT)
                gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, cube[0])
                gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glEnable(gl.GL_DEPTH_TEST)
            gl.glDepthMask(gl.GL_TRUE)
            gl.glDisable(gl.GL_BLEND)
            gl.glEnable(gl.GL_CULL_FACE)
            gl.glCullFace(gl.GL_BACK)
            offset = bool(getattr(store, "polygon_offset", False))
            if offset:
                gl.glEnable(gl.GL_POLYGON_OFFSET_FILL)
                gl.glPolygonOffset(1.0, 1.0)
            vlist.draw(gl.GL_TRIANGLES)
            if offset:
                gl.glDisable(gl.GL_POLYGON_OFFSET_FILL)
            gl.glDisable(gl.GL_CULL_FACE)
            gl.glDisable(gl.GL_DEPTH_TEST)
            if uvs:
                store._unbind_face_data()
            if thickness:
                DepthTarget.unbind_raw(SHADOW_RAW_UNIT)
            if cube_env:
                gl.glActiveTexture(gl.GL_TEXTURE0 + CUBE_UNIT)
                gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, 0)
            for unit in (ALBEDO_UNIT, SHADOW_UNIT):
                gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
                gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glUseProgram(0)
        if cube_env:
            gl.glDisable(gl.GL_TEXTURE_CUBE_MAP_SEAMLESS)

    def eye_position(self) -> tuple[float, float, float]:
        return tuple(float(c) for c in self.app.camera.eye())

    def draw(self, row: str) -> None:
        if row == "worklight":
            self.worklight(False)
        elif row == "wl eyes full":
            self.worklight(True)
        elif row == "ld skin":
            self.lookdev(background=False, eyes=False, albedo_map=True, env_spec=True, shadow=False)
        elif row == "ld frame":
            self.lookdev(background=True, eyes=True, albedo_map=True, env_spec=True, shadow=False)
        elif row == "ld no env":
            self.lookdev(background=True, eyes=True, albedo_map=True, env_spec=False, shadow=False)
        elif row == "ld no map":
            self.lookdev(background=True, eyes=True, albedo_map=False, env_spec=True, shadow=False)
        elif row == "ld shadow":
            self.lookdev(background=True, eyes=True, albedo_map=True, env_spec=True, shadow=True)
        elif row == "app render":
            self.app.viewport.render()
        else:
            raise ValueError(row)


class DepthTarget:
    """(d): a DEPTH_COMPONENT24 texture with compare mode, its depth-only FBO and the depth program. P3 (`--p3`): any
    `size`, the casters with or without the eyes, and a second sampler object without compare mode for the raw depth
    (the thickness)."""

    def __init__(self, locations: dict, size: int = SHADOW_SIZE) -> None:
        from pyglet import gl

        self.size = int(size)
        texture, fbo = gl.GLuint(), gl.GLuint()
        gl.glGenTextures(1, ctypes.byref(texture))
        gl.glBindTexture(gl.GL_TEXTURE_2D, texture.value)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_DEPTH_COMPONENT24, self.size, self.size, 0,
                        gl.GL_DEPTH_COMPONENT, gl.GL_FLOAT, None)
        for name, value in ((gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR), (gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR),
                            (gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE), (gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE),
                            (gl.GL_TEXTURE_COMPARE_MODE, gl.GL_COMPARE_REF_TO_TEXTURE),
                            (gl.GL_TEXTURE_COMPARE_FUNC, gl.GL_LEQUAL)):
            gl.glTexParameteri(gl.GL_TEXTURE_2D, name, value)
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        gl.glGenFramebuffers(1, ctypes.byref(fbo))
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo.value)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_DEPTH_ATTACHMENT, gl.GL_TEXTURE_2D, texture.value, 0)
        gl.glDrawBuffer(gl.GL_NONE)
        gl.glReadBuffer(gl.GL_NONE)
        self.status = gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        gl.glDrawBuffer(gl.GL_BACK)
        gl.glReadBuffer(gl.GL_BACK)
        self.texture, self.fbo = texture.value, fbo.value
        self.program = Program([(DEPTH_VS.format(**locations), "vertex"), (DEPTH_FS, "fragment")])
        self.light_vp = list(IDENTITY4)
        self.depth_range = 1.0  # world units from the near to the far plane of the last pass
        self._raw_sampler = None

    @property
    def complete(self) -> bool:
        return self.status == 0x8CD5  # GL_FRAMEBUFFER_COMPLETE

    def render(self, drawn, key_direction, app, eyes: bool = True) -> None:
        """The depth pass from the key (`eyes` False: only the non-eye meshes cast)."""
        from pyglet import gl

        centre, radius = world_bounds(app)
        self.light_vp = look_at_ortho(key_direction, centre, 1.15 * radius)
        self.depth_range = (4.0 - 0.01) * 1.15 * radius  # `look_at_ortho`'s far - near
        viewport = (gl.GLint * 4)()
        gl.glGetIntegerv(gl.GL_VIEWPORT, viewport)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.fbo)
        gl.glViewport(0, 0, self.size, self.size)
        gl.glClear(gl.GL_DEPTH_BUFFER_BIT)
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_POLYGON_OFFSET_FILL)
        gl.glPolygonOffset(2.0, 4.0)
        self.program.use()
        self.program.set("u_light_vp", tuple(self.light_vp))
        for rm, _obj, eye in drawn:
            if eye is not None and not eyes:
                continue
            store = rm.store
            vlist = store.vertex_list() if hasattr(store, "vertex_list") else None
            if vlist is None:
                continue
            model = store.uniform_data("model_uniforms")
            self.program.set("u_model", tuple(model) if len(model) == 16 else IDENTITY4)
            vlist.draw(gl.GL_TRIANGLES)
        gl.glUseProgram(0)
        gl.glDisable(gl.GL_POLYGON_OFFSET_FILL)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        gl.glViewport(*viewport)

    def bind(self, unit: int) -> None:
        from pyglet import gl

        gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture)
        gl.glActiveTexture(gl.GL_TEXTURE0)

    def bind_raw(self, unit: int) -> None:
        """The same texture on `unit` through a sampler object without compare mode (GL 3.3 core; the eye pass uses
        sampler objects already): the raw depth for the thickness."""
        from pyglet import gl

        if self._raw_sampler is None:
            ident = gl.GLuint()
            gl.glGenSamplers(1, ctypes.byref(ident))
            for name, value in ((gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST), (gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST),
                                (gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE), (gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE),
                                (gl.GL_TEXTURE_COMPARE_MODE, gl.GL_NONE)):
                gl.glSamplerParameteri(ident.value, name, value)
            self._raw_sampler = ident.value
        gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture)
        gl.glBindSampler(unit, self._raw_sampler)
        gl.glActiveTexture(gl.GL_TEXTURE0)

    @staticmethod
    def unbind_raw(unit: int) -> None:
        from pyglet import gl

        gl.glBindSampler(unit, 0)
        gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        gl.glActiveTexture(gl.GL_TEXTURE0)

    def release(self) -> None:
        from pyglet import gl

        gl.glDeleteTextures(1, ctypes.byref(gl.GLuint(self.texture)))
        gl.glDeleteFramebuffers(1, ctypes.byref(gl.GLuint(self.fbo)))
        if self._raw_sampler is not None:
            gl.glDeleteSamplers(1, ctypes.byref(gl.GLuint(self._raw_sampler)))
        self.program.delete()

    def texels_written(self) -> int:
        import numpy as np
        from pyglet import gl

        buf = (gl.GLfloat * (self.size * self.size))()
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture)
        gl.glGetTexImage(gl.GL_TEXTURE_2D, 0, gl.GL_DEPTH_COMPONENT, gl.GL_FLOAT, buf)
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        return int((np.frombuffer(buf, np.float32) < 1.0).sum())


# -- measurements --------------------------------------------------------------------------------------------------------


def timed_frame(window, size, query, draw) -> tuple[float, float]:
    """One cleared frame of `draw()`: (GPU ms by GL_TIME_ELAPSED, wall ms of the draw + glFinish)."""
    from pyglet import gl

    window.switch_to()
    gl.glViewport(0, 0, *size)
    gl.glClearColor(*CLEAR, 1.0)
    gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
    gl.glFinish()
    start = time.perf_counter()
    gl.glBeginQuery(gl.GL_TIME_ELAPSED, query)
    try:
        draw()
    finally:
        gl.glEndQuery(gl.GL_TIME_ELAPSED)  # also when the draw raised: the next row's query must be able to begin
    gl.glFinish()
    wall = (time.perf_counter() - start) * 1e3
    value = ctypes.c_uint64()
    gl.glGetQueryObjectui64v(query, gl.GL_QUERY_RESULT, ctypes.byref(value))
    return value.value / 1e6, wall


def read_rgb(size):
    import numpy as np
    from pyglet import gl

    buf = (gl.GLubyte * (size[0] * size[1] * 3))()
    gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
    gl.glReadPixels(0, 0, size[0], size[1], gl.GL_RGB, gl.GL_UNSIGNED_BYTE, buf)
    return np.frombuffer(buf, np.uint8).reshape(size[1], size[0], 3)[::-1].copy()


def read_coverage(size) -> float:
    import numpy as np
    from pyglet import gl

    buf = (gl.GLfloat * (size[0] * size[1]))()
    gl.glReadPixels(0, 0, size[0], size[1], gl.GL_DEPTH_COMPONENT, gl.GL_FLOAT, buf)
    return float((np.frombuffer(buf, np.float32) < 1.0).mean())


def write_png(directory: str, name: str, rgb) -> None:
    import numpy as np

    from mirai.iris_import import encode_png

    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    rgba = np.concatenate([rgb, np.full(rgb.shape[:2] + (1,), 255, np.uint8)], axis=2)
    (out / f"{name}.png").write_bytes(encode_png(np.ascontiguousarray(rgba)))


def measure_frames(window, app, frames: Frames, args, size) -> list[str]:
    from pyglet import gl

    query = gl.GLuint()
    gl.glGenQueries(1, ctypes.byref(query))
    rows = [r for r in ROWS if r != "ld shadow" or frames.depth is not None]
    lines = [f"(a) frame rows, {size[0]}x{size[1]}, {args.draws} rounds after {WARMUP_ROUNDS}; GL_TIME_ELAPSED ms; "
             f"'vs wl' = minus `worklight`; CPU = wall ms of the draw + glFinish"]
    verdict = []
    for surface in args.surfaces:
        if not set_surface(app, surface):
            lines.append(f"  [{surface}] not available (SubD refused): skipped")
            continue
        for view in args.views:
            set_view(app, view)
            gpu = {r: [] for r in rows}
            cpu = {r: [] for r in rows}
            images, coverage = {}, 0.0
            for round_ in range(WARMUP_ROUNDS + args.draws):
                for row in rows:
                    ms, wall = timed_frame(window, size, query.value, lambda: frames.draw(row))
                    if round_ >= WARMUP_ROUNDS:
                        gpu[row].append(ms)
                        cpu[row].append(wall)
                    if round_ == WARMUP_ROUNDS + args.draws - 1:
                        if row == "ld frame":
                            coverage = read_coverage(size)
                        if row in ("worklight", "ld frame", "ld shadow"):
                            images[row] = read_rgb(size)
            tris = sum(triangles(rm) for rm, _o, eye in frames.drawn() if eye is None)
            eye_tris = sum(triangles(rm) for rm, _o, eye in frames.drawn() if eye is not None)
            lines.append(f"  [{surface} / {view}] skin triangles {tris}, eye triangles {eye_tris}, the meshes cover "
                         f"{100.0 * coverage:.1f} % of the frame")
            lines.append(f"      {'row':<13} {'GPU p50':>9} {'min':>8} {'max':>8} {'vs wl':>9} {'CPU p50':>9}")
            floor = statistics.median(gpu["worklight"])
            for row in rows:
                lines.append(format_row(row, gpu[row], cpu[row], None if row == "worklight" else floor))
            if "ld shadow" in images:
                diff = images["ld frame"].astype(int).sum(axis=2) - images["ld shadow"].astype(int).sum(axis=2)
                lines.append(f"      (d) the shadow lookup darkens {int((diff > 24).sum())} px (of "
                             f"{size[0] * size[1]})")
            frame_ms = statistics.median(gpu["ld frame"])
            if size == (1024, 768) and view == "framed":
                verdict.append(f"  LD-D10 [{surface} / framed / 1024x768]: `ld frame` {frame_ms:.2f} ms GPU = "
                               f"{100.0 * frame_ms / FRAME_BUDGET_MS:.0f} % of the 33.3 ms frame (30 fps); "
                               f"`worklight` {floor:.2f} ms")
            if args.png:
                for row, rgb in images.items():
                    write_png(args.png, f"{row.replace(' ', '_')}_{surface}_{view}_{size[0]}x{size[1]}", rgb)
    gl.glDeleteQueries(1, ctypes.byref(query))
    if verdict:
        lines.append("")
        lines.extend(verdict)
        lines.append("  (the pass only: the app's overlays, HUD, panels and the CPU side add to the frame; "
                     "the reference PC decides, LD-D10)")
    if frames.depth is not None:
        lines.append(f"  (d) depth FBO {'complete' if frames.depth.complete else f'INCOMPLETE 0x{frames.depth.status:04X}'}"
                     f", {SHADOW_SIZE}^2 DEPTH_COMPONENT24, compare mode; texels written in the last pass "
                     f"{frames.depth.texels_written()} of {SHADOW_SIZE * SHADOW_SIZE}")
    if frames.first_use:
        lines.append("  skin stand-in variants, compile + link on first use (cold, ms): " + ", ".join(
            f"{'map' if k[0] else 'colour'}{'+env' if k[1] else ''}{'+shadow' if k[2] else ''} {v:.1f}"
            for k, v in sorted(frames.first_use.items())))
    return lines


def measure_uv_request(window, app, frames: Frames, size, repeats: int = 5) -> list[str]:
    """(b): the first UV request on the drawn head, its first draw, and taking it back."""
    from pyglet import gl

    lines = ["(b) UV request on the head (Worklight texture hidden, so its UVs are inactive); ms wall"]
    display = app.display
    shown = display.show_texture
    display.show_texture = False
    app._objects.sync_views()
    app.update_viewport(0.0)
    for surface in SURFACES:
        if not set_surface(app, surface):
            lines.append(f"  [{surface}] not available: skipped")
            continue
        vp = app.viewport
        rm = vp.surface_render_mesh or vp.render_mesh
        if rm._uv_active:
            lines.append(f"  [{surface}] UVs already active: nothing to measure")
            continue
        on, first_draw, off = [], [], []
        for _ in range(1 + repeats):
            rm._uv_wanted = lambda rm=rm: rm.mesh.has_face_uvs()  # the stand-in request
            rm.mark_material_dirty()
            t0 = time.perf_counter()
            vp.sync()
            t1 = time.perf_counter()
            active = rm._uv_active
            window.switch_to()
            gl.glViewport(0, 0, *size)
            gl.glFinish()
            t2 = time.perf_counter()
            frames.lookdev(background=False, eyes=False, albedo_map=True, env_spec=True, shadow=False)
            gl.glFinish()
            t3 = time.perf_counter()
            del rm._uv_wanted
            rm.mark_material_dirty()
            t4 = time.perf_counter()
            vp.sync()
            t5 = time.perf_counter()
            on.append((t1 - t0) * 1e3)
            first_draw.append((t3 - t2) * 1e3)
            off.append((t5 - t4) * 1e3)
            if not active:
                lines.append(f"  [{surface}] the request did not activate the UVs: stand-in broken")
                break
        flat = []
        for _ in range(repeats):
            t0 = time.perf_counter()
            rm._triangle_uvs_flat()
            flat.append((time.perf_counter() - t0) * 1e3)
        lines.append(f"  [{surface}] {triangles(rm)} triangles, has UVs {rm.mesh.has_face_uvs()}")
        lines.append(f"      request on  (Viewport.sync): first {on[0]:8.2f}   p50 of {repeats} more "
                     f"{statistics.median(on[1:]):8.2f}")
        lines.append(f"      first draw after (upload):   first {first_draw[0]:8.2f}   p50 "
                     f"{statistics.median(first_draw[1:]):8.2f}")
        lines.append(f"      request off (Viewport.sync): first {off[0]:8.2f}   p50 {statistics.median(off[1:]):8.2f}")
        lines.append(f"      `_triangle_uvs_flat()` alone p50 {statistics.median(flat):8.2f}")
    display.show_texture = shown
    app._objects.sync_views()
    set_surface(app, "cage")
    return lines


def measure_cube() -> list[str]:
    """(c): render-to-RGBA16F cube faces, the chain's GPU time, read-back and textureLod checks."""
    import numpy as np
    from pyglet import gl

    from viewport import eye_optics as eo

    lines = [f"(c) RGBA16F cube {CUBE_SIZE}^2, mips to 2^2, every face and level through an FBO"]
    levels = int(math.log2(CUBE_SIZE))  # 128 .. 2
    texture, fbo, query, vao = gl.GLuint(), gl.GLuint(), gl.GLuint(), gl.GLuint()
    gl.glGenTextures(1, ctypes.byref(texture))
    gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, texture.value)
    for level in range(levels):
        side = CUBE_SIZE >> level
        for face in range(6):
            gl.glTexImage2D(gl.GL_TEXTURE_CUBE_MAP_POSITIVE_X + face, level, gl.GL_RGBA16F, side, side, 0, gl.GL_RGBA,
                            gl.GL_FLOAT, None)
    gl.glTexParameteri(gl.GL_TEXTURE_CUBE_MAP, gl.GL_TEXTURE_BASE_LEVEL, 0)
    gl.glTexParameteri(gl.GL_TEXTURE_CUBE_MAP, gl.GL_TEXTURE_MAX_LEVEL, levels - 1)
    gl.glTexParameteri(gl.GL_TEXTURE_CUBE_MAP, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR_MIPMAP_LINEAR)
    gl.glTexParameteri(gl.GL_TEXTURE_CUBE_MAP, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
    gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, 0)
    gl.glGenFramebuffers(1, ctypes.byref(fbo))
    gl.glGenQueries(1, ctypes.byref(query))
    gl.glGenVertexArrays(1, ctypes.byref(vao))
    program = Program(cube_sources())
    program.use()
    for name, value in studio_values().items():
        program.set(name, value)
    viewport = (gl.GLint * 4)()
    gl.glGetIntegerv(gl.GL_VIEWPORT, viewport)
    statuses = set()

    def chain(samples: int) -> float:
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo.value)
        gl.glBindVertexArray(vao.value)
        program.use()
        gl.glFinish()
        gl.glBeginQuery(gl.GL_TIME_ELAPSED, query.value)
        for level in range(levels):
            side = CUBE_SIZE >> level
            gl.glViewport(0, 0, side, side)
            program.set("u_size", float(side))
            program.set("u_roughness", level / (levels - 1))
            program.set("u_samples", 1 if level == 0 else samples)
            for face in range(6):
                gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0,
                                          gl.GL_TEXTURE_CUBE_MAP_POSITIVE_X + face, texture.value, level)
                statuses.add(gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER))
                program.set("u_face", face)
                gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        gl.glEndQuery(gl.GL_TIME_ELAPSED)
        gl.glFinish()
        value = ctypes.c_uint64()
        gl.glGetQueryObjectui64v(query.value, gl.GL_QUERY_RESULT, ctypes.byref(value))
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        return value.value / 1e6

    times = {}
    for samples in CUBE_SAMPLES:
        chain(samples)  # warm-up (compile, allocation)
        times[samples] = sorted(chain(samples) for _ in range(5))[2]
    error = gl.glGetError()
    complete = statuses == {0x8CD5}
    lines.append(f"  FBO status: {'complete for every face and level' if complete else sorted(hex(s) for s in statuses)}"
                 f"; glGetError 0x{error:04X}; program compile + link {program.compile_ms:.1f} ms")
    for samples, ms in times.items():
        lines.append(f"  chain (6 faces x {levels} levels; level 0 = 1 sample, others {samples} samples): "
                     f"{ms:8.2f} ms GPU (median of 5)")
    # level 0 read back against the NumPy studio (the last chain wrote it with 1 sample, roughness 0)
    side = CUBE_SIZE
    worst = 0.0
    centre_texels = {}
    gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, texture.value)
    for level in (0, 3):
        s = CUBE_SIZE >> level
        for face in range(6):
            buf = (gl.GLfloat * (s * s * 4))()
            gl.glGetTexImage(gl.GL_TEXTURE_CUBE_MAP_POSITIVE_X + face, level, gl.GL_RGBA, gl.GL_FLOAT, buf)
            img = np.frombuffer(buf, np.float32).reshape(s, s, 4)
            centre_texels[(level, face)] = img[s // 2 - 1:s // 2 + 1, s // 2 - 1:s // 2 + 1, :3].mean(axis=(0, 1))
            if level == 0:
                for ty, tx in ((0, 0), (s // 2, s // 3), (s - 1, s - 1), (s // 4, 3 * s // 4)):
                    d = np.array(cube_face_direction(face, (tx + 0.5) / s * 2 - 1, (ty + 0.5) / s * 2 - 1))
                    want = eo.td_env((d / np.linalg.norm(d))[None, :], 0.0)[0]
                    worst = max(worst, float(np.max(np.abs(img[ty, tx, :3] - want) / (np.abs(want) + 1e-2))))
    gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, 0)
    lines.append(f"  level 0 vs eye_optics.td_env at 24 texels: worst relative error {worst:.4f} (RGBA16F: about 1e-3)")
    # textureLod back into a 6x1 RGBA32F target
    sampler = Program([(FULLSCREEN_VS, "vertex"), (CUBE_SAMPLE_FS, "fragment")])
    target, target_fbo = gl.GLuint(), gl.GLuint()
    gl.glGenTextures(1, ctypes.byref(target))
    gl.glBindTexture(gl.GL_TEXTURE_2D, target.value)
    gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA32F, 6, 1, 0, gl.GL_RGBA, gl.GL_FLOAT, None)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
    gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
    gl.glGenFramebuffers(1, ctypes.byref(target_fbo))
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target_fbo.value)
    gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, target.value, 0)
    sample_status = gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER)
    gl.glViewport(0, 0, 6, 1)
    sampler.use()
    sampler.set("u_cube", 1)
    gl.glActiveTexture(gl.GL_TEXTURE1)
    gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, texture.value)
    lod_error = 0.0
    for level in (0, 3):
        sampler.set("u_lod", float(level))
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        buf = (gl.GLfloat * 24)()
        gl.glReadPixels(0, 0, 6, 1, gl.GL_RGBA, gl.GL_FLOAT, buf)
        got = np.frombuffer(buf, np.float32).reshape(6, 4)[:, :3]
        for face in range(6):
            want = centre_texels[(level, face)]
            lod_error = max(lod_error, float(np.max(np.abs(got[face] - want) / (np.abs(want) + 1e-2))))
    gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, 0)
    gl.glActiveTexture(gl.GL_TEXTURE0)
    gl.glBindVertexArray(0)
    gl.glUseProgram(0)
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
    gl.glViewport(*viewport)
    lines.append(f"  textureLod at the 6 face centres, lod 0 and 3, vs the read-back centre texels: worst relative "
                 f"error {lod_error:.4f} (6x1 RGBA32F target {'complete' if sample_status == 0x8CD5 else hex(sample_status)})")
    for name in (target, texture):
        gl.glDeleteTextures(1, ctypes.byref(name))
    for name in (fbo, target_fbo):
        gl.glDeleteFramebuffers(1, ctypes.byref(name))
    gl.glDeleteQueries(1, ctypes.byref(query))
    gl.glDeleteVertexArrays(1, ctypes.byref(vao))
    program.delete()
    sampler.delete()
    return lines


# -- P3-0 (`--p3`, AD-039): the candidates for the P3 fixed settings --------------------------------------------------


def p3_rows() -> list[tuple[str, dict]]:
    """The P3 frame rows: (name, keywords of `Frames.lookdev` on top of `ld frame`). Every row is a whole stand-in
    LookDev frame (background, skin, eyes full), so `vs ld` is the effect's own cost."""
    rows: list[tuple[str, dict]] = [("ld frame", {})]
    for size, grid in P3_SHADOW:
        rows.append((f"shadow {size // 1024}k x{grid * grid}", {"shadow": True, "shadow_size": size, "shadow_grid": grid,
                                                               "render_depth": False}))
    size, grid = P3_SETTING
    tag = f"{size // 1024}k x{grid * grid}"
    rows += [
        (f"drag {tag}", {"shadow": True, "shadow_size": size, "shadow_grid": grid, "render_depth": True}),
        (f"thick {tag}", {"shadow": True, "shadow_size": size, "shadow_grid": grid, "render_depth": False,
                          "thickness": True}),
        ("dual direct", {"dual": 1}),
        ("dual env", {"dual": 2}),
        ("cube env", {"cube_env": True}),
        ("cube dual env", {"cube_env": True, "dual": 2}),
        ("p3 all", {"shadow": True, "shadow_size": size, "shadow_grid": grid, "render_depth": False,
                    "thickness": True, "dual": 1, "cube_env": True}),
    ]
    return rows


def build_env_cube(samples: int = P3_CUBE_SAMPLES, corner_fix: bool = True) -> tuple[int, int, float]:
    """The analytic studio prefiltered on the GPU into a 128² RGBA16F cube, mips to 2² (the (c) chain, level L at
    roughness L / (levels - 1)): (texture, levels, GPU ms). `corner_fix`: a corner texel takes the cube corner's
    direction, so the three texels meeting there hold the same value (the GPU form of the lab's corner equalization)."""
    from pyglet import gl

    levels = int(math.log2(CUBE_SIZE))
    texture, fbo, query, vao = gl.GLuint(), gl.GLuint(), gl.GLuint(), gl.GLuint()
    gl.glGenTextures(1, ctypes.byref(texture))
    gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, texture.value)
    for level in range(levels):
        side = CUBE_SIZE >> level
        for face in range(6):
            gl.glTexImage2D(gl.GL_TEXTURE_CUBE_MAP_POSITIVE_X + face, level, gl.GL_RGBA16F, side, side, 0, gl.GL_RGBA,
                            gl.GL_FLOAT, None)
    gl.glTexParameteri(gl.GL_TEXTURE_CUBE_MAP, gl.GL_TEXTURE_BASE_LEVEL, 0)
    gl.glTexParameteri(gl.GL_TEXTURE_CUBE_MAP, gl.GL_TEXTURE_MAX_LEVEL, levels - 1)
    gl.glTexParameteri(gl.GL_TEXTURE_CUBE_MAP, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR_MIPMAP_LINEAR)
    gl.glTexParameteri(gl.GL_TEXTURE_CUBE_MAP, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
    for wrap in (gl.GL_TEXTURE_WRAP_S, gl.GL_TEXTURE_WRAP_T, gl.GL_TEXTURE_WRAP_R):
        gl.glTexParameteri(gl.GL_TEXTURE_CUBE_MAP, wrap, gl.GL_CLAMP_TO_EDGE)
    gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, 0)
    gl.glGenFramebuffers(1, ctypes.byref(fbo))
    gl.glGenQueries(1, ctypes.byref(query))
    gl.glGenVertexArrays(1, ctypes.byref(vao))
    program = Program(cube_sources())
    program.use()
    for name, value in studio_values().items():
        program.set(name, value)
    program.set("u_corner_fix", 1 if corner_fix else 0)
    viewport = (gl.GLint * 4)()
    gl.glGetIntegerv(gl.GL_VIEWPORT, viewport)
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo.value)
    gl.glBindVertexArray(vao.value)
    gl.glFinish()
    gl.glBeginQuery(gl.GL_TIME_ELAPSED, query.value)
    for level in range(levels):
        side = CUBE_SIZE >> level
        gl.glViewport(0, 0, side, side)
        program.set("u_size", float(side))
        program.set("u_roughness", level / (levels - 1))
        program.set("u_samples", 1 if level == 0 else samples)
        for face in range(6):
            gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0,
                                      gl.GL_TEXTURE_CUBE_MAP_POSITIVE_X + face, texture.value, level)
            program.set("u_face", face)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
    gl.glEndQuery(gl.GL_TIME_ELAPSED)
    gl.glFinish()
    value = ctypes.c_uint64()
    gl.glGetQueryObjectui64v(query.value, gl.GL_QUERY_RESULT, ctypes.byref(value))
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
    gl.glBindVertexArray(0)
    gl.glUseProgram(0)
    gl.glViewport(*viewport)
    gl.glDeleteFramebuffers(1, ctypes.byref(fbo))
    gl.glDeleteQueries(1, ctypes.byref(query))
    gl.glDeleteVertexArrays(1, ctypes.byref(vao))
    program.delete()
    return texture.value, levels, value.value / 1e6


def corner_spread(texture: int, levels: int) -> list[float]:
    """Per level, the largest relative difference among the three texels that meet at a cube corner (0 = equal)."""
    import numpy as np
    from pyglet import gl

    out = []
    gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, texture)
    for level in range(levels):
        side = CUBE_SIZE >> level
        faces = []
        for face in range(6):
            buf = (gl.GLfloat * (side * side * 4))()
            gl.glGetTexImage(gl.GL_TEXTURE_CUBE_MAP_POSITIVE_X + face, level, gl.GL_RGBA, gl.GL_FLOAT, buf)
            faces.append(np.frombuffer(buf, np.float32).reshape(side, side, 4)[..., :3].copy())
        worst = 0.0
        for corner in np.array(np.meshgrid([-1.0, 1.0], [-1.0, 1.0], [-1.0, 1.0])).T.reshape(-1, 3):
            texels = []
            for face in range(6):
                for ty, tx in ((0, 0), (0, side - 1), (side - 1, 0), (side - 1, side - 1)):
                    u, v = (tx + 0.5) / side * 2 - 1, (ty + 0.5) / side * 2 - 1
                    d = np.array(cube_face_direction(face, float(np.sign(u)), float(np.sign(v))))
                    if np.allclose(d, corner):
                        texels.append(faces[face][ty, tx])
            if len(texels) == 3:
                values = np.array(texels)
                worst = max(worst, float(np.max((values.max(0) - values.min(0)) / (np.abs(values).mean(0) + 1e-3))))
        out.append(worst)
    gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, 0)
    return out


def measure_depth_passes(window, app, frames: "Frames", args, size) -> list[str]:
    """The depth pass alone (it runs only on a pose, geometry or key change): GPU ms per map size, casters with and
    without the eyes, cage and SubD 1."""
    from pyglet import gl

    query = gl.GLuint()
    gl.glGenQueries(1, ctypes.byref(query))
    lines = [f"(p3) {vram_free()} at the start", "(p3) depth pass alone (re-rendered only on a pose / geometry / key change; a drag pays it per frame), "
             f"GL_TIME_ELAPSED ms, {args.draws} rounds after {WARMUP_ROUNDS}"]
    lines.append(f"      {'surface':<8} {'map':>6} {'casters':<12} {'GPU p50':>9} {'min':>8} {'max':>8}")
    key = frames.values["u_light_dir"][0]
    for surface in args.surfaces:
        if not set_surface(app, surface):
            lines.append(f"  [{surface}] not available (SubD refused): skipped")
            continue
        drawn = frames.drawn()
        for map_size in P3_DEPTH_SIZES:
            target = DepthTarget(frames.locations, map_size)
            for eyes in (False, True):
                values = []
                for round_ in range(WARMUP_ROUNDS + args.draws):
                    ms, _wall = timed_frame(window, size, query.value, lambda: target.render(drawn, key, app, eyes))
                    if round_ >= WARMUP_ROUNDS:
                        values.append(ms)
                p50, lo, hi = summary(values)
                lines.append(f"      {surface:<8} {map_size:>6} {'skin + eyes' if eyes else 'skin':<12} "
                             f"{p50:9.2f} {lo:8.2f} {hi:8.2f}")
            if not target.complete:
                lines.append(f"      depth FBO {map_size}^2 INCOMPLETE 0x{target.status:04X}")
            target.release()
    gl.glDeleteQueries(1, ctypes.byref(query))
    return lines


def vram_free() -> str:
    """Free video memory as the driver reports it (`GL_NVX_gpu_memory_info`, NVIDIA; diagnostics only), else a note."""
    from pyglet import gl

    try:
        if not gl.gl_info.have_extension("GL_NVX_gpu_memory_info"):
            return "VRAM free: not reported by the driver"
        free, total = gl.GLint(), gl.GLint()
        gl.glGetIntegerv(0x9049, ctypes.byref(free))   # GPU_MEMORY_INFO_CURRENT_AVAILABLE_VIDMEM_NVX (KiB)
        gl.glGetIntegerv(0x9047, ctypes.byref(total))  # GPU_MEMORY_INFO_DEDICATED_VIDMEM_NVX (KiB)
        return f"VRAM free {free.value / 1024:.0f} of {total.value / 1024:.0f} MiB"
    except Exception as exc:  # a diagnostic must never end the run
        return f"VRAM free: query failed ({exc})"


def drain_gl_errors() -> list[int]:
    """Read every pending GL error (raw call, no pyglet errcheck) - after a failed row the next row starts clean."""
    from pyglet import gl

    errors = []
    for _ in range(16):
        code = gl.glGetError()
        if not code:
            break
        errors.append(int(code))
    return errors


def measure_p3(window, app, frames: "Frames", args, size):
    """P3-0 (AD-039): the P3 frame rows (`p3_rows`) per surface and view, against `ld frame`. A generator: every line
    is printed as soon as it exists, so a failure late in the run keeps what came before. A row that raises a GL error
    (e.g. out of memory) is reported with the free VRAM and dropped for the rest of the run; the others continue."""
    from pyglet import gl
    from pyglet.gl.lib import GLException

    window.switch_to()
    yield f"(p3) before the cube: {vram_free()}"
    raw_tex, levels, raw_ms = build_env_cube(corner_fix=False)
    raw_spread = corner_spread(raw_tex, levels)
    gl.glDeleteTextures(1, ctypes.byref(gl.GLuint(raw_tex)))
    cube_tex, levels, cube_ms = build_env_cube(corner_fix=True)
    fixed_spread = corner_spread(cube_tex, levels)
    yield (f"(p3) environment cube {CUBE_SIZE}^2 RGBA16F, mips to 2^2, the analytic studio prefiltered on the "
           f"GPU ({P3_CUBE_SAMPLES} samples): {cube_ms:.2f} ms with the corner fix, {raw_ms:.2f} ms without")
    yield ("      corner spread per level (largest relative difference of the 3 texels at a cube corner), "
           "without / with the fix: " + ", ".join(f"L{i} {a:.3f}/{b:.3f}"
                                                    for i, (a, b) in enumerate(zip(raw_spread, fixed_spread))))
    rows = [(name, options) for name, options in p3_rows() if not args.p3_rows or name in args.p3_rows
            or name == "ld frame"]
    sizes = sorted({options["shadow_size"] for _name, options in rows if options.get("shadow")})
    targets = {s: DepthTarget(frames.locations, s) for s in sizes}  # only the maps the chosen rows read
    yield f"      after the cube and the shadow maps ({', '.join(f'{s}^2' for s in targets) or 'none'}): {vram_free()}"
    yield ""
    failed: dict[str, str] = {}
    query = gl.GLuint()
    gl.glGenQueries(1, ctypes.byref(query))
    yield (f"(p3) frame rows, {size[0]}x{size[1]}, {args.draws} rounds after {WARMUP_ROUNDS}; GL_TIME_ELAPSED ms; "
           "'vs ld' = minus `ld frame` (the effect's own cost); shadow rows read a map rendered once (a still "
           "pose), `drag` renders it every frame; casters: skin only (the eyes receive, AD-039 S2)")
    verdict = []
    key = frames.values["u_light_dir"][0]

    def draw(options: dict) -> None:
        options = dict(options)
        map_size = options.pop("shadow_size", None)
        shadow = options.pop("shadow", False)
        render_depth = options.pop("render_depth", True)
        depth = targets[map_size] if shadow else None
        if shadow and render_depth:
            depth.render(frames.drawn(), key, app, eyes=False)
        frames.lookdev(background=True, eyes=True, albedo_map=True, env_spec=True, shadow=shadow, depth=depth,
                       render_depth=False, cube=(cube_tex, levels), **options)

    for surface in args.surfaces:
        if not set_surface(app, surface):
            yield f"  [{surface}] not available (SubD refused): skipped"
            continue
        for view in args.views:
            set_view(app, view)
            for target in targets.values():
                target.render(frames.drawn(), key, app, eyes=False)
            yield f"  [{surface} / {view}] {vram_free()}"
            gpu = {name: [] for name, _o in rows}
            cpu = {name: [] for name, _o in rows}
            images = {}
            for round_ in range(WARMUP_ROUNDS + args.draws):
                for name, options in rows:
                    if name in failed:
                        continue
                    try:
                        ms, wall = timed_frame(window, size, query.value, lambda: draw(options))
                    except GLException as exc:
                        errors = drain_gl_errors()
                        frames_reset()
                        failed[name] = f"{exc}".strip()
                        yield (f"      {name}: GL error in round {round_} ({failed[name]}; then pending "
                               f"{[hex(e) for e in errors]}); {vram_free()}; the row is dropped")
                        continue
                    if round_ >= WARMUP_ROUNDS:
                        gpu[name].append(ms)
                        cpu[name].append(wall)
                    if round_ == WARMUP_ROUNDS + args.draws - 1 and name in ("ld frame", rows[1][0], "p3 all"):
                        images[name] = read_rgb(size)
            yield f"      {'row':<13} {'GPU p50':>9} {'min':>8} {'max':>8} {'vs ld':>9} {'CPU p50':>9}"
            floor = statistics.median(gpu["ld frame"]) if gpu["ld frame"] else None
            for name, _o in rows:
                if not gpu[name]:
                    yield f"      {name:<13} failed: {failed.get(name, 'no rounds')}"
                    continue
                yield format_row(name, gpu[name], cpu[name], None if name == "ld frame" else floor)
            if "ld frame" in images:
                base = images["ld frame"].astype(int).sum(axis=2)
                for name in (rows[1][0], "p3 all"):
                    if name in images and name != "ld frame":
                        diff = base - images[name].astype(int).sum(axis=2)
                        yield (f"      {name}: {int((diff > 24).sum())} px darker, {int((diff < -24).sum())} px "
                               f"brighter than `ld frame` (of {size[0] * size[1]})")
            if size == (1024, 768) and view == "framed" and gpu.get("p3 all"):
                total = statistics.median(gpu["p3 all"])
                verdict.append(f"  LD-D10 [{surface} / framed / 1024x768]: `p3 all` {total:.2f} ms GPU = "
                               f"{100.0 * total / FRAME_BUDGET_MS:.0f} % of the 33.3 ms frame; `ld frame` "
                               f"{floor:.2f} ms")
            if args.png:
                for name, rgb in images.items():
                    write_png(args.png, f"p3_{name.replace(' ', '_')}_{surface}_{view}_{size[0]}x{size[1]}", rgb)
    gl.glDeleteQueries(1, ctypes.byref(query))
    states = ", ".join(f"{s}^2 {'complete' if t.complete else f'INCOMPLETE 0x{t.status:04X}'}"
                       for s, t in targets.items())
    yield f"  depth FBOs: {states}; the raw-depth sampler object for `thick`"
    if failed:
        yield "  failed rows: " + "; ".join(f"{name} ({why})" for name, why in failed.items())
    for target in targets.values():
        target.release()
    gl.glDeleteTextures(1, ctypes.byref(gl.GLuint(cube_tex)))
    if verdict:
        yield ""
        yield from verdict
        yield ("  (stand-ins: the production effects follow AD-039; the reference PC decides each slice's fixed "
               "setting)")


def frames_reset() -> None:
    """After a draw raised mid-frame: the state a row may have left (program, units 0-7 incl. sampler objects, cube
    seamless filtering, the timer query ended by `timed_frame`)."""
    from pyglet import gl

    drain_gl_errors()
    gl.glUseProgram(0)
    gl.glBindVertexArray(0)
    for unit in range(8):
        gl.glBindSampler(unit, 0)
        gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
        for target in (gl.GL_TEXTURE_2D, gl.GL_TEXTURE_CUBE_MAP, gl.GL_TEXTURE_BUFFER):
            gl.glBindTexture(target, 0)
    gl.glActiveTexture(gl.GL_TEXTURE0)
    for cap in (gl.GL_TEXTURE_CUBE_MAP_SEAMLESS, gl.GL_DEPTH_TEST, gl.GL_CULL_FACE, gl.GL_POLYGON_OFFSET_FILL,
                gl.GL_BLEND):
        gl.glDisable(cap)
    gl.glDepthMask(gl.GL_TRUE)
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
    drain_gl_errors()


def measure_compile(app, locations) -> list[str]:
    """First use: eye shell variants cold (a never-seen comment) and unchanged twice; `EyePass.program()` fresh."""
    from viewport import eye_shaders as es
    from viewport.eye_pass import EyePass

    lines = ["(compile) first use, compile + link wall ms (cold = a comment no driver cache has seen; warm = the same "
             "source again; the LOOKDEV variant will be one more cold compile of this size)"]
    variants = (("plain", False, False, False), ("look", True, False, False), ("look+iris", True, True, False),
                ("look+iris+sclera", True, True, True))
    for name, look, iris, sclera in variants:
        sources = es.shell_sources(locations, "V2", 3, "studio", True, False, look, iris, sclera)
        cold_sources = [(src + (f"\n// probe {uuid.uuid4().hex}\n" if kind == "fragment" else ""), kind)
                        for src, kind in sources]
        cold = Program(cold_sources)
        first = Program(sources)
        again = Program(sources)
        size = len(sources[1][0])
        lines.append(f"  eye V2 L3 studio fit {name:<17} cold {cold.compile_ms:8.1f}   as shipped {first.compile_ms:8.1f}"
                     f"   again {again.compile_ms:8.1f}   fragment {size} chars")
        for program in (cold, first, again):
            program.delete()
    eyes = [o for o in app.scene.objects.values() if o.eye is not None and not app.scene.is_hidden(o.id)]
    if eyes:
        spec = eyes[0].eye
        fresh = EyePass()
        display = app.viewport.eye_display
        import dataclasses

        start = time.perf_counter()
        fresh.program(dataclasses.replace(display, tier="full"), spec.limbus_level, True, spec.look is not None,
                      spec.look is not None and spec.look.iris is not None, False)
        lines.append(f"  EyePass.program() on a fresh pass, the scene eye's full-tier variant: "
                     f"{(time.perf_counter() - start) * 1e3:.1f} ms (pyglet ShaderProgram incl. introspection)")
        fresh.release()
    return lines


def header_lines(app, sh_ms: float) -> list[str]:
    scene = app.scene
    lines = [f"Scene: {SCENE.relative_to(REPO_ROOT).as_posix()}, edit object {scene.edit_object.name!r}"]
    for oid, obj in scene.objects.items():
        if scene.is_hidden(oid):
            continue
        mesh = obj.mesh
        kind = "eye" if obj.eye is not None else ("edit" if oid == scene.edit_object_id else "object")
        extra = ""
        if obj.eye is not None:
            extra = (f", look {'yes' if obj.eye.look is not None else 'no'}, iris "
                     f"{'yes' if obj.eye.look is not None and obj.eye.look.iris is not None else 'no'}, sclera map "
                     f"{'yes' if obj.eye.sclera_texture else 'no'}, level L{obj.eye.limbus_level}")
        else:
            source = albedo_source(app, obj)
            extra = (f", UVs {'yes' if mesh.has_face_uvs() else 'no'}, albedo "
                     f"{'none' if source is None else ('paint composite' if not isinstance(source, str) else 'file')}")
        lines.append(f"  {kind:<6} {obj.name!r}: {len(list(mesh.all_face_ids()))} faces{extra}")
    hidden = [obj.name for oid, obj in scene.objects.items() if scene.is_hidden(oid)]
    if hidden:
        lines.append(f"  hidden in the file (not drawn): {', '.join(repr(n) for n in hidden)}")
    lines.append(f"SH9 projection of the studio on the CPU (4096 directions, NumPy): {sh_ms:.1f} ms")
    return lines


def run_single(args) -> int:
    import pyglet

    from drag_cost._paths import source_state
    from drag_cost.probe_drag_gl import machine_info

    size = tuple(args.size)
    window, app = build_app(size)
    width, height = window.get_framebuffer_size()
    size = (width, height)
    title = "LookDev P3-0 probe (AD-039, 2026-11-22)" if args.p3 else "LookDev LD-0 probe (AD-038 draft, 2026-11-19)"
    print(f"{title}, {width}x{height}")
    for line in machine_info(pyglet.gl.gl_info.get_version_string(), pyglet.gl.gl_info.get_renderer()):
        print(line)
    print(f"Source: {source_state()}")
    values, sh_ms = lookdev_values()
    for line in header_lines(app, sh_ms):
        print(line)
    print()
    if args.p3:
        frames = Frames(window, app, values, depth=False)
        for line in ([] if args.p3_no_depth else measure_depth_passes(window, app, frames, args, size)):
            print(line, flush=True)
        print()
        for line in measure_p3(window, app, frames, args, size):
            print(line, flush=True)
        return _finish(window)
    extras = set() if args.no_extras else set(EXTRAS) - args.skip
    frames = Frames(window, app, values, depth="depth" in extras)
    if "compile" in extras:
        for line in measure_compile(app, frames.locations):
            print(line)
        print()
    for line in measure_frames(window, app, frames, args, size):
        print(line)
    if "uv" in extras:
        print()
        for line in measure_uv_request(window, app, frames, size):
            print(line)
    if "cube" in extras:
        print()
        window.switch_to()
        for line in measure_cube():
            print(line)
    return _finish(window)


def _finish(window) -> int:
    from pyglet import gl

    error = gl.glGetError()
    print()
    print(f"glGetError at the end: 0x{error:04X}")
    window.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.size is not None:
        return run_single(args)
    status = 0
    for index, (w, h) in enumerate(args.sizes):
        command = [sys.executable, str(Path(__file__).resolve()), "--size", str(w), str(h), "--draws", str(args.draws),
                   "--surfaces", ",".join(args.surfaces), "--views", ",".join(args.views)]
        if args.skip:
            command += ["--skip", ",".join(sorted(args.skip))]
        if index > 0 or args.no_extras:
            command.append("--no-extras")
        if args.png:
            command += ["--png", args.png]
        if args.p3:
            command.append("--p3")
            if args.p3_rows:
                command += ["--p3-rows", ",".join(args.p3_rows)]
            if args.p3_no_depth:
                command.append("--p3-no-depth")
        sys.stdout.flush()
        status = max(status, subprocess.call(command))
        print(flush=True)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
