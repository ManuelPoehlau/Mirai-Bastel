"""Knife session render data (WP-06 Slice B7; WP-KNIFE-01 S2) — headless, no GPU.

What a running Knife session shows, as plain world positions. Since S2 the
mesh is not cut while clicking (`KnifeTool` keeps a virtual path, resolved at
commit), so the session is drawn from its path:

- `placed_points`: every point placed so far, once each (vertex, edge point
  or — S3 — interior point; an earlier point clicked again, or a closed
  chain's start continuing the next one, is not drawn twice);
- `path_segments`: the segments commit will cut, between their points'
  positions (a skip along an existing edge is not drawn — it cuts nothing;
  a chain closed by clicking its start draws its closing segment);
- `start_point`: the last placed point, where the next segment starts (F3);
- `prospective_point`: the hovered target — the vertex, the point at `t` on
  the hovered edge (G1, also before the first click), the point inside the
  hovered face (S3, the Lab's face-hover marker), or an own point (the snap:
  own points and vertices look the same);
- `target_edge`: the hovered edge;
- `line_preview`: from the start point to the prospective point;
- `prospective_crossings`: where the hovered segment crosses edges on its
  way (WP-KNIFE-01 S4, the planner's crossing dots).

WP-KNIFE-01 S4 (Manu, 2026-10-02): a point in empty space (`{"kind":
"space", "position"}`) gets no marker and no segment once placed — only the
cuts commit will make stay drawn — but it can be the start point (the
rubber band runs from it) and the prospective point (the cursor in space).

`Application` builds it from `KnifeTool.path` and hands it to the viewport's
tool layers; tests read it directly. Under a symmetry definition (AD-SYM-03 §10, slice 6c) the caller also hands the builder the
session's `SymmetricKnifeView` (`symmetry`): the drawn path is then split by the **commit's own clip**
(`symmetry.clip` is `clip_path`, never a second implementation) into the working side's part - the
fields above - its mirror image (`mirror_*`, every position through `mirror_position`) and the part
the commit will not cut (`clipped_*`: the other-side points and segments of the path, and a hovered
target on the other side with its line, edge and crossings). `refused` is the hovered target a click
would be refused for (F3 = A): its point, edge and the line from the start, drawn in the refused style.
With no `symmetry` all those fields are empty and the data is what it always was.

Invalid targets never reach this module
as a prospective target — the caller passes `target=None` for them, so there
is no preview point and no line (`PROVISIONAL`, mirrors the Playground's
"invalid → hover cleared").
"""

from __future__ import annotations

from dataclasses import dataclass

from core import EdgeId

Vec3 = tuple[float, float, float]
Segment = tuple[Vec3, Vec3]


@dataclass(frozen=True)
class KnifeRenderData:
    start_point: Vec3 | None
    prospective_point: Vec3 | None
    target_edge: Segment | None
    line_preview: Segment | None
    path_segments: tuple[Segment, ...]
    placed_points: tuple[Vec3, ...] = ()
    prospective_crossings: tuple[Vec3, ...] = ()
    # -- AD-SYM-03 slice 6c (empty without a symmetry view) ------------------------------------------
    # The mirror image of the working side's fields above (same meaning, `mirror_position` of each):
    mirror_start_point: Vec3 | None = None
    mirror_prospective_point: Vec3 | None = None
    mirror_target_edge: Segment | None = None
    mirror_line_preview: Segment | None = None
    mirror_path_segments: tuple[Segment, ...] = ()
    mirror_placed_points: tuple[Vec3, ...] = ()
    mirror_prospective_crossings: tuple[Vec3, ...] = ()
    # What the commit will not cut (the other side of the clip): path points / segments, and the hovered
    # target on the other side with its crossings (points) and its edge and line (segments):
    clipped_points: tuple[Vec3, ...] = ()
    clipped_segments: tuple[Segment, ...] = ()
    clipped_hover_points: tuple[Vec3, ...] = ()
    clipped_hover_segments: tuple[Segment, ...] = ()
    # The hovered target a click is refused for (F3 = A): its point, and its edge and the line from the start:
    refused_points: tuple[Vec3, ...] = ()
    refused_segments: tuple[Segment, ...] = ()
    #: +1 / -1 the working side (the normal's side or the opposite), 0 undecided or no symmetry.
    working_side: int = 0


def target_position(mesh, target: dict) -> Vec3 | None:
    """World position of a knife target or path record: the vertex itself, the
    point at `t` along the edge (same lerp the Playground preview uses), or a
    face point's own position (S3). None for other kinds and for handles the
    mesh no longer knows."""
    kind = target.get("kind")
    if kind == "face" and target.get("position") is not None and mesh.is_valid_face(target["face_id"]):
        return tuple(target["position"])
    if kind == "space" and target.get("position") is not None:
        return tuple(target["position"])
    if kind == "vertex" and mesh.is_valid_vertex(target["vertex_id"]):
        return tuple(mesh.vertex_position(target["vertex_id"]))
    if kind == "edge" and mesh.is_valid_edge(target["edge_id"]):
        va, vb = mesh.edge_vertices(target["edge_id"])
        p0 = mesh.vertex_position(va)
        p1 = mesh.vertex_position(vb)
        t = target["t"]
        return tuple(p0[i] + t * (p1[i] - p0[i]) for i in range(3))
    return None


def _segment(mesh, edge_id: EdgeId) -> Segment:
    va, vb = mesh.edge_vertices(edge_id)
    return (tuple(mesh.vertex_position(va)), tuple(mesh.vertex_position(vb)))


#: A pen lift is drawn like a chain end that is not closed as a loop (the loop below ends at "closed").
_DRAWN_LIFT = {"kind": "break", "reason": "closed", "cyclic": False}


def _drawn(path):
    return [_DRAWN_LIFT if p["kind"] == "break" and p.get("reason") == "lift" else p for p in path]


def _walk(mesh, path):
    """The drawn geometry of `path`: `positions` pid -> position, `placed` (pid, position) once per point,
    `segments` the cuts (a, b) between consecutive points of a chain (a closed loop's closing segment too)
    and `keys` the point-id pair of each segment (so two walks of one path can be compared)."""
    positions: dict = {}
    placed: list = []
    segments: list[Segment] = []
    keys: list = []
    prev = first = None
    prev_pid = first_pid = None
    for p in path:
        if p["kind"] == "break":
            if p.get("reason") == "closed":
                if p.get("cyclic") and prev is not None and first is not None and prev != first:
                    segments.append((prev, first))
                    keys.append(frozenset((prev_pid, first_pid)))
                first = first_pid = None
            prev = prev_pid = None
            continue
        if p["kind"] == "space":
            prev = prev_pid = None     # no marker, no segment: only the cuts stay drawn (S4)
            continue
        pos = target_position(mesh, p)
        if pos is None:
            prev = prev_pid = None
            continue
        if p["pid"] not in positions:
            positions[p["pid"]] = pos
            placed.append((p["pid"], pos))
        if prev is not None:
            segments.append((prev, pos))
            keys.append(frozenset((prev_pid, p["pid"])))
        if first is None:
            first, first_pid = pos, p["pid"]
        prev, prev_pid = pos, p["pid"]
    return positions, placed, segments, keys


def _mirror_segment(symmetry, segment):
    return None if segment is None else (symmetry.mirror(segment[0]), symmetry.mirror(segment[1]))


def build_knife_render_data(
    mesh,
    path,
    target: dict | None,
    highlight_edge: EdgeId | None,
    crossings=(),
    *,
    symmetry=None,
    refused: dict | None = None,
    pen_up: bool = False,
) -> KnifeRenderData:
    """`path` = `KnifeTool.path` (records incl. skip breaks); `target` = the
    valid prospective target or None (an own-point target `{"kind": "point",
    "pid"}` is looked up in `path`); `highlight_edge` = the hovered edge.
    Handles the mesh no longer knows are skipped, like the selection overlays
    (AD-001). `crossings` = the hovered segment's crossing positions (S4).

    `symmetry` (slice 6c): the session's `SymmetricKnifeView` - the working side's part, its mirror and the
    clipped part are built from the commit's own clip (module docstring). `refused`: the hovered target a
    click is refused for, drawn in the refused style. `pen_up`: the pen is lifted, no point starts the next
    segment - no start, no line (the symmetric fields are built that way; the plain data is cut by the
    caller, as before)."""
    # The Application hands the path with its pen lifts already drawn as chain ends; a symmetric session
    # (which also gets the raw path from a test) maps them itself so the clip and the walk agree.
    positions, placed_all, segments_all, keys_all = _walk(mesh, path if symmetry is None else _drawn(path))
    last = next((p for p in reversed(path) if p["kind"] != "break"), None)
    if last is not None and last["kind"] == "space":
        start_point = target_position(mesh, last)
    else:
        start_point = positions.get(last["pid"]) if last is not None else None
    if pen_up:
        start_point = last = None
    if target is None:
        prospective = None
    elif target.get("kind") == "point":
        prospective = positions.get(target.get("pid"))
    else:
        prospective = target_position(mesh, target)
    target_edge = (
        _segment(mesh, highlight_edge)
        if highlight_edge is not None and mesh.is_valid_edge(highlight_edge)
        else None
    )
    cross = tuple(tuple(c) for c in crossings)
    if symmetry is None and refused is None:
        line = (start_point, prospective) if start_point is not None and prospective is not None else None
        return KnifeRenderData(start_point, prospective, target_edge, line, tuple(segments_all),
                               tuple(pos for _pid, pos in placed_all), cross)

    placed = [pos for _pid, pos in placed_all]
    segments = list(segments_all)
    clipped_points: list = []
    clipped_segments: list = []
    hover_points: list = []
    hover_segments: list = []
    side = 0
    start_dropped = False
    prospective_off = False
    crossings_off: list = []
    if symmetry is not None:
        try:
            clip = symmetry.clip(path)
        except Exception as exc:       # the commit would refuse this path (P2 keeps such a click out)
            if not getattr(exc, "commit_refusal", False):
                raise
            clip = None
        if clip is not None and clip.side:
            side = clip.side
            kept_ids = {id(p) for p in clip.path}
            _positions, placed_w, segments_w, keys_w = _walk(mesh, _drawn(clip.path))
            kept_pids = {pid for pid, _pos in placed_w}
            placed = [pos for _pid, pos in placed_w]
            clipped_points = [pos for pid, pos in placed_all if pid not in kept_pids]
            segments = list(segments_w)
            kept_keys = set(keys_w)
            clipped_segments = [seg for seg, key in zip(segments_all, keys_all) if key not in kept_keys]
            start_dropped = last is not None and id(last) not in kept_ids

            def off(pos):                # the other side of the working side (the plane itself is on both)
                return symmetry.side(pos) == -side

            prospective_off = prospective is not None and (
                (target is not None and target.get("kind") != "space" and off(prospective))
            )
            crossings_off = [c for c in cross if off(c)]

    hover_ok = not (start_dropped or prospective_off)
    line = (start_point, prospective) if start_point is not None and prospective is not None else None
    if prospective_off:
        hover_points.append(prospective)
    hover_points.extend(crossings_off)
    cross_w = tuple(c for c in cross if c not in set(crossings_off))
    if line is not None and not hover_ok:
        hover_segments.append(line)
    if target_edge is not None and prospective_off:
        hover_segments.append(target_edge)

    work_prospective = None if prospective_off else prospective
    work_edge = None if prospective_off else target_edge
    work_line = line if hover_ok else None
    work_start = None if start_dropped else start_point

    mirror: dict = {}
    if symmetry is not None:
        mirror = dict(
            mirror_start_point=None if work_start is None else symmetry.mirror(work_start),
            mirror_prospective_point=None if work_prospective is None else symmetry.mirror(work_prospective),
            mirror_target_edge=_mirror_segment(symmetry, work_edge),
            mirror_line_preview=_mirror_segment(symmetry, work_line),
            mirror_path_segments=tuple(_mirror_segment(symmetry, seg) for seg in segments),
            mirror_placed_points=tuple(symmetry.mirror(pos) for pos in placed),
            mirror_prospective_crossings=tuple(symmetry.mirror(c) for c in cross_w),
        )

    refused_points: tuple = ()
    refused_segments: tuple = ()
    if refused is not None:
        pos = positions.get(refused.get("pid")) if refused.get("kind") == "point" else target_position(mesh, refused)
        if pos is not None:
            refused_points = (pos,)
            segs = []
            if refused.get("kind") == "edge" and mesh.is_valid_edge(refused["edge_id"]):
                segs.append(_segment(mesh, refused["edge_id"]))
            if start_point is not None:
                segs.append((start_point, pos))
            refused_segments = tuple(segs)

    return KnifeRenderData(
        work_start, work_prospective, work_edge, work_line, tuple(segments), tuple(placed), cross_w,
        clipped_points=tuple(clipped_points), clipped_segments=tuple(clipped_segments),
        clipped_hover_points=tuple(hover_points), clipped_hover_segments=tuple(hover_segments),
        refused_points=refused_points, refused_segments=refused_segments, working_side=side, **mirror,
    )
