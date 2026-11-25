"""AD-040 LD-3a, the pure and headless parts (§10.1): `resolve` against the tier table (G-3), the activity tracker with
a fake clock (G-4), render fields only (G-5), the frame signature's completeness (G-6), Auto's hysteresis and the timer
missing (G-7), the idle ceiling, the settings file (G-12) and the Worklight creating nothing (G-13, headless part).

The GL gates (G-1, G-8 … G-11, the timer) are in `tests/test_gl_lookdev_quality.py`."""

from __future__ import annotations

import ast
import dataclasses
import itertools
import json
from pathlib import Path

import pytest

import tests._bootstrap  # noqa: F401

from mirai import lookdev_quality_settings as qs
from mirai.application import Application
from viewport import lookdev_quality as lq
from viewport.lookdev_features import FeatureReport
from viewport.lookdev_optics import LookdevEffects, effective
from viewport.lookdev_quality import (CONVERGED, INTERACTIVE, REFINE, SETTLING, ActivityTracker, AutoTier,
                                      IdleCeiling, RenderConfig, resolve)

ALL = LookdevEffects(area_diffuse=True, soft_shadow=True)  # every built effect on
FEATURES = (None, FeatureReport(), FeatureReport(depth_texture=False), FeatureReport(sampler_objects=False),
            FeatureReport(cube_rgba16f=False, texture_units=False))


def _allowed_sets():
    names = LookdevEffects.names()
    yield ALL
    yield LookdevEffects()  # the defaults (S8, S9 off)
    yield LookdevEffects(**{n: False for n in names})
    for name in names:  # each effect off alone
        yield dataclasses.replace(ALL, **{name: False})


# -- G-3: resolve -----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("features", FEATURES, ids=lambda f: "none" if f is None else ",".join(f.missing()) or "all")
def test_resolve_never_draws_an_effect_that_is_not_allowed(features):
    """Q2: per tier x refine x state x idle tier x drops, the configuration's effects are within effective(allowed)."""
    for allowed in _allowed_sets():
        base = effective(allowed, features)
        for tier, refine, state, idle, n in itertools.product(lq.AUTO_TIERS, (False, True), lq.STATES, lq.IDLE_TIERS,
                                                              range(len(lq.IDLE_DROPS) + 1)):
            config = resolve(tier, allowed, features, refine, state, idle, lq.IDLE_DROPS[:n])
            assert lq.subset(config.effects, base), (tier, refine, state, idle, allowed)
            assert config.samples == 1 and not config.jitter  # LD-3a: no accumulation


def test_resolve_follows_the_tier_table():
    """AD-040 §2.2: Entwurf drops shadow, eye shadow, thickness, dual lobe, S8 and S9 (cube, regions and maps stay:
    Q1 - artist-authored); Mittel drops S9; Hoch draws everything allowed; Maximal adds the 2048² map and 256 samples."""
    entwurf = resolve("entwurf", ALL).effects
    assert entwurf == LookdevEffects(shadow=False, eye_shadow=False, thickness=False, dual_lobe=False,
                                     area_diffuse=False, soft_shadow=False, cube=True, regions=True, maps=True)
    assert resolve("mittel", ALL).effects == dataclasses.replace(ALL, soft_shadow=False)
    assert resolve("hoch", ALL).effects == ALL
    for tier in lq.AUTO_TIERS:
        config = resolve(tier, ALL)
        assert (config.shadow_size, config.cube_samples) == (1024, 64)
    maximal = resolve("hoch", ALL, refine=True, state=REFINE, idle_tier="maximal")
    assert (maximal.effects, maximal.shadow_size, maximal.cube_samples) == (ALL, 2048, 256)
    idle_hoch = resolve("entwurf", ALL, refine=True, state=CONVERGED, idle_tier="hoch")
    assert (idle_hoch.effects, idle_hoch.shadow_size, idle_hoch.cube_samples) == (ALL, 1024, 64)


def test_refinement_off_draws_the_tier_in_every_state_and_hoch_is_todays_frame():
    """Q3 / §2.3: with refinement off the tier is the one configuration in every state; Hoch = the effects in force
    (S9 included while working), the P3 map and cube, every frame's map (Q-LD3-1's default)."""
    for features in FEATURES:
        for allowed in _allowed_sets():
            for state in lq.STATES:
                config = resolve("hoch", allowed, features, False, state, "maximal")
                assert config == RenderConfig(effective(allowed, features), 1024, "every", 64)


def test_the_idle_only_rule():
    """F-R3: with refinement on, no interactive configuration holds S9, the 2048² map, 256 samples or accumulation."""
    for tier, state, idle in itertools.product(lq.AUTO_TIERS, (INTERACTIVE, SETTLING), lq.IDLE_TIERS):
        config = resolve(tier, ALL, None, True, state, idle)
        assert not config.effects.soft_shadow and config.shadow_size == 1024 and config.cube_samples == 64
        assert config.samples == 1
    assert resolve("hoch", ALL, None, True, REFINE, "hoch").effects.soft_shadow


def test_the_shadow_updates_apply_while_interactive_only():
    """§2.2: Entwurf frozen, Hoch / Mittel the Q-LD3-1 policy while Interactive; every other state renders every
    change (the first Settling frame brings the map up to date)."""
    for policy in lq.SHADOW_UPDATES:
        assert resolve("hoch", ALL, state=INTERACTIVE, drag_updates=policy).shadow_updates == policy
        assert resolve("mittel", ALL, state=INTERACTIVE, drag_updates=policy).shadow_updates == policy
        assert resolve("entwurf", ALL, state=INTERACTIVE, drag_updates=policy).shadow_updates == "frozen"
        for state in (SETTLING, REFINE, CONVERGED):
            for tier, refine in itertools.product(lq.AUTO_TIERS, (False, True)):
                assert resolve(tier, ALL, None, refine, state, drag_updates=policy).shadow_updates == "every"
    assert lq.DEFAULT_DRAG_UPDATES == "every"  # Q-LD3-1 open: today's map by default
    assert [lq.SHADOW_DEFER[p] for p in lq.SHADOW_UPDATES] == [0, 1, None]


def test_the_ceiling_drops_s9_then_the_large_map():
    first = resolve("hoch", ALL, None, True, REFINE, "maximal", ("soft_shadow",))
    assert not first.effects.soft_shadow and first.shadow_size == 2048
    both = resolve("hoch", ALL, None, True, REFINE, "maximal", lq.IDLE_DROPS)
    assert not both.effects.soft_shadow and both.shadow_size == 1024 and both.cube_samples == 256


def test_resolve_refuses_unknown_names():
    for args in (("auto", ALL), ("maximal", ALL)):
        with pytest.raises(ValueError):
            resolve(*args)
    with pytest.raises(ValueError):
        resolve("hoch", ALL, idle_tier="mittel")
    with pytest.raises(ValueError):
        resolve("hoch", ALL, state="idle")
    with pytest.raises(ValueError):
        resolve("hoch", ALL, drag_updates="never")


def test_reachable_holds_every_tier_with_auto_and_the_idle_tier_with_refinement():
    auto = lq.reachable("auto", ALL, None, True, "maximal")
    effects = {c.effects for c in auto}
    assert resolve("entwurf", ALL).effects in effects and resolve("mittel", ALL).effects in effects
    assert ALL in effects  # the idle tier (S9)
    assert {c.shadow_size for c in auto} == {1024, 2048}
    fixed = lq.reachable("mittel", ALL)
    assert {c.effects for c in fixed} == {resolve("mittel", ALL).effects}


def test_held_back_says_where_an_effect_is_drawn():
    config = resolve("hoch", ALL, None, True, INTERACTIVE, "maximal")
    held = lq.held_back(config, ALL, None, "auto", True, "maximal")
    assert held == {"soft_shadow": "in Ruhe (Maximal)"}
    config = resolve("entwurf", ALL)
    held = lq.held_back(config, ALL, None, "auto", False, "hoch")
    assert held["shadow"] == "aktiv in: Hoch, Mittel" and held["soft_shadow"] == "aktiv in: Hoch"
    assert "cube" not in held
    assert lq.held_back(resolve("hoch", ALL), ALL, None, "hoch") == {}


# -- G-4: the activity tracker -------------------------------------------------------------------------------------

def test_the_tracker_walks_interactive_settling_refine_converged():
    tracker = ActivityTracker(wait=0.3)
    assert tracker.step("a", False, 0.0) == INTERACTIVE  # the first tick
    assert tracker.step("a", False, 1 / 60) == SETTLING
    states = [tracker.step("a", False, 0.1) for _ in range(3)]
    assert states == [SETTLING, SETTLING, REFINE]  # 0.3 s of quiet
    assert tracker.n == 0
    assert tracker.step("a", False, 0.1) == CONVERGED  # N = 1 in LD-3a: one refine frame
    assert tracker.step("a", False, 0.1) == CONVERGED


@pytest.mark.parametrize("at", [SETTLING, REFINE, CONVERGED])
def test_a_change_returns_to_interactive_in_the_same_tick(at):
    tracker = ActivityTracker(wait=0.1)
    tracker.step("a", False, 0.0)
    while tracker.state != at:
        tracker.step("a", False, 0.05)
    assert tracker.step("b", False, 0.0) == INTERACTIVE
    assert tracker.n == 0 and tracker.quiet == 0.0


def test_held_keeps_the_room_interactive():
    """A slow drag that leaves one tick unchanged is not quiet."""
    tracker = ActivityTracker(wait=0.1)
    tracker.step("a", False, 0.0)
    for _ in range(20):
        assert tracker.step("a", True, 0.05) == INTERACTIVE
    assert tracker.step("a", False, 0.05) == SETTLING


def test_the_wait_is_bounded():
    assert ActivityTracker(wait=0.01).wait == 0.1 and ActivityTracker(wait=9.0).wait == 2.0
    tracker = ActivityTracker(wait=2.0)
    tracker.step("a", False, 0.0)
    for _ in range(19):
        assert tracker.step("a", False, 0.1) == SETTLING
    tracker.step("a", False, 0.1)
    assert tracker.step("a", False, 0.1) == REFINE  # after 2.0 s


# -- G-5: render fields only ---------------------------------------------------------------------------------------

def test_the_configuration_holds_render_fields_only_and_the_module_imports_no_core():
    """Q1 structurally: the fields are render fields; the module imports nothing of Core, the mesh, morph, pose or
    material modules (it cannot reach them)."""
    assert lq.config_fields() == ("effects", "shadow_size", "shadow_updates", "cube_samples", "samples", "jitter")
    source = Path(lq.__file__).read_text(encoding="utf-8")
    imported = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom):
            imported.add(("." * node.level) + (node.module or ""))
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    assert imported <= {"__future__", "statistics", "collections", "dataclasses", ".lookdev_optics"}, imported
    for forbidden in ("core", "mirai", "morph", "pose", "skin", "material", "gl"):
        assert not any(forbidden in name.split(".") for name in imported)


# -- G-7: Auto -----------------------------------------------------------------------------------------------------

def _feed(auto, ms, frames, start=0.0, step=1 / 30, tier=None):
    changed, t = [], start
    for _ in range(frames):
        if auto.feed(ms, tier or auto.tier, t):
            changed.append((t, auto.tier))
        t += step
    return changed, t


def test_auto_steps_down_above_the_target_at_most_once_per_two_seconds():
    auto = AutoTier()
    assert auto.tier == "hoch"
    changed, t = _feed(auto, 14.0, 29)
    assert changed == [] and auto.tier == "hoch"  # a window of 30 frames first
    changed, t = _feed(auto, 14.0, 1, t)
    assert changed and auto.tier == "mittel" and auto.remembered["hoch"] == 14.0
    changed, t = _feed(auto, 14.0, 40, t)  # 1.33 s later: the pace holds it
    assert auto.tier == "mittel" and changed == []
    changed, t = _feed(auto, 14.0, 30, t)
    assert auto.tier == "entwurf"
    _feed(auto, 30.0, 200, t)
    assert auto.tier == "entwurf"  # the lowest tier


def test_auto_steps_up_only_when_the_next_tier_was_measured_below_the_target():
    auto = AutoTier()
    _, t = _feed(auto, 14.0, 30)  # Hoch measured 14 ms -> Mittel
    assert auto.tier == "mittel"
    _, t = _feed(auto, 3.0, 300, t)
    assert auto.tier == "mittel"  # Hoch's remembered 14 ms > 12 ms: never up
    auto = AutoTier()
    auto.remembered["hoch"] = 10.0
    auto.tier = "mittel"
    changed, t = _feed(auto, 5.0, 59)
    assert auto.tier == "mittel"  # 60 frames below 6 ms first
    changed, t = _feed(auto, 5.0, 1, t)
    assert auto.tier == "hoch"


def test_auto_ignores_frames_of_another_tier_and_holds_mittel_without_a_timer():
    auto = AutoTier()
    _feed(auto, 30.0, 100, tier="mittel")  # frames drawn before the last change
    assert auto.tier == "hoch" and auto.p50 is None
    auto.unavailable()
    assert auto.tier == "mittel"
    _feed(auto, 30.0, 100)
    assert auto.tier == "mittel"
    assert auto.reason() == "Auto aus – Zeitmessung nicht verfügbar"
    auto.reset()
    assert auto.tier == "mittel"


def test_auto_reason_and_status_lines():
    auto = AutoTier()
    assert auto.reason() == "Auto"
    _feed(auto, 14.0, 30)
    assert auto.tier == "mittel" and auto.reason() == "Auto: 14 ms > 12 ms"  # why not Hoch
    _feed(auto, 8.0, 30, 10.0)
    assert auto.reason() == "Auto: 14 ms > 12 ms"  # still why: Hoch measured 14 ms
    assert lq.status_line(INTERACTIVE, "mittel", auto, False, "hoch") == "Interaktiv – Mittel (Auto: 14 ms > 12 ms)"
    hoch = AutoTier()
    _feed(hoch, 8.0, 30)
    assert hoch.reason() == "Auto: 8 ms"
    assert lq.status_line(SETTLING, "hoch", None, True, "maximal") == "Interaktiv – Hoch"
    assert lq.status_line(CONVERGED, "mittel", auto, True, "maximal") == "Ruhe – Maximal"
    assert lq.status_line(REFINE, "mittel", None, False, "maximal") == "Ruhe – Mittel"
    ceiling = IdleCeiling()
    for _ in range(lq.IDLE_CEILING_FRAMES):
        ceiling.feed(63.0)
    assert lq.status_line(CONVERGED, "hoch", None, True, "maximal", ceiling) == \
        "Ruhe – Maximal (ohne Weicher Schatten: 63 ms > 50 ms)"


def test_the_idle_ceiling_drops_one_knob_per_measured_window():
    ceiling = IdleCeiling()
    for _ in range(lq.IDLE_CEILING_FRAMES):
        ceiling.feed(30.0)
    assert ceiling.drops == ()
    dropped = [ceiling.feed(80.0) for _ in range(lq.IDLE_CEILING_FRAMES)]
    assert dropped[-1] and ceiling.drops == ("soft_shadow",)
    for _ in range(3 * lq.IDLE_CEILING_FRAMES):
        ceiling.feed(80.0)
    assert ceiling.drops == lq.IDLE_DROPS  # nothing more to drop
    ceiling.reset()
    assert ceiling.drops == () and ceiling.note() == ""


# -- G-12: the machine setting ----------------------------------------------------------------------------------------

def test_the_settings_round_trip(tmp_path):
    path = tmp_path / "state" / qs.FILE_NAME
    assert qs.load(path) == qs.DEFAULTS
    assert qs.DEFAULTS.as_dict() == {"tier": "auto", "refine": False, "idle_tier": "hoch", "wait": 0.3,
                                     "drag_updates": "every"}
    wanted = qs.QualitySettings("mittel", True, "maximal", 0.8, "frozen")
    assert qs.save(path, wanted)
    assert qs.load(path) == wanted
    assert not list(path.parent.glob("*.tmp"))


@pytest.mark.parametrize("text, expected", [
    ("not json", qs.DEFAULTS),
    ("[1, 2]", qs.DEFAULTS),
    ('{"tier": "ultra", "refine": "yes", "wait": 7, "idle_tier": "maximal"}',
     qs.QualitySettings(idle_tier="maximal")),
    ('{"tier": "entwurf", "future_key": 1, "wait": 1}', qs.QualitySettings(tier="entwurf", wait=1.0)),
])
def test_a_bad_file_or_value_falls_back_to_the_defaults_and_unknown_keys_are_ignored(tmp_path, text, expected):
    path = tmp_path / qs.FILE_NAME
    path.write_text(text, encoding="utf-8")
    assert qs.load(path) == expected


def test_the_default_path_is_the_users_state_directory():
    path = qs.default_path()
    assert path.name == "lookdev_quality.json" and path.parent.name == ".mirai_bastel"


@pytest.fixture
def app(tmp_path) -> Application:
    app = Application()
    app.init_scene("cube")
    app.set_viewport_size(800, 600)
    app.frame_scene()
    app.set_lookdev_quality_path(tmp_path / qs.FILE_NAME)
    return app


def test_the_app_writes_the_setting_and_nothing_into_the_scene(app, tmp_path):
    from core.serialization import scene_to_dict

    before = json.dumps(scene_to_dict(app.scene), sort_keys=True, default=str)
    history = len(app.history)
    assert app.open_lookdev()
    view_before = app.lookdev.studio
    assert app.set_lookdev_quality(tier="mittel", refine=True, idle_tier="maximal", wait=0.5)
    assert qs.load(tmp_path / qs.FILE_NAME) == qs.QualitySettings("mittel", True, "maximal", 0.5)
    assert app.lookdev.studio == view_before and len(app.history) == history  # no view state, no Undo
    assert json.dumps(scene_to_dict(app.scene), sort_keys=True, default=str) == before
    assert not app.set_lookdev_quality(tier="mittel")  # unchanged
    assert not app.set_lookdev_quality(tier="ultra") and "LookDev Qualität" in app.status_message
    assert app.set_lookdev_quality(wait=9.0) and app.lookdev_quality.wait == 2.0  # clamped
    other = Application()
    other.set_lookdev_quality_path(tmp_path / qs.FILE_NAME)
    assert other.lookdev_quality.tier == "mittel"  # read once at start


def test_the_scene_file_holds_no_quality(app, tmp_path):
    app.open_lookdev()
    app.set_lookdev_quality(tier="entwurf", refine=True)
    path = tmp_path / "s.mirai.json"
    app.save_scene_file(path)
    text = path.read_text(encoding="utf-8")
    for word in ("entwurf", "refine", "idle_tier", "drag_updates"):
        assert word not in text


# -- G-13 (headless part): the Worklight has none of it --------------------------------------------------------------

def test_the_worklight_creates_no_tracker_config_or_timing(app):
    app.update_viewport(1 / 60)
    viewport = app.viewport
    assert app.lookdev_activity is None and viewport.lookdev_config is None and not viewport.lookdev_timing
    assert viewport._lookdev_pass is None
    assert app.open_lookdev()
    app.update_viewport(1 / 60)
    assert app.lookdev_activity == INTERACTIVE and viewport.lookdev_config is not None and viewport.lookdev_timing
    assert app.close_lookdev()
    app.update_viewport(1 / 60)
    assert app.lookdev_activity is None and viewport.lookdev_config is None and not viewport.lookdev_timing
    assert viewport._lookdev_reachable == ()


def test_the_app_settles_refines_and_returns_on_a_change(app):
    app.set_lookdev_quality(refine=True, idle_tier="maximal")
    app.set_lookdev_effect("soft_shadow", True)
    assert app.open_lookdev()
    app.update_viewport(0.0)
    assert app.lookdev_activity == INTERACTIVE
    assert not app.viewport.lookdev_config.effects.soft_shadow  # F-R3: not while working
    assert "soft_shadow" in app.lookdev_effect_tiers()
    for _ in range(6):
        app.update_viewport(0.1)
    assert app.lookdev_activity in (REFINE, CONVERGED)
    config = app.viewport.lookdev_config
    assert config.effects.soft_shadow and config.shadow_size == 2048 and config.cube_samples == 256
    assert app.lookdev_quality_status() == "Ruhe – Maximal"
    app.camera.orbit(0.1, 0.0)
    app._camera_changed()
    app.update_viewport(0.0)
    assert app.lookdev_activity == INTERACTIVE and not app.viewport.lookdev_config.effects.soft_shadow
    assert app.lookdev_quality_status().startswith("Interaktiv – Hoch")


def test_a_held_interaction_or_material_preview_keeps_the_room_interactive(app):
    assert app.open_lookdev()
    app.update_viewport(0.0)
    assert app.preview_lookdev_material_values(roughness=0.3)
    for _ in range(10):
        app.update_viewport(0.1)
    assert app.lookdev_activity == INTERACTIVE  # a held slider, unchanged for a second
    app.end_lookdev_material_preview()
    for _ in range(5):
        app.update_viewport(0.1)
    assert app.lookdev_activity in (REFINE, CONVERGED)


# -- G-6: the signature -----------------------------------------------------------------------------------------------

def test_hover_the_status_line_and_the_wire_do_not_change_the_signature(app):
    assert app.open_lookdev()
    app.update_viewport(0.0)
    viewport = app.viewport
    size, key = (app.viewport_width, app.viewport_height), app._quality_key()
    before = viewport.lookdev_signature(size, key)
    app.set_status("irgendwas")
    app._set_hovered(None)
    app.set_lookdev_wire(True)
    app.update_viewport(0.0)
    assert viewport.lookdev_signature(size, key) == before
    for _ in range(5):
        app.update_viewport(0.1)
    assert app.lookdev_activity in (REFINE, CONVERGED)
