"""Morph evaluation and the replacement-surface provider (AD-013 H7), GL-free.

The lab's representation (`PROVISIONAL`, a lab convention, not a morph-target format — AD-021 §4.9
decides that home): the target is a second scene object whose Mesh was made as an ID-identical copy
of the base's Mesh (`Mesh.from_state(base.export_state())`). The artist sculpts it with the app's
own tools; a vertex of the base and the vertex with the same ID in the target form one pair, as long
as both meshes still have the same topology (`topology_signature`).

The target is *relative* by default and can be switched to *absolute* (Manu 2026-10-17, J-3; both
are kept, `relative`, key B in the lab; later a checkbox). Relative: what it stores is read as the offset `d = t − r`
from a reference `r`, the base as it was when the target was last changed. Editing the base later
moves the target along: the shape shown at 100 % is `b + d`, with `b` the base now. While `b == r`
that is exactly `t`. The reference is lab state of one session (not saved): after a reopen it is
the base as loaded (`PROVISIONAL`; the stored home is AD-021 §4.9).

Absolute: `t' = t` always. The mixture is also shown on the base while the *target* is the edit object
(`entry_surfaces`, viewport hook H7-E): `sync` is then called with the target's mesh, and the base — an
object entry of the viewport — is drawn as the mixture, so the weight keys work while sculpting the target.

Evaluation per vertex, weight `k` in whole percent (review CLAUDE-001 F-8, R-7), with `t'` = `t`
while `b == r`, else `b + (t − r)`:

- `k == 0`   no surface at all: the viewport draws the base itself (F-3);
- `k == 100` exactly `t'`;
- otherwise  `b + w·(t' − b)` with `w = k / 100` — exact where base and target agree and exactly
  mirrored for mirrored inputs. (`(1 − w)·b + w·t` moves unchanged regions by one rounding step.)

Jaw pose (`PROVISIONAL`, a temporary stand-in for the rig, Manu 2026-10-25): after the mixture the base's
vertices of the polygroup named "Kiefer" (or "Unterkiefer" / "Jaw") are turned about a hinge axis (X through
`jaw_pivot`) by `jaw_angle`, fading out over `JAW_FALLOFF_RINGS` edge rings outside the group. Morph first, pose
second: a "jaw open" or "smile" target is sculpted on the rest jaw and rides along with the pose. Like the weight it
is view state (no History, not saved) and shown on the base only.

The provider never writes base or target (H7-R2: display only). It wakes on the H7 triggers, on a
weight change and on a new status message of the app (`status_serial`): H7 reports no change of a
*non-edit* object's mesh (Apply transform on the target, its Undo), but every such path posts a
status (review F-10). Its own messages are posted only when the text changes, and the serial is
read again after its own post, so it never wakes itself (F-1).
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from typing import Optional

from core.mesh import Mesh

#: Weight range in whole percent.
MIN_WEIGHT, MAX_WEIGHT = 0, 100

#: `PROVISIONAL`: the mean target-minus-base shift, as a share of the base's bounding-box
#: diagonal, above which the lab says the target carries an offset (Ctrl+A on the placed target,
#: review F-2). A sculpted expression stays far below it.
OFFSET_WARNING_SHARE = 0.25

#: Polygroup names (case-insensitive) that mark the jaw; the first region of the base that matches is used.
JAW_REGION_NAMES = ("kiefer", "unterkiefer", "jaw")
#: `PROVISIONAL`: edge rings outside the jaw group over which the pose fades to zero.
JAW_FALLOFF_RINGS = 3
#: Whole degrees; the pose is limited to this range either way.
MAX_JAW_ANGLE = 60

MESSAGE_JAW_REGION = "Kiefer: keine Polygroup 'Kiefer' an der Basis (Auswahl, Strg+G, dann Strg+Alt+N: Name 'Kiefer')"
MESSAGE_MISSING = "Morph aus: Basis oder Ziel fehlt in der Szene"
MESSAGE_TOPOLOGY = (
    "Morph aus: Topologie von Basis und Ziel weicht ab (Strg+Z bis sie wieder gleich ist)"
)
MESSAGE_OFFSET = (
    "Morph: das Ziel ist als Ganzes gegen die Basis verschoben (Strg+A übernommen?) - Strg+Z"
)

EDITING_BASE = "base"
EDITING_TARGET = "target"
EDITING_OTHER = "other"


def topology_signature(mesh) -> tuple:
    """Vertex IDs, edges (ID + endpoints) and faces (ID + boundary), each sorted by ID.

    Equal signatures of two meshes mean an ID-preserving copy of the whole topology, so a vertex
    of one and the vertex with the same ID of the other are a well-defined pair. Sorted, so the
    insertion order of the containers does not matter; a rotated face loop counts as different
    (a false refusal, on the safe side — review F-15)."""
    return (
        tuple(sorted(int(v) for v in mesh.all_vertex_ids())),
        tuple(sorted((int(e), *(int(v) for v in mesh.edge_vertices(e))) for e in mesh.all_edge_ids())),
        tuple(sorted((int(f), *(int(v) for v in mesh.face_vertices(f))) for f in mesh.all_face_ids())),
    )


class _SignatureCache:
    """`topology_signature` of one mesh, recomputed only when its change journal (`Mesh.watch`) reports a
    touched edge or face or a vertex that appeared or vanished. Sorting every ID of a dense mesh (gollum,
    87 500 V) on each update cost ~0.7 s; a pose or weight step moves vertices only."""

    def __init__(self, mesh) -> None:
        self.mesh = mesh
        self._watch = mesh.watch()
        self._signature: Optional[tuple] = None

    def get(self) -> tuple:
        change = self._watch.take()
        if self._signature is None or self._topology_touched(change):
            self._signature = topology_signature(self.mesh)
        return self._signature

    def _topology_touched(self, change) -> bool:
        if change.edges or change.faces:
            return True
        mesh = self.mesh
        return any(before is None or not mesh.is_valid_vertex(vid) for vid, before in change.vertices.items())


def blend(base: tuple, target: tuple, weight: int) -> tuple:
    """One morphed position for a weight in whole percent (module docstring)."""
    if weight >= MAX_WEIGHT:
        return tuple(target)
    if weight <= MIN_WEIGHT:
        return tuple(base)
    w = weight / 100.0
    return tuple(b + w * (t - b) for b, t in zip(base, target))


def evaluate(base_mesh, target_mesh, weight: int) -> dict:
    """The morphed position of every base vertex (reference for tests and the bench)."""
    return {
        vid: blend(base_mesh.vertex_position(vid), target_mesh.vertex_position(vid), weight)
        for vid in base_mesh.all_vertex_ids()
    }


def clamp_weight(weight: int) -> int:
    return max(MIN_WEIGHT, min(MAX_WEIGHT, int(weight)))


def clamp_jaw_angle(angle: int) -> int:
    return max(-MAX_JAW_ANGLE, min(MAX_JAW_ANGLE, int(angle)))


def jaw_region(mesh):
    """The base's jaw polygroup (`JAW_REGION_NAMES`), or None."""
    regions = mesh.face_regions
    if regions is None:
        return None
    return next((r for r in regions.regions if r.name.lower() in JAW_REGION_NAMES), None)


def jaw_weights(mesh, region) -> dict:
    """Pose weight per vertex: 1 on the vertices of the group's live faces, falling off linearly to 0 over
    `JAW_FALLOFF_RINGS` edge rings outside it. Only vertices with a weight above 0 are in the result."""
    weights = {}
    frontier = []
    for fid in region.faces:
        if mesh.is_valid_face(fid):
            for vid in mesh.face_vertices(fid):
                if vid not in weights:
                    weights[vid] = 1.0
                    frontier.append(vid)
    if not frontier or JAW_FALLOFF_RINGS <= 0:
        return weights
    neighbours: dict = {}
    for eid in mesh.all_edge_ids():
        a, b = mesh.edge_vertices(eid)
        neighbours.setdefault(a, []).append(b)
        neighbours.setdefault(b, []).append(a)
    for ring in range(1, JAW_FALLOFF_RINGS + 1):
        w = 1.0 - ring / (JAW_FALLOFF_RINGS + 1)
        nxt = []
        for vid in frontier:
            for other in neighbours.get(vid, ()):
                if other not in weights:
                    weights[other] = w
                    nxt.append(other)
        frontier = nxt
    return weights


def rotate_about_x(point: tuple, pivot: tuple, angle: float) -> tuple:
    """`point` turned by `angle` (radians, right-hand rule) about the X axis through `pivot`."""
    c, s = math.cos(angle), math.sin(angle)
    y, z = point[1] - pivot[1], point[2] - pivot[2]
    return (point[0], pivot[1] + y * c - z * s, pivot[2] + y * s + z * c)


def pose_jaw(position: tuple, pivot: tuple, angle_degrees: float, weight: float) -> tuple:
    """One posed position. Positive `angle_degrees` is the right-hand rotation about +X: it opens a jaw that
    faces +Z (the chin swings down)."""
    return rotate_about_x(position, pivot, math.radians(angle_degrees * weight))


def _bbox_diagonal(positions) -> float:
    if not positions:
        return 0.0
    lo = [min(p[i] for p in positions) for i in range(3)]
    hi = [max(p[i] for p in positions) for i in range(3)]
    return math.dist(lo, hi)


class MorphSurfaceProvider:
    """H7 provider: `sync(mesh, selection) -> moved`, `surface_mesh`, `dirty` (module docstring).

    `scene` is read only. `base_id` / `target_id` are the two ObjectIds resolved once after the
    lab's scene file was loaded (`lab_scene.resolve_pair`). `post` posts a status line
    (`Application.set_status`), `serial` reads `Application.status_serial`."""

    def __init__(
        self,
        scene,
        base_id,
        target_id,
        *,
        post: Optional[Callable[[str], None]] = None,
        serial: Optional[Callable[[], int]] = None,
    ) -> None:
        self.scene = scene
        self.base_id = base_id
        self.target_id = target_id
        self._post = post
        self._serial = serial or (lambda: 0)
        self._seen_serial = self._serial()
        self._dirty = False
        self._signatures: dict = {}

        #: the mesh the viewport draws instead of the base's faces (None = the edit mesh itself)
        self.surface_mesh: Optional[Mesh] = None
        #: why there is no (correct) surface, or a warning; posted once per new text
        self.message: Optional[str] = None
        #: which object the app is editing at the last sync: EDITING_BASE / _TARGET / _OTHER
        self.editing = EDITING_BASE
        #: H7-E: replacement surfaces of object entries, `{key: Mesh}` and their moved vertices
        self.entry_surfaces: dict = {}
        self.entry_moved: dict = {}
        #: relative (default) or absolute target (module docstring); view state like the weight
        self.relative = True
        self._surface_ok = False
        self.last_update_ms: Optional[float] = None
        self.last_changed = 0
        #: why the jaw pose cannot be shown (None = fine)
        self._jaw_message: Optional[str] = None

        self._weight = MIN_WEIGHT
        #: jaw pose (module docstring): degrees, hinge point (None = derived from the group), view state
        self._jaw_angle = 0
        self._jaw_pivot: Optional[tuple] = None
        self._jaw_region = None
        self._jaw_weights: dict = {}
        self._jaw_signature: Optional[tuple] = None
        self._surface: Optional[Mesh] = None
        self._surface_signature: Optional[tuple] = None
        self._shown: dict = {}
        self._target_valid = False
        self._target_signature: Optional[tuple] = None
        self._target_positions: dict = {}
        #: the reference of the relative target (module docstring); None until the first read
        self._reference: Optional[dict] = None
        self._target_offset = False

    # -- weight (view state: no History, not saved) ---------------------------------------

    @property
    def weight(self) -> int:
        return self._weight

    def set_weight(self, weight: int) -> int:
        weight = clamp_weight(weight)
        if weight != self._weight:
            self._weight = weight
            self._dirty = True
        return self._weight

    # -- jaw pose (view state like the weight) ---------------------------------------------

    @property
    def jaw_angle(self) -> int:
        return self._jaw_angle

    @property
    def jaw_pivot(self) -> Optional[tuple]:
        return self._jaw_pivot

    @property
    def active(self) -> bool:
        """Something to show: a morph weight above 0 or a jaw pose."""
        return self._weight != MIN_WEIGHT or self._jaw_angle != 0

    def set_jaw_angle(self, angle: int) -> int:
        angle = clamp_jaw_angle(angle)
        if angle != self._jaw_angle:
            self._jaw_angle = angle
            self._dirty = True
        return self._jaw_angle

    def set_jaw_pivot(self, pivot: Optional[tuple]) -> None:
        pivot = None if pivot is None else tuple(float(c) for c in pivot)
        if pivot != self._jaw_pivot:
            self._jaw_pivot = pivot
            self._dirty = True

    def set_relative(self, relative: bool) -> bool:
        relative = bool(relative)
        if relative != self.relative:
            self.relative = relative
            self._dirty = True
        return self.relative

    # -- H7 -------------------------------------------------------------------------------

    @property
    def dirty(self) -> bool:
        """Read by the viewport every frame: an own request, or a new app status (F-10)."""
        return self._dirty or self._serial() != self._seen_serial

    @dirty.setter
    def dirty(self, value: bool) -> None:
        self._dirty = bool(value)

    def sync(self, mesh, selection) -> set:
        if self._serial() != self._seen_serial:
            # Something the viewport does not report may have changed the target (Apply, Undo).
            self._target_valid = False
        self._seen_serial = self._serial()
        self._dirty = False
        self.entry_surfaces, self.entry_moved = {}, {}

        objects = self.scene.objects
        base = objects.get(self.base_id)
        target = objects.get(self.target_id)
        if base is None or target is None:
            self.surface_mesh = None
            self._set_message(MESSAGE_MISSING)
            return set()
        if mesh is target.mesh:
            # Sculpting the target: it is drawn as itself, and the base beside it shows the
            # mixture at the current weight (H7-E), so the effect is seen while working.
            self.editing = EDITING_TARGET
            self.surface_mesh = None
            self._target_valid = False  # the edit mesh changes under us: read it every sync ...
            if not self.active:
                return set()
            rebuilt, changed = self._update_surface(base.mesh, target.mesh)
            self._target_valid = False  # ... and once more when the base is edited again
            if self._surface_ok:
                self.entry_surfaces = {self.base_id: self._surface}
                self.entry_moved = {self.base_id: set() if rebuilt else changed}
            return set()
        if mesh is not base.mesh:
            self.editing = EDITING_OTHER
            self.surface_mesh = None
            return set()
        self.editing = EDITING_BASE
        if not self.active and self._target_valid:
            self.surface_mesh = None
            return set()
        # At 0 % too when the target is not valid: the reference of the relative target must be
        # taken before the base is edited, not when the weight is first raised.
        rebuilt, changed = self._update_surface(mesh, target.mesh)
        if not self._surface_ok:
            return set()
        # A new surface object is rebuilt by the viewport from its current positions anyway.
        return set() if rebuilt else changed

    def _signature(self, mesh) -> tuple:
        cache = self._signatures.get(id(mesh))
        if cache is None or cache.mesh is not mesh:
            cache = self._signatures[id(mesh)] = _SignatureCache(mesh)
        return cache.get()

    def _update_surface(self, base_mesh, target_mesh) -> tuple:
        """Reads the target when it is not valid, then (weight > 0 and pairing intact) updates the
        shared surface Mesh to the mixture. Sets `surface_mesh` (the edit-mesh slot, only when the
        base is the edit mesh) and `_surface_ok`; returns (rebuilt, changed vertices)."""
        started = time.perf_counter()
        self._surface_ok = False
        base_signature = self._signature(base_mesh)
        if not self._target_valid:
            self._read_target(target_mesh, base_mesh, base_signature)
        if not self.active:
            self.surface_mesh = None
            return False, set()
        if base_signature != self._target_signature:
            self.surface_mesh = None
            self._set_message(MESSAGE_TOPOLOGY)
            return False, set()
        jaw, pivot = self._read_jaw(base_mesh, base_signature)
        self._set_message(self._jaw_message or (MESSAGE_OFFSET if self._target_offset else None))

        rebuilt = self._surface is None or base_signature != self._surface_signature
        if rebuilt:
            self._surface = Mesh.from_state(base_mesh.export_state())
            self._surface_signature = base_signature
            self._shown = {}
        surface, shown, target_positions, weight = self._surface, self._shown, self._target_positions, self._weight
        reference, relative = self._reference, self.relative
        angle = self._jaw_angle
        changed = set()
        for vid in base_mesh.all_vertex_ids():
            b, t = tuple(base_mesh.vertex_position(vid)), target_positions[vid]
            if relative:
                r = reference[vid]
                if b != r:
                    t = tuple(bi + (ti - ri) for bi, ti, ri in zip(b, t, r))
            position = blend(b, t, weight)
            if jaw:
                w = jaw.get(vid)
                if w:
                    position = pose_jaw(position, pivot, angle, w)
            if shown.get(vid) != position:
                shown[vid] = position
                surface.set_vertex_position(vid, position)
                changed.add(vid)
        self._surface_ok = True
        self.surface_mesh = surface if self.editing == EDITING_BASE else None
        self.last_changed = len(changed)
        self.last_update_ms = (time.perf_counter() - started) * 1000.0
        return rebuilt, changed

    def _read_jaw(self, base_mesh, base_signature: tuple) -> tuple:
        """(weights, pivot) of the pose, or ({}, None) when there is none to show; sets `_jaw_message`
        when a pose is asked for but cannot be shown."""
        self._jaw_message = None
        if self._jaw_angle == 0:
            return {}, None
        region = jaw_region(base_mesh)
        if region is None:
            self._jaw_message = MESSAGE_JAW_REGION
            return {}, None
        if region is not self._jaw_region or base_signature != self._jaw_signature:
            self._jaw_region, self._jaw_signature = region, base_signature
            self._jaw_weights = jaw_weights(base_mesh, region)
        pivot = self._jaw_pivot or self._default_pivot(base_mesh)
        return self._jaw_weights, pivot

    def _default_pivot(self, base_mesh) -> tuple:
        """Without a set hinge: the group's centre in X, its top in Y and its back in Z (a jaw facing +Z)."""
        points = [base_mesh.vertex_position(v) for v in self._jaw_weights if self._jaw_weights[v] == 1.0]
        return (
            sum(p[0] for p in points) / len(points),
            max(p[1] for p in points),
            min(p[2] for p in points),
        )

    def _read_target(self, target_mesh, base_mesh, base_signature: tuple) -> None:
        signature = self._signature(target_mesh)
        positions = {vid: tuple(target_mesh.vertex_position(vid)) for vid in target_mesh.all_vertex_ids()}
        self._target_valid = True
        if signature != base_signature:
            # No pairing: keep the reference, so that Undo back to equal topology resumes it.
            self._target_signature = signature
            self._target_positions = positions
            return
        if self._reference is None or self._target_signature != signature or positions != self._target_positions:
            # The target was shaped (or undone) against the base as it is now.
            self._reference = {vid: tuple(base_mesh.vertex_position(vid)) for vid in base_mesh.all_vertex_ids()}
        self._target_signature = signature
        self._target_positions = positions
        self._target_offset = self._offset_is_large(base_mesh)

    def _offset_is_large(self, base_mesh) -> bool:
        ids = list(base_mesh.all_vertex_ids())
        if not ids:
            return False
        mean = [0.0, 0.0, 0.0]
        for vid in ids:
            r, t = self._reference[vid], self._target_positions[vid]
            for i in range(3):
                mean[i] += t[i] - r[i]
        shift = math.hypot(*(m / len(ids) for m in mean))
        return shift > OFFSET_WARNING_SHARE * _bbox_diagonal([base_mesh.vertex_position(v) for v in ids])

    def _set_message(self, message: Optional[str]) -> None:
        if message == self.message:
            return
        self.message = message
        if message is not None and self._post is not None:
            self._post(message)
            # Our own post must not wake us again (review F-1).
            self._seen_serial = self._serial()
