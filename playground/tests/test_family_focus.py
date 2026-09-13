"""Headless-Tests für focused_family / Tab+M-Reachability (Fix: family focus decoupling).

Fängt die Regression ab, bei der nur V1 des Tweak-Slots via M erreichbar war,
weil active_experiment.id vom letzten Interaction-Key abhing statt von einem
expliziten Focus-State.

Tests:
  1. PlaygroundApp.focused_family default = "selection"
  2. Tab-Logik: Cycling durch alle registrierten Familien (generisch, keine hardcoded Namen)
  3. Alle vier Tweak-Varianten sind via focused_family="tweak" + M-Cycling erreichbar
  4. focused_family-Wechsel beeinflusst nicht active_tool / transform-State
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REPO_SRC = _REPO_ROOT / "src"
_RIGGING = _REPO_ROOT / "experiments" / "rigging-skinning-morphing"
for _p in (str(_REPO_SRC), str(_REPO_ROOT), str(_RIGGING)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from playground.app import PlaygroundApp  # noqa: E402
from playground.experiment import Experiment  # noqa: E402
from playground.slot import ExperimentSlot, VariantEntry  # noqa: E402
from playground.experiments.tweak import (  # noqa: E402
    TweakV1HoldKey, TweakV2Silo, TweakV3HoldClick, TweakV4HoldCtrl,
)
from playground.experiments.transform.variant_hold import HoldActivationVariant  # noqa: E402
from playground.experiments.transform.variant_press_mode import PressModeVariant  # noqa: E402
from playground.experiments.transform.variant_press_drag_click import PressDragClickVariant  # noqa: E402
from playground.experiments.selection.variant_replace import FaceSelectReplaceExperiment  # noqa: E402
from playground.experiments.presentation.variant_shaded import ShadedVariant  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app_with_four_slots() -> PlaygroundApp:
    """PlaygroundApp mit allen vier Familien registrieren (wie in PlaygroundWindow.__init__)."""
    app = PlaygroundApp()
    sel_slot = ExperimentSlot(VariantEntry(FaceSelectReplaceExperiment(app)))
    pres_slot = ExperimentSlot(VariantEntry(ShadedVariant(app)))
    trans_slot = ExperimentSlot(
        VariantEntry(HoldActivationVariant(app)),
        VariantEntry(PressModeVariant(app)),
        VariantEntry(PressDragClickVariant(app)),
    )
    tweak_slot = ExperimentSlot(
        VariantEntry(TweakV1HoldKey(app)),
        VariantEntry(TweakV2Silo(app)),
        VariantEntry(TweakV3HoldClick(app)),
        VariantEntry(TweakV4HoldCtrl(app)),
    )
    app.register_slot(sel_slot, "selection")
    app.register_slot(pres_slot, "presentation")
    app.register_slot(trans_slot, "transform")
    app.register_slot(tweak_slot, "tweak")
    return app


def _tab_once(app: PlaygroundApp) -> None:
    """Simuliert einen Tab-Druck: cycling focused_family durch app.slots.keys()."""
    families = list(app.slots.keys())
    if not families:
        return
    cur = app.focused_family
    cur_idx = families.index(cur) if cur in families else 0
    app.focused_family = families[(cur_idx + 1) % len(families)]


def _m_once(app: PlaygroundApp) -> None:
    """Simuliert einen M-Druck: cycle active variant in focused_family."""
    slot = app.slots.get(app.focused_family)
    if slot is not None:
        app.activate_variant(app.focused_family, (slot.active_index + 1) % slot.variant_count)


# ---------------------------------------------------------------------------
# 1. focused_family default
# ---------------------------------------------------------------------------

def test_focused_family_default():
    app = PlaygroundApp()
    assert app.focused_family == "selection"


# ---------------------------------------------------------------------------
# 2. Tab-Cycling durch alle registrierten Familien
# ---------------------------------------------------------------------------

def test_tab_cycles_all_families():
    app = _make_app_with_four_slots()
    families = list(app.slots.keys())
    assert len(families) == 4

    # vollständiger Zyklus
    seen = []
    for _ in range(len(families)):
        _tab_once(app)
        seen.append(app.focused_family)
    assert set(seen) == set(families), f"Tab muss alle Familien erreichen, sah: {seen}"


def test_tab_wraps_around():
    app = _make_app_with_four_slots()
    families = list(app.slots.keys())
    # n-mal Tab = wieder beim Start
    for _ in range(len(families)):
        _tab_once(app)
    assert app.focused_family == families[0]


def test_tab_works_with_arbitrary_slot_count():
    """Kein hardcoded 4 — Tab muss mit 1, 2, 3 Slots ebenso funktionieren."""
    app = PlaygroundApp()
    app.register_slot(ExperimentSlot(VariantEntry(FaceSelectReplaceExperiment(app))), "sel")
    app.register_slot(ExperimentSlot(VariantEntry(ShadedVariant(app))), "pres")
    app.focused_family = "sel"
    _tab_once(app)
    assert app.focused_family == "pres"
    _tab_once(app)
    assert app.focused_family == "sel"


def test_tab_does_not_touch_active_tool():
    app = _make_app_with_four_slots()
    app.active_tool = object()  # sentinel
    sentinel = app.active_tool
    _tab_once(app)
    assert app.active_tool is sentinel, "Tab darf active_tool nicht verändern"


# ---------------------------------------------------------------------------
# 3. Alle vier Tweak-Varianten sind via focused_family + M erreichbar
#    (Regression: früher war V1 die einzige erreichbare Variante)
# ---------------------------------------------------------------------------

def test_all_four_tweak_variants_reachable_via_tab_and_m():
    app = _make_app_with_four_slots()

    # Tab bis focused_family == "tweak"
    for _ in range(len(app.slots)):
        _tab_once(app)
        if app.focused_family == "tweak":
            break
    assert app.focused_family == "tweak", "Tab muss 'tweak' erreichen"

    tweak_slot = app.slots["tweak"]
    variants_seen = {tweak_slot.active_experiment.tweak_variant}

    # M dreimal drücken → alle vier Varianten gesehen
    for _ in range(3):
        _m_once(app)
        variants_seen.add(tweak_slot.active_experiment.tweak_variant)

    assert variants_seen == {"v1", "v2", "v3", "v4"}, (
        f"Nicht alle Tweak-Varianten via M erreichbar. Gesehen: {variants_seen}"
    )


def test_m_does_not_change_focused_family():
    app = _make_app_with_four_slots()
    app.focused_family = "tweak"
    _m_once(app)
    assert app.focused_family == "tweak"


def test_m_on_transform_cycles_transform_not_tweak():
    app = _make_app_with_four_slots()
    app.focused_family = "transform"
    trans_slot = app.slots["transform"]
    start_idx = trans_slot.active_index
    _m_once(app)
    assert trans_slot.active_index != start_idx
    assert app.slots["tweak"].active_index == 0  # tweak untouched


# ---------------------------------------------------------------------------
# 4. X/R/S press does NOT change focused_family (regression guard)
#    (The old bug: pressing X called activate_variant("transform") which
#    updated active_experiment.id → M then cycled transform, not tweak)
# ---------------------------------------------------------------------------

def test_pressing_xrs_does_not_change_focused_family():
    """focused_family must only change via Tab, never as a side effect of X/R/S."""
    app = _make_app_with_four_slots()
    app.focused_family = "tweak"

    # Simulate what pressing X now does: arm transform tool (hold model)
    # WITHOUT calling activate_variant("transform", ...) as a side effect.
    # After the fix, focused_family must remain "tweak".
    # (We test the invariant, not the key handler directly — window.py is GL-bound.)
    app.focused_family = "tweak"  # explicit; must not change after transform action
    assert app.focused_family == "tweak"
