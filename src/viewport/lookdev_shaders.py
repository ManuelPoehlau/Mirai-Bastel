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
- P3 (AD-039 §2.3): one define per effect. Library text an effect needs is its own string, appended only when the effect
  is on (`LD_SHADOW_SRC`); body text is an `#ifdef` block that `skin_sources` resolves with `eye_shaders._without`
  when the effect is off, so with every effect off the sources are M1's, character for character
  (`PINNED_SKIN_SOURCES_SHA256`, `tests/test_lookdev_shaders.py`). `LD_COMMON_SRC` does not change in P3 (the eye's
  LOOKDEV pin).
- `LD_SHADOW_SRC` (S1, AD-039 §4 / §16.6): the key's shadow map and `ld_key_visibility(p, n, l)` (3 x 3
  bilinear-compare fetches one texel apart with a receiver-plane bias and a normal offset sideways to the key; outside the map = lit; the
  key's softness is the map's effective resolution, `u_ld_shadow_scale`); the `SHADOW` block subtracts the key's own
  diffuse and specular term times (1 - visibility). Twins: `lookdev_optics.pcf_visibility` / `ld_key_shadowed`.
  S2 (AD-039 §5): the eye's `LD_SHADOW` variant appends the same string (`eye_shaders.shell_sources`).
  `SHADOW_DEPTH_SRC`: the depth pass's program (`viewport.lookdev_shadow.KeyShadow`).
- `LD_DUAL_LOBE_SRC` (S3, AD-039 §6 / §18): `ld_direct_dual` and `ld_specular_dual`, the skin's two-lobe twins of
  `direct_specular` / `ld_specular` (roughness x 0.75 and x 1.3, mixed 0.85 / 0.15, each lobe widened by the light's
  size); the `DUAL_LOBE` blocks call them for the three lights, the `SHADOW` block's key term included. The analytic
  studio's reflection keeps one lobe (P3-0 run 2: a second analytic lobe costs +0.9 to +4 ms); with S5's cube
  (`CUBE_ENV`) the reflection takes both lobes (two lookups, P3-0 run 5). Twins:
  `lookdev_optics.ld_direct_dual` / `ld_specular_dual`.
- `LD_THICKNESS_SRC` (S4, AD-039 §7 / §19): the key's map read a second time as raw depth (`u_ld_shadow_depth` on unit 7,
  a sampler object without compare mode) at the fragment's own map point; `ld_key_thickness` is the distance the
  key light travels inside the mesh to the fragment, `ld_key_transmission` its `exp(-thickness / scale)` (0 outside the
  map, and 0 below `THICKNESS_EDGE`: no tissue in front means the key came through an opening, §19.6). The `THICKNESS` block replaces M1's view-rim backscatter proxy with it. Needs `LD_SHADOW_SRC` (the effect needs
  the shadow). Twins: `lookdev_optics.bilinear_depth` / `key_transmission` / `ld_backscatter`.
- S7 (AD-039 §10 / §20): the material's image maps, one define each - `ROUGHNESS_MAP` (a linear grey value multiplying
  the roughness before the specular AA), `NORMAL_MAP` (a tangent-space map in the frame of the screen derivatives of
  position and UV: no tangent buffer; `LD_NORMAL_MAP_SRC`, twins `lookdev_optics.normal_map_tangent` /
  `cotangent_frame` / `ld_normal_mapped`), `TRANSLUCENCY_MAP` (a grey value multiplying the backscatter: S4's
  transmission, or M1's proxy without S4). `LD_MAP_UV` is set with any of them: the body's block that reads the
  fragment's UV from the triangle UVs in uniform control flow (`map_on` 0 on a triangle without UVs: no map applies).
  With a normal map the key map's lookups (shadow, thickness) keep the geometric normal (`n_geo`). Units 9-11
  (`MAP_UNITS`).
- `LD_CUBE_SRC` (S5, AD-039 §8 / §21): the studio's reflection from a prefiltered cube (`u_ld_env_cube` on unit 8,
  `ld_env_cube`: `textureLod` at the effective roughness, level L at roughness L / (levels - 1)) instead of
  evaluating `ld_studio` per pixel; the `CUBE_ENV` block inside `ENV_SPEC` calls it, with `DUAL_LOBE` twice (the two
  lobes' roughness, mixed as the lights'). The cube's content **is** the analytic studio: `CUBE_PREFILTER_SRC` renders
  `ld_studio(d, 0)` into level 0 and a GGX importance-sampled prefilter of it (64 samples, the corner fix) into the
  rougher levels (`viewport.lookdev_cube.EnvCube`). Twins: `lookdev_optics.cube_texel_directions` /
  `prefilter_ggx` / `cube_lod`. The eye keeps the analytic studio (AD-039 §8).
- `LD_AREA_SRC` (S8 „Weiches Licht“, AD-039 §23): the lights' diffuse term as a finite (sphere) emitter -
  `ld_area_wrap`, the C1 horizon spline over the band |n.l + wrap| < sin sigma with sin sigma = size x
  `AREA_SIN_MAX`, then / (1 + wrap) (size 0 = `ld_wrap`; outside the band nothing changes), and `ld_diffuse_area`, the
  twin of `ld_diffuse` with it. The `AREA_DIFFUSE` blocks call it for the three lights and in the `SHADOW` block's key
  term, where the band joins the wrap's excess under the lifted lookup (§16.7, rule „lifted“ of the assessment §6.2).
  Twins: `lookdev_optics.ld_area_wrap` / `ld_diffuse_area` / `ld_key_shadowed(..., area=True)`. The eye keeps
  `ld_diffuse` (`LD_COMMON_SRC` unchanged).
- `LD_SOFT_SHADOW_SRC` (S9 „Weicher Schatten“, AD-039 §24): the key's penumbra from the receiver-to-blocker distance
  (PCSS, the assessment's „K16c“): `ld_key_shadow_soft` - a blocker search of 16 raw-depth fetches (S4's sampler on unit
  7; `LD_SOFT_SHADOW_DEPTH_SRC` declares it when `THICKNESS` is off), then 16 bilinear-compare fetches each for the
  key's and the lifted lookup with the radius (z - blocker) x tan sigma; the map at full resolution
  (`KeyShadow.update(..., key_size=0)`). The `SOFT_SHADOW` block replaces the `SHADOW` block's two lookups. Twin:
  `lookdev_optics.soft_shadow_visibility`.

Colour (AD-038 §5.5): every albedo is an sRGB artist value, decoded here; lights are linear; one `lookdev_output` per
pixel. Directions are world space; `u_ld_env_rot` turns a world direction into the studio's frame (rotation, and the
camera's frame with "Licht folgt Kamera"), the lights arrive already turned (`lookdev_optics.frame_uniforms`).
"""

from __future__ import annotations

import math

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
#: Texture units of the skin pass (C1): the store's triangle UVs, the albedo. 0 stays pyglet's (AD-039 §2.4).
UV_UNIT = 3
ALBEDO_UNIT = 4
#: AD-039 §2.4: the key's shadow map (compare sampler), S1.
SHADOW_UNIT = 6
#: AD-039 §2.4: the same map's raw depth through a sampler object without compare mode, S4.
SHADOW_RAW_UNIT = 7
#: AD-039 §2.4 / §10: the material's roughness, normal and translucency maps, S7.
MAP_UNITS = {"roughness": 9, "normal": 10, "translucency": 11}
#: AD-039 §2.4 / §8: the studio's prefiltered environment cube, S5.
CUBE_UNIT = 8
#: AD-039 §2.4 / §9: the triangles' material slots (an R32F buffer texture), S6.
REGION_UNIT = 12
#: AD-039 §9: the material slots of a `REGIONS` program - the object's own (0) and at most four regions
#: (`core.scene.LOOK_REGIONS_MAX`).
REGION_SLOTS = 5
#: S5 (AD-039 §8, `PROVISIONAL` fixed setting; LD-3's knobs later): a 128² RGBA16F cube with mips down to 2² (7 levels),
#: level L prefiltered at perceptual roughness L / (CUBE_LEVELS - 1) with CUBE_SAMPLES GGX importance samples.
CUBE_SIZE = 128
CUBE_LEVELS = 7
CUBE_SAMPLES = 64
#: The P3 defines in their fixed order (the skin program key, AD-039 §2.3 point 4).
SKIN_EFFECTS = ("SHADOW", "DUAL_LOBE", "THICKNESS")
#: S7's defines, one per map (AD-039 §10), in the key's order after `SKIN_EFFECTS`.
SKIN_MAPS = ("ROUGHNESS_MAP", "NORMAL_MAP", "TRANSLUCENCY_MAP")
#: S7: a map's 8-bit value 128 is its zero (a flat normal map is (128, 128, 255): no tilt), so the decode is
#: value x 255 / 128 - 1 (`PROVISIONAL`; twin `lookdev_optics.normal_map_tangent`).
NORMAL_MAP_ZERO = 128.0 / 255.0
#: The compare's depth bias in the map's [0, 1] depth (`PROVISIONAL`, AD-039 §4; twin `lookdev_optics.pcf_visibility`).
SHADOW_DEPTH_BIAS = 0.0005
#: The receiver-plane slope's limit (depth per UV, both in the map's units: 10 = 84° from the key).
SHADOW_SLOPE_MAX = 10.0
#: The wrap's excess looks the map up this many normal offsets further out along the normal (`PROVISIONAL`, AD-039
#: §16.7): past a convex surface's own shadow at the terminator, still inside a crease's cast shadow.
SHADOW_WRAP_LIFT = 4.0
#: S3 (AD-039 §6, Q-P3-7 fixed): the two lobes' perceptual roughness as factors of the material's, and the first lobe's
#: share (`PROVISIONAL`, the common real-time skin default; twin `lookdev_optics.ld_specular_dual`).
DUAL_LOBE_SCALES = (0.75, 1.3)
DUAL_LOBE_MIX = 0.85
#: S4 (AD-039 §7 / §19.2): the key light's path inside the mesh over which the transmission falls to 1/e, in world
#: units (`PROVISIONAL`; the AD's "0.6 cm" assumed 1 unit = 1 cm, which `Gollum_Head_05` does not follow). 0.05 until
#: 2026-11-24; 0.02 since §19.8: at 0.05 the 0.02-0.1 chords through the face's front (nose / cheek) washed the shadow
#: side red, at 0.02 they are dark and the ears with the key behind still glow.
THICKNESS_SCALE = 0.02
#: The thickness below which no light comes through, in world units (`PROVISIONAL`, AD-039 §19.6, 2026-11-24): a surface
#: facing away from the key with no tissue in front of it is not lit through but reached through an opening (an eye
#: socket behind a non-casting eyeball, the mouth, the neck's rim) or past a clipped caster; the transmission rises
#: from 0 at no thickness to full at this one.
THICKNESS_EDGE = 0.1 * THICKNESS_SCALE
#: The opening rule only holds on a facet that faces away from the key (AD-039 §19.8): a facet turned toward it (its
#: geometric normal, n_face . l >= 0) is rightly its own nearest surface - on a faceted cage with smooth normals the
#: terminator's facets are. The rule fades out between n_face . l = -this and 0.
THICKNESS_FACE = 0.1
#: S8 (AD-039 §23): a light's size as its angular radius sigma, sin sigma = size x this (sigma 40° at size 1, a large
#: softbox close to the face; `PROVISIONAL`, Manu's practical test decides 40° or 30°). Highlight (`ld_lobe`) and shadow
#: (`lookdev_optics.shadow_resolution`) keep their own mappings of the size.
AREA_SIN_MAX = math.sin(math.radians(40.0))
#: Below this sin sigma the band is not widened further (the spline's 1 / 4s): a point light is `ld_wrap` within 2.5e-5.
AREA_SIN_MIN = 1e-4
#: S9 „Weicher Schatten“ (AD-039 §24; the PCSS assessment's „K16c“, all `PROVISIONAL`, tuned on Gollum_Head_05 and the
#: shapes against 32 hard keys over the emitter): the key's penumbra grows with the receiver-to-blocker distance and
#: sigma (the S8 mapping, sin sigma = size x `AREA_SIN_MAX`). The map's UV and depth both span its 2R, so a depth
#: difference is a UV length: penumbra radius = (z - mean blocker depth) x tan sigma.
SOFT_SHADOW_TAPS = 16             # blocker-search fetches (raw depth) and PCF fetches (bilinear compare) per lookup
SOFT_SHADOW_SEARCH = 0.15         # the search reaches blockers up to this far above the receiver (map depth, x tan sigma)
SOFT_SHADOW_SEARCH_MIN = 2.0      # the search radius's floor in texels (production's 3 x 3 PCF reaches 2 texels)
SOFT_SHADOW_PCF_MIN = 1.0         # the PCF radius's floor in texels (a hard key = the 3 x 3 PCF's footprint)
SOFT_SHADOW_MAX = 48.0            # the search / PCF radius's cap in texels of the full map
SOFT_SHADOW_CONE = 2.0            # beyond the near zone a fetch is a blocker max(this, cot sigma) x |o| above the
#                                   receiver: the light's own cone (a blocker at |o| hides part of the disc only when it
#                                   lies higher than |o| cot sigma), at least this steep (a large key)
SOFT_SHADOW_LEVEL = 0.5           # beyond the near zone the PCF compares against half the mean blocker height
SOFT_SHADOW_NEAR = 1.5            # texels: the receiver plane decides within it, the cone / level from 2.5 x it
SOFT_SHADOW_FADE = 4.0            # the PCF counts in full from this many blockers found (the early out's edge); a
#                                   blocker found within the near zone counts in full at once (a contact blocker under
#                                   a large key: only the innermost fetches can see it)
SOFT_SHADOW_BAND_LIFT = 0.23      # the lifted lookup's extra lift: x R x s³ (R the map's radius, s = sin sigma)


def soft_shadow_taps(count: int, centre: bool) -> tuple[tuple[float, float], ...]:
    """The fetch offsets in the unit disc: a Vogel spiral (golden angle; fixed, noise-free), radius sqrt((i + 0.5) / n)
    (even in area: the PCF) or (i + 0.5) / n (denser near the centre: the blocker search, so a thin contact blocker - a
    lip crease, a nostril's rim - is not missed)."""
    golden = math.pi * (3.0 - math.sqrt(5.0))
    out = []
    for i in range(count):
        r = (i + 0.5) / count if centre else math.sqrt((i + 0.5) / count)
        out.append((r * math.cos(i * golden), r * math.sin(i * golden)))
    return tuple(out)


SOFT_SHADOW_SEARCH_TAPS = soft_shadow_taps(SOFT_SHADOW_TAPS, True)
SOFT_SHADOW_PCF_TAPS = soft_shadow_taps(SOFT_SHADOW_TAPS, False)


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
#ifdef REGIONS
// AD-039 §9: the material of each slot (0 = the object's, 1-4 its regions) and the triangles' slots; the body reads the
// triangle's values through globals named like the uniforms of the variant without regions
const int LD_SLOTS = {REGION_SLOTS};
uniform samplerBuffer u_triangle_material;
uniform vec3 u_slot_base_color[LD_SLOTS];
uniform float u_slot_albedo[LD_SLOTS];  // 1 = the albedo map (where the triangle has UVs), 0 = the colour
uniform float u_slot_roughness[LD_SLOTS];
uniform float u_slot_fresnel[LD_SLOTS];  // F0 (not `u_slot_f0`: pyglet cuts an array name's last digit)
uniform vec3 u_slot_wrap[LD_SLOTS];
uniform float u_slot_backscatter[LD_SLOTS];
uniform vec3 u_slot_backscatter_color[LD_SLOTS];
vec3 u_base_color;
float u_roughness;
float u_f0;
vec3 u_wrap;
float u_backscatter;
vec3 u_backscatter_color;
float ld_slot_albedo;
#else
uniform vec3 u_base_color;
uniform float u_roughness;
uniform float u_f0;
uniform vec3 u_wrap;
uniform float u_backscatter;
uniform vec3 u_backscatter_color;
#endif
#ifdef ALBEDO_MAP
uniform samplerBuffer u_triangle_uvs;
uniform sampler2D u_albedo;
#endif
#ifdef LD_MAP_UV
#ifndef ALBEDO_MAP
uniform samplerBuffer u_triangle_uvs;
#endif
#endif
#ifdef ROUGHNESS_MAP
uniform sampler2D u_roughness_map;
#endif
#ifdef NORMAL_MAP
uniform sampler2D u_normal_map;
uniform float u_normal_strength;
uniform float u_normal_green;  // 1 OpenGL (green up), -1 DirectX (green down)
#endif
#ifdef TRANSLUCENCY_MAP
uniform sampler2D u_translucency_map;
#endif
out vec4 out_color;

const float SPEC_AA_K = {SPEC_AA_K!r};

void main() {{
#ifdef REGIONS
    {{
        // AD-039 §9: the triangle's slot; a value outside the slots (a stale or free slot) draws the object's material
        int slot = int(texelFetch(u_triangle_material, gl_PrimitiveID).r + 0.5);
        slot = slot < 0 || slot >= LD_SLOTS ? 0 : slot;
        u_base_color = u_slot_base_color[slot];
        u_roughness = u_slot_roughness[slot];
        u_f0 = u_slot_fresnel[slot];
        u_wrap = u_slot_wrap[slot];
        u_backscatter = u_slot_backscatter[slot];
        u_backscatter_color = u_slot_backscatter_color[slot];
        ld_slot_albedo = u_slot_albedo[slot];
    }}
#endif
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
#ifdef LD_MAP_UV
    // AD-039 §10: the fragment's UV for the material's maps, in uniform control flow (the normal map's frame takes its
    // derivatives, a map's mip level its own); map_on 0 on a triangle without UVs - no map applies there
    int map_t = gl_PrimitiveID * 3;
    vec2 map_a = texelFetch(u_triangle_uvs, map_t).xy;
    float map_on = float(map_a.x > -1.0e29);
    vec2 map_uv = map_on > 0.5 ? map_a * g_bary.x + texelFetch(u_triangle_uvs, map_t + 1).xy * g_bary.y
                                 + texelFetch(u_triangle_uvs, map_t + 2).xy * g_bary.z : vec2(0.0);
#endif
#ifdef NORMAL_MAP
    // AD-039 §10: the normal map tilts the shading normal; the key map's lookups keep the geometric one
    vec3 n_geo = n;
    {{
        vec3 mapped = ld_normal_mapped(n, v_world_pos, map_uv, texture(u_normal_map, map_uv).rgb, u_normal_strength,
                                       u_normal_green);
        n = map_on > 0.5 ? mapped : n;
    }}
#endif
    float nv = max(dot(n, v), 1e-4);
#ifdef ROUGHNESS_MAP
    // AD-039 §10: the roughness map (a linear grey value) multiplies the material's roughness, before the specular AA
    float alpha = u_roughness * mix(1.0, texture(u_roughness_map, map_uv).r, map_on);
    alpha *= alpha;
#else
    float alpha = u_roughness * u_roughness;
#endif
    alpha = sqrt(clamp(alpha * alpha + SPEC_AA_K * (dot(dndx, dndx) + dot(dndy, dndy)), 1e-6, 1.0));
    float rough = sqrt(alpha);
    vec3 albedo = u_base_color;
#ifdef ALBEDO_MAP
    {{
        int t = gl_PrimitiveID * 3;
        vec2 a = texelFetch(u_triangle_uvs, t).xy;
#ifdef REGIONS
        if (a.x > -1.0e29 && ld_slot_albedo > 0.5) {{
#else
        if (a.x > -1.0e29) {{
#endif
            vec2 uv = a * g_bary.x + texelFetch(u_triangle_uvs, t + 1).xy * g_bary.y
                    + texelFetch(u_triangle_uvs, t + 2).xy * g_bary.z;
            albedo = texture(u_albedo, uv).rgb;
        }}
    }}
#endif
    albedo = srgb_decode(albedo);
#ifdef DUAL_LOBE
    // AD-039 §6: the lights' highlight as two lobes, a sharp one and a broad tail
#ifdef AREA_DIFFUSE
    // AD-039 §23: the lights' diffuse term as finite emitters (each light's size softens its terminator)
    vec3 colour = albedo * ld_diffuse_area(n, u_wrap) + ld_specular_dual(n, v, rough, u_f0);
#else
    vec3 colour = albedo * ld_diffuse(n, u_wrap) + ld_specular_dual(n, v, rough, u_f0);
#endif
#else
#ifdef AREA_DIFFUSE
    vec3 colour = albedo * ld_diffuse_area(n, u_wrap) + ld_specular(n, v, rough, u_f0);
#else
    vec3 colour = albedo * ld_diffuse(n, u_wrap) + ld_specular(n, v, rough, u_f0);
#endif
#endif
#ifdef SHADOW
    // AD-039 §4 / §16.7: the key's own terms (ld_diffuse / ld_specular's i = 0) times (1 - visibility): the key in
    // shadow. Its Lambert part and its highlight take the map's answer at the surface; the wrap's excess past Lambert
    // (light the organic presets carry past the terminator) takes it at the point lifted out along the normal, so a
    // convex surface's own facets do not cut the wrap while a cast shadow in a crease keeps it dark
    {{
        float ndl = dot(n, u_ld_light_dir[0]);
#ifdef NORMAL_MAP
#ifdef SOFT_SHADOW
        // AD-039 §24: both lookups with the penumbra of the key's disc (one blocker search, two PCFs)
        vec2 vis_soft = ld_key_shadow_soft(v_world_pos, n_geo, u_ld_light_dir[0]);
        float vis = vis_soft.x;
        float vis_wrap = vis_soft.y;
#else
        float vis = ld_key_visibility(v_world_pos, n_geo, u_ld_light_dir[0]);
        float vis_wrap = ld_key_visibility_lifted(v_world_pos, n_geo, u_ld_light_dir[0]);
#endif
#else
#ifdef SOFT_SHADOW
        // AD-039 §24: both lookups with the penumbra of the key's disc (one blocker search, two PCFs)
        vec2 vis_soft = ld_key_shadow_soft(v_world_pos, n, u_ld_light_dir[0]);
        float vis = vis_soft.x;
        float vis_wrap = vis_soft.y;
#else
        float vis = ld_key_visibility(v_world_pos, n, u_ld_light_dir[0]);
        float vis_wrap = ld_key_visibility_lifted(v_world_pos, n, u_ld_light_dir[0]);
#endif
#endif
        vec3 lambert = vec3(max(ndl, 0.0));
#ifdef DUAL_LOBE
        colour -= u_ld_light_color[0]
#ifdef AREA_DIFFUSE
                // AD-039 §23: the key's area band joins the wrap's excess under the lifted lookup (rule „lifted“)
                * (albedo * ((1.0 - vis) * lambert
                             + (1.0 - vis_wrap) * (ld_area_wrap(ndl, u_wrap, u_ld_light_size[0]) - lambert))
#else
                * (albedo * ((1.0 - vis) * lambert + (1.0 - vis_wrap) * (ld_wrap(ndl, u_wrap) - lambert))
#endif
                   + (1.0 - vis) * ld_direct_dual(n, v, u_ld_light_dir[0], rough, u_ld_light_size[0], u_f0));
#else
        colour -= u_ld_light_color[0]
#ifdef AREA_DIFFUSE
                // AD-039 §23: the key's area band joins the wrap's excess under the lifted lookup (rule „lifted“)
                * (albedo * ((1.0 - vis) * lambert
                             + (1.0 - vis_wrap) * (ld_area_wrap(ndl, u_wrap, u_ld_light_size[0]) - lambert))
#else
                * (albedo * ((1.0 - vis) * lambert + (1.0 - vis_wrap) * (ld_wrap(ndl, u_wrap) - lambert))
#endif
                   + (1.0 - vis) * direct_specular(n, v, u_ld_light_dir[0], ld_lobe(rough, u_ld_light_size[0]), u_f0));
#endif
    }}
#endif
#ifdef ENV_SPEC
#ifdef CUBE_ENV
    // AD-039 §8: the studio's reflection from its prefiltered cube; with the dual lobe as two lookups (§11.1 run 5)
    {{
        vec3 r_env = reflect(-v, n);
#ifdef DUAL_LOBE
        vec3 env = mix(ld_env_cube(r_env, rough * LD_DUAL_SCALES.y), ld_env_cube(r_env, rough * LD_DUAL_SCALES.x),
                       LD_DUAL_MIX);
#else
        vec3 env = ld_env_cube(r_env, rough);
#endif
        colour += env * env_brdf_approx(u_f0, rough, nv);
    }}
#else
    colour += ld_env_specular(reflect(-v, n), rough) * env_brdf_approx(u_f0, rough, nv);
#endif
#endif
#ifdef THICKNESS
    // AD-039 §7: the key's light through thin parts (ears, nostril wings) - how far it travelled inside the mesh, from
    // the key's depth map - in place of M1's view-rim proxy
    // the facet's own normal (screen derivatives of the world position; uniform control flow), toward the camera
    vec3 n_face = cross(dFdx(v_world_pos), dFdy(v_world_pos));
    float n_face_len = length(n_face);
    n_face = n_face_len > 0.0 ? n_face / n_face_len : n;
    if (dot(n_face, v) < 0.0) n_face = -n_face;
    float back = ld_key_transmission(v_world_pos, dot(n_face, u_ld_light_dir[0]))
               * max(-dot(n, u_ld_light_dir[0]), 0.0);
#else
    float back = (1.0 - nv) * (1.0 - nv) * (1.0 - nv) * max(-dot(n, u_ld_light_dir[0]), 0.0);
#endif
#ifdef TRANSLUCENCY_MAP
    // AD-039 §10: the translucency map (a linear grey value) scales the light through thin parts
    back *= mix(1.0, texture(u_translucency_map, map_uv).r, map_on);
#endif
    colour += u_backscatter * back * srgb_decode(u_backscatter_color) * albedo * u_ld_light_color[0];
    out_color = vec4(lookdev_output(colour), 1.0);
}}
"""


LD_AREA_SRC = f"""
// -- LookDev P3 S8 (AD-039 §23): the lights' diffuse term as finite emitters - a sphere light of angular radius sigma,
// sin sigma = size x LD_AREA_SIN_MAX
const float LD_AREA_SIN_MAX = {AREA_SIN_MAX!r};  // sin 40° (PROVISIONAL)
const float LD_AREA_SIN_MIN = {AREA_SIN_MIN!r};
// light i's diffuse factor: the sphere light's irradiance as the C1 horizon spline ((x + s)² / 4s between x = -s and
// +s, x above), the cosine shifted by the wrap and renormalized as ld_wrap; size 0 = ld_wrap, the lit side unchanged
vec3 ld_area_wrap(float ndl, vec3 w, float size) {{
    float s = max(size * LD_AREA_SIN_MAX, LD_AREA_SIN_MIN);
    vec3 x = vec3(ndl) + w;
    vec3 t = max(x + s, 0.0);
    return mix(t * t / (4.0 * s), x, step(vec3(s), x)) / (vec3(1.0) + w);
}}
// ld_diffuse with ld_area_wrap: key, fill and rim, each with its own size, plus SH9
vec3 ld_diffuse_area(vec3 n, vec3 wrap) {{
    vec3 light = ld_env_diffuse(n);
    for (int i = 0; i < LD_LIGHTS; ++i)
        light += u_ld_light_color[i] * ld_area_wrap(dot(n, u_ld_light_dir[i]), wrap, u_ld_light_size[i]);
    return light;
}}
"""

LD_SHADOW_SRC = f"""
// -- LookDev P3 S1 (AD-039 §4, §16.6): the key's shadow map, 3 x 3 bilinear-compare fetches one texel apart
uniform sampler2DShadow u_ld_shadow;
uniform mat4 u_ld_shadow_vp;
uniform float u_ld_shadow_radius;  // the fetch spacing: one texel of the map's storage, in its UV
uniform float u_ld_shadow_scale;   // the rendered part of the map (effective / storage size: the key's softness)
uniform float u_ld_shadow_offset;  // the normal offset, world units
const float LD_SHADOW_BIAS = {SHADOW_DEPTH_BIAS!r};
const float LD_SHADOW_SLOPE_MAX = {SHADOW_SLOPE_MAX!r};
const float LD_SHADOW_WRAP_LIFT = {SHADOW_WRAP_LIFT!r};
// the map point (u, v, depth in [0, 1]) of world point p, offset along its normal n projected off the key direction
// l: sideways in the map (against acne at grazing light), never toward the light (a surface facing the key right
// behind an occluder's edge - inside a nostril - would leak)
vec3 ld_shadow_coord(vec3 p, vec3 n, vec3 l) {{
    vec4 lp = u_ld_shadow_vp * vec4(p + (n - l * dot(n, l)) * u_ld_shadow_offset, 1.0);
    return lp.xyz / lp.w * 0.5 + 0.5;
}}
// the map point of p lifted `lift` normal offsets out along n (the wrap's lookup, see the SHADOW block)
vec3 ld_shadow_coord_lifted(vec3 p, vec3 n, vec3 l, float lift) {{
    vec4 lp = u_ld_shadow_vp * vec4(p + ((n - l * dot(n, l)) + n * lift) * u_ld_shadow_offset, 1.0);
    return lp.xyz / lp.w * 0.5 + 0.5;
}}
// 3 x 3 fetches around the map point sp; each compares the depth of the receiver's plane at the fetch (slope = d depth
// / d uv: the receiver-plane bias, so a fetch off the centre does not dip under a curved surface); outside = lit
float ld_shadow_pcf(vec3 sp, vec2 slope) {{
    float step_uv = u_ld_shadow_radius / u_ld_shadow_scale;
    float sum = 0.0;
    for (int y = -1; y <= 1; ++y)
        for (int x = -1; x <= 1; ++x) {{
            vec2 o = vec2(float(x), float(y)) * step_uv;
            sum += texture(u_ld_shadow, vec3((sp.xy + o) * u_ld_shadow_scale,
                                             sp.z - LD_SHADOW_BIAS + dot(slope, o)));
        }}
    float inside = float(all(greaterThanEqual(sp, vec3(0.0))) && all(lessThanEqual(sp, vec3(1.0))));
    return mix(1.0, sum / 9.0, inside);
}}
// the receiver's slope (d depth / d uv) from the screen derivatives of its map point (call in uniform control flow)
vec2 ld_shadow_slope(vec3 sp) {{
    vec3 dx = dFdx(sp);
    vec3 dy = dFdy(sp);
    float det = dx.x * dy.y - dx.y * dy.x;
    vec2 slope = abs(det) > 1e-14 ? vec2(dy.y * dx.z - dx.y * dy.z, dx.x * dy.z - dy.x * dx.z) / det : vec2(0.0);
    return clamp(slope, -LD_SHADOW_SLOPE_MAX, LD_SHADOW_SLOPE_MAX);
}}
// the key's visibility at world point p with normal n, the key toward l: 1 lit, 0 in its shadow
float ld_key_visibility(vec3 p, vec3 n, vec3 l) {{
    vec3 sp = ld_shadow_coord(p, n, l);
    return ld_shadow_pcf(sp, ld_shadow_slope(sp));
}}
// the same at p lifted out along n: a convex surface's own shadow just past the terminator is left behind, a crease's
// cast shadow (the far wall of a nostril, a mouth corner) is not
float ld_key_visibility_lifted(vec3 p, vec3 n, vec3 l) {{
    vec3 sp = ld_shadow_coord_lifted(p, n, l, LD_SHADOW_WRAP_LIFT);
    return ld_shadow_pcf(sp, ld_shadow_slope(sp));
}}
"""

LD_DUAL_LOBE_SRC = f"""
// -- LookDev P3 S3 (AD-039 §6): dual-lobe specular on skin - roughness x {DUAL_LOBE_SCALES[0]!r} and x {DUAL_LOBE_SCALES[1]!r}, mixed
// {DUAL_LOBE_MIX!r} / {1.0 - DUAL_LOBE_MIX:.2f}; each lobe is widened by the light's size as ld_lobe
const vec2 LD_DUAL_SCALES = vec2({DUAL_LOBE_SCALES[0]!r}, {DUAL_LOBE_SCALES[1]!r});
const float LD_DUAL_MIX = {DUAL_LOBE_MIX!r};
float ld_direct_dual(vec3 n, vec3 v, vec3 l, float roughness, float size, float f0) {{
    return mix(direct_specular(n, v, l, ld_lobe(roughness * LD_DUAL_SCALES.y, size), f0),
               direct_specular(n, v, l, ld_lobe(roughness * LD_DUAL_SCALES.x, size), f0), LD_DUAL_MIX);
}}
vec3 ld_specular_dual(vec3 n, vec3 v, float roughness, float f0) {{
    vec3 c = vec3(0.0);
    for (int i = 0; i < LD_LIGHTS; ++i)
        c += u_ld_light_color[i] * ld_direct_dual(n, v, u_ld_light_dir[i], roughness, u_ld_light_size[i], f0);
    return c;
}}
"""

LD_THICKNESS_SRC = f"""
// -- LookDev P3 S4 (AD-039 §7): the key's map as raw depth (a sampler object without compare) - the thickness
uniform sampler2D u_ld_shadow_depth;
uniform float u_ld_shadow_range;  // world units per unit of the map's depth
const float LD_THICKNESS_SCALE = {THICKNESS_SCALE!r};
const float LD_THICKNESS_EDGE = {THICKNESS_EDGE!r};
const float LD_THICKNESS_FACE = {THICKNESS_FACE!r};
// the distance (world units) the key light travels inside the mesh before it reaches p: p's depth from the key past
// the nearest surface in the map, at p's own map point (no normal offset: it would shift the lookup across the
// surface's slope and read a thickness where there is none). x: through the bilinear depth of the 4 texels around
// the point; y: past the farthest of the 4 (the least tissue any of them holds, AD-039 §19.7); negative outside the map
vec2 ld_key_thickness(vec3 p) {{
    vec4 lp = u_ld_shadow_vp * vec4(p, 1.0);
    vec3 sp = lp.xyz / lp.w * 0.5 + 0.5;
    ivec2 last = textureSize(u_ld_shadow_depth, 0) - 1;
    vec2 xy = sp.xy * u_ld_shadow_scale * vec2(last + 1) - 0.5;
    ivec2 i = ivec2(floor(xy));
    vec2 f = xy - floor(xy);
    float d00 = texelFetch(u_ld_shadow_depth, clamp(i, ivec2(0), last), 0).r;
    float d10 = texelFetch(u_ld_shadow_depth, clamp(i + ivec2(1, 0), ivec2(0), last), 0).r;
    float d01 = texelFetch(u_ld_shadow_depth, clamp(i + ivec2(0, 1), ivec2(0), last), 0).r;
    float d11 = texelFetch(u_ld_shadow_depth, clamp(i + ivec2(1, 1), ivec2(0), last), 0).r;
    float stored = mix(mix(d00, d10, f.x), mix(d01, d11, f.x), f.y);
    float farthest = max(max(d00, d10), max(d01, d11));
    float inside = float(all(greaterThanEqual(sp, vec3(0.0))) && all(lessThanEqual(sp, vec3(1.0))));
    return mix(vec2(-1.0), vec2(max(sp.z - stored, 0.0), max(sp.z - farthest, 0.0)) * u_ld_shadow_range, inside);
}}
// the share of the key's light that comes through: exp(-thickness / scale); outside the map none, and none where no
// tissue lies in front of p (p itself is the nearest surface: the key reaches it through an opening, AD-039 §19.6) -
// decided on the 4 texels, so the edge of an opening does not blend the surface's own depth into a thin glowing line
// (§19.7), and only on a facet facing away from the key (`face_l` = its geometric normal . l, §19.8): a facet turned
// toward the key is rightly its own nearest surface
float ld_key_transmission(vec3 p, float face_l) {{
    vec2 t = ld_key_thickness(p);
    float tissue = max(smoothstep(0.0, LD_THICKNESS_EDGE, t.y), smoothstep(-LD_THICKNESS_FACE, 0.0, face_l));
    return t.x < 0.0 ? 0.0 : exp(-t.x / LD_THICKNESS_SCALE) * tissue;
}}
"""

def _vec2_array(taps) -> str:
    return ",\n    ".join(f"vec2({x!r}, {y!r})" for x, y in taps)


#: S9 (AD-039 §24): the raw depth's sampler (S4's unit 7) when „Durchleuchtung“ is off; with it on,
#: `LD_THICKNESS_SRC` declares the same uniform and this string is not appended (no `#ifdef` in a library string).
LD_SOFT_SHADOW_DEPTH_SRC = """
uniform sampler2D u_ld_shadow_depth;  // the key's map as raw depth (unit 7, a sampler object without compare)
"""

LD_SOFT_SHADOW_SRC = f"""
// -- LookDev P3 S9 „Weicher Schatten“ (AD-039 §24): the key's penumbra from the receiver-to-blocker distance and the
// key's angular radius sigma (sin sigma = size x LD_SOFT_SIN_MAX, the S8 mapping). One blocker search in the raw depth,
// then a PCF of radius (z - mean blocker depth) x tan sigma at the surface (vis) and at the lifted point (vis_wrap).
// Near the map point (LD_SOFT_NEAR texels) both compare against the receiver plane as ld_shadow_pcf does; farther out
// against a cone (search) and half the blockers' height (PCF) instead: a per-triangle plane extrapolated over tens of
// texels at a grazing key would shadow the receiver's own surface in facets (the PCSS assessment §3).
const int LD_SOFT_TAPS = {SOFT_SHADOW_TAPS};
const vec2 LD_SOFT_SEARCH_TAPS[LD_SOFT_TAPS] = vec2[](
    {_vec2_array(SOFT_SHADOW_SEARCH_TAPS)});
const vec2 LD_SOFT_PCF_TAPS[LD_SOFT_TAPS] = vec2[](
    {_vec2_array(SOFT_SHADOW_PCF_TAPS)});
const float LD_SOFT_SIN_MAX = {AREA_SIN_MAX!r};
const float LD_SOFT_SEARCH = {SOFT_SHADOW_SEARCH!r};
const float LD_SOFT_SEARCH_MIN = {SOFT_SHADOW_SEARCH_MIN!r};
const float LD_SOFT_PCF_MIN = {SOFT_SHADOW_PCF_MIN!r};
const float LD_SOFT_MAX = {SOFT_SHADOW_MAX!r};
const float LD_SOFT_CONE = {SOFT_SHADOW_CONE!r};
const float LD_SOFT_LEVEL = {SOFT_SHADOW_LEVEL!r};
const float LD_SOFT_NEAR = {SOFT_SHADOW_NEAR!r};
const float LD_SOFT_FADE = {SOFT_SHADOW_FADE!r};
const float LD_SOFT_BAND_LIFT = {SOFT_SHADOW_BAND_LIFT!r};
float ld_soft_tan_sigma() {{
    float s = u_ld_light_size[0] * LD_SOFT_SIN_MAX;
    return s / sqrt(max(1.0 - s * s, 1e-6));
}}
// 0 within LD_SOFT_NEAR texels of the map point (the receiver plane decides), 1 from 2.5 x that (cone / level)
float ld_soft_far(vec2 o) {{
    return smoothstep(LD_SOFT_NEAR, 2.5 * LD_SOFT_NEAR, length(o) * u_ld_shadow_scale / u_ld_shadow_radius);
}}
// x: the summed depth of the blockers around sp within radius r (map UV), y: how many, z: how many of them in the
// near zone (weighted by 1 - ld_soft_far)
vec3 ld_soft_blockers(vec3 sp, vec2 slope, float r, float cone) {{
    vec3 acc = vec3(0.0);
    for (int k = 0; k < LD_SOFT_TAPS; ++k) {{
        vec2 o = LD_SOFT_SEARCH_TAPS[k] * r;
        float d = textureLod(u_ld_shadow_depth, (sp.xy + o) * u_ld_shadow_scale, 0.0).r;
        float far = ld_soft_far(o);
        float b = step(d, sp.z - 2.0 * LD_SHADOW_BIAS + mix(dot(slope, o), -length(o) * cone, far));
        acc += vec3(d * b, b, b * (1.0 - far));
    }}
    return acc;
}}
// LD_SOFT_TAPS bilinear-compare fetches in a disc of radius r around sp; near the centre against the receiver plane,
// farther out against the level `level` above the receiver; outside the map = lit
float ld_soft_pcf(vec3 sp, vec2 slope, float r, float level) {{
    float sum = 0.0;
    for (int k = 0; k < LD_SOFT_TAPS; ++k) {{
        vec2 o = LD_SOFT_PCF_TAPS[k] * r;
        float ref = sp.z - LD_SHADOW_BIAS + mix(dot(slope, o), -level, ld_soft_far(o));
        sum += textureLod(u_ld_shadow, vec3((sp.xy + o) * u_ld_shadow_scale, ref), 0.0);
    }}
    float inside = float(all(greaterThanEqual(sp, vec3(0.0))) && all(lessThanEqual(sp, vec3(1.0))));
    return mix(1.0, sum / float(LD_SOFT_TAPS), inside);
}}
// (vis, vis_wrap) at the map point sp and the lifted map point spl with their receiver-plane slopes: one blocker
// search at sp (no blocker = lit, the early out), then the PCF at both with the penumbra of the mean blocker depth; the
// PCF counts in full from LD_SOFT_FADE blockers found, or from one in the near zone. Call after the derivatives (it
// branches).
vec2 ld_soft_visibility(vec3 sp, vec3 spl, vec2 slope, vec2 slope_l) {{
    float texel = u_ld_shadow_radius / u_ld_shadow_scale;
    float tan_sigma = ld_soft_tan_sigma();
    float rs = clamp(LD_SOFT_SEARCH * tan_sigma, LD_SOFT_SEARCH_MIN * texel, LD_SOFT_MAX * u_ld_shadow_radius);
    vec3 found = ld_soft_blockers(sp, slope, rs, max(LD_SOFT_CONE, 1.0 / max(tan_sigma, 1e-3)));
    if (found.y < 0.5) return vec2(1.0);
    float depth = max(sp.z - found.x / found.y, 0.0);
    float r = clamp(depth * tan_sigma, LD_SOFT_PCF_MIN * texel, LD_SOFT_MAX * u_ld_shadow_radius);
    float level = LD_SOFT_LEVEL * depth;
    float w = min(found.y / LD_SOFT_FADE + found.z, 1.0);
    return vec2(1.0) - w * (vec2(1.0) - vec2(ld_soft_pcf(sp, slope, r, level), ld_soft_pcf(spl, slope_l, r, level)));
}}
// (vis, vis_wrap): ld_key_visibility / ld_key_visibility_lifted with the key's penumbra. The lifted point rises by
// LD_SHADOW_WRAP_LIFT offsets plus LD_SOFT_BAND_LIFT x R x s³ (the height a point in the band n.l in (-s, 0) needs to
// leave a convex surface's own shadow; R the map's radius as the scene's scale). The derivatives first (uniform control
// flow), then ld_soft_visibility.
vec2 ld_key_shadow_soft(vec3 p, vec3 n, vec3 l) {{
    vec3 sp = ld_shadow_coord(p, n, l);
    float s = u_ld_light_size[0] * LD_SOFT_SIN_MAX;
    float radius = 1.0 / length(vec3(u_ld_shadow_vp[0][0], u_ld_shadow_vp[1][0], u_ld_shadow_vp[2][0]));
    vec3 spl = ld_shadow_coord_lifted(p, n, l, LD_SHADOW_WRAP_LIFT
                                      + LD_SOFT_BAND_LIFT * radius * s * s * s / max(u_ld_shadow_offset, 1e-9));
    vec2 slope = ld_shadow_slope(sp);
    vec2 slope_l = ld_shadow_slope(spl);
    return ld_soft_visibility(sp, spl, slope, slope_l);
}}
"""

LD_NORMAL_MAP_SRC = f"""
// -- LookDev P3 S7 (AD-039 §10): a tangent-space normal map without a tangent buffer - the frame from the screen
// derivatives of world position and UV (per triangle: a 2 x 2 quad never spans two triangles), orthogonal to the
// interpolated normal
const float LD_NORMAL_ZERO = {NORMAL_MAP_ZERO!r};
// the map's texel -> the tangent-space normal (128 = 0), its tilt times strength, green flipped for a DirectX map
vec3 ld_normal_tangent(vec3 texel, float strength, float green) {{
    vec3 t = texel / LD_NORMAL_ZERO - 1.0;
    return vec3(t.x * strength, t.y * strength * green, max(t.z, 0.0));
}}
// the cotangent frame of normal n from the screen derivatives of position (dp1, dp2) and UV (duv1, duv2): tangent and
// bitangent scaled together (their ratio is the UV's stretch), n itself; a degenerate UV gives a zero frame
mat3 ld_cotangent_frame(vec3 n, vec3 dp1, vec3 dp2, vec2 duv1, vec2 duv2) {{
    vec3 dp2perp = cross(dp2, n);
    vec3 dp1perp = cross(n, dp1);
    vec3 t = dp2perp * duv1.x + dp1perp * duv2.x;
    vec3 b = dp2perp * duv1.y + dp1perp * duv2.y;
    float m = max(dot(t, t), dot(b, b));
    float s = m > 1e-30 ? inversesqrt(m) : 0.0;
    return mat3(t * s, b * s, n);
}}
// the shading normal at world point p with UV uv: n tilted by the map's texel (call in uniform control flow)
vec3 ld_normal_mapped(vec3 n, vec3 p, vec2 uv, vec3 texel, float strength, float green) {{
    mat3 frame = ld_cotangent_frame(n, dFdx(p), dFdy(p), dFdx(uv), dFdy(uv));
    vec3 m = frame * ld_normal_tangent(texel, strength, green);
    return dot(m, m) > 1e-12 ? normalize(m) : n;
}}
"""

LD_CUBE_SRC = f"""
// -- LookDev P3 S5 (AD-039 §8): the studio's reflection from its prefiltered cube (studio frame), level L at
// roughness L / {CUBE_LEVELS - 1}
uniform samplerCube u_ld_env_cube;
const float LD_CUBE_MAX_LOD = {float(CUBE_LEVELS - 1)!r};
// world reflection r -> the studio's reflected light as a lobe of `roughness` sees it (ld_env_specular's twin)
vec3 ld_env_cube(vec3 r, float roughness) {{
    return u_ld_env_intensity * textureLod(u_ld_env_cube, u_ld_env_rot * r,
                                           clamp(roughness, 0.0, 1.0) * LD_CUBE_MAX_LOD).rgb;
}}
"""

#: S5 (AD-039 §8): the cube's prefilter, one face of one level per draw (a full-screen triangle into the face through an
#: FBO). Level 0 (`u_samples` 1) is `ld_studio(d, 0)`; a rougher level is the GGX importance-sampled mean of it around
#: the texel's direction (N = V = R, weighted by N.L), `u_samples` Hammersley points. Corner fix (AD-039 C7): a corner
#: texel takes the cube corner's direction, so the three texels meeting there are equal by construction.
CUBE_PREFILTER_SRC = """
uniform int u_face;
uniform float u_size;
uniform float u_roughness;
uniform int u_samples;
out vec4 out_color;
// the GL cube-map direction of `face` (+X, -X, +Y, -Y, +Z, -Z) at (s, t) in [-1, 1] (GL 3.3 table 3.19)
vec3 ld_cube_direction(int face, vec2 st) {
    if (face == 0) return vec3(1.0, -st.y, -st.x);
    if (face == 1) return vec3(-1.0, -st.y, st.x);
    if (face == 2) return vec3(st.x, 1.0, st.y);
    if (face == 3) return vec3(st.x, -1.0, -st.y);
    if (face == 4) return vec3(st.x, -st.y, 1.0);
    return vec3(-st.x, -st.y, -1.0);
}
float ld_radical_inverse(uint bits) {
    bits = (bits << 16u) | (bits >> 16u);
    bits = ((bits & 0x55555555u) << 1u) | ((bits & 0xAAAAAAAAu) >> 1u);
    bits = ((bits & 0x33333333u) << 2u) | ((bits & 0xCCCCCCCCu) >> 2u);
    bits = ((bits & 0x0F0F0F0Fu) << 4u) | ((bits & 0xF0F0F0F0u) >> 4u);
    bits = ((bits & 0x00FF00FFu) << 8u) | ((bits & 0xFF00FF00u) >> 8u);
    return float(bits) * 2.3283064365386963e-10;
}
void main() {
    vec2 st = gl_FragCoord.xy / u_size * 2.0 - 1.0;
    vec2 texel = floor(gl_FragCoord.xy);
    vec2 last = vec2(u_size - 1.0);
    if ((texel.x == 0.0 || texel.x == last.x) && (texel.y == 0.0 || texel.y == last.y)) st = sign(st);
    vec3 n = normalize(ld_cube_direction(u_face, st));
    if (u_samples <= 1) {
        out_color = vec4(ld_studio(n, 0.0), 1.0);
        return;
    }
    vec3 up = abs(n.y) < 0.999 ? vec3(0.0, 1.0, 0.0) : vec3(1.0, 0.0, 0.0);
    vec3 tx = normalize(cross(up, n));
    vec3 ty = cross(n, tx);
    float a = max(u_roughness * u_roughness, 1e-3);
    vec3 sum = vec3(0.0);
    float weight = 0.0;
    for (int i = 0; i < u_samples; ++i) {
        vec2 xi = vec2(float(i) / float(u_samples), ld_radical_inverse(uint(i)));
        float phi = 2.0 * PI * xi.x;
        float cos_t = sqrt((1.0 - xi.y) / (1.0 + (a * a - 1.0) * xi.y));
        float sin_t = sqrt(1.0 - cos_t * cos_t);
        vec3 h = tx * (cos(phi) * sin_t) + ty * (sin(phi) * sin_t) + n * cos_t;
        vec3 l = reflect(-n, h);
        float ndl = dot(n, l);
        if (ndl > 0.0) {
            sum += ld_studio(l, 0.0) * ndl;
            weight += ndl;
        }
    }
    out_color = vec4(sum / max(weight, 1e-6), 1.0);
}
"""


def cube_prefilter_sources() -> list[tuple[str, str]]:
    """S5's prefilter program: the full-screen triangle, the studio library (`LD_BRDF_SRC` + `LD_COMMON_SRC`: the
    content is `ld_studio` itself, so skin and eye reflect one studio) and `CUBE_PREFILTER_SRC`."""
    return [(FULLSCREEN_VERTEX_SRC, "vertex"),
            ("#version 330 core\n" + LD_BRDF_SRC + LD_COMMON_SRC + CUBE_PREFILTER_SRC, "fragment")]


#: The depth pass from the key (`KeyShadow`): its own minimal program - the position at the store's location, the
#: object's model matrix and the key's view-projection; an empty fragment stage (depth only).
SHADOW_DEPTH_VERTEX_SRC = """#version 330 core
layout(location = {position}) in vec3 position;
uniform mat4 u_model;
uniform mat4 u_ld_shadow_vp;
void main() {{ gl_Position = u_ld_shadow_vp * u_model * vec4(position, 1.0); }}
"""
SHADOW_DEPTH_FRAGMENT_SRC = """#version 330 core
void main() {}
"""


def shadow_depth_sources(locations: dict[str, int]) -> list[tuple[str, str]]:
    return [(SHADOW_DEPTH_VERTEX_SRC.format(**locations), "vertex"), (SHADOW_DEPTH_FRAGMENT_SRC, "fragment")]


def skin_sources(locations: dict[str, int], albedo_map: bool, env_spec: bool, shadow: bool = False,
                 dual_lobe: bool = False, thickness: bool = False, roughness_map: bool = False,
                 normal_map: bool = False, translucency_map: bool = False,
                 cube_env: bool = False, regions: bool = False,
                 area_diffuse: bool = False, soft_shadow: bool = False) -> list[tuple[str, str]]:
    """The skin program (AD-038 §3.2): the textured Worklight program's vertex and geometry sources formatted with the
    Worklight program's attribute locations, the LookDev fragment source. Variants: `ALBEDO_MAP`, `ENV_SPEC`; P3
    (AD-039 §2.3): `SHADOW` (S1), `DUAL_LOBE` (S3), `THICKNESS` (S4, needs `shadow`); S7 (§10): `ROUGHNESS_MAP`,
    `NORMAL_MAP`, `TRANSLUCENCY_MAP` (with `LD_MAP_UV` for any of them); S5 (§8): `CUBE_ENV` (needs `env_spec`); S6 (§9):
    `REGIONS` (the material per triangle from its slot); S8 (§23): `AREA_DIFFUSE` (the lights' diffuse term as finite
    emitters); S9 (§24): `SOFT_SHADOW` (the key's penumbra from the blocker distance; needs `shadow`). An effect that is
    off leaves no text behind
    (its library string is not appended, its body blocks are resolved away), so every effect off = M1's sources."""
    from .eye_shaders import _without
    from .gl_render_store import TEXTURED_GEOMETRY_SRC, TEXTURED_VERTEX_SRC

    if thickness and not shadow:
        raise ValueError("THICKNESS reads the key's map: it needs SHADOW (AD-039 §2.1)")
    if soft_shadow and not shadow:
        raise ValueError("SOFT_SHADOW softens the key's map lookups: it needs SHADOW (AD-039 §24)")
    if cube_env and not env_spec:
        raise ValueError("CUBE_ENV is the studio's reflection: it needs ENV_SPEC (AD-039 §8)")
    maps = roughness_map or normal_map or translucency_map
    flags = (("ALBEDO_MAP", albedo_map), ("ENV_SPEC", env_spec), ("SHADOW", shadow), ("DUAL_LOBE", dual_lobe),
             ("THICKNESS", thickness), ("ROUGHNESS_MAP", roughness_map), ("NORMAL_MAP", normal_map),
             ("TRANSLUCENCY_MAP", translucency_map), ("LD_MAP_UV", maps), ("CUBE_ENV", cube_env),
             ("REGIONS", regions), ("AREA_DIFFUSE", area_diffuse), ("SOFT_SHADOW", soft_shadow))
    defines = "".join(f"#define {name} 1\n" for name, on in flags if on)
    body = SKIN_BODY
    for name, on in flags[2:]:
        if not on:
            body = _without(body, name)
    library = (LD_BRDF_SRC + LD_COMMON_SRC + (LD_AREA_SRC if area_diffuse else "")
               + (LD_SHADOW_SRC if shadow else "") + (LD_DUAL_LOBE_SRC if dual_lobe else "")
               + (LD_THICKNESS_SRC if thickness else "")
               + (LD_SOFT_SHADOW_DEPTH_SRC if soft_shadow and not thickness else "")
               + (LD_SOFT_SHADOW_SRC if soft_shadow else "")
               + (LD_NORMAL_MAP_SRC if normal_map else "") + (LD_CUBE_SRC if cube_env else ""))
    fragment = "#version 330 core\n" + defines + library + body
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
