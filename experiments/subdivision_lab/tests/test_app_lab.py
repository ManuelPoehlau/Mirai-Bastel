"""The SubD Lab on the app path, headless (TraceStore, no window) — since 2026-10-23 a harness
around the Production SubD preview.

Built like `run.build_app_lab`. SubD itself (surface, lines, keys, fallback) is the app's and is
tested in `tests/test_subdivision_app.py`; here only what the lab adds: its A/B key (lab context,
conflict-checked against every app context including `subd`), the HUD line, and that every other
key — the SubD keys included — reaches the app.
"""

from __future__ import annotations

import pytest

from mirai.interaction.input import SUBD_CONTEXT, Input
from mirai.subdivision import VIEW_CAGE, VIEW_ISO, VIEW_OFF

from subdivision_lab.lab_app import (
    LAB_KEYS,
    TOGGLE_AB,
    LabBindingConflict,
    assert_lab_keys_free,
    hud_text,
    lab_key_press,
    startup_listing,
)
from subdivision_lab.run import build_app_lab
from subdivision_lab.subd import SubdSurface

WIDTH, HEIGHT = 800, 600
V = Input("key", "v")
B = Input("key", "b")
W = Input("key", "w")


@pytest.fixture
def lab_app():
    return build_app_lab("subd_cube", WIDTH, HEIGHT)


def frame(app) -> None:
    app.viewport.sync()


def test_lab_keys_are_free_in_every_app_context_and_conflicts_abort(lab_app):
    app, _lab = lab_app
    assert_lab_keys_free(app.bindings)
    app.bindings.set_default(B, "Something", context=SUBD_CONTEXT)
    with pytest.raises(LabBindingConflict):
        assert_lab_keys_free(app.bindings)


def test_the_app_preview_is_what_the_lab_shows(lab_app):
    app, lab = lab_app
    assert lab.preview is app.subdivision
    assert lab_key_press(app, lab, V)  # the app's SubD key, forwarded
    frame(app)
    assert lab.effective_view() == VIEW_CAGE
    assert app.viewport.surface_provider is app.subdivision.provider
    surface = SubdSurface(app.viewport.mesh)
    assert lab.provider.derived_counts[1] == surface.predicted_face_count(lab.level)


def test_ab_toggles_the_cage_view_and_restores_view_and_level(lab_app):
    app, lab = lab_app
    lab_key_press(app, lab, V)
    lab_key_press(app, lab, V)  # iso
    lab_key_press(app, lab, Input("key", "3", frozenset({"ctrl"})))
    frame(app)
    state = app.viewport.mesh.export_state()
    assert lab_key_press(app, lab, B)
    frame(app)
    assert lab.ab_active and app.subdivision.view == VIEW_OFF
    assert app.viewport.surface_render_mesh is None
    assert "(A/B)" in hud_text(lab, "subd_cube")
    assert lab_key_press(app, lab, B)
    frame(app)
    assert not lab.ab_active
    assert app.subdivision.view == VIEW_ISO and lab.level == 3
    assert app.viewport.surface_render_mesh is not None
    assert app.viewport.mesh.export_state() == state


def test_ab_with_the_preview_off_compares_nothing(lab_app):
    app, lab = lab_app
    assert not lab_key_press(app, lab, B)
    assert "nichts zu vergleichen" in app.status_message


def test_v_during_ab_ends_ab(lab_app):
    app, lab = lab_app
    lab_key_press(app, lab, V)
    lab_key_press(app, lab, B)
    lab_key_press(app, lab, V)  # the app cycles off -> cage
    assert not lab.ab_active
    assert app.subdivision.view == VIEW_CAGE


def test_lab_key_refused_while_a_transform_is_armed(lab_app):
    app, lab = lab_app
    lab_key_press(app, lab, V)
    vid = sorted(app.viewport.mesh.all_vertex_ids(), key=int)[0]
    app.selection.set({vid})
    app.key_press(W)
    assert not lab_key_press(app, lab, B)
    assert "ignoriert" in app.status_message
    app.key_release(W)


def test_other_keys_go_to_the_app(lab_app):
    app, lab = lab_app
    assert lab_key_press(app, lab, Input("key", "2"))
    assert app.selection.mode.name == "EDGE"


def test_hud_and_listing(lab_app):
    app, lab = lab_app
    lab_key_press(app, lab, V)
    frame(app)
    text = hud_text(lab, "subd_cube", frame_ms=16.0)
    assert "Stufe" in text and "Fläche" in text and "Aufbau" in text and "Frame 16.0 ms" in text
    listing = "\n".join(startup_listing())
    assert "SubdCycleView" in listing and TOGGLE_AB in listing


def test_every_lab_key_is_listed_once():
    inputs = [entry.input for entry in LAB_KEYS]
    assert len(inputs) == len(set(inputs))
