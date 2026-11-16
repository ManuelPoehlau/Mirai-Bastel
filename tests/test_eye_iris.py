"""Eye LookDev phase 4 (Manu 2026-11-16, "1 go (v11), 2 go"), headless: the iris values `core.EyeIris` inside the look
(validation, scene file v11 only with iris values, v10 files read and written as before), the app path (Undo,
preview, presets keep an eye's iris values, the Eye Lab's controls) and the NumPy references of `viewport.eye_optics`
- the key's path through the cornea against a forward ray trace, the height derived from the iris image's brightness,
the pupil weights and the relief normal. GPU parity and the drawing: `test_gl_eye_pass.py`."""

from __future__ import annotations

import dataclasses
import json
import math

import numpy as np
import pytest

import tests._bootstrap  # noqa: F401

from core import EyeIris, EyeLook, Scene
from core.serialization import (EYE_IRIS_FORMAT_VERSION, EYE_LOOK_FORMAT_VERSION, scene_from_dict,
                                scene_to_dict)
from mirai import eye_presets
from mirai.application import Application
from mirai.eye_object import (DEFAULT_EYE, DEFAULT_IRIS, DEFAULT_LOOK, eye_transform, look_value, shell_mesh,
                              with_changes)
from mirai.interaction.input import Input
from viewport import eye_optics as eo

CTRL_Z = Input("key", "z", frozenset({"ctrl"}))
G = eo.EyeGeometry.from_values(DEFAULT_EYE)
IRIS = dataclasses.replace(DEFAULT_IRIS, light=0.8, crescent=1.4, rim_shadow=0.6, relief=0.5, relief_source="alpha",
                           pupil_edge_mm=0.1, pupil_margin=0.3)


# -- Core: EyeIris and file v11 --------------------------------------------------------------------------------------


@pytest.mark.parametrize("changes", [
    dict(light=1.1), dict(light=-0.1), dict(crescent=2.5), dict(rim_shadow=2.0), dict(rim_shadow_mm=0.0),
    dict(relief=1.5), dict(relief_mm=0.0), dict(relief_source="height"), dict(pupil_edge_mm=-0.1),
    dict(pupil_edge_mm=3.0), dict(pupil_margin=1.2), dict(light=math.nan), dict(light=None),
])
def test_invalid_iris_values_are_refused(changes):
    with pytest.raises(ValueError):
        dataclasses.replace(DEFAULT_IRIS, **changes)


def test_iris_is_optional_typed_and_strict():
    assert DEFAULT_LOOK.iris is None and "iris" not in DEFAULT_LOOK.to_dict()
    with pytest.raises(ValueError):
        dataclasses.replace(DEFAULT_LOOK, iris={"light": 1.0})
    look = dataclasses.replace(DEFAULT_LOOK, iris=IRIS)
    assert EyeLook.from_dict(json.loads(json.dumps(look.to_dict()))) == look
    assert EyeLook.from_dict(DEFAULT_LOOK.to_dict()).iris is None  # a phase 3 look: no iris values
    raw = IRIS.to_dict()
    for broken in ({k: v for k, v in raw.items() if k != "relief"}, raw | {"caustic": 1.0}, [1.0]):
        with pytest.raises(ValueError):
            EyeIris.from_dict(broken)
    assert all(getattr(DEFAULT_IRIS, name) == 0.0 for name in eo.IRIS_AMOUNTS)


def _scene_with_eye():
    scene = Scene()
    eye = scene.add_object(shell_mesh(DEFAULT_EYE), name="eye")
    eye.eye = dataclasses.replace(DEFAULT_EYE, look=dataclasses.replace(DEFAULT_LOOK, wet_sclera=0.5))
    eye.transform = eye_transform((3.0, 1.0, 0.0))
    return scene, eye


def test_v11_only_with_iris_values_and_v10_files_read_and_write_as_before():
    scene, eye = _scene_with_eye()
    v10 = json.loads(json.dumps(scene_to_dict(scene)))
    assert v10["version"] == EYE_LOOK_FORMAT_VERSION
    assert "iris" not in next(o for o in v10["objects"] if "eye" in o)["eye"]["look"]
    loaded = scene_from_dict(v10)  # a v10 file of phase 3: the look without iris values
    assert next(o for o in loaded.objects.values() if o.eye is not None).eye == eye.eye
    eye.eye = with_changes(eye.eye, **{"look.iris.relief": 0.4})
    data = json.loads(json.dumps(scene_to_dict(scene)))
    assert data["version"] == EYE_IRIS_FORMAT_VERSION == EYE_LOOK_FORMAT_VERSION + 1
    raw = next(o for o in data["objects"] if "eye" in o)["eye"]["look"]
    assert raw["iris"]["relief"] == 0.4 and raw["wet_sclera"] == 0.5
    back = next(o for o in scene_from_dict(data).objects.values() if o.eye is not None)
    assert back.eye == eye.eye
    eye.eye = with_changes(eye.eye, **{"look.iris": None})  # the iris values removed: the same v10 file again
    assert json.loads(json.dumps(scene_to_dict(scene))) == v10


@pytest.mark.parametrize("corrupt", [
    lambda iris: iris.update(relief=3.0), lambda iris: iris.pop("light"), lambda iris: iris.update(caustic=1.0),
    lambda iris: iris.update(relief_source="normal"),
])
def test_an_invalid_iris_makes_the_file_invalid(corrupt):
    scene, eye = _scene_with_eye()
    eye.eye = with_changes(eye.eye, **{"look.iris.light": 1.0})
    data = json.loads(json.dumps(scene_to_dict(scene)))
    corrupt(next(o for o in data["objects"] if "eye" in o)["eye"]["look"]["iris"])
    with pytest.raises(ValueError):
        scene_from_dict(data)


def test_with_changes_sets_one_iris_value_and_keeps_the_rest():
    first = with_changes(DEFAULT_EYE, **{"look.iris.crescent": 1.5})
    assert first.look == dataclasses.replace(DEFAULT_LOOK, iris=dataclasses.replace(DEFAULT_IRIS, crescent=1.5))
    second = with_changes(first, **{"look.wet_sclera": 0.3, "look.iris.relief": 0.2})
    assert (second.look.wet_sclera, second.look.iris.crescent, second.look.iris.relief) == (0.3, 1.5, 0.2)
    assert look_value(DEFAULT_EYE, "iris.relief_mm") == DEFAULT_IRIS.relief_mm
    assert look_value(second, "iris.crescent") == 1.5 and look_value(second, "wet_sclera") == 0.3
    assert with_changes(second, **{"look.iris": None}).look == dataclasses.replace(second.look, iris=None)
    with pytest.raises(ValueError):
        with_changes(first, **{"look.iris.relief_source": "bump"})


# -- the app path -----------------------------------------------------------------------------------------------------


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.set_viewport_size(800, 600)
    return app


def _depth(app) -> int:
    return len(app._selection_undo_stack)


def test_an_iris_value_is_one_undo_step_previews_live_and_saves_as_v11(app, tmp_path):
    eye = app.add_eye()
    app.set_eye(**{"look.wet_sclera": 0.5})
    depth = _depth(app)
    assert app.preview_eye(**{"look.iris.light": 0.4}) is True
    assert app.viewport._eye_entries[eye.id].spec.look.iris.light == 0.4 and eye.eye.look.iris is None
    assert app.set_eye(**{"look.iris.light": 0.6}) is True and _depth(app) == depth + 1
    assert eye.eye.look.iris == dataclasses.replace(DEFAULT_IRIS, light=0.6) and eye.eye.look.wet_sclera == 0.5
    assert app.set_eye(**{"look.iris.crescent": 3.0}) is False and "crescent" in app.status_message
    path = tmp_path / "iris.mirai.json"
    assert app.save_scene_file(path) is True
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == 11
    fresh = Application()
    fresh.init_scene("cube")
    fresh.load_scene("file", scene_path=path)
    assert [o.eye.look for o in fresh.scene.objects.values() if o.eye is not None] == [eye.eye.look]
    app.key_press(CTRL_Z)
    assert eye.eye.look.iris is None and app.save_scene_file(path) is True
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == 10  # the reflections only: the file of phase 3


@pytest.fixture
def preset_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(eye_presets, "PRESET_DIR", tmp_path)
    monkeypatch.setattr(eye_presets.load_presets, "__defaults__", (tmp_path,))
    monkeypatch.setattr(eye_presets.save_preset, "__defaults__", (tmp_path,))
    return tmp_path


def test_presets_keep_an_eyes_iris_unless_they_carry_one(app, preset_dir):
    """A preset look without iris values (phase 3's, or saved from an eye without them) leaves the eye's iris values;
    "Iris (Startwerte)" sets only them; a preset saved with iris values carries them."""
    eye = app.add_eye()
    app.set_eye(limbus_level=3, **{"look.iris.relief": 0.7})
    assert app.apply_eye_preset(eye_presets.LOOK_START_NAME) is True
    assert eye.eye.look.wet_sclera == eye_presets.LOOK_START["look"].wet_sclera and eye.eye.look.iris.relief == 0.7
    app.set_eye(**{"look.wet_sclera": 0.2})
    assert app.apply_eye_preset(eye_presets.IRIS_START_NAME) is True
    assert eye.eye.look.iris == eye_presets.IRIS_START["look.iris"] and eye.eye.look.wet_sclera == 0.2
    assert eye.eye.limbus_level == 3
    assert app.save_eye_preset("Gollum Iris") is True
    data = json.loads((preset_dir / "gollum_iris.json").read_text(encoding="utf-8"))
    assert data["values"]["look"]["iris"]["relief"] == eye_presets.IRIS_START["look.iris"].relief
    app.set_eye(**{"look.iris": None})
    assert app.apply_eye_preset("Gollum Iris") is True and eye.eye.look.iris == eye_presets.IRIS_START["look.iris"]
    assert app.apply_eye_preset(eye_presets.BUILTIN_NAME) is True and eye.eye.look is None


def test_eye_lab_iris_controls(app):
    from gui import eye_model as em

    eye = app.add_eye()
    for field, _label, lo, hi, _fmt in em.IRIS_SLIDERS:
        assert field.startswith("look.iris.") and lo <= em.value(eye.eye, field) <= hi
    names = {row[0][len("look.iris."):] for row in em.IRIS_SLIDERS} | {"relief_source"}
    assert names == set(DEFAULT_IRIS.to_dict()) and set(em.RELIEF_SOURCE_LABELS) == {"luminance", "alpha"}
    assert em.set_value(app, "look.iris.relief_source", "alpha") is True
    assert em.value(eye.eye, "look.iris.relief_source") == "alpha"
    assert em.set_value(app, "look.wet_sclera", 0.4) is True and em.set_value(app, "look.iris.relief", 0.3) is True
    # phase 5 (Manu 2026-11-16): the height source belongs to the iris image's import, so the reset keeps it
    assert em.reset_iris(app) is True and eye.eye.look.wet_sclera == 0.4
    assert eye.eye.look.iris == dataclasses.replace(DEFAULT_IRIS, relief_source="alpha")
    em.set_value(app, "look.iris.relief_source", "luminance")
    assert em.reset_iris(app) is True and eye.eye.look.iris is None  # with the default source: no iris values


def test_iris_values_draw_only_in_the_full_tier(app):
    from viewport.eye_pass import EyeDisplay, uses_iris, uses_look

    eye = app.add_eye()
    draw = app.viewport._eye_entries[eye.id]
    full = EyeDisplay(tier="full")
    assert not uses_iris(draw, full)
    app.set_eye(**{"look.iris.pupil_edge_mm": 0.1})
    draw = app.viewport._eye_entries[eye.id]
    assert uses_iris(draw, full) and uses_look(draw, full)  # the iris alone needs the look program too
    assert not uses_iris(draw, EyeDisplay(tier="fast")) and not uses_look(draw, EyeDisplay(tier="fast"))
    app.set_eye(**{"look.iris.pupil_edge_mm": 0.0})  # every amount at 0 again: the program of phase 3
    assert not uses_iris(app.viewport._eye_entries[eye.id], full)


# -- the references in eye_optics ---------------------------------------------------------------------------------


def _forward_irradiance(az_deg: float, xs, rng, n=1_500_000, bin_width=0.03):
    """A forward ray trace: a parallel beam of irradiance 1 from azimuth `az_deg` (in the x-z plane) through the cornea
    (V2) onto the iris; the irradiance on the iris surface in bins along x (y = 0)."""
    l = eo.normalize(np.array([math.sin(math.radians(az_deg)), 0.0, math.cos(math.radians(az_deg))]))
    u = eo.normalize(np.cross(l, [0.0, 1.0, 0.0]))
    v = np.cross(l, u)
    disk = 1.3
    rr, ph = disk * np.sqrt(rng.uniform(0, 1, n)), rng.uniform(0, 2 * np.pi, n)
    o = np.array([0.0, 0.0, G.apex_z - 0.3]) + 3.0 * l + (rr * np.cos(ph))[:, None] * u + (rr * np.sin(ph))[:, None] * v
    d = np.broadcast_to(-l, o.shape)
    centre = np.array([0.0, 0.0, G.anterior_centre_z])
    ok, t = eo.sphere_entry(o, d, centre, G.cornea_radius)
    entry = o + t[:, None] * d
    ok &= entry[:, 2] >= G.limbus_z
    refracted = eo.normalize(eo.refract(d, eo.normalize(entry - centre), eo.N_AIR / eo.N_EFFECTIVE))
    hit, ti, ri = eo.iris_cone_hit(entry, refracted, G)
    ok &= hit & (ri <= G.iris_radius)
    p = entry + ti[:, None] * refracted
    area = bin_width * bin_width * math.sqrt(1.0 + G.iris_b ** 2)
    return l, np.array([(ok & (np.abs(p[:, 0] - x) < bin_width / 2) & (np.abs(p[:, 1]) < bin_width / 2)).sum()
                        for x in xs]) * (math.pi * disk * disk / n) / area


@pytest.mark.parametrize("az", [0.0, 40.0, 70.0, 80.0])
def test_the_keys_path_through_the_cornea_matches_a_forward_ray_trace(az):
    """Roadmap #4: the irradiance the model gives the iris (concentration x cosine x not shaded) agrees with a forward
    ray trace, from a frontal key to a grazing one: the focusing opposite the key (the crescent, up to 6 x the
    unrefracted key's cosine at 80 degrees), the scleral rim's shadow near the key, the far edge the key cannot
    reach."""
    xs = np.array([-0.4, -0.3, -0.15, 0.15, 0.3, 0.4])
    width = 0.03
    l, traced = _forward_irradiance(az, xs, np.random.default_rng(int(az)), bin_width=width)
    # the model averaged over each bin (the edges are steep), with a nearly hard rim shadow like the trace's
    k = (np.arange(7) + 0.5) / 7 * width - width / 2
    ox, oy = np.meshgrid(k, k)
    xy = np.stack([xs[:, None] + ox.ravel()[None, :], np.broadcast_to(oy.ravel(), (len(xs), ox.size))], -1)
    hits = eo._cone_point(xy, G)
    d, _trans, conc, shadow = eo.iris_key_terms(hits, l, 0.01 * eo.MM, G)
    cos = np.sum(eo.iris_cone_normal(hits, G) * d, -1)
    model = (conc * np.maximum(cos, eo.CRESCENT_MIN_COS) * (1.0 - shadow)).mean(-1)
    hits = hits[:, ox.size // 2]
    unlit = traced < 0.05
    assert np.all(model[unlit] < 0.1), (az, traced, model)
    assert np.allclose(model[~unlit], traced[~unlit], rtol=0.15, atol=0.08), (az, traced, model)
    if az >= 70.0:
        unrefracted = np.maximum(np.sum(eo.iris_cone_normal(hits, G) * l, -1), 0.0)
        assert traced[1] > 3.0 * unrefracted[1]  # the crescent at x = -0.3, opposite the key


def test_the_light_path_is_converged_and_refuses_unreachable_points():
    rng = np.random.default_rng(13)
    n = 4000
    r, ph = G.iris_radius * np.sqrt(rng.uniform(0, 1, n)), rng.uniform(0, 2 * np.pi, n)
    hits = eo._cone_point(np.stack([r * np.cos(ph), r * np.sin(ph)], -1), G)
    off, az = np.radians(rng.uniform(0, 85, n)), rng.uniform(0, 2 * np.pi, n)
    l = np.stack([np.sin(off) * np.cos(az), np.sin(off) * np.sin(az), np.cos(off)], -1)
    ok, entry, d, cos_in, _aperture, _phi = eo.iris_light_path(hits, l, G)
    assert 0.5 < ok.mean() < 0.99
    # forward: the key refracted at the entry passes through the hit
    centre = np.array([0.0, 0.0, G.anterior_centre_z])
    t_in = eo.normalize(eo.refract(-l, eo.normalize(entry - centre), eo.N_AIR / eo.N_EFFECTIVE))
    miss = np.linalg.norm(np.cross(hits - entry, t_in), axis=-1)
    assert miss[ok].max() < 1e-6 and np.all(cos_in[ok] > 0.0)
    assert np.allclose(d[ok], eo.normalize(-t_in[ok]), atol=1e-6)


def test_derived_height_is_flat_outside_the_annulus_and_follows_brightness():
    size = 256
    c = (np.arange(size) + 0.5) / size * 2.0 - 1.0
    y, x = np.meshgrid(c, c, indexing="ij")
    rho, ang = np.hypot(x, y), np.arctan2(y, x)
    rgb = np.full((size, size, 3), 0.5)
    rgb[..., :] = (0.5 + 0.2 * np.sin(40 * ang) + 0.3 * (rho > 0.5))[..., None]  # fibres and a brighter outer zone
    rgb[rho < 0.2] = 0.0  # the pupil
    rgb[rho > 0.9] = 1.0  # a white background
    h = eo.iris_height(rgb, 0.2, 0.9)
    assert h.shape == (size, size) and 0.0 <= h.min() and h.max() <= 1.0
    assert np.all(h[rho < 0.15] == 0.5) and np.all(h[rho > 0.97] == 0.5)
    ring = (rho > 0.3) & (rho < 0.45)
    bright = ring & (np.sin(40 * ang) > 0.7)
    dark = ring & (np.sin(40 * ang) < -0.7)
    assert h[bright].mean() > 0.6 and h[dark].mean() < 0.4  # fibres raised, gaps deep
    zone = (rho > 0.6) & (rho < 0.8)
    assert abs(h[zone].mean() - h[ring].mean()) < 0.05  # the colour zones are not a step
    assert np.array_equal(h, eo.iris_height(rgb, 0.2, 0.9))
    assert np.all(eo.iris_height(np.full((64, 64, 3), 0.4), 0.2, 0.9) == 0.5)


def test_pupil_weights_and_relief_normal():
    r = np.linspace(0.5, 1.5, 201) * G.pupil_radius
    hard, margin = eo.pupil_weights(r, 0.0, 0.03, G)
    assert np.array_equal(hard, (r < G.pupil_radius).astype(float))
    soft, _ = eo.pupil_weights(r, 0.02, 0.03, G)
    assert np.all(np.diff(soft) <= 0) and soft[0] == 1.0 and soft[-1] == 0.0
    assert soft[np.argmin(np.abs(r - G.pupil_radius))] == pytest.approx(0.5, abs=0.02)
    assert margin[r <= G.pupil_radius].min() == 1.0 and margin[r >= G.pupil_radius + 0.03].max() == 0.0
    hits = eo._cone_point(np.array([[0.2, 0.1], [-0.3, 0.05], [0.0, 0.0]]), G)
    assert np.allclose(eo.relief_normal(hits, np.zeros((3, 2)), G), eo.iris_cone_normal(hits, G))
    tilted = eo.relief_normal(hits, np.array([[1.0, 0.0]] * 3), G)
    assert np.all(tilted[:, 0] < eo.iris_cone_normal(hits, G)[:, 0])  # rising toward +x: the normal leans to -x
