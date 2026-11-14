"""The synthetic eye (headless)."""

from __future__ import annotations

import math

import numpy as np

from lookdev_eye_lab import eye_geometry as geo


def _newell(points):
    n = np.zeros(3)
    for k in range(len(points)):
        a, b = points[k], points[(k + 1) % len(points)]
        n += ((a[1] - b[1]) * (a[2] + b[2]), (a[2] - b[2]) * (a[0] + b[0]), (a[0] - b[0]) * (a[1] + b[1]))
    return n / np.linalg.norm(n)


def _faces(mesh):
    for f in mesh.all_face_ids():
        yield f, np.array([mesh.vertex_position(v) for v in mesh.face_vertices(f)])


def test_spheres_face_outward():
    parts = geo.build_parts()
    centres = {"sclera": (0, 0, 0), "cornea": (0, 0, geo.CORNEA_CENTRE_Z), "chrome": geo.CHROME_CENTRE,
               "grey": geo.GREY_CENTRE}
    for name, centre in centres.items():
        for _f, p in _faces(parts[name]):
            assert _newell(p) @ (p.mean(axis=0) - np.array(centre)) > 0, name


def test_cornea_rim_is_the_sclera_limbus_and_the_iris_lies_behind_it_inside_the_sclera():
    parts = geo.build_parts()
    rim = lambda m: {tuple(np.round(m.vertex_position(v), 9)) for v in m.all_vertex_ids()  # noqa: E731
                     if abs(m.vertex_position(v)[2] - geo.LIMBUS_Z) < 1e-9}
    assert len(rim(parts["sclera"])) == geo.SEGMENTS and rim(parts["sclera"]) == rim(parts["cornea"])
    for v in parts["iris"].all_vertex_ids():
        x, y, z = parts["iris"].vertex_position(v)
        assert z < geo.LIMBUS_Z and x * x + y * y + z * z < 1.0  # behind the limbus, inside the sclera (no poke-through)


def test_iris_faces_the_front_and_carries_planar_uvs():
    iris = geo.build_parts()["iris"]
    assert iris.has_face_uvs()
    for f, p in _faces(iris):
        uvs = iris.face_uvs(f)
        r = math.hypot(*p.mean(axis=0)[:2])
        if r > geo.PUPIL_RADIUS * 1.001 and p[:, 2].min() > geo.iris_z(geo.PUPIL_RADIUS) - 1e-9:
            assert _newell(p)[2] > 0.5
            for (x, y, _z), uv in zip(p, uvs):
                assert np.allclose(uv, geo.iris_uv(x, y))
        else:
            assert all(np.allclose(uv, (0.5, 0.5)) for uv in uvs)  # pupil wall / floor: the black centre


def test_iris_image_has_a_black_pupil_and_coloured_stroma(tmp_path):
    img = geo.iris_image(128)
    assert img.shape == (128, 128, 3) and img.min() >= 0.0 and img.max() <= 1.0
    assert img[64, 64].max() < 0.02  # pupil
    ring = img[64, 64 + int(64 * 0.6)]
    assert ring.max() > 0.2
    path = geo.write_iris_png(tmp_path / "iris.png")
    stamp = path.stat().st_mtime_ns
    geo.write_iris_png(path)
    assert path.stat().st_mtime_ns == stamp  # unchanged content is not rewritten (texture cache key stays)
