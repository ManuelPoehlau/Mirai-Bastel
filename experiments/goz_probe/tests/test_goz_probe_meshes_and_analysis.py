"""Test meshes A/B/C (README §3) and the sent-vs-received comparison."""

from __future__ import annotations

import random

from goz_probe import make_meshes
from goz_probe.goz_probe_format import GozFile, as_float32
from goz_probe.probe_common import analyse, analysis_lines, load_sent


def test_meshes_are_deterministic(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    make_meshes.write_meshes(a)
    make_meshes.write_meshes(b)
    names = sorted(p.name for p in a.iterdir())
    assert names == ["A.obj", "A.sent.json", "B.obj", "B.sent.json", "C.obj", "C.sent.json"]
    assert all((a / n).read_bytes() == (b / n).read_bytes() for n in names)


def _newell(points):
    nx = ny = nz = 0.0
    for i, p in enumerate(points):
        q = points[(i + 1) % len(points)]
        nx += (p[1] - q[1]) * (p[2] + q[2])
        ny += (p[2] - q[2]) * (p[0] + q[0])
        nz += (p[0] - q[0]) * (p[1] + q[1])
    return nx, ny, nz


def test_tripod_is_asymmetric_with_outward_faces(tmp_path):
    make_meshes.write_meshes(tmp_path, ids=("A",))
    sent = load_sent(tmp_path)["A"]
    pts, faces = sent["positions"], sent["faces"]
    assert len(pts) == 24 and len(faces) == 18 and all(len(f) == 4 for f in faces)
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    extents = [round(h - l, 9) for l, h in zip(lo, hi)]
    assert extents == [1.0, 0.75, 0.45] and all(v > 0 for v in lo)  # distinct extents, off the origin
    for box in range(3):
        corners = pts[8 * box: 8 * box + 8]
        centre = [sum(c[i] for c in corners) / 8 for i in range(3)]
        for face in faces[6 * box: 6 * box + 6]:
            poly = [pts[i] for i in face]
            n = _newell(poly)
            fc = [sum(p[i] for p in poly) / 4 for i in range(3)]
            assert sum(n[i] * (fc[i] - centre[i]) for i in range(3)) > 0  # counter-clockwise seen from outside


def test_mirai_sphere_has_triangles_and_id_gaps(tmp_path):
    make_meshes.write_meshes(tmp_path, ids=("B",))
    sent = load_sent(tmp_path)["B"]
    assert (len(sent["positions"]), len(sent["faces"])) == (481, 508)
    assert sum(1 for f in sent["faces"] if len(f) == 3) == 64
    assert sent["vertex_ids"] != list(range(481)) and sent["face_ids"] != list(range(508))
    assert max(i for f in sent["faces"] for i in f) == 480  # dense indices, not IDs


def test_head_matches_its_obj(tmp_path):
    make_meshes.write_meshes(tmp_path, ids=("C",))
    sent = load_sent(tmp_path)["C"]
    assert (len(sent["positions"]), len(sent["faces"])) == (326, 324)
    from loaders.obj_loader import load_obj

    data = load_obj(tmp_path / "C.obj")
    assert [list(f) for f in data.faces] == sent["faces"]


def _received(sent, transform, faces=None) -> GozFile:
    goz = GozFile(header_text=b"")
    goz.points = [tuple(as_float32(c) for c in transform(p)) for p in sent["positions"]]
    goz.faces = [tuple(f) for f in (faces if faces is not None else sent["faces"])]
    return goz


def _sent_a(tmp_path):
    make_meshes.write_meshes(tmp_path, ids=("A",))
    return load_sent(tmp_path)["A"]


def test_identity_round_trip_is_bit_identical(tmp_path):
    sent = _sent_a(tmp_path)
    result = analyse(_received(sent, lambda p: p), sent)
    assert result["order"] == "same" and result["mapping_is_signed_permutation"]
    assert result["positions"]["changed"] == 0
    assert any("bitgleich" in line for line in analysis_lines(result))


def test_rotation_about_x_is_detected_and_exact(tmp_path):
    sent = _sent_a(tmp_path)
    result = analyse(_received(sent, lambda p: (p[0], -p[1], -p[2])), sent)
    axes = {m["axis"]: (m["from"], round(m["factor"], 9)) for m in result["axes"]}
    assert axes == {"x": ("x", 1.0), "y": ("y", -1.0), "z": ("z", -1.0)}
    assert result["positions"]["changed"] == 0


def test_axis_swap_and_scale_from_bbox_when_order_differs(tmp_path):
    sent = _sent_a(tmp_path)
    received = _received(sent, lambda p: (2 * p[0], 2 * p[2], -2 * p[1]))
    random.Random(1).shuffle(received.points)
    result = analyse(received, sent)
    assert result["axes"][0]["method"] == "bbox"
    axes = {m["axis"]: (m["from"], round(m["factor"], 5)) for m in result["axes"]}
    assert axes == {"x": ("x", 2.0), "y": ("z", 2.0), "z": ("y", -2.0)}


def test_moved_vertices_and_reversed_faces_are_counted(tmp_path):
    sent = _sent_a(tmp_path)
    moved = _received(sent, lambda p: p)
    moved.points[3] = (moved.points[3][0] + 0.01, moved.points[3][1], moved.points[3][2])
    result = analyse(moved, sent)
    assert result["positions"]["changed"] == 1 and result["positions"]["first_changed"] == [3]
    flipped = analyse(_received(sent, lambda p: p, faces=[f[::-1] for f in sent["faces"]]), sent)
    assert flipped["faces"]["reversed_winding"] == 18 and flipped["order"] == "same counts, faces differ"
