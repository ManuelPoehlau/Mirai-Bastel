"""AD-033 §4: the parametric eye's data - `core.EyeSpec` (value, validation), `SceneObject.eye` (default None), scene
file v9 (round trip, written only with an eye, older versions load without one, an invalid eye refused) - and the
shell builder / fit reader of `mirai.eye_object` (headless)."""

from __future__ import annotations

import dataclasses
import json
import math

import pytest

import tests._bootstrap  # noqa: F401

from core import EyeSpec, Mesh, Scene, SceneObject
from core.ids import ObjectId
from core.serialization import EYE_FORMAT_VERSION, GROUP_FORMAT_VERSION, scene_from_dict, scene_to_dict
from mirai.eye_object import DEFAULT_EYE, EYE_SCALE_CM, eye_transform, read_fit_sidecar, shape_changed, shell_mesh, with_changes
from viewport.eye_optics import EyeGeometry


def test_default_eye_is_the_labs_eye():
    g = EyeGeometry.from_values(DEFAULT_EYE)
    assert (DEFAULT_EYE.cornea_radius, DEFAULT_EYE.limbus_radius, DEFAULT_EYE.pupil_radius) == (0.65, 0.49, 0.16)
    assert g.limbus_z == pytest.approx(math.sqrt(1 - 0.49 ** 2))
    assert g.iris_radius == pytest.approx(0.5980, abs=1e-4)  # the lab's IRIS_RADIUS
    assert g.angle[0] == pytest.approx(0.466, abs=0.002)  # the chamber angle (P1b: r 5.59 mm)
    assert DEFAULT_EYE.limbus_level == 0 and DEFAULT_EYE.fit_pupil is None and not DEFAULT_EYE.asymmetry


def test_chamber_angle_is_computed_once_per_anatomy_and_stays_the_bisections_value():
    """The eye pass asks for the angle for every eye on every frame (the 80-step bisection was most of its CPU time,
    reference PC 2026-11-16): one computation per anatomy, the same numbers."""
    from viewport import eye_optics as eo

    spec = with_changes(DEFAULT_EYE, pupil_radius=0.1234, iris_concavity=0.0271)  # an anatomy no other test uses
    g = EyeGeometry.from_values(spec)
    lo, hi = 0.0, eo.POSTERIOR_RADIUS
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if float(g.posterior_z(mid)) > float(g.iris_z(mid)) else (lo, mid)
    before = eo._chamber_angle.cache_info()
    first = g.angle
    again = EyeGeometry.from_values(spec).angle  # another instance of the same anatomy
    after = eo._chamber_angle.cache_info()
    assert first == again == (lo, float(g.iris_z(lo)))
    assert after.misses == before.misses + 1 and after.hits == before.hits + 1


@pytest.mark.parametrize("changes", [
    dict(limbus_radius=1.0), dict(limbus_radius=0.0), dict(cornea_radius=0.4), dict(iris_root_z=0.9),
    dict(iris_root_z=0.0), dict(pupil_radius=0.5), dict(pupil_radius=0.0), dict(iris_concavity=-0.01),
    dict(fit_pupil=0.2), dict(fit_pupil=0.5, fit_limbus=0.4), dict(fit_pupil=0.2, fit_limbus=1.2),
    dict(hold_outer_color=1), dict(limbus_level=4), dict(limbus_level=True), dict(colour_source="paint"),
    dict(limbal_colour=(1.2, 0.0, 0.0)), dict(band_mm=0.0), dict(strength=1.1), dict(falloff=0.0),
    dict(overlap_mm=-0.1), dict(normal_mm=math.nan), dict(asymmetry="yes"), dict(cornea_radius=True),
])
def test_invalid_eye_values_are_refused(changes):
    with pytest.raises(ValueError):
        dataclasses.replace(DEFAULT_EYE, **changes)


def test_eye_is_a_frozen_value_and_defaults_to_none_at_the_object():
    with pytest.raises(dataclasses.FrozenInstanceError):
        DEFAULT_EYE.pupil_radius = 0.2
    scene = Scene()
    obj = scene.add_object(Mesh())
    assert obj.eye is None
    obj.eye = DEFAULT_EYE
    with pytest.raises(TypeError):
        SceneObject(ObjectId(9), Mesh(), eye={"pupil_radius": 0.16})


def _scene_with_eye():
    scene = Scene()
    eye = scene.add_object(shell_mesh(DEFAULT_EYE), name="eye")
    eye.eye = dataclasses.replace(DEFAULT_EYE, fit_pupil=0.22, fit_limbus=0.88, hold_outer_color=True,
                                  limbus_level=2, overlap_mm=0.3, asymmetry=True)
    eye.transform = eye_transform((3.0, 1.0, 0.0))
    return scene, eye


def test_v9_round_trip_and_only_written_with_an_eye():
    scene = Scene()
    assert scene_to_dict(scene)["version"] < EYE_FORMAT_VERSION
    scene, eye = _scene_with_eye()
    data = json.loads(json.dumps(scene_to_dict(scene)))
    assert data["version"] == EYE_FORMAT_VERSION == GROUP_FORMAT_VERSION + 1
    raw = next(o for o in data["objects"] if o["name"] == "eye")
    assert raw["eye"]["limbus_level"] == 2 and raw["eye"]["fit_limbus"] == 0.88
    assert all("eye" not in o for o in data["objects"] if o["name"] != "eye")
    loaded = scene_from_dict(data)
    back = next(o for o in loaded.objects.values() if o.name == "eye")
    assert back.eye == eye.eye and back.transform.scale == EYE_SCALE_CM
    assert next(o for o in loaded.objects.values() if o.name != "eye").eye is None


def test_older_versions_load_without_eyes_and_an_invalid_eye_is_refused():
    scene, _eye = _scene_with_eye()
    data = scene_to_dict(scene)
    for raw in data["objects"]:
        raw.pop("eye", None)
    data["version"] = 8
    assert all(o.eye is None for o in scene_from_dict(data).objects.values())
    data = scene_to_dict(scene)
    raw = next(o for o in data["objects"] if "eye" in o)
    raw["eye"]["pupil_radius"] = 0.9
    with pytest.raises(ValueError):
        scene_from_dict(data)
    raw["eye"] = {"pupil_radius": 0.16}  # missing fields
    with pytest.raises(ValueError):
        scene_from_dict(data)


def test_shell_is_closed_and_shares_the_limbus_ring():
    mesh = shell_mesh(DEFAULT_EYE)
    v, e, f = len(mesh.all_vertex_ids()), len(mesh.all_edge_ids()), len(mesh.all_face_ids())
    assert v - e + f == 2  # a closed sphere
    g = EyeGeometry.from_values(DEFAULT_EYE)
    ring = [mesh.vertex_position(vid) for vid in mesh.all_vertex_ids()
            if abs(mesh.vertex_position(vid)[2] - g.limbus_z) < 1e-9]
    assert len(ring) == 64 and all(math.hypot(p[0], p[1]) == pytest.approx(0.49) for p in ring)
    apex = max(mesh.vertex_position(vid)[2] for vid in mesh.all_vertex_ids())
    assert apex == pytest.approx(g.apex_z)
    for vid in mesh.all_vertex_ids():  # every vertex on the sclera sphere or the cornea sphere
        x, y, z = mesh.vertex_position(vid)
        on_sclera = abs(math.sqrt(x * x + y * y + z * z) - 1.0) < 1e-9
        on_cornea = abs(math.sqrt(x * x + y * y + (z - g.anterior_centre_z) ** 2) - g.cornea_radius) < 1e-9
        assert on_sclera or on_cornea


def test_shape_changed_only_for_the_shell_values():
    assert shape_changed(DEFAULT_EYE, dataclasses.replace(DEFAULT_EYE, cornea_radius=0.7))
    assert not shape_changed(DEFAULT_EYE, dataclasses.replace(DEFAULT_EYE, pupil_radius=0.2, limbus_level=3))


@pytest.mark.parametrize("content, expected, reason", [
    ('{"pupil": 0.22, "limbus": 0.88, "hold_outer_color": true}', (0.22, 0.88, True), ""),
    ('{"pupil": 0.22, "limbus": 0.9}', (0.22, 0.9, False), ""),
    ('{"pupil": 0.5, "limbus": 0.4}', None, "0 < pupil < limbus"),
    ('{"pupil": 0.2, "limbus": 0.9, "hold": true}', None, "unknown key 'hold'"),
    ('{not json', None, "cannot be read"),
])
def test_fit_sidecar_reader(tmp_path, content, expected, reason):
    image = tmp_path / "iris.png"
    image.write_bytes(b"png")
    assert read_fit_sidecar(image) == (None, "")
    (tmp_path / "iris.json").write_bytes(content.encode("utf-8-sig"))  # a BOM, as Windows writes
    fit, note = read_fit_sidecar(image)
    if expected is None:
        assert fit is None and reason in note
    else:
        assert note == "" and (fit["fit_pupil"], fit["fit_limbus"], fit["hold_outer_color"]) == expected
