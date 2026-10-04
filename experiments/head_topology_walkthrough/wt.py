"""Walkthrough driver: existing Playground tools, scripted, plus read-only measurement.

Nothing here edits the mesh by itself. Every topology change goes through a tool that already
lives in the repo (`playground/topology_tools/*`, `mirai.interaction.tools.*`); this module only
picks the selection geometrically (the script's replacement for mouse clicks), mirrors moves by
hand (symmetry is not available in the Playground, so the left/right partner gets the mirrored
operation explicitly), measures the result, and takes screenshots.

Run under a virtual display: `xvfb-run -a python run_walkthrough.py` (see README).
"""

from __future__ import annotations

import math
import sys
from collections import Counter
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from playground._paths import ensure_paths  # noqa: E402

ensure_paths()

from core import OperationContext  # noqa: E402
from core.operations.move import MoveOperation  # noqa: E402
from mirai.interaction.tools.rotate import RotateTool  # noqa: E402
from mirai.interaction.tools.scale import ScaleTool  # noqa: E402
from mirai.interaction.tools.transform import _VertexSelectionView  # noqa: E402
from playground.app import PlaygroundApp  # noqa: E402
from playground.topology_tools.connect_edges import connect_selected_edges  # noqa: E402
from playground.topology_tools.extrude import ExtrudeTool  # noqa: E402
from playground.topology_tools.loop_insert import loop_insert  # noqa: E402
from playground.topology_tools.loop_ring import edge_loop, edge_ring  # noqa: E402
from playground.topology_tools.loop_slide import LoopSlideTool  # noqa: E402
from playground.window import PlaygroundWindow  # noqa: E402

EPS = 1e-6
W, H = 1280, 800


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a):
    n = math.sqrt(a[0] ** 2 + a[1] ** 2 + a[2] ** 2)
    return (a[0] / n, a[1] / n, a[2] / n) if n > 1e-12 else (0.0, 0.0, 0.0)


class WT:
    def __init__(self, shots_dir: Path) -> None:
        self.shots = Path(shots_dir)
        self.shots.mkdir(parents=True, exist_ok=True)
        self.app = PlaygroundApp()
        self.win = PlaygroundWindow(self.app, initial_mesh="cube")
        self.win._hud.draw = lambda: None  # clean frames; the HUD is app chrome, not content
        self.app.display_state.set_wireframe_overlay(True)
        self.app.show_vertices = False
        self.n_tool_calls = Counter()

    # -- handles -----------------------------------------------------------
    @property
    def scene(self):
        return self.app.scene

    @property
    def mesh(self):
        return self.app.scene.mesh

    @property
    def cam(self):
        return self.app.camera

    # -- geometry queries (script's stand-in for clicking) ------------------
    def pos(self, v):
        return self.mesh.vertex_position(v)

    def face_center(self, f):
        vs = [self.pos(v) for v in self.mesh.face_vertices(f)]
        n = len(vs)
        return tuple(sum(p[i] for p in vs) / n for i in range(3))

    def face_normal(self, f):
        vs = [self.pos(v) for v in self.mesh.face_vertices(f)]
        nx = ny = nz = 0.0
        for i in range(len(vs)):
            a, b = vs[i], vs[(i + 1) % len(vs)]
            nx += (a[1] - b[1]) * (a[2] + b[2])
            ny += (a[2] - b[2]) * (a[0] + b[0])
            nz += (a[0] - b[0]) * (a[1] + b[1])
        return _norm((nx, ny, nz))

    def faces_where(self, pred):
        return {f for f in self.mesh.all_face_ids() if pred(self.face_center(f), self.face_normal(f))}

    def verts_where(self, pred):
        return {v for v in self.mesh.all_vertex_ids() if pred(self.pos(v))}

    def edges_where(self, pred):
        out = set()
        for e in self.mesh.all_edge_ids():
            a, b = self.mesh.edge_vertices(e)
            if pred(self.pos(a), self.pos(b)):
                out.add(e)
        return out

    def face_verts(self, faces):
        out = set()
        for f in faces:
            out.update(self.mesh.face_vertices(f))
        return out

    def vertex_at(self, p, tol=1e-5):
        best = None
        for v in self.mesh.all_vertex_ids():
            q = self.pos(v)
            d = abs(q[0] - p[0]) + abs(q[1] - p[1]) + abs(q[2] - p[2])
            if d < tol:
                return v
            if best is None or d < best[0]:
                best = (d, v)
        return None

    def mirror_vertex(self, v):
        x, y, z = self.pos(v)
        if abs(x) < EPS:
            return v
        return self.vertex_at((-x, y, z))

    def mirror_faces(self, faces):
        out = set()
        for f in faces:
            mv = {self.mirror_vertex(v) for v in self.mesh.face_vertices(f)}
            for g in self.mesh.all_face_ids():
                if set(self.mesh.face_vertices(g)) == mv:
                    out.add(g)
        return out

    # -- tools ------------------------------------------------------------
    def loop_cut(self, edge):
        """Playground Loop Insert (ring through `edge`, connected)."""
        self.n_tool_calls["loop_insert"] += 1
        return loop_insert(self.scene, edge)

    def extrude(self, faces, distance=0.0):
        """Playground ExtrudeTool (region extrude). The distance is applied as a Move of the
        new cap along its normal right after (driver convention: no pixel dragging)."""
        self.n_tool_calls["extrude"] += 1
        t = ExtrudeTool(self.scene, self.cam)
        t.activate()
        t.begin(face_ids=set(faces))
        t.commit()
        caps = set(t.new_face_ids)
        t.deactivate()
        if distance:
            comps = self._components(caps)
            for comp in comps:
                n = _norm(tuple(sum(self.face_normal(f)[i] for f in comp) for i in range(3)))
                self._move_raw(self.face_verts(comp), tuple(distance * c for c in n))
        return caps

    def _components(self, faces):
        faces = set(faces)
        comps = []
        while faces:
            seed = faces.pop()
            comp = {seed}
            stack = [seed]
            while stack:
                f = stack.pop()
                for e in self.mesh.face_edges(f):
                    for g in self.mesh.edge_faces(e):
                        if g in faces:
                            faces.discard(g)
                            comp.add(g)
                            stack.append(g)
            comps.append(comp)
        return comps

    def _move_raw(self, vids, delta):
        vids = set(vids)
        if not vids:
            return
        ctx = OperationContext(
            target=self.mesh, selection=_VertexSelectionView(vids), history=self.scene.history,
            params={"pivot": None},
        )
        op = MoveOperation(ctx)
        op.begin()
        op.update(delta=delta)
        op.commit()

    def move(self, vids, delta, mirror=True):
        """Core MoveOperation. mirror=True: the partner on the other side receives the mirrored
        delta (dx flipped) by hand; seam vertices (x=0) only move in the plane."""
        self.n_tool_calls["move"] += 1
        vids = set(vids)
        dx, dy, dz = delta
        seam = {v for v in vids if abs(self.pos(v)[0]) < EPS}
        side = vids - seam
        partners = set()
        if mirror:
            for v in side:
                m = self.mirror_vertex(v)
                if m is None:
                    raise RuntimeError(f"no mirror partner for {v} at {self.pos(v)}")
                if m not in vids:
                    partners.add(m)
        self._move_raw(side, delta)
        self._move_raw(seam, (0.0, dy, dz) if mirror else delta)
        self._move_raw(partners, (-dx, dy, dz))

    def scale(self, vids, factor, pivot, space=None, mirror=False):
        """Playground/Production ScaleTool with an exact factor (pixel gesture inverted).
        `factor` may be a float (uniform) with space=None, or a float with space='x'/'y'/'z'."""
        self.n_tool_calls["scale"] += 1
        groups = [(set(vids), pivot)]
        if mirror:
            mv = {self.mirror_vertex(v) for v in vids}
            if mv != set(vids):
                groups.append((mv, (-pivot[0], pivot[1], pivot[2])))
        for vs, pv in groups:
            t = ScaleTool()
            t.activate()
            t.begin(scene=self.scene, camera=self.cam, vertex_ids=set(vs), pivot=pv, space=space)
            t.update(dx=(factor - 1.0) / ScaleTool.SCALE_PER_PIXEL, dy=0.0, width=W, height=H)
            t.commit()
            t.deactivate()

    def rotate(self, vids, angle_deg, pivot, space="x"):
        """RotateTool about a world axis through `pivot` (pixel gesture inverted for an exact angle)."""
        self.n_tool_calls["rotate"] += 1
        t = RotateTool()
        t.activate()
        t.begin(scene=self.scene, camera=self.cam, vertex_ids=set(vids), pivot=pivot, space=space)
        t.update(dx=math.radians(angle_deg) / RotateTool.RADIANS_PER_PIXEL, dy=0.0, width=W, height=H)
        t.commit()
        t.deactivate()

    def pole_map(self):
        return {v: (k, p) for v, k, p in self.poles()}

    def slide(self, loop_edges, t):
        """Playground LoopSlideTool, parameter t in [-1, 1] (fraction of the way to a neighbour)."""
        self.n_tool_calls["loop_slide"] += 1
        tool = LoopSlideTool(self.scene, self.cam)
        tool.activate()
        tool.begin(edge_ids=set(loop_edges))
        tool.update(dx=t * W / 2.0, dy=0.0, width=W, height=H)
        tool.commit()
        tool.deactivate()

    def slide_to(self, loop_edges, sample_vertex, axis, target):
        """Slide a closed loop with the LoopSlideTool until `sample_vertex` reaches `target`
        on `axis` (driver convenience: probe once, then one more update; still a single tool run)."""
        self.n_tool_calls["loop_slide"] += 1
        tool = LoopSlideTool(self.scene, self.cam)
        tool.activate()
        tool.begin(edge_ids=set(loop_edges))
        t0 = 0.05
        y0 = self.pos(sample_vertex)[axis]
        tool.update(dx=t0 * W / 2.0, dy=0.0, width=W, height=H)
        y1 = self.pos(sample_vertex)[axis]
        if abs(y1 - y0) < 1e-12:
            tool.cancel()
            tool.deactivate()
            raise RuntimeError("slide probe did not move the sample vertex")
        if (target - y0) * (y1 - y0) >= 0:
            t_star = t0 * (target - y0) / (y1 - y0)
        else:  # the target lies on the other side: slide is piecewise linear (t<0 uses the other neighbour)
            tool.update(dx=-2 * t0 * W / 2.0, dy=0.0, width=W, height=H)
            y2 = self.pos(sample_vertex)[axis]
            t_star = -t0 * (target - y0) / (y2 - y0)
            t0 = -t0
        tool.update(dx=(t_star - t0) * W / 2.0, dy=0.0, width=W, height=H)
        tool.commit()
        tool.deactivate()
        return self.pos(sample_vertex)[axis]

    def loop_vertices(self, edges):
        out = set()
        for e in edges:
            out.update(self.mesh.edge_vertices(e))
        return out

    def connect(self, edges):
        self.n_tool_calls["connect"] += 1
        return connect_selected_edges(self.scene, set(edges))

    def loop_of(self, edge):
        return edge_loop(self.mesh, edge).as_set()

    def ring_of(self, edge):
        return edge_ring(self.mesh, edge).as_set()

    # -- measurement (read only) -------------------------------------------
    def boundary_vertices(self):
        out = set()
        for e in self.mesh.all_edge_ids():
            if len(self.mesh.edge_faces(e)) != 2:
                out.update(self.mesh.edge_vertices(e))
        return out

    def valence(self, v):
        return len(self.mesh.vertex_edges(v))

    def poles(self):
        """Interior vertices whose valence is not 4: [(vid, valence, pos)]."""
        bnd = self.boundary_vertices()
        out = []
        for v in self.mesh.all_vertex_ids():
            if v in bnd:
                continue
            k = self.valence(v)
            if k != 4:
                out.append((v, k, self.pos(v)))
        return out

    def metrics(self):
        m = self.mesh
        sizes = Counter(len(m.face_vertices(f)) for f in m.all_face_ids())
        poles = self.poles()
        half = [p for p in poles if p[2][0] > EPS]
        seam = [p for p in poles if abs(p[2][0]) <= EPS]
        return {
            "V": len(m.all_vertex_ids()), "E": len(m.all_edge_ids()), "F": len(m.all_face_ids()),
            "face_sizes": dict(sorted(sizes.items())),
            "poles_total": len(poles),
            "poles_half_x_gt0": len(half),
            "poles_on_seam": len(seam),
            "poles_by_valence": dict(sorted(Counter(p[1] for p in poles).items())),
            "boundary_vertices": len(self.boundary_vertices()),
            "symmetric": self.is_symmetric(),
            "euler": len(m.all_vertex_ids()) - len(m.all_edge_ids()) + len(m.all_face_ids()),
            "edges_without_two_faces": sum(1 for e in m.all_edge_ids() if len(m.edge_faces(e)) != 2),
            "loose_vertices": sum(1 for v in m.all_vertex_ids() if not m.vertex_edges(v)),
        }

    def is_symmetric(self):
        for v in self.mesh.all_vertex_ids():
            x, y, z = self.pos(v)
            if self.vertex_at((-x, y, z), tol=1e-6) is None:
                return False
        return True

    def border_length(self, faces):
        """Number of boundary edges of a face set (the 'ring count' of a patch)."""
        faces = set(faces)
        n = 0
        for f in faces:
            for e in self.mesh.face_edges(f):
                if sum(1 for g in self.mesh.edge_faces(e) if g in faces) == 1:
                    n += 1
        return n

    @staticmethod
    def poles_of(mesh):
        """Poles of an arbitrary mesh (used on throw-away copies). Face-less edges are ignored."""
        live = [e for e in mesh.all_edge_ids() if len(mesh.edge_faces(e)) > 0]
        bnd = set()
        for e in live:
            if len(mesh.edge_faces(e)) != 2:
                bnd.update(mesh.edge_vertices(e))
        val = Counter()
        for e in live:
            for v in mesh.edge_vertices(e):
                val[v] += 1
        return [(v, k, mesh.vertex_position(v)) for v, k in val.items() if v not in bnd and k != 4]

    def poles_in(self, pred):
        return [p for p in self.poles() if pred(p[2])]

    # -- screenshots --------------------------------------------------------
    def set_view(self, yaw_deg, pitch_deg, dist, target):
        self.cam.yaw = math.radians(yaw_deg)
        self.cam.pitch = math.radians(pitch_deg)
        self.cam.distance = dist
        self.cam.target = target
        self.cam.camera_revision += 1

    def _vertex_normal(self, v):
        acc = [0.0, 0.0, 0.0]
        for e in self.mesh.vertex_edges(v):
            for f in self.mesh.edge_faces(e):
                n = self.face_normal(f)
                acc = [acc[i] + n[i] for i in range(3)]
        return _norm(tuple(acc))

    def snap(self, name, annotate=True, highlight_faces=(), note=None):
        """Render the current mesh through the Playground window and save PNG.
        annotate: overlay red/blue discs on E-/N-poles (valence 5+ / 3) and mark highlighted
        faces' vertices; drawn on top of the frame in the screenshot only (not in the app)."""
        from PIL import Image, ImageDraw
        import pyglet
        from pyglet.gl import glFinish

        self.app.update(0.0)
        self.win._rebuild_vbo()
        self.win._rebuild_selection_vbo()
        for _ in range(3):
            self.win.switch_to()
            self.win.dispatch_events()
            self.win.dispatch_event("on_draw")
        glFinish()
        img = pyglet.image.get_buffer_manager().get_color_buffer().get_image_data()
        data = img.get_data("RGB", img.width * 3)
        im = Image.frombytes("RGB", (img.width, img.height), data).transpose(Image.FLIP_TOP_BOTTOM)
        if annotate:
            dr = ImageDraw.Draw(im, "RGBA")
            eye = self.cam.eye()
            hl = self.face_verts(highlight_faces)
            for v in hl:
                self._disc(dr, v, eye, (255, 200, 0, 255), 5, ring=True)
            for v, k, p in self.poles():
                col = (230, 40, 40, 255) if k >= 5 else (40, 110, 255, 255)
                self._disc(dr, v, eye, col, 8)
            dr.rectangle([0, 0, im.width, 34], fill=(0, 0, 0, 170))
            dr.text((10, 10), note or name, fill=(255, 255, 255, 255))
            dr.text((im.width - 330, 10),
                    "red = E-pole (5)   blue = N-pole (3)   yellow ring = patch", fill=(255, 255, 255, 255))
        out = self.shots / f"{name}.png"
        im.save(out)
        return out

    def _disc(self, dr, v, eye, col, r, ring=False):
        p = self.pos(v)
        n = self._vertex_normal(v)
        to_eye = _norm(_sub(eye, p))
        if n[0] * to_eye[0] + n[1] * to_eye[1] + n[2] * to_eye[2] <= 0.05:
            return  # back-facing: hidden by the surface
        s = self.cam.project_to_screen(p, W, H)
        if s is None:
            return
        x, y = s[0], H - s[1]
        if ring:
            dr.ellipse([x - r, y - r, x + r, y + r], outline=col, width=2)
        else:
            dr.ellipse([x - r, y - r, x + r, y + r], fill=col, outline=(255, 255, 255, 255))
