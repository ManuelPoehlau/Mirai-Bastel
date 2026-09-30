"""Session-State-Persistenz (playground/session_state.py + Window-Verdrahtung).

Zwei Ebenen:
  - Unit: capture/save/load/apply gegen eine headless `PlaygroundApp` mit den
    echten Slots (roundtrip, kaputte/fehlende Datei, unbekannte IDs, Version,
    atomarer Write).
  - Integration: echtes (headless) `PlaygroundWindow` mit tmp-State-Pfad, per
    Tastenhandler bedient wie im Live-Fenster. Vergleich: wiederhergestellter
    Zustand == manuell geschalteter Zustand (Familie, Varianten, Display, HUD).

Nicht getestet (bewusst nicht persistiert): Komponenten-Modus, Selection-Method,
Kamera, Mesh.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT / "src"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from pyglet.window import key as _key  # noqa: E402

from mirai.viewport.display import DisplayMode  # noqa: E402
from playground import session_state  # noqa: E402
from playground.selector import SelectMode  # noqa: E402


def _window(path: Path | None, restore: bool = True):
    from playground.app import PlaygroundApp
    from playground.window import PlaygroundWindow

    app = PlaygroundApp()
    win = PlaygroundWindow(
        app, initial_mesh="cube", session_state_path=path, restore_session=restore
    )
    return win, app


def _family_variants(app) -> dict[str, str]:
    return {fid: session_state.variant_key(s.active) for fid, s in app.slots.items()}


def _press(win, symbol, modifiers=0) -> None:
    win.on_key_press(symbol, modifiers)


def _focus(win, family: str) -> None:
    """Per Tab (wie der Artist) auf `family` fokussieren."""
    for _ in range(len(win.app.slots)):
        if win.app.focused_family == family:
            return
        _press(win, _key.TAB)
    raise AssertionError(f"family {family!r} nicht per Tab erreichbar")


def _select_variant(win, family: str, variant_class: str) -> None:
    """Per M (wie der Artist) die Variante `variant_class` der Family aktivieren."""
    _focus(win, family)
    slot = win.app.slots[family]
    for _ in range(slot.variant_count):
        if session_state.variant_key(slot.active) == variant_class:
            return
        _press(win, _key.M)
    raise AssertionError(f"{variant_class!r} nicht per M erreichbar")


def _observable(win, app) -> dict:
    return {
        "focused": app.focused_family,
        "variants": _family_variants(app),
        "active_experiment": type(app.active_experiment).__name__,
        "display": (app.display_state.mode, app.display_state.wireframe_overlay),
        "select_mode": app.select_mode,
        "hud": win._hud._full_text(),
    }


# ---------------------------------------------------------------------------
# Unit — Datei-I/O
# ---------------------------------------------------------------------------

@pytest.fixture
def win_app():
    win, app = _window(None)
    try:
        yield win, app
    finally:
        win.close()


def test_roundtrip(tmp_path, win_app):
    win, app = win_app
    _select_variant(win, "knife_face", "KnifeFaceVariantD")
    _press(win, _key.D, _key.MOD_SHIFT)
    path = tmp_path / "state.json"

    assert session_state.save_app(app, path)
    state = session_state.load(path)

    assert state == session_state.capture(app)
    assert state["version"] == session_state.STATE_VERSION
    assert state["focused_family"] == "knife_face"
    assert state["variants"]["knife_face"] == "KnifeFaceVariantD"
    assert state["display"]["wireframe_overlay"] is True


def test_missing_file_falls_back(tmp_path):
    assert session_state.load(tmp_path / "nope.json") is None


@pytest.mark.parametrize("content", ["", "{not json", "[1, 2]", "null", '"text"'])
def test_corrupt_file_falls_back(tmp_path, content):
    path = tmp_path / "state.json"
    path.write_text(content, encoding="utf-8")
    assert session_state.load(path) is None


@pytest.mark.parametrize("version", [0, 2, "1", None])
def test_version_mismatch_falls_back(tmp_path, version):
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"version": version, "focused_family": "tweak"}))
    assert session_state.load(path) is None


def test_missing_version_falls_back(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"focused_family": "tweak"}))
    assert session_state.load(path) is None


def test_save_is_atomic_and_leaves_no_temp_file(tmp_path):
    path = tmp_path / "state.json"
    assert session_state.save(path, {"version": 1, "a": 1})
    assert json.loads(path.read_text()) == {"version": 1, "a": 1}
    assert [p.name for p in tmp_path.iterdir()] == ["state.json"]


def test_failed_replace_keeps_previous_file_intact(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    session_state.save(path, {"version": 1, "a": "old"})

    def boom(*_a, **_k):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", boom)
    assert session_state.save(path, {"version": 1, "a": "new"}) is False

    assert json.loads(path.read_text()) == {"version": 1, "a": "old"}
    assert [p.name for p in tmp_path.iterdir()] == ["state.json"]  # tmp aufgeräumt


def test_save_to_unwritable_location_does_not_raise(tmp_path):
    assert session_state.save(tmp_path / "missing_dir" / "state.json", {"version": 1}) is False


# ---------------------------------------------------------------------------
# Unit — apply()
# ---------------------------------------------------------------------------

def test_unknown_variant_only_that_entry_falls_back(win_app):
    _win, app = win_app
    state = {
        "version": 1,
        "focused_family": "knife_face",
        "variants": {
            "knife_face": "KnifeFaceVariantQ5",
            "tweak": "TweakV999DoesNotExist",   # unbekannte Variante
            "ghost_family": "Whatever",          # unbekannte Family
            "transform": "PressModeVariant",
        },
        "display": {"mode": "NOT_A_MODE", "wireframe_overlay": True},
    }
    tweak_before = session_state.variant_key(app.slots["tweak"].active)

    skipped = session_state.apply(app, state)

    assert len(skipped) == 3
    assert session_state.variant_key(app.slots["knife_face"].active) == "KnifeFaceVariantQ5"
    assert session_state.variant_key(app.slots["transform"].active) == "PressModeVariant"
    assert session_state.variant_key(app.slots["tweak"].active) == tweak_before
    assert app.focused_family == "knife_face"
    assert app.display_state.wireframe_overlay is True  # gültiger Teil bleibt


def test_unknown_focused_family_keeps_default(win_app):
    _win, app = win_app
    session_state.apply(app, {"version": 1, "focused_family": "ghost"})
    assert app.focused_family == "selection"


@pytest.mark.parametrize("state", [
    {"version": 1, "variants": ["not", "a", "dict"], "display": "x", "focused_family": ["x"]},
    {"version": 1, "variants": {"tweak": ["unhashable"]}, "display": {"mode": ["x"], "wireframe_overlay": "yes"}},
    {"version": 1},
])
def test_malformed_sections_never_raise(win_app, state):
    _win, app = win_app
    before = _family_variants(app)
    session_state.apply(app, state)
    assert _family_variants(app) == before


# ---------------------------------------------------------------------------
# Integration — echtes Fenster
# ---------------------------------------------------------------------------

def test_selection_default_is_modifier_without_any_state():
    """4.B: Registry-Default = Modifier (KEEP, selection/decision.md), unabhängig
    von der Registrierungsreihenfolge und ohne State-Datei."""
    win, app = _window(None)
    try:
        assert session_state.variant_key(app.slots["selection"].active) == "FaceSelectModifierExperiment"
        assert app.select_mode is SelectMode.MODIFIER
        assert app.focused_family == "selection"
    finally:
        win.close()


def test_restart_restores_state_like_manual_switching(tmp_path):
    """Akzeptanz 1/4/6: Knife Face + Variante + Nicht-Default-Selection +
    Wireframe Overlay → schließen → Start: identischer Zustand ohne Tastendruck."""
    path = tmp_path / "state.json"

    win1, app1 = _window(path)
    try:
        _select_variant(win1, "selection", "FaceSelectToggleExperiment")
        _select_variant(win1, "presentation", "FlatVariant")
        _press(win1, _key.D, _key.MOD_SHIFT)              # Wireframe Overlay an
        _select_variant(win1, "knife_face", "KnifeFaceVariantQ5")  # Fokus endet hier
        manual = _observable(win1, app1)
    finally:
        win1.close()                                       # speichert
    assert path.is_file()

    win2, app2 = _window(path)
    try:
        restored = _observable(win2, app2)
        assert restored == manual
        assert restored["focused"] == "knife_face"
        assert restored["variants"]["knife_face"] == "KnifeFaceVariantQ5"
        assert restored["variants"]["selection"] == "FaceSelectToggleExperiment"
        assert restored["select_mode"] is SelectMode.TOGGLE
        assert restored["display"] == (DisplayMode.FLAT_SHADED, True)
        # Kein Phantom-Tool: nichts wurde "aktiviert", nur Varianten geschaltet.
        assert app2.active_tool is None
        assert win2._current_tool_type is None
        assert win2._active_session() is None
    finally:
        win2.close()


def test_wireframe_mode_and_overlay_restore(tmp_path):
    path = tmp_path / "state.json"
    win1, app1 = _window(path)
    try:
        _select_variant(win1, "presentation", "WireframeVariant")
        _press(win1, _key.D, _key.MOD_SHIFT)
    finally:
        win1.close()
    win2, app2 = _window(path)
    try:
        assert app2.display_state.mode is DisplayMode.WIREFRAME
        assert app2.display_state.wireframe_overlay is True
    finally:
        win2.close()


def test_state_is_saved_on_every_change_not_only_on_close(tmp_path):
    """Crash-Sicherheit: die Datei ist nach jedem Wechsel aktuell."""
    path = tmp_path / "state.json"
    win, app = _window(path)
    try:
        _press(win, _key.TAB)
        assert json.loads(path.read_text())["focused_family"] == app.focused_family
        _press(win, _key.M)
        stored = json.loads(path.read_text())["variants"]
        assert stored[app.focused_family] == session_state.variant_key(app.slots[app.focused_family].active)
        _press(win, _key.D, _key.MOD_SHIFT)
        assert json.loads(path.read_text())["display"]["wireframe_overlay"] is True
    finally:
        win.close()


def test_unknown_variant_in_file_restores_the_rest(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(json.dumps({
        "version": 1,
        "focused_family": "knife_face",
        "variants": {
            "knife_face": "KnifeFaceVariantD",
            "tweak": "RemovedVariant",
            "selection": "FaceSelectToggleExperiment",
        },
        "display": {"mode": "WIREFRAME", "wireframe_overlay": True},
    }))
    win, app = _window(path)
    try:
        v = _family_variants(app)
        assert v["knife_face"] == "KnifeFaceVariantD"
        assert v["selection"] == "FaceSelectToggleExperiment"
        assert v["tweak"] == "TweakV2Silo"        # Registry-Default
        assert app.focused_family == "knife_face"
        assert app.display_state.mode is DisplayMode.WIREFRAME
    finally:
        win.close()


@pytest.mark.parametrize("content", [None, "{corrupt", '{"version": 99}'])
def test_missing_or_corrupt_file_starts_with_defaults(tmp_path, content):
    path = tmp_path / "state.json"
    if content is not None:
        path.write_text(content)
    win, app = _window(path)
    try:
        assert app.focused_family == "selection"
        assert session_state.variant_key(app.slots["selection"].active) == "FaceSelectModifierExperiment"
    finally:
        win.close()


def test_reset_starts_with_defaults_and_overwrites_file_on_close(tmp_path):
    """Akzeptanz 5: --reset-state ⇒ restore_session=False."""
    path = tmp_path / "state.json"
    win1, app1 = _window(path)
    try:
        _select_variant(win1, "knife_face", "KnifeFaceVariantQ5")
    finally:
        win1.close()

    win2, app2 = _window(path, restore=False)
    try:
        assert app2.focused_family == "selection"
        assert session_state.variant_key(app2.slots["knife_face"].active) == "KnifeFaceVariantB"
        assert json.loads(path.read_text())["focused_family"] == "knife_face"  # noch nicht überschrieben
    finally:
        win2.close()
    stored = json.loads(path.read_text())
    assert stored["focused_family"] == "selection"
    assert stored["variants"]["knife_face"] == "KnifeFaceVariantB"


def test_window_without_path_never_touches_disk(tmp_path, monkeypatch):
    monkeypatch.setattr(session_state, "save", lambda *a, **k: pytest.fail("save() aufgerufen"))
    win, _app = _window(None)
    try:
        _press(win, _key.TAB)
        _press(win, _key.M)
    finally:
        win.close()


def test_input_truth_and_entry_point_flag():
    """Kein neuer Hotkey / keine Bindung: Reset läuft nur über den CLI-Flag."""
    assert session_state.RESET_FLAG == "--reset-state"
    run_src = (_ROOT / "playground" / "run.py").read_text(encoding="utf-8")
    assert "RESET_FLAG" in run_src and "restore_session" in run_src
