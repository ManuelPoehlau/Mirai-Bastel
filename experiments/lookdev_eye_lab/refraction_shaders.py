"""P1b GLSL: the corneal refraction (2026-11-14). P1's `shaders.py` is used as it is (its `LIB_SRC` for the
colour path, BRDF and studio); nothing there changes.

`REFRACTION_LIB_SRC` holds the ray functions, each the twin of the same-named function in `cornea_optics.py`
(compared on the GPU by `tests/test_gl_refraction.py`).

**The refractive cornea program** (`cornea_sources`, variants by `#define`: `TECH` 1 / 2 / 3 = T-B / T-C / T-D as in
P1, `VARIANT` 2 / 3, `DEBUG_KIND` for the ray-class map):
- drawn from the cornea entry's VertexList (the anterior surface mesh = P1's cornea cap) as an **opaque** pass:
  depth test on, depth write on, no blending. It replaces the iris mesh (not drawn in V2 / V3): every view of the
  iris goes through the cornea, so the iris is shaded where the refracted ray meets it.
- per fragment the view ray is intersected with the analytic anterior sphere (the mesh is only the raster footprint;
  at the tessellated rim the fragment's own position stands in), refracted (V2: once to 1.3375; V3: to 1.376, then at
  the posterior sphere to 1.336), and traced to P1's iris cone, the pupil, or the limbal tissue;
- colour = (1 - F) · T_inner · L_inside + reflection, all in linear light, then P1's colour path. F is Schlick with
  P1's cornea F0 (IOR 1.376 by default) so the reflection equals P1's shells; L_inside is the iris (P1's image, sRGB
  decoded, lit by the key and the studio ambient on the cone's normal - light is not refracted on its way in) or the
  limbal tissue (dark limbal colour -> sclera by `limbus_weight`); a ray into the pupil sees P1's pupil colour.
- the iris image is sampled before any branch (implicit derivatives are undefined in non-uniform control flow);
  with a radial fit (`out/iris_custom.json`, `#define IRIS_FIT`) through `iris_fit.GLSL_SRC`, else planar.
"""

from __future__ import annotations

from . import cornea_optics as co
from . import iris_fit as fit
from . import shaders

VARIANT_IDS = {"V2": 2, "V3": 3}

REFRACTION_LIB_SRC = f"""
const float N_AIR = {co.N_AIR!r};
const float N_CORNEA = {co.N_CORNEA!r};
const float N_AQUEOUS = {co.N_AQUEOUS!r};
const float N_EFFECTIVE = {co.N_EFFECTIVE!r};
const float RAY_EPS = {co.EPS!r};
const int KIND_MISS = {co.MISS};
const int KIND_IRIS = {co.IRIS};
const int KIND_PUPIL = {co.PUPIL};
const int KIND_LIMBUS = {co.LIMBUS};

uniform vec3 u_ant_centre;
uniform float u_ant_radius;
uniform vec3 u_post_centre;
uniform float u_post_radius;
uniform float u_cap_z;
uniform vec2 u_angle;
uniform float u_iris_a;
uniform float u_iris_b;
uniform float u_iris_radius;
uniform float u_pupil_radius;
uniform float u_limbus_radius;

// cornea_optics.sphere_entry
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

// cornea_optics.iris_cone_hit: z = a + b r, extended to r = 0
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

// cornea_optics.limbus_weight
float limbus_weight(float r_entry) {{
    return smoothstep(0.0, 1.0, clamp((r_entry - u_angle.x) / (u_limbus_radius - u_angle.x), 0.0, 1.0));
}}

// cornea_optics.schlick_scalar
float schlick_scalar(float f0, float cos_theta) {{
    float m = 1.0 - clamp(cos_theta, 0.0, 1.0);
    return f0 + (1.0 - f0) * (m * m * m * m * m);
}}

// cornea_optics.trace (variant 2 / 3; V1 never reaches this program)
int trace_cornea(vec3 eye, vec3 d, int variant, out vec3 entry, out vec3 normal, out vec3 hit,
                 out float transmit_inner) {{
    d = normalize(d);
    transmit_inner = 1.0;
    float ta;
    bool hit_a = sphere_entry(eye, d, u_ant_centre, u_ant_radius, ta);
    entry = eye + ta * d;
    normal = normalize(entry - u_ant_centre);
    hit = entry;
    if (!hit_a || entry.z < u_cap_z - 1e-9) return KIND_MISS;
    float eta = N_AIR / (variant == 2 ? N_EFFECTIVE : N_CORNEA);
    vec3 t_dir = normalize(refract(d, normal, eta));
    float tp;
    bool hit_p = sphere_entry(entry, t_dir, u_post_centre, u_post_radius, tp);
    vec3 pp = entry + tp * t_dir;
    if (!hit_p || pp.z < u_angle.y) return KIND_LIMBUS;
    vec3 start = entry;
    if (variant == 3) {{
        vec3 np = normalize(pp - u_post_centre);
        vec3 inner = refract(t_dir, np, N_CORNEA / N_AQUEOUS);
        if (length(inner) < 0.5) return KIND_LIMBUS;  // total internal reflection
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
"""

CORNEA_FRAGMENT_BODY = """
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

// The same environment / specular terms as P1's surface program (shaders.SURFACE_FRAGMENT_BODY), repeated here
// because that body is a whole program, not a library.
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

void main() {
    vec3 dir = normalize(v_world_pos - u_eye);
    vec3 entry;
    vec3 n;
    vec3 hit;
    float transmit_inner;
    int kind = trace_cornea(u_eye, dir, VARIANT, entry, n, hit, transmit_inner);
    if (kind == KIND_MISS) {
        // The tessellated rim lies a hair outside the analytic sphere / cap: the fragment itself is the entry.
        entry = v_world_pos;
        n = normalize(v_world_pos - u_ant_centre);
        kind = KIND_LIMBUS;
    }
    // Sampled before any branch: implicit derivatives need uniform control flow.
#ifdef IRIS_FIT
    vec3 iris_albedo = srgb_decode(texture(u_iris_texture, iris_fit_uv(hit.xy)).rgb);
#else
    vec3 iris_albedo = srgb_decode(texture(u_iris_texture, vec2(0.5) + hit.xy / (2.0 * u_iris_radius)).rgb);
#endif
#ifdef DEBUG_KIND
    out_color = vec4(kind == KIND_IRIS ? 1.0 : 0.0, kind == KIND_PUPIL ? 1.0 : 0.0, kind == KIND_LIMBUS ? 1.0 : 0.0,
                     1.0);
    return;
#endif
    vec3 v = -dir;
    vec3 inside;
    if (kind == KIND_LIMBUS) {
        inside = lit(mix(u_limbus_albedo, u_sclera_albedo, limbus_weight(length(entry.xy))), n);
    } else {
        float r = length(hit.xy);
        vec3 cone_n = normalize(vec3(-u_iris_b * hit.xy / max(r, 1e-6), 1.0));
        // A ray through the pupil goes into the dark interior. The cone continued inside the pupil is only the
        // classifier; sampling the image there would read a coarse mip near the cone's apex (the root switches
        // between neighbouring pixels): a constant, the image's own pupil colour.
        inside = lit(kind == KIND_PUPIL ? u_pupil_albedo : iris_albedo, cone_n);
    }
    float fresnel = schlick(u_f0, max(dot(n, v), 0.0)).x;
    vec3 colour = (1.0 - fresnel) * transmit_inner * inside + specular(n, v, u_roughness, u_f0);
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
        o.xyz = refract(normalize(a.xyz), normalize(b.xyz), c.x);
    } else if (u_func == 1) {
        float t;
        bool h = sphere_entry(a.xyz, normalize(b.xyz), c.xyz, a.w, t);
        o = vec4(h ? t : -1.0, h ? 1.0 : 0.0, 0.0, 0.0);
    } else if (u_func == 2) {
        float t;
        float r;
        bool h = iris_cone_hit(a.xyz, normalize(b.xyz), t, r);
        o = vec4(h ? t : -1.0, h ? r : -1.0, h ? 1.0 : 0.0, 0.0);
    } else if (u_func == 3) {
        o.x = limbus_weight(a.x);
        o.y = schlick_scalar(a.y, a.z);
    } else if (u_func == 4 || u_func == 5) {
        vec3 entry;
        vec3 n;
        vec3 hit;
        float tin;
        int kind = trace_cornea(a.xyz, b.xyz, int(c.x + 0.5), entry, n, hit, tin);
        o = u_func == 4 ? vec4(hit, float(kind)) : vec4(entry, tin);
    }
#ifdef IRIS_FIT
    if (u_func == 6) {
        o.xy = iris_fit_uv(a.xy);
        o.z = iris_fit_share(a.z);
    }
#endif
    out_value = o;
}
"""

PARITY_FUNCS = {"refract": 0, "sphere_entry": 1, "iris_cone_hit": 2, "limbus_schlick": 3, "trace_hit": 4,
                "trace_entry": 5, "iris_fit": 6}


def _fit_src(iris_fit: bool) -> str:
    return "#define IRIS_FIT 1\n" + fit.GLSL_SRC if iris_fit else ""


def cornea_sources(locations: dict[str, int], tech: int, variant: int, debug_kind: bool = False,
                   iris_fit: bool = False):
    """`iris_fit`: sample the iris image through the radial fit (`iris_fit.GLSL_SRC`); off = the planar mapping, the
    program text as before."""
    header = "#version 330 core\n" + "".join(
        f"#define {k} {v}\n" for k, v in (("TECH", tech), ("VARIANT", variant)) if v is not None)
    if debug_kind:
        header += "#define DEBUG_KIND 1\n"
    fragment = header + shaders.LIB_SRC + REFRACTION_LIB_SRC + _fit_src(iris_fit) + CORNEA_FRAGMENT_BODY
    return [(shaders.SURFACE_VERTEX_SRC.format(**locations), "vertex"), (fragment, "fragment")]


def parity_sources(iris_fit: bool = False):
    return [(shaders.FULLSCREEN_VERTEX_SRC, "vertex"),
            ("#version 330 core\n" + shaders.LIB_SRC + REFRACTION_LIB_SRC + _fit_src(iris_fit)
             + PARITY_FRAGMENT_BODY, "fragment")]
