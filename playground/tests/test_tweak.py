"""Headless-Tests für Tweak Lab (playground/experiments/tweak/).

Testet headless-testable Logik:
  1. has_selection() — korrekte Erkennung in allen drei Component-Modi
  2. add_temp_target() — fügt in den richtigen Set ein
  3. clear_temp_target() — leert den richtigen Set
  4. toggle_persistent_mode() — Toggle-Semantik
  5. Slot-Registrierung — vier Varianten vorhanden, richtige IDs
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

from core.selection import SelectionMode  # noqa: E402
from playground.experiments.tweak._target import (  # noqa: E402
    add_temp_target,
    clear_temp_target,
    has_selection,
    toggle_persistent_mode,
)
from playground.experiments.tweak import (  # noqa: E402
    TweakV1HoldKey,
    TweakV2Silo,
    TweakV3HoldClick,
    TweakV4HoldCtrl,
)
from playground.slot import ExperimentSlot, VariantEntry  # noqa: E402


# ---------------------------------------------------------------------------
# Mock-Selektion (kein GL, kein Mesh)
# ---------------------------------------------------------------------------

class _Sel:
    def __init__(self, mode: SelectionMode = SelectionMode.FACE) -> None:
        self.mode = mode
        self.faces: set = set()
        self.vertices: set = set()
        self.edges: set = set()


# ---------------------------------------------------------------------------
# 1. has_selection()
# ---------------------------------------------------------------------------

def test_has_selection_false_when_empty_face():
    sel = _Sel(SelectionMode.FACE)
    assert not has_selection(sel)


def test_has_selection_true_when_face_present():
    sel = _Sel(SelectionMode.FACE)
    sel.faces.add(42)
    assert has_selection(sel)


def test_has_selection_false_when_empty_vertex():
    sel = _Sel(SelectionMode.VERTEX)
    assert not has_selection(sel)


def test_has_selection_true_when_vertex_present():
    sel = _Sel(SelectionMode.VERTEX)
    sel.vertices.add(7)
    assert has_selection(sel)


def test_has_selection_false_when_empty_edge():
    sel = _Sel(SelectionMode.EDGE)
    assert not has_selection(sel)


def test_has_selection_true_when_edge_present():
    sel = _Sel(SelectionMode.EDGE)
    sel.edges.add(3)
    assert has_selection(sel)


# ---------------------------------------------------------------------------
# 2. add_temp_target()
# ---------------------------------------------------------------------------

def test_add_temp_target_face_mode():
    sel = _Sel(SelectionMode.FACE)
    add_temp_target(sel, 99)
    assert 99 in sel.faces
    assert not sel.vertices
    assert not sel.edges


def test_add_temp_target_vertex_mode():
    sel = _Sel(SelectionMode.VERTEX)
    add_temp_target(sel, 5)
    assert 5 in sel.vertices
    assert not sel.faces


def test_add_temp_target_edge_mode():
    sel = _Sel(SelectionMode.EDGE)
    add_temp_target(sel, 11)
    assert 11 in sel.edges
    assert not sel.faces


# ---------------------------------------------------------------------------
# 3. clear_temp_target()
# ---------------------------------------------------------------------------

def test_clear_temp_target_face():
    sel = _Sel(SelectionMode.FACE)
    sel.faces.add(1)
    clear_temp_target(sel)
    assert not sel.faces


def test_clear_temp_target_vertex():
    sel = _Sel(SelectionMode.VERTEX)
    sel.vertices.add(2)
    clear_temp_target(sel)
    assert not sel.vertices


def test_clear_temp_target_edge():
    sel = _Sel(SelectionMode.EDGE)
    sel.edges.add(3)
    clear_temp_target(sel)
    assert not sel.edges


# ---------------------------------------------------------------------------
# 4. toggle_persistent_mode()
# ---------------------------------------------------------------------------

def test_toggle_from_none_activates_mode():
    assert toggle_persistent_mode(None, "move") == "move"


def test_toggle_same_key_deactivates():
    assert toggle_persistent_mode("move", "move") is None


def test_toggle_different_key_switches():
    assert toggle_persistent_mode("move", "rotate") == "rotate"


def test_toggle_from_none_to_scale():
    assert toggle_persistent_mode(None, "scale") == "scale"


def test_toggle_scale_to_none():
    assert toggle_persistent_mode("scale", "scale") is None


def test_toggle_rotate_to_move():
    assert toggle_persistent_mode("rotate", "move") == "move"


# ---------------------------------------------------------------------------
# 5. Slot-Registrierung — vier Varianten, korrekte IDs und tweak_variant
# ---------------------------------------------------------------------------

class _FakeApp:
    pass


def test_tweak_slot_has_four_variants():
    app = _FakeApp()
    slot = ExperimentSlot(
        VariantEntry(TweakV1HoldKey(app)),
        VariantEntry(TweakV2Silo(app)),
        VariantEntry(TweakV3HoldClick(app)),
        VariantEntry(TweakV4HoldCtrl(app)),
    )
    assert slot.variant_count == 4


def test_tweak_variant_ids_are_tweak():
    app = _FakeApp()
    for cls in (TweakV1HoldKey, TweakV2Silo, TweakV3HoldClick, TweakV4HoldCtrl):
        assert cls(app).id == "tweak"


def test_tweak_variant_tags():
    app = _FakeApp()
    assert TweakV1HoldKey(app).tweak_variant == "v1"
    assert TweakV2Silo(app).tweak_variant == "v2"
    assert TweakV3HoldClick(app).tweak_variant == "v3"
    assert TweakV4HoldCtrl(app).tweak_variant == "v4"


def test_tweak_slot_cycles():
    app = _FakeApp()
    slot = ExperimentSlot(
        VariantEntry(TweakV1HoldKey(app)),
        VariantEntry(TweakV2Silo(app)),
        VariantEntry(TweakV3HoldClick(app)),
        VariantEntry(TweakV4HoldCtrl(app)),
    )
    assert slot.active_experiment.tweak_variant == "v1"
    slot.activate(1)
    assert slot.active_experiment.tweak_variant == "v2"
    slot.activate(3)
    assert slot.active_experiment.tweak_variant == "v4"
    slot.activate(0)
    assert slot.active_experiment.tweak_variant == "v1"
