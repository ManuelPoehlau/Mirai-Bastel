"""Symmetric Knife commit coordinator (AD-SYM-03 §10, slice 6b; headless, not wired).

`coordinate_knife(mesh, path, session_before) -> KnifeResolution` is the Knife's own commit under a
symmetry definition: **K-C + clip** (AD-SYM-03 §10.4–§10.7, AD-017 §13). The session path is clipped
at the seam to the working side (§10.5, §10.6), resolved **once** by the unchanged resolver, its kept
mutations are checked against the working side and replayed **mirrored** (placement at
`mirror_position`, no post-op snap), seam rule S1 is applied inside the same mutation, and the
completeness delta (D-strict) is checked. The Knife without a definition never reaches this module.

Why a module of its own and not a function of `symmetric_ops`: the replay is Knife-only (§10.4
item 2); the shared services (`SymmetryIndex`, `is_exact_plane`, `seam_after_split`, the completeness
report) are used as they are.

Contract:

- `mesh` is at `session_before` (the Knife never touches it before commit); `path` is the full session
  path, points in space included — the clip needs them (§10.6) and strips them itself.
- Success: the mesh holds the working side's cut and its exact mirror, the seam is maintained, the
  returned `KnifeResolution` is the resolver's report of the **clipped working-side cut** (residue F4 = A:
  `path_edges` are the working side's connecting cut edges, plus cut edges on the plane; mirror edges and
  seam halves are not in it; `kept_calls` are the source's calls, not the replayed ones). The caller still
  owes the integrity net (`check_commit`) and the single `MeshStateCommand`.
- Refusal: `SymmetryRefusal` (a `KnifeRefusal`) with a status text; **the coordinator itself has taken
  every mutation back** (`load_state(session_before)`), so the mesh is the session start whatever the
  caller does next. Any other exception also leaves the mesh restored before it propagates.
- Exactness (AR-1, INV-5): sides are exact signs of the plane coordinate, no tolerance; an exact plane
  only (`is_exact_plane`), any of ±X, ±Y, ±Z through the origin.

Dependency direction: `symmetric_knife` -> `symmetric_ops`, `symmetry_coordination`, `symmetry`,
`topology.knife_resolve`, `core`; never `application`, never `topology.knife` (the tool gets this
function injected at `begin`, and recognises its refusals by `KnifeRefusal.commit_refusal`).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core import EdgeId, FaceId, VertexId
from core.mesh import Mesh, MeshError, SymmetryDefinition

from .symmetric_ops import (
    TEXT_DELTA,
    TEXT_NON_EXACT_PLANE,
    TEXT_UNPAIRED,
    SymmetryRefusal,
    _require_definition,
)
from .symmetry import mirror_position
from .symmetry_coordination import (
    SymmetryIndex,
    completeness_report,
    delta_check,
    is_exact_plane,
    seam_after_split,
)
from .topology.knife_resolve import (
    KeptCall,
    KeptSplitEdge,
    KeptSplitFace,
    KnifeResolution,
    is_break,
    is_chain_end,
    resolve_cross_face,
)

#: Refusal texts of the Knife's commit (visible status line, each says what happened and what to do).
#: Engineering defaults (AD-SYM-03 §10, slice 6b); the Artist sees them in the 6c practical test.
#: `TEXT_UNPAIRED`, `TEXT_DELTA` and `TEXT_NON_EXACT_PLANE` are `symmetric_ops`'s.
TEXT_KNIFE_PLANE_IN_FACE = (
    "Symmetrie: Der Schnitt kreuzt die Mitte innerhalb einer Fläche (kein Punkt auf der Mitte zum Kappen) — "
    "den Schnitt über einen Punkt auf der Mitte führen, auf einer Seite bleiben oder Symmetrie "
    "ausschalten (Shift+S)"
)
TEXT_KNIFE_SEED_LOST = (
    "Symmetrie: Geschlossene Schleife über die Mitte — ihr Startpunkt im Innern einer Fläche würde mit "
    "gekappt, die nächste Kette hängt daran — die Schleife auf einer Seite beginnen oder Symmetrie "
    "ausschalten (Shift+S)"
)
TEXT_KNIFE_ON_PLANE = (
    "Symmetrie: Der Schnitt liegt in einer Fläche auf oder über der Mitte — nichts geändert; abseits der "
    "Mitte schneiden oder Symmetrie ausschalten (Shift+S)"
)
TEXT_KNIFE_OTHER_SIDE = (
    "Symmetrie: Der Schnitt greift auf die Gegenseite — nichts geändert; auf der Arbeitsseite bleiben "
    "oder Symmetrie ausschalten (Shift+S)"
)
TEXT_KNIFE_UNKNOWN_CALL = (
    "Symmetrie: Der Schnitt enthält einen Schritt, der sich nicht spiegeln lässt — nichts geändert; "
    "Symmetrie ausschalten (Shift+S)"
)
TEXT_KNIFE_SELF_PARTNER_EDGE = (
    "Symmetrie: Der Schnitt trifft eine Kante, die die Mitte kreuzt — nichts geändert; abseits davon "
    "schneiden oder Symmetrie ausschalten (Shift+S)"
)
TEXT_KNIFE_COLLISION = (
    "Symmetrie: Die Spiegelseite wäre schon vom Schnitt getroffen — nichts geändert; auf einer Seite "
    "schneiden oder Symmetrie ausschalten (Shift+S)"
)
TEXT_KNIFE_MIRROR_FAILED = (
    "Symmetrie: Der Schnitt lässt sich auf der Spiegelseite nicht eindeutig wiederholen — nichts "
    "geändert; anders schneiden oder Symmetrie ausschalten (Shift+S)"
)


#: The click-time refusals' own wording (slice 6c, F3 = A; engineering defaults for the Artist test): the commit's
#: `TEXT_UNPAIRED` speaks of a "selection", which a hovered Knife point is not. Same reasons, same rules.
TEXT_KNIFE_TARGET_UNPAIRED = (
    "Symmetrie: Dieser Punkt hat keinen Spiegelpartner — an einer Stelle mit Partner schneiden oder "
    "Symmetrie ausschalten (Shift+S)"
)
TEXT_KNIFE_FACE_UNPAIRED = (
    "Symmetrie: Der Schnitt läuft durch eine Fläche ohne Spiegelpartner — an einer Stelle mit Partner "
    "schneiden oder Symmetrie ausschalten (Shift+S)"
)


class KnifeRefusal(SymmetryRefusal):
    """A `SymmetryRefusal` of the Knife's commit. `commit_refusal` is how `KnifeTool` (which imports
    nothing from symmetry) recognises a refusal of an injected coordinator: it takes the commit back,
    shows `str(exc)` and pushes no history; any other exception propagates. `violations[0]` is the
    refusal's reason in English (diagnostics, not shown)."""

    commit_refusal = True

    def __init__(self, text: str, reason: str, violations: tuple[str, ...] = ()) -> None:
        super().__init__(text, (reason,) + tuple(violations))
        self.reason = reason


# ---------------------------------------------------------------------------------------------
# Sides (exact signs, AR-1)
# ---------------------------------------------------------------------------------------------

def _signed_distance(definition: SymmetryDefinition, position) -> float:
    # The formula of `symmetry_coordination` / `symmetry` (the sum over all three axes).
    return sum((p - o) * n for p, o, n in zip(position, definition.plane_point, definition.plane_normal))


def _sign(x: float) -> int:
    return (x > 0.0) - (x < 0.0)


def _record_position(mesh: Mesh, p: dict):
    """World position of a path record on the session-start mesh (`knife_preview.target_position`'s rule,
    which the planner and the resolver use: the vertex, `p0 + t * (p1 - p0)` on an edge, a face point's
    own position, a point in space)."""
    kind = p["kind"]
    if kind == "vertex":
        return tuple(mesh.vertex_position(p["vertex_id"]))
    if kind == "edge":
        va, vb = mesh.edge_vertices(p["edge_id"])
        p0, p1 = mesh.vertex_position(va), mesh.vertex_position(vb)
        t = p["t"]
        return tuple(p0[i] + t * (p1[i] - p0[i]) for i in range(3))
    return tuple(p["position"])    # "face" and "space"


def _is_mesh_record(p: dict) -> bool:
    return p["kind"] in ("vertex", "edge", "face")


@dataclass
class ClippedPath:
    """The session path after the side rule and the clip (§10.5, §10.6).

    `side` is the working side (+1: the normal's side, -1: the opposite), 0 when no mesh record lies off
    the plane (the first kept call decides then). `path` is the clipped path **with** the working side's
    points in space still in it; `coordinate_knife` strips them for the resolver."""

    side: int
    path: list = field(default_factory=list)
    stretches: int = 0            # maximal other-side stretches replaced by one pen lift
    dropped: int = 0              # records dropped (mesh records and points in space)
    dropped_space: int = 0
    rotated: int = 0              # cyclic chains rotated before the clip

    @property
    def clipped(self) -> bool:
        """Mesh records were dropped or a chain was rotated (a dropped point in space alone changes
        nothing the resolver sees)."""
        return self.dropped > self.dropped_space or self.rotated > 0


def clip_path(mesh: Mesh, definition: SymmetryDefinition, path: list[dict]) -> ClippedPath:
    """Working side and clipped session path (AD-SYM-03 §10.5, §10.6). Pure: `mesh` is the session-start
    mesh, nothing is changed.

    - side of a record: the exact sign of its plane coordinate; 0 = on the plane (a seam vertex, an edge
      point on a seam edge): it belongs to both sides;
    - working side: the side of the first **mesh** record off the plane (clicked or a planner crossing; a
      point in space does not choose: its plane coordinate is the arbitrary depth `space_point` gives it);
    - a cut segment (no break between) from a working-side record straight to an other-side record
      crosses the plane inside a face, there is no seam record to clip at -> refused (item 9);
    - a cyclic chain holding an other-side record is first rotated to start right after its last one, so
      its closing segment stays a cut; if the chain's interior start is the seed the next chain continues
      from, the clip would lose it -> refused;
    - every maximal stretch of other-side records (mesh records and points in space) becomes one pen
      lift; the breaks inside it go with it; a record on the plane ends or starts a run there.

    Without a mesh record off the plane nothing is clipped. Raises `KnifeRefusal`."""
    side = {id(p): _sign(_signed_distance(definition, _record_position(mesh, p))) for p in path if not is_break(p)}
    of = lambda p: side[id(p)]  # noqa: E731
    w = next((of(p) for p in path if _is_mesh_record(p) and of(p)), 0)
    if not w:
        return ClippedPath(0, list(path))
    crossing = {w, -w}

    prev = first = None
    for p in path:                         # 1. a cut straight across the plane
        if is_break(p):
            if is_chain_end(p):
                if p.get("cyclic") and prev is not None and first is not None and {of(prev), of(first)} == crossing:
                    raise KnifeRefusal(TEXT_KNIFE_PLANE_IN_FACE, "plane crossed inside a face (closing segment)")
                first = None
            prev = None
            continue
        if first is None:
            first = p
        if prev is not None and {of(prev), of(p)} == crossing:
            raise KnifeRefusal(TEXT_KNIFE_PLANE_IN_FACE, "plane crossed inside a face")
        prev = p

    result = ClippedPath(w)
    out, cur = [], []                      # 2. rotate cyclic chains that hold an other-side record
    for i, p in enumerate(path):
        if not is_chain_end(p):
            cur.append(p)
            continue
        if p.get("cyclic") and any(of(q) == -w for q in cur if not is_break(q)):
            j = max(k for k, q in enumerate(cur) if not is_break(q) and of(q) == -w)
            start = cur[0]
            nxt = path[i + 1] if i + 1 < len(path) else None
            if start["kind"] == "face" and nxt is not None and not is_break(nxt) and nxt["pid"] == start["pid"]:
                raise KnifeRefusal(TEXT_KNIFE_SEED_LOST, "clipped closed chain whose interior start is a seed")
            cur = cur[j + 1:] + cur[:j + 1]
            result.rotated += 1
            p = {"kind": "break", "reason": "lift", "clip": True}   # no closing segment any more
        out.extend(cur)
        out.append(p)
        cur = []
    out.extend(cur)

    clipped, off = [], False               # 3. clip
    for p in out:
        if is_break(p):
            if not off:
                clipped.append(p)
            continue
        if of(p) == -w:
            if not off:
                result.stretches += 1
                if clipped and not is_chain_end(clipped[-1]):
                    clipped.append({"kind": "break", "reason": "lift", "clip": True})
            off = True
            result.dropped += 1
            result.dropped_space += p["kind"] == "space"
            continue
        off = False
        clipped.append(p)
    result.path = clipped
    return result


# ---------------------------------------------------------------------------------------------
# The kept-call guard (§10.5): the net under the clip
# ---------------------------------------------------------------------------------------------

def _face_side(distances) -> int | None:
    """+1 / -1: a face of the normal's / the opposite side (vertices on the plane allowed, one off);
    None: in the plane or across it (item 9: nothing can be cut there)."""
    lo, hi = min(distances), max(distances)
    if lo >= 0.0 and hi > 0.0:
        return 1
    if hi <= 0.0 and lo < 0.0:
        return -1
    return None


def _guard_kept(mesh: Mesh, definition: SymmetryDefinition, kept: tuple[KeptCall, ...], w: int) -> int:
    """Every kept `split_edge` must lie on the working side or on the plane, every kept `split_face` in a
    face of the working side; a face on or spanning the plane is refused (item 9), an unknown kind too
    (fail-closed, AD-017 §13 item 6). Returns the working side (taken from the first kept call off the
    plane when no record chose it)."""
    for call in kept:
        if isinstance(call, KeptSplitEdge):
            s = _sign(_signed_distance(definition, call.position))
        elif isinstance(call, KeptSplitFace):
            distances = [_signed_distance(definition, mesh.vertex_position(v))
                         for v in set(call.face_1_vertices) | set(call.face_2_vertices)]
            if not distances:
                raise KnifeRefusal(TEXT_KNIFE_UNKNOWN_CALL, "kept split_face without halves (malformed report, fail-closed)")
            s = _face_side(distances)
            if s is None:
                raise KnifeRefusal(TEXT_KNIFE_ON_PLANE, "kept cut inside a face on or spanning the plane (item 9)")
        else:
            raise KnifeRefusal(TEXT_KNIFE_UNKNOWN_CALL, f"unknown kept call {getattr(call, 'op', call)!r} (fail-closed)")
        if s and not w:
            w = s
        if s and s != w:
            raise KnifeRefusal(TEXT_KNIFE_OTHER_SIDE, "kept mutation on the other side (side rule)")
    return w


# ---------------------------------------------------------------------------------------------
# Strict replay (AD-017 §13 item 6)
# ---------------------------------------------------------------------------------------------

class _Replay:
    """Applies the mirror of every kept call, in call order, to the mesh that already holds the source's
    cut. Original elements map through the **session-start** partners (taken as plain maps before anything
    is cut, so they stay readable after the source cut); elements the source created map through the call
    results. A seam edge is its own partner and is not split again (S1 maintains the seam)."""

    def __init__(self, mesh: Mesh, definition: SymmetryDefinition, index: SymmetryIndex) -> None:
        self.mesh = mesh
        self.definition = definition
        self.vertex_partner = {v: index.vertex_partner(v) for v in mesh.all_vertex_ids()}
        self.edge_partner = {e: index.edge_partner(e) for e in mesh.all_edge_ids()}
        self.face_partner = {f: index.face_partner(f) for f in mesh.all_face_ids()}
        self._split_by: dict = {}
        self.vmap: dict = {}
        self.emap: dict = {}
        self.fmap: dict = {}

    def mirror(self, position):
        return tuple(mirror_position(tuple(position), self.definition.plane_point, self.definition.plane_normal))

    def mv(self, v: VertexId) -> VertexId:
        w = self.vmap[v] if v in self.vmap else self.vertex_partner.get(v)
        if w is None:
            raise KnifeRefusal(TEXT_UNPAIRED, "vertex without partner")
        return w

    def me(self, e: EdgeId) -> EdgeId:
        w = self.emap[e] if e in self.emap else self.edge_partner.get(e)
        if w is None:
            raise KnifeRefusal(TEXT_UNPAIRED, "edge without partner")
        return w

    def mf(self, f: FaceId) -> FaceId:
        w = self.fmap[f] if f in self.fmap else self.face_partner.get(f)
        if w is None:
            raise KnifeRefusal(TEXT_UNPAIRED, "face without partner")
        return w

    def edge_ends(self, edge_id: EdgeId) -> tuple[VertexId, VertexId]:
        """The ends of a split edge **as it was split**, in Core's order (first end, second end). The report
        names the edge and its halves, not its ends, and the orientation of the edges `split_face` creates is
        not semantic in Core; but `split_edge` returns the half at the first end first, so the ends follow from
        the halves: the first end of `half_1` and the second end of `half_2`, recursively until an edge that
        still exists (read from the mesh — the source's cut, before the first mirrored mutation, never
        changes the ends of an existing edge)."""
        call = self._split_by.get(edge_id)
        if call is None:
            return tuple(self.mesh.edge_vertices(edge_id))
        return self.edge_ends(call.half_1)[0], self.edge_ends(call.half_2)[1]

    def run(self, kept: tuple[KeptCall, ...]) -> int:
        self._split_by = {c.edge_id: c for c in kept if isinstance(c, KeptSplitEdge)}
        n = 0
        for call in kept:
            if isinstance(call, KeptSplitEdge):
                n += self._split_edge(call)
            elif isinstance(call, KeptSplitFace):
                n += self._split_face(call)
            else:
                raise KnifeRefusal(TEXT_KNIFE_UNKNOWN_CALL, f"unknown kept call {getattr(call, 'op', call)!r} (fail-closed)")
        return n

    def _split_edge(self, call: KeptSplitEdge) -> int:
        mesh, d = self.mesh, self.definition
        a, b = self.edge_ends(call.edge_id)    # the halves are (a, vertex) and (vertex, b), Core's order
        e2 = self.me(call.edge_id)
        if e2 == call.edge_id:
            # Its own partner: a seam edge (both ends on the plane) is not split again. One that crosses
            # the plane (N5) lies only in self-mirrored faces and would map its halves onto themselves,
            # not crossed: refused instead.
            if any(_signed_distance(d, mesh.vertex_position(v)) != 0.0 for v in (a, b)):
                raise KnifeRefusal(TEXT_KNIFE_SELF_PARTNER_EDGE, "self-partner edge crossing the plane (N5)")
            if _signed_distance(d, call.position) != 0.0:
                raise KnifeRefusal(TEXT_KNIFE_SELF_PARTNER_EDGE, "self-partner edge split off the plane")
            self.vmap[call.vertex] = call.vertex
            self.emap[call.half_1] = call.half_1
            self.emap[call.half_2] = call.half_2
            return 0
        a2 = self.mv(a)
        self.mv(b)                      # both ends need a partner (raises otherwise)
        if not mesh.is_valid_edge(e2):
            raise KnifeRefusal(TEXT_KNIFE_COLLISION, "mirror edge already cut by the source")
        try:
            vertex, x1, x2 = mesh.split_edge(e2, 0.5)
        except (MeshError, KeyError) as exc:
            raise KnifeRefusal(TEXT_KNIFE_MIRROR_FAILED, f"mirror edge split refused ({type(exc).__name__})") from None
        # Placement at replay: the mirror vertex sits exactly at the mirror of the source vertex (t = 0.5
        # above only chose a valid place on the edge to start from).
        mesh.set_vertex_position(vertex, self.mirror(call.position))
        self.vmap[call.vertex] = vertex
        straight = a2 in mesh.edge_vertices(x1)
        self.emap[call.half_1], self.emap[call.half_2] = (x1, x2) if straight else (x2, x1)
        return 1

    def _split_face(self, call: KeptSplitFace) -> int:
        mesh = self.mesh
        g = self.mf(call.face_id)
        if g == call.face_id:
            raise KnifeRefusal(TEXT_KNIFE_ON_PLANE, "cut inside a self-mirrored face")
        if not mesh.is_valid_face(g):
            raise KnifeRefusal(TEXT_KNIFE_COLLISION, "mirror face already cut by the source")
        a2, b2 = self.mv(call.a), self.mv(call.b)
        try:
            new_vertices, new_edges, g1, g2 = mesh.split_face(g, a2, b2, [self.mirror(p) for p in call.positions])
        except (MeshError, KeyError) as exc:
            raise KnifeRefusal(TEXT_KNIFE_MIRROR_FAILED, f"mirror face cut refused ({str(exc)[:40]})") from None
        self.vmap.update(zip(call.new_vertices, new_vertices))
        self.emap.update(zip(call.new_edges, new_edges))
        # Match the two halves by inclusion, not equality: a seam split the source made *after* this call
        # already put its (self-mirrored) vertex into the mirror face too, so a mirror half can hold plane
        # vertices the recorded half did not have yet.
        c1 = {self.mv(v) for v in call.face_1_vertices}
        c2 = {self.mv(v) for v in call.face_2_vertices}
        h1, h2 = set(mesh.face_vertices(g1)), set(mesh.face_vertices(g2))
        straight, crossed = c1 <= h1 and c2 <= h2, c1 <= h2 and c2 <= h1
        if straight == crossed:
            raise KnifeRefusal(TEXT_KNIFE_MIRROR_FAILED, "mirror halves not distinguishable")
        self.fmap[call.face_1], self.fmap[call.face_2] = (g1, g2) if straight else (g2, g1)
        return 1


def _seam_after_kept_splits(definition: SymmetryDefinition, kept: tuple[KeptCall, ...]) -> SymmetryDefinition:
    """Seam rule S1 for every kept split of a (then current) seam edge, in call order."""
    for call in kept:
        if isinstance(call, KeptSplitEdge) and call.edge_id in definition.seam_edges:
            definition = seam_after_split(definition, {call.edge_id: (call.half_1, call.half_2)})
    return definition


# ---------------------------------------------------------------------------------------------
# The coordinator
# ---------------------------------------------------------------------------------------------

def _refuse_unpaired_targets(index: SymmetryIndex, path: list[dict]) -> None:
    """F3 = A at the commit (the net under the click-time refusal of 6c): every mesh record of the
    clipped path needs a mirror partner."""
    for p in path:
        if is_break(p) or p["kind"] == "space":
            continue
        kind = p["kind"]
        partner = (index.vertex_partner(p["vertex_id"]) if kind == "vertex"
                   else index.edge_partner(p["edge_id"]) if kind == "edge"
                   else index.face_partner(p["face_id"]))
        if partner is None:
            raise KnifeRefusal(TEXT_UNPAIRED, f"{kind} target without partner")


class SymmetricKnifeView:
    """What a running symmetric Knife session reads from the symmetry, built once at `begin` (6c).

    The mesh does not change during a session (the Knife cuts at commit), so one `SymmetryIndex` serves
    every hover and click: no index rebuild and no resolve per frame. Everything here is the commit's own
    logic — `clip` is `clip_path`, the unpaired rule is the one `coordinate_knife` applies to the clipped
    path, the face rules are `_guard_kept`'s — so the preview and the click-time refusals (F3 = A) cannot
    show or refuse something the commit does differently (INV-11). Raises `KnifeRefusal`
    (`TEXT_NON_EXACT_PLANE`) when the plane is not exact: no session is started then.

    `KnifeTool` and `knife_preview` take this object as an opaque duck-typed argument (they import
    nothing from symmetry)."""

    def __init__(self, mesh: Mesh) -> None:
        self.mesh = mesh
        self.definition = _require_definition(mesh)
        if not is_exact_plane(self.definition):
            raise KnifeRefusal(TEXT_NON_EXACT_PLANE, "non-exact plane")
        self.index = SymmetryIndex(mesh)

    def side(self, position) -> int:
        """Exact sign of the plane coordinate (AR-1): +1, -1, 0 on the plane."""
        return _sign(_signed_distance(self.definition, position))

    def mirror(self, position) -> tuple:
        return tuple(mirror_position(tuple(position), self.definition.plane_point, self.definition.plane_normal))

    def clip(self, path: list[dict]) -> ClippedPath:
        """The commit's own side rule and clip (`clip_path`); raises `KnifeRefusal`."""
        return clip_path(self.mesh, self.definition, path)

    def refusal(self, path: list[dict], cut_faces: dict) -> KnifeRefusal | None:
        """The click-time refusal (F3 = A; P2) for the session path `path` (the path with the click
        added), or None. It is the front part of the commit, nothing else: the clip (a cut across the
        plane inside a face, a lost seed), the unpaired rule on the clipped path's mesh records, and for
        every cut stretch that survives the clip the face it cuts — it needs a partner, must not lie on or
        across the plane (item 9) and must lie on the working side. What only the resolve shows (collision,
        mirror failure, the completeness delta) stays a refusal at Enter.

        `cut_faces`: `frozenset({pid_a, pid_b}) -> FaceId`, the face a cut stretch lies in (the tool's
        click-time `_link`); a stretch without an entry is not checked."""
        try:
            clip = self.clip(path)
        except KnifeRefusal as exc:
            return exc
        points = [p for p in clip.path if p["kind"] != "space"]
        try:
            _refuse_unpaired_targets(self.index, points)
        except KnifeRefusal as exc:
            return KnifeRefusal(TEXT_KNIFE_TARGET_UNPAIRED, exc.reason)
        w = clip.side
        for a, b in _cut_pairs(clip.path):
            face = cut_faces.get(frozenset((a["pid"], b["pid"])))
            if face is None:
                continue
            if self.index.face_partner(face) is None:
                return KnifeRefusal(TEXT_KNIFE_FACE_UNPAIRED, "cut face without partner")
            s = _face_side([_signed_distance(self.definition, self.mesh.vertex_position(v))
                            for v in self.mesh.face_vertices(face)])
            if s is None:
                return KnifeRefusal(TEXT_KNIFE_ON_PLANE, "cut inside a face on or spanning the plane (item 9)")
            if not w:
                w = s
            elif s != w:
                return KnifeRefusal(TEXT_KNIFE_OTHER_SIDE, "cut in a face of the other side (side rule)")
        return None


def _cut_pairs(path: list[dict]):
    """The point pairs the resolver cuts between in `path`: consecutive points of a chain (not across a
    break) and the closing segment of a loop closed as one (`KnifeTool.cut_segments`' rule). Points in space
    take part like any other record; their stretches are breaks in a stored path, so no pair arises."""
    prev = first = None
    for p in path:
        if is_chain_end(p):
            if p.get("cyclic") and prev is not None and first is not None and prev is not first:
                yield prev, first
            prev = first = None
            continue
        if is_break(p):
            prev = None
            continue
        if prev is not None and prev is not p:
            yield prev, p
        if first is None:
            first = p
        prev = p


def coordinate_knife(mesh: Mesh, path: list[dict], session_before: dict) -> KnifeResolution:
    """The symmetric Knife commit (module docstring): side rule and clip, one resolve, kept-call guard,
    strict mirrored replay, seam rule S1, completeness delta. Raises `KnifeRefusal` (a `SymmetryRefusal`)
    with the mesh restored to `session_before`; returns the resolver's `KnifeResolution` of the clipped
    working-side cut otherwise. Pushes nothing."""
    definition = _require_definition(mesh)
    if not is_exact_plane(definition):
        raise KnifeRefusal(TEXT_NON_EXACT_PLANE, "non-exact plane")
    index = SymmetryIndex(mesh)                    # partners come from the session start (N8)
    before = completeness_report(mesh, index)
    clip = clip_path(mesh, definition, path)
    resolver_path = [p for p in clip.path if p["kind"] != "space"]
    _refuse_unpaired_targets(index, resolver_path)
    partners = _Replay(mesh, definition, index)    # read before the first cut, like the index

    try:
        res = resolve_cross_face(mesh, resolver_path, session_before)
        kept = res.kept_calls
        if not kept:
            return res                             # nothing cut: nothing to mirror, the mesh is untouched
        w = _guard_kept(mesh, definition, kept, clip.side)
        if not w:
            raise KnifeRefusal(TEXT_KNIFE_ON_PLANE, "no kept call off the plane (item 9)")
        partners.run(kept)
        mesh.symmetry_definition = _seam_after_kept_splits(definition, kept)
        delta = delta_check(before, completeness_report(mesh))
        if not delta.ok:
            raise KnifeRefusal(TEXT_DELTA, "completeness delta (D-strict)", delta.violations)
        return res
    except BaseException:
        # Whatever went wrong, the source's cut and the replay's mutations are taken back as a whole.
        mesh.load_state(session_before)
        raise
