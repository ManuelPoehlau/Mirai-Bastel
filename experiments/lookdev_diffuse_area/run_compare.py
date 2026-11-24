"""A/B renders of the key's diffuse term through the real LookDev pass (2026-11-24; disposable experiment).

    xvfb-run -a python experiments/lookdev_diffuse_area/run_compare.py --out <dir>             # everything
    xvfb-run -a python experiments/lookdev_diffuse_area/run_compare.py --scene gollum --sizes 0.5 --ref 16

What it does (nothing in `src/` changes; the scene files are only read):
- builds the app as `main.py` does (`Application.init_scene("file", ...)` with `main.GL_TYPES`), opens the LookDev room,
  sets one fixed study light in memory: studio "Dramatic" (key azimuth 70, elevation 20, the side light that puts
  the terminator across the face), rim off, fill size 0 (so only the key is a finite emitter), exposure 0, Reinhard,
  effects Schatten + Doppel-Glanz (S1 + S3), eyes not shown, no wire, no symmetry plane. The same light, camera, exposure and tone curve for
  every image.
- per material (Neutral: wrap 0; Creature Skin: wrap 0.3 x tint (1, 0.65, 0.5); both with the albedo "Farbe", so the
  shading reads without the paint) and key size (0 / 0.25 / 0.5 / 1):
  - the variants (`area_glsl.Variant`: A = production, B, B2, C16, B-split, B-point) diffuse-only;
  - REF: the ground truth of an area key - `--ref` renders of the *production* shader (method A, key size 0: a hard
    map and point light) with the key's direction on the emitter's cap (`area_math.cap_directions`, Vogel spiral),
    each key colour x 2 / (1 + cos sigma) (the lit side stays where it was), averaged in linear light. Each direction
    casts its own hard shadow, so REF has the true soft shadows, concavities and nostrils included;
  - "beauty" A, B and B-split (specular on) for the look.
  Every image is captured linear (exposure x colour) into an RGBA32F FBO and tone-mapped / encoded in NumPy with
  production's twin (`lookdev_optics.lookdev_output`, Reinhard).
- metrics against REF on the object's pixels (display values 0..255): mean |error|, and the share of pixels more than
  8/255 brighter (a leak, a bright rim) or darker (missing light) than REF.

`--production` (2026-11-24, after AD-039 §23 built S8): per size also production itself with its effect „Weiches
Licht“ (`area_diffuse`) on and off - variant A's patch only takes the specular / linear output levers, the diffuse
term is the production shader's own (with the effect on the body calls `ld_diffuse_area`, which the patch does not
touch) - and the largest difference "P-on vs B" and "P-off vs A" (diffuse-only and beauty), linear and in 8 bit.

Scenes: `gollum` = scenes/Gollum_Head_05.mirai.json at SubD 1 (views "face": the front close-up of nose, mouth and
eyes; "framed": the 3/4 view); `shapes` = a generated scene (sphere, cylinder, a concave panel with a bowl and a
groove), cage = the drawn surface (they are dense already).
"""

from __future__ import annotations

import argparse
import ctypes
import json
import math
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
for p in (REPO / "src", REPO / "experiments", HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np  # noqa: E402

import area_glsl as ag  # noqa: E402
import area_math as am  # noqa: E402

GOLLUM = REPO / "scenes" / "Gollum_Head_05.mirai.json"
SIZES = (0.0, 0.25, 0.5, 1.0)
MATERIALS = ("Neutral", "Creature Skin")
KEY = (70.0, 20.0)
STUDIO = "Dramatic"
VARIANTS = {"A": ag.Variant("A", spec=False, linear=True),
            "B": ag.Variant("B", spec=False, linear=True),
            "B2": ag.Variant("B2", spec=False, linear=True),
            "C16": ag.Variant("C", samples=16, spec=False, linear=True),
            "B-split": ag.Variant("B", excess="split", spec=False, linear=True),
            "B-point": ag.Variant("B", excess="point", spec=False, linear=True),
            "A-liftfull": ag.Variant("A", lift="full", spec=False, linear=True),
            "B-liftfull": ag.Variant("B", lift="full", spec=False, linear=True),
            "B-liftmid": ag.Variant("B", lift="mid", spec=False, linear=True)}
BEAUTY = {"A beauty": ag.Variant("A", linear=True), "B beauty": ag.Variant("B", linear=True),
          "B-split beauty": ag.Variant("B", excess="split", linear=True)}
THRESHOLD = 8.0


# -- the app -----------------------------------------------------------------------------------------------------------

def build_app(scene_path: Path, size):
    import pyglet

    import main as src_main
    from mirai.application import Application

    window = pyglet.window.Window(width=size[0], height=size[1], visible=False)
    app = Application()
    from mirai.subdivision.gl_lines import GLSubdLineOverlay

    # the SubD cage lines over the smooth surface would cover the shading: not drawn (this process only)
    GLSubdLineOverlay.draw = lambda self, camera_uniforms, layers=None: None
    app.init_scene("file", scene_path=str(scene_path), **src_main.GL_TYPES)
    app.set_viewport_size(*size)
    app.update_viewport(0.0)
    return window, app


def shapes_scene(path: Path) -> Path:
    """Sphere (r 1), a vertical cylinder (r 0.7), a concave panel (a closed slab whose front holds a bowl and a groove)
    side by side, Y up, facing +Z. Dense enough that the cage is the smooth surface."""
    from core import Mesh, Scene
    from core.serialization import scene_to_json

    class Builder:
        def __init__(self):
            self.mesh, self.pos = Mesh(), {}

        def v(self, p):
            vid = self.mesh.add_vertex(tuple(float(c) for c in p))
            self.pos[vid] = np.asarray(p, dtype=np.float64)
            return vid

        def face(self, ids, outward):
            pts = [self.pos[i] for i in ids]
            n = np.zeros(3)
            for a, b in zip(pts, pts[1:] + pts[:1]):  # Newell
                n += np.cross(a, b)
            self.mesh.add_face(list(ids) if np.dot(n, outward) >= 0.0 else list(reversed(ids)))

    def sphere(cx, rings=48, segs=96, r=1.0):
        b = Builder()
        c = np.array([cx, 0.0, 0.0])
        top, bottom = b.v((cx, r, 0.0)), b.v((cx, -r, 0.0))
        rows = []
        for i in range(1, rings):
            t = math.pi * i / rings
            rows.append([b.v((cx + r * math.sin(t) * math.sin(2 * math.pi * j / segs), r * math.cos(t),
                              r * math.sin(t) * math.cos(2 * math.pi * j / segs))) for j in range(segs)])
        out = lambda ids: np.mean([b.pos[i] for i in ids], axis=0) - c  # noqa: E731
        for j in range(segs):
            k = (j + 1) % segs
            for ids in ([top, rows[0][j], rows[0][k]], [bottom, rows[-1][k], rows[-1][j]]):
                b.face(ids, out(ids))
        for ra, rb in zip(rows, rows[1:]):
            for j in range(segs):
                k = (j + 1) % segs
                ids = [ra[j], rb[j], rb[k], ra[k]]
                b.face(ids, out(ids))
        return b.mesh

    def cylinder(cx, r=0.7, h=2.0, segs=96, rings=8):
        b = Builder()
        rows = [[b.v((cx + r * math.sin(2 * math.pi * j / segs), h / 2 - h * i / rings,
                      r * math.cos(2 * math.pi * j / segs))) for j in range(segs)] for i in range(rings + 1)]
        for ra, rb in zip(rows, rows[1:]):
            for j in range(segs):
                k = (j + 1) % segs
                ids = [ra[j], rb[j], rb[k], ra[k]]
                o = np.mean([b.pos[i] for i in ids], axis=0) - np.array([cx, 0.0, 0.0])
                o[1] = 0.0
                b.face(ids, o)
        b.face(rows[0], np.array([0.0, 1.0, 0.0]))
        b.face(rows[-1], np.array([0.0, -1.0, 0.0]))
        return b.mesh

    def panel(cx, w=2.0, h=2.0, n=96, depth=0.6):  # deeper than the bowl (0.41)
        def z(x, y):
            d = 0.0
            rb = math.hypot(x, y - 0.45)
            if rb < 0.55:  # a bowl (a spherical cap, 0.41 deep)
                d = max(d, math.sqrt(0.55 ** 2 - rb ** 2) * 0.75)
            g = abs(y + 0.5)
            if g < 0.22 and abs(x) < 0.85:  # a horizontal groove (a half round, 0.26 deep)
                d = max(d, math.sqrt(0.22 ** 2 - g ** 2) * 1.2)
            return -d
        b = Builder()
        xs = [-w / 2 + w * j / n for j in range(n + 1)]
        ys = [h / 2 - h * i / n for i in range(n + 1)]
        front = [[b.v((cx + x, y, z(x, y))) for x in xs] for y in ys]
        back = [[b.v((cx + x, y, -depth)) for x in xs] for y in ys]
        for i in range(n):
            for j in range(n):
                b.face([front[i][j], front[i + 1][j], front[i + 1][j + 1], front[i][j + 1]], np.array([0, 0, 1.0]))
                b.face([back[i][j], back[i + 1][j], back[i + 1][j + 1], back[i][j + 1]], np.array([0, 0, -1.0]))
        for k in range(n):  # the four sides as quad strips
            b.face([front[0][k], front[0][k + 1], back[0][k + 1], back[0][k]], np.array([0, 1.0, 0]))
            b.face([front[n][k], front[n][k + 1], back[n][k + 1], back[n][k]], np.array([0, -1.0, 0]))
            b.face([front[k][0], front[k + 1][0], back[k + 1][0], back[k][0]], np.array([-1.0, 0, 0]))
            b.face([front[k][n], front[k + 1][n], back[k + 1][n], back[k][n]], np.array([1.0, 0, 0]))
        return b.mesh

    scene = Scene()
    sphere_obj = scene.add_object(sphere(-2.6), name="Kugel")
    scene.add_object(cylinder(0.0), name="Zylinder")
    scene.add_object(panel(2.6), name="Mulde")
    scene.edit_object_id = sphere_obj.id
    path.write_text(scene_to_json(scene), encoding="utf-8")
    return path


# -- capture -----------------------------------------------------------------------------------------------------------

class Capture:
    """An RGBA32F + depth FBO: `render(app)` -> (linear rgb (h, w, 3), object mask)."""

    def __init__(self, size):
        from pyglet import gl

        self.size = size
        w, h = size
        self.fbo, self.tex, self.depth = gl.GLuint(), gl.GLuint(), gl.GLuint()
        gl.glGenTextures(1, ctypes.byref(self.tex))
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.tex)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA32F, w, h, 0, gl.GL_RGBA, gl.GL_FLOAT, None)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
        gl.glGenRenderbuffers(1, ctypes.byref(self.depth))
        gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, self.depth)
        gl.glRenderbufferStorage(gl.GL_RENDERBUFFER, gl.GL_DEPTH24_STENCIL8, w, h)
        gl.glGenFramebuffers(1, ctypes.byref(self.fbo))
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.fbo)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, self.tex, 0)
        gl.glFramebufferRenderbuffer(gl.GL_FRAMEBUFFER, gl.GL_DEPTH_STENCIL_ATTACHMENT, gl.GL_RENDERBUFFER, self.depth)
        assert gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER) == gl.GL_FRAMEBUFFER_COMPLETE
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)

    def render(self, window, app):
        from pyglet import gl

        w, h = self.size
        window.switch_to()
        app.update_viewport(0.0)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.fbo)
        gl.glViewport(0, 0, w, h)
        gl.glClearColor(0.0, 0.0, 0.0, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT | gl.GL_STENCIL_BUFFER_BIT)
        app.viewport.render()
        gl.glFinish()
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.fbo)
        rgba = (gl.GLfloat * (w * h * 4))()
        depth = (gl.GLfloat * (w * h))()
        gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
        gl.glReadPixels(0, 0, w, h, gl.GL_RGBA, gl.GL_FLOAT, rgba)
        gl.glReadPixels(0, 0, w, h, gl.GL_DEPTH_COMPONENT, gl.GL_FLOAT, depth)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        img = np.frombuffer(rgba, np.float32).reshape(h, w, 4)[::-1, :, :3].astype(np.float64)
        mask = np.frombuffer(depth, np.float32).reshape(h, w)[::-1] < 1.0
        return img, mask


def display(linear, mask, background=(0.02, 0.02, 0.024)) -> np.ndarray:
    from viewport.lookdev_optics import lookdev_output

    out = np.empty(linear.shape)
    out[:] = background
    out[mask] = lookdev_output(linear[mask], 1.0, "reinhard")
    return np.clip(np.round(out * 255.0), 0, 255).astype(np.uint8)


def write_png(path: Path, rgb) -> None:
    from mirai.iris_import import encode_png

    rgba = np.concatenate([rgb, np.full(rgb.shape[:2] + (1,), 255, np.uint8)], axis=2)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encode_png(np.ascontiguousarray(rgba)))


# -- the study setup ---------------------------------------------------------------------------------------------------

def prepare(window, app, capture) -> None:
    app.set_eyes_shown(False)
    app.set_lookdev_wire(False)
    if app.toggle_symmetry_display():  # it was hidden: hide it again
        app.toggle_symmetry_display()
    app.open_lookdev()
    for _ in range(20):
        if not app.lookdev.preparing:
            break
        capture.render(window, app)
    app.set_lookdev_studio_preset(STUDIO)
    app.set_lookdev_studio(rotation=0.0, follow_camera=False, exposure=0.0, tone_curve="reinhard")
    app.set_lookdev_light("rim", on=False)
    app.set_lookdev_light("fill", size=0.0)
    app.set_lookdev_light("key", azimuth=KEY[0], elevation=KEY[1], size=0.0)
    from viewport.lookdev_optics import LookdevEffects

    for name in LookdevEffects.names():
        app.set_lookdev_effect(name, name in ("shadow", "dual_lobe"))
    settle(window, app, capture)


def settle(window, app, capture) -> None:
    for _ in range(20):
        app.update_viewport(0.0)
        if not app.lookdev.preparing:
            return
        capture.render(window, app)
    raise RuntimeError("LookDev kept preparing")


def set_material(app, name: str) -> None:
    from core import ObjectState

    ids = [oid for oid, obj in app.scene.objects.items()
           if obj.eye is None and obj.state is ObjectState.NORMAL and not obj.hidden]
    app.select_objects(ids)
    app.set_lookdev_material(name)
    app.set_lookdev_material_values(albedo_source="color")
    app.select_objects([])


def use(app, variant: ag.Variant) -> None:
    ag.install(variant)
    ag.reset_programs(app)


def render_variant(window, app, capture, variant):
    use(app, variant)
    capture.render(window, app)  # compiles
    return capture.render(window, app)


def render_reference(window, app, capture, size: float, count: int):
    """REF: the production shader under `count` hard point keys spread over the emitter's cap, averaged."""
    s = float(am.size_to_sin(size))
    use(app, VARIANTS["A"])
    key = app.lookdev.studio.key
    if s < am.S_MIN:
        app.set_lookdev_light("key", size=0.0)
        capture.render(window, app)
        return capture.render(window, app)
    base_intensity = key.intensity
    l0 = am.direction(*KEY)
    right, up = am.frame_for(l0)
    local = am.cap_directions(s, count)
    norm = 2.0 / (1.0 + math.sqrt(1.0 - s * s))
    acc, mask = None, None
    app.set_lookdev_light("key", size=0.0, intensity=base_intensity * norm)
    for d in local:
        w = d[0] * right + d[1] * up + d[2] * l0
        el = math.degrees(math.asin(max(-1.0, min(1.0, w[1]))))
        az = math.degrees(math.atan2(w[0], w[2]))
        app.set_lookdev_light("key", azimuth=az, elevation=el)
        img, m = capture.render(window, app)
        acc = img if acc is None else acc + img
        mask = m if mask is None else (mask | m)
    app.set_lookdev_light("key", azimuth=KEY[0], elevation=KEY[1], intensity=base_intensity)
    return acc / len(local), mask


def crop_box(mask, pad: int = 12):
    rows, cols = np.where(mask.any(axis=1))[0], np.where(mask.any(axis=0))[0]
    h, w = mask.shape
    return (max(rows[0] - pad, 0), min(rows[-1] + pad + 1, h), max(cols[0] - pad, 0), min(cols[-1] + pad + 1, w))


def crop(img, box):
    return img[box[0]:box[1], box[2]:box[3]]


def metrics(img8, ref8, mask) -> dict:
    d = img8.astype(np.float64)[mask] - ref8.astype(np.float64)[mask]
    lum = d @ np.array([0.2126, 0.7152, 0.0722])
    return {"mae": float(np.mean(np.abs(lum))), "brighter": float(np.mean(lum > THRESHOLD)),
            "darker": float(np.mean(lum < -THRESHOLD)), "max_brighter": float(lum.max(initial=0.0))}


def diff_map(img8, ref8, mask, gain: float = 4.0) -> np.ndarray:
    d = (img8.astype(np.float64) - ref8.astype(np.float64)) @ np.array([0.2126, 0.7152, 0.0722])
    out = np.full(img8.shape, 24, np.float64)
    out[..., 0] += np.clip(d * gain, 0, 230)
    out[..., 2] += np.clip(-d * gain, 0, 230)
    out[..., 1] += 0.0
    out[~mask] = 0
    return out.astype(np.uint8)


def sheet(rows: list[list[np.ndarray]], gap: int = 4) -> np.ndarray:
    h, w = rows[0][0].shape[:2]
    out = np.zeros((len(rows) * (h + gap) - gap, len(rows[0]) * (w + gap) - gap, 3), np.uint8)
    for i, row in enumerate(rows):
        for j, img in enumerate(row):
            out[i * (h + gap):i * (h + gap) + h, j * (w + gap):j * (w + gap) + w] = img
    return out


def views_for(scene: str):
    if scene == "gollum":
        return ("face", "framed")
    return ("front",)


def set_camera(app, scene: str, view: str) -> None:
    from drag_cost.probe_lookdev import set_view

    if scene == "gollum":
        set_view(app, view)
        return
    cam = app.camera
    cam.set_view(0.0, math.radians(5.0))
    cam.frame_on_bounds((0.0, 0.0, 0.0), 3.9, 1.05)
    app.viewport.on_camera_changed()
    app.update_viewport(0.0)


def run_scene(scene: str, args, out: Path, log) -> dict:
    from drag_cost.probe_lookdev import set_surface

    path = GOLLUM if scene == "gollum" else shapes_scene(Path(tempfile.mkdtemp(prefix="ldx_shapes_")) / "shapes.mirai.json")
    window, app = build_app(path, args.size)
    if scene == "gollum" and not set_surface(app, "subd1"):
        raise RuntimeError("SubD 1 could not be set")
    capture = Capture(window.get_framebuffer_size())
    prepare(window, app, capture)
    results = {}
    try:
        for view in views_for(scene):
            set_camera(app, scene, view)
            for material in MATERIALS:
                set_material(app, material)
                settle(window, app, capture)
                grid, diffs, beauty = [], [], []
                box = None
                for size in args.sizes:
                    t0 = time.perf_counter()
                    app.set_lookdev_light("key", size=size)
                    settle(window, app, capture)
                    images = {}
                    for name in args.variants:
                        img, mask = render_variant(window, app, capture, VARIANTS[name])
                        images[name] = display(img, mask)
                    linear = {}
                    for name, variant in BEAUTY.items():
                        img, mask = render_variant(window, app, capture, variant)
                        images[name] = display(img, mask)
                        linear[name] = img
                    production = {}
                    if args.production:
                        for name in ("A", "B"):
                            linear[name], _ = render_variant(window, app, capture, VARIANTS[name])
                        for on in (True, False):  # ends off, as the variants ran
                            app.set_lookdev_effect("area_diffuse", on)
                            settle(window, app, capture)
                            tag = "P-on" if on else "P-off"
                            for suffix, variant in (("", VARIANTS["A"]), (" beauty", BEAUTY["A beauty"])):
                                img, mask = render_variant(window, app, capture, variant)
                                images[tag + suffix] = display(img, mask)
                                linear[tag + suffix] = img
                        for prod, var in (("P-on", "B"), ("P-off", "A"), ("P-on beauty", "B beauty"),
                                          ("P-off beauty", "A beauty")):
                            lin = float(np.abs(linear[prod] - linear[var]).max())
                            eight = int(np.abs(images[prod].astype(int) - images[var].astype(int)).max())
                            production[f"{prod} vs {var}"] = {"linear_max": lin, "display_max": eight}
                    ref, rmask = render_reference(window, app, capture, size, args.ref)
                    app.set_lookdev_light("key", size=size)
                    images["REF"] = display(ref, rmask)
                    key = f"{scene}/{view}/{material}/size {size:g}"
                    results[key] = {name: metrics(images[name], images["REF"], rmask) for name in args.variants}
                    if production:
                        results[key]["production"] = production
                    log(f"{key}  ({time.perf_counter() - t0:.0f} s)")
                    for pair, d in production.items():
                        log(f"    production {pair:<24} max |diff| linear {d['linear_max']:.2e}  "
                            f"display {d['display_max']}/255")
                    for name in args.variants:
                        m = results[key][name]
                        log(f"    {name:<12} mae {m['mae']:5.2f}/255  brighter>8 {100 * m['brighter']:5.2f} %  "
                            f"darker>8 {100 * m['darker']:5.2f} %  max+ {m['max_brighter']:5.1f}")
                    tag = f"{scene}_{view}_{material.replace(' ', '')}_s{int(round(size * 100)):03d}"
                    if box is None:
                        box = crop_box(rmask)
                    images = {k: crop(img, box) for k, img in images.items()}
                    rmask = crop(rmask, box)
                    for name, img in images.items():
                        write_png(out / "frames" / f"{tag}_{name.replace(' ', '_')}.png", img)
                    grid.append([images[n] for n in ("A", "B", "B-split", "C16", "REF") if n in images])
                    diffs.append([diff_map(images[n], images["REF"], rmask) for n in ("A", "B", "B-split", "C16")
                                  if n in images])
                    beauty.append([images["A beauty"], images["B beauty"], images["B-split beauty"]])
                mtag = f"{scene}_{view}_{material.replace(' ', '')}"
                # rows = sizes; columns = A, B, B-split, C16, REF (diff: the same without REF)
                write_png(out / f"sheet_{mtag}.png", sheet(grid))
                write_png(out / f"diff_{mtag}.png", sheet(diffs))
                write_png(out / f"beauty_{mtag}.png", sheet(beauty))
    finally:
        ag.uninstall()
        app.close_lookdev()
        window.close()
    return results


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", default=str(HERE / "out"))
    parser.add_argument("--scene", default="shapes,gollum")
    parser.add_argument("--sizes", default=",".join(f"{s:g}" for s in SIZES))
    parser.add_argument("--variants", default=",".join(VARIANTS))
    parser.add_argument("--ref", type=int, default=32, help="REF: key directions on the cap")
    parser.add_argument("--size", type=int, nargs=2, default=(1024, 768))
    parser.add_argument("--production", action="store_true",
                        help="also production with „Weiches Licht“ on / off against B / A (AD-039 §23)")
    args = parser.parse_args(argv)
    args.sizes = tuple(float(s) for s in args.sizes.split(","))
    args.variants = tuple(v for v in args.variants.split(",") if v)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    lines = []

    def log(text):
        print(text, flush=True)
        lines.append(text)

    from pyglet import gl  # noqa: F401 - opens the shadow context first

    from drag_cost._paths import source_state

    log(f"lookdev_diffuse_area run_compare, {args.size[0]}x{args.size[1]}, REF {args.ref} directions, "
        f"S_MAX {am.S_MAX:.4f} (sigma(1) = {float(am.sigma_degrees(1.0)):.1f} deg)")
    log(f"Source: {source_state()}")
    results = {}
    for scene in args.scene.split(","):
        results.update(run_scene(scene, args, out, log))
    (out / "metrics.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    (out / "log.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
