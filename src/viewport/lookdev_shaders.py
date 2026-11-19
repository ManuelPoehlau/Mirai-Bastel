"""GLSL of the LookDev room (AD-038 §5.2): one linear colour pipeline for the skin pass and the eye's LOOKDEV variant.

Three strings, each with its NumPy twin in `lookdev_optics` (GPU parity: `tests/test_gl_lookdev_parity.py`):

- `LD_COMMON_SRC` - included by **both** passes: the `u_ld_*` uniforms (studio, SH9, the three lights, exposure, tone
  curve, the key's area frame), `srgb_decode`, `sh9`, `ld_studio` (the eye's `td_env` with the studio as uniforms),
  `ld_diffuse` (key / fill / rim wrap + SH9), `ld_specular` (GGX from the three lights, each light's size widening the
  lobe) and `lookdev_output` (exposure -> tone curve -> `srgb_encode`). It uses `srgb_encode`, `direct_specular`,
  `erf_approx`, `box_profile` and the constants `PI`, `MIN_DIRECT_ROUGHNESS`, `TD_SIGMA_*` and defines none of them:
  the eye program has them from `eye_shaders.EYE_LIB_SRC`, the skin program from `LD_BRDF_SRC` (C7: a second definition
  would be a GLSL redefinition error).
- `LD_BRDF_SRC` - the skin program only: those constants and functions, cut **character for character** out of
  `EYE_LIB_SRC` (`tests/test_lookdev_shaders.py` asserts each is a substring of it), so both passes share one BRDF and
  one colour encode.
- `SKIN_BODY` - the skin program's fragment body (AD-038 §3.2). Its vertex and geometry stages are the textured
  Worklight program's own (`skin_sources`), so transform, barycentrics and `gl_PrimitiveID` are those of the Worklight:
  the depth contract I-1 by construction.

Colour (AD-038 §5.5): every albedo is an sRGB artist value, decoded here; lights are linear; one `lookdev_output` per
pixel. Directions are world space; `u_ld_env_rot` turns a world direction into the studio's frame (rotation, and the
camera's frame with "Licht folgt Kamera"), the lights arrive already turned (`lookdev_optics.frame_uniforms`).
"""

from __future__ import annotations

from . import eye_shaders as es

#: The `EYE_LIB_SRC` constants and functions the skin program needs (and `LD_COMMON_SRC` uses).
BRDF_CONSTANTS = ("PI", "MIN_DIRECT_ROUGHNESS", "TD_SIGMA_SCALE", "TD_SIGMA_POWER")
BRDF_FUNCTIONS = ("srgb_encode", "ggx_d", "smith_vis", "schlick_scalar", "direct_specular", "env_brdf_approx",
                  "erf_approx", "box_profile")
#: At most this many studio rectangles (uniform arrays; AD-038 §6).
MAX_STUDIO = 4
#: Tone curves (`u_ld_tone`): the M1 default and the diagnostic (AD-038 §15 Q2).
TONE_CURVES = {"reinhard": 0, "clamp": 1}
#: The skin's specular anti-aliasing: alpha² grows by this times the screen-space variance of the normal.
SPEC_AA_K = 0.5
#: Texture units of the skin pass (C1): the store's triangle UVs, the albedo. 0 stays pyglet's, 6 the P3 shadow map's.
UV_UNIT = 3
ALBEDO_UNIT = 4


def constant_src(name: str, library: str = es.EYE_LIB_SRC) -> str:
    """The `const ... <name> = ...;` line of `library` (with its newline)."""
    for line in library.splitlines(keepends=True):
        if line.startswith("const ") and line.split("=")[0].split()[-1] == name:
            return line
    raise KeyError(name)


def function_src(name: str, library: str = es.EYE_LIB_SRC) -> str:
    """The definition of the GLSL function `name` in `library`, from its return type to its closing brace at the start
    of a line (with its newline)."""
    for line_start in _line_starts(library):
        line = library[line_start:library.find("\n", line_start)]
        head = line.split("(")[0].split()
        if len(head) == 2 and head[1] == name and line.rstrip().endswith("{"):
            end = library.index("\n}\n", line_start) + 3
            return library[line_start:end]
    raise KeyError(name)


def _line_starts(text: str):
    start = 0
    while start < len(text):
        yield start
        nxt = text.find("\n", start)
        if nxt < 0:
            return
        start = nxt + 1


LD_BRDF_SRC = ("\n// -- LookDev: the eye's BRDF and colour encode (cut from eye_shaders.EYE_LIB_SRC, AD-038 C7)\n"
               + "".join(constant_src(n) for n in BRDF_CONSTANTS)
               + "".join(function_src(n) for n in BRDF_FUNCTIONS))

LD_COMMON_SRC = f"""
// -- LookDev (AD-038 §5.2): the studio, SH9, the lights and the output, shared by the skin and the eye
const int LD_LIGHTS = 3;
const int LD_MAX_STUDIO = {MAX_STUDIO};
const vec3 LD_LUMA = vec3(0.2126, 0.7152, 0.0722);
uniform vec3 u_ld_light_dir[LD_LIGHTS];
uniform vec3 u_ld_light_color[LD_LIGHTS];
uniform float u_ld_light_size[LD_LIGHTS];
uniform vec3 u_ld_sh[9];
uniform mat3 u_ld_env_rot;
uniform float u_ld_env_intensity;
uniform int u_ld_studio_n;
uniform vec3 u_ld_studio_centre[LD_MAX_STUDIO];
uniform vec3 u_ld_studio_right[LD_MAX_STUDIO];
uniform vec3 u_ld_studio_up[LD_MAX_STUDIO];
uniform vec2 u_ld_studio_half[LD_MAX_STUDIO];
uniform vec3 u_ld_studio_radiance[LD_MAX_STUDIO];
uniform vec3 u_ld_zenith;
uniform vec3 u_ld_horizon;
uniform vec3 u_ld_floor;
uniform float u_ld_horizon_width;
uniform float u_ld_edge_sigma;
uniform float u_ld_exposure;
uniform int u_ld_tone;
uniform vec3 u_ld_key_up;
uniform vec3 u_ld_key_right;

vec3 srgb_decode(vec3 c) {{
    c = clamp(c, 0.0, 1.0);
    return mix(pow((c + 0.055) / 1.055, vec3(2.4)), c / 12.92, vec3(lessThanEqual(c, vec3(0.04045))));
}}
// SH9 irradiance / pi in the studio frame (coefficients convolved with the clamped cosine on the CPU)
vec3 sh9(vec3 n) {{
    return u_ld_sh[0] * 0.282095
         + u_ld_sh[1] * (0.488603 * n.y) + u_ld_sh[2] * (0.488603 * n.z) + u_ld_sh[3] * (0.488603 * n.x)
         + u_ld_sh[4] * (1.092548 * n.x * n.y) + u_ld_sh[5] * (1.092548 * n.y * n.z)
         + u_ld_sh[6] * (0.315392 * (3.0 * n.z * n.z - 1.0))
         + u_ld_sh[7] * (1.092548 * n.x * n.z) + u_ld_sh[8] * (0.546274 * (n.x * n.x - n.y * n.y));
}}
// eye_shaders.td_env with the studio as uniforms (the parametric studio), studio frame
vec3 ld_studio(vec3 d, float roughness) {{
    float lobe = TD_SIGMA_SCALE * pow(roughness * roughness, TD_SIGMA_POWER);
    float sigma = sqrt(u_ld_edge_sigma * u_ld_edge_sigma + lobe * lobe);
    float width = sqrt(u_ld_horizon_width * u_ld_horizon_width + lobe * lobe);
    vec3 sky = u_ld_horizon + (u_ld_zenith - u_ld_horizon) * clamp(d.y, 0.0, 1.0);
    vec3 value = u_ld_floor + (sky - u_ld_floor) * smoothstep(-width, width, d.y);
    for (int i = 0; i < LD_MAX_STUDIO; ++i) {{
        if (i >= u_ld_studio_n) break;
        float dc = dot(d, u_ld_studio_centre[i]);
        float x = atan(dot(d, u_ld_studio_right[i]), dc + 1e-12);
        float y = atan(dot(d, u_ld_studio_up[i]), dc + 1e-12);
        value += box_profile(x, u_ld_studio_half[i].x, sigma) * box_profile(y, u_ld_studio_half[i].y, sigma)
               * smoothstep(0.0, 0.25, dc) * u_ld_studio_radiance[i];
    }}
    return value;
}}
// world normal / reflection -> the studio's diffuse light and its visible reflection
vec3 ld_env_diffuse(vec3 n) {{ return u_ld_env_intensity * sh9(u_ld_env_rot * n); }}
vec3 ld_env_specular(vec3 r, float roughness) {{ return u_ld_env_intensity * ld_studio(u_ld_env_rot * r, roughness); }}
vec3 ld_wrap(float ndl, vec3 w) {{ return max((vec3(ndl) + w) / (vec3(1.0) + w), vec3(0.0)); }}
// the diffuse light at a world normal: key, fill and rim with a per-channel wrap, plus SH9
vec3 ld_diffuse(vec3 n, vec3 wrap) {{
    vec3 light = ld_env_diffuse(n);
    for (int i = 0; i < LD_LIGHTS; ++i) light += u_ld_light_color[i] * ld_wrap(dot(n, u_ld_light_dir[i]), wrap);
    return light;
}}
// the lights' GGX highlights; a light's size widens the lobe (alpha + size)
float ld_lobe(float roughness, float size) {{ return sqrt(min(roughness * roughness + size, 1.0)); }}
vec3 ld_specular(vec3 n, vec3 v, float roughness, float f0) {{
    vec3 c = vec3(0.0);
    for (int i = 0; i < LD_LIGHTS; ++i)
        c += u_ld_light_color[i] * direct_specular(n, v, u_ld_light_dir[i], ld_lobe(roughness, u_ld_light_size[i]), f0);
    return c;
}}
vec3 ld_tone(vec3 c) {{
    if (u_ld_tone == 1) return clamp(c, 0.0, 1.0);
    return c / (1.0 + dot(c, LD_LUMA));
}}
// once per pixel: exposure, the tone curve, the sRGB encode
vec3 lookdev_output(vec3 c) {{ return srgb_encode(ld_tone(max(c, 0.0) * u_ld_exposure)); }}
"""

SKIN_BODY = f"""
in vec3 v_normal;
in vec3 v_world_pos;
in vec3 g_bary;
uniform mat4 u_view;
uniform mat4 u_proj;
uniform vec3 u_base_color;
uniform float u_roughness;
uniform float u_f0;
uniform vec3 u_wrap;
uniform float u_backscatter;
uniform vec3 u_backscatter_color;
#ifdef ALBEDO_MAP
uniform samplerBuffer u_triangle_uvs;
uniform sampler2D u_albedo;
#endif
out vec4 out_color;

const float SPEC_AA_K = {SPEC_AA_K!r};

void main() {{
    vec3 n = normalize(v_normal);
    // derivatives outside any branch (undefined in non-uniform control flow)
    vec3 dndx = dFdx(n);
    vec3 dndy = dFdy(n);
    if (!gl_FrontFacing) n = -n;
    vec3 v;
    if (u_proj[3][3] == 1.0) {{
        v = normalize(transpose(mat3(u_view)) * vec3(0.0, 0.0, 1.0));
    }} else {{
        vec3 camera = -transpose(mat3(u_view)) * u_view[3].xyz;
        v = normalize(camera - v_world_pos);
    }}
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
    vec3 colour = albedo * ld_diffuse(n, u_wrap) + ld_specular(n, v, rough, u_f0);
#ifdef ENV_SPEC
    colour += ld_env_specular(reflect(-v, n), rough) * env_brdf_approx(u_f0, rough, nv);
#endif
    float back = (1.0 - nv) * (1.0 - nv) * (1.0 - nv) * max(-dot(n, u_ld_light_dir[0]), 0.0);
    colour += u_backscatter * back * srgb_decode(u_backscatter_color) * albedo * u_ld_light_color[0];
    out_color = vec4(lookdev_output(colour), 1.0);
}}
"""


def skin_sources(locations: dict[str, int], albedo_map: bool, env_spec: bool) -> list[tuple[str, str]]:
    """The skin program (AD-038 §3.2): the textured Worklight program's vertex and geometry sources formatted with the
    Worklight program's attribute locations, the LookDev fragment source. Variants: `ALBEDO_MAP`, `ENV_SPEC`."""
    from .gl_render_store import TEXTURED_GEOMETRY_SRC, TEXTURED_VERTEX_SRC

    defines = "".join(f"#define {name} 1\n" for name, on in (("ALBEDO_MAP", albedo_map), ("ENV_SPEC", env_spec)) if on)
    fragment = "#version 330 core\n" + defines + LD_BRDF_SRC + LD_COMMON_SRC + SKIN_BODY
    return [(TEXTURED_VERTEX_SRC.format(**locations), "vertex"), (TEXTURED_GEOMETRY_SRC, "geometry"),
            (fragment, "fragment")]


FULLSCREEN_VERTEX_SRC = """#version 330 core
out vec2 v_uv;
void main() {
    vec2 p = vec2(float((gl_VertexID << 1) & 2), float(gl_VertexID & 2));
    v_uv = p;
    gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}
"""

#: The background (AD-038 §8): solid (bottom = top) or a vertical gradient, written as picked - not exposed, not
#: tone-mapped, not encoded.
BACKGROUND_FRAGMENT_SRC = """#version 330 core
in vec2 v_uv;
uniform vec3 u_bottom;
uniform vec3 u_top;
out vec4 out_color;
void main() { out_color = vec4(mix(u_bottom, u_top, clamp(v_uv.y, 0.0, 1.0)), 1.0); }
"""


def background_sources() -> list[tuple[str, str]]:
    return [(FULLSCREEN_VERTEX_SRC, "vertex"), (BACKGROUND_FRAGMENT_SRC, "fragment")]
