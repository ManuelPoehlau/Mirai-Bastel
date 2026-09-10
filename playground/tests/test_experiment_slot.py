"""Headless-Tests für ExperimentSlot (WP-AP-02).

Kein GL, kein Fenster, kein pyglet. Prüft:
    1. ExperimentSlot mit einer Variante — active gibt erste Variante zurück
    2. activate() wechselt Variante und ruft deactivate/activate-Hooks auf
    3. set_decision() setzt Decision auf aktiver Variante
    4. Decision.UNDECIDED ist der Default
    5. generate_decision_md() erzeugt valides Markdown
    6. write_decision_md() schreibt Datei und Inhalt stimmt
    7. ExperimentSlot ohne Varianten wirft ValueError
    8. activate() mit ungültigem Index wirft IndexError
    9. HUD update_experiment() zeigt Decision-Status korrekt an
    10. PlaygroundApp.set_slot() + activate_variant() arbeiten zusammen
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

import pytest  # noqa: E402

from playground.experiment import Experiment  # noqa: E402
from playground.hud import PlaygroundHUD  # noqa: E402
from playground.slot import Decision, ExperimentSlot, VariantEntry  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _TrackingExperiment(Experiment):
    """Experiment das activate/deactivate-Aufrufe aufzeichnet."""

    def __init__(self, eid: str, name: str = "", variant: str = "") -> None:
        self.id = eid
        self.name = name or eid
        self.variant = variant
        self.activated = 0
        self.deactivated = 0

    def activate(self) -> None:
        self.activated += 1

    def deactivate(self) -> None:
        self.deactivated += 1


def _make_slot(*ids: str) -> ExperimentSlot:
    variants = [VariantEntry(_TrackingExperiment(eid, variant=eid)) for eid in ids]
    return ExperimentSlot(*variants)


# ---------------------------------------------------------------------------
# 1. Basis: active zeigt erste Variante
# ---------------------------------------------------------------------------

def test_slot_initial_active_is_first():
    slot = _make_slot("a", "b", "c")
    assert slot.active.experiment.id == "a"
    assert slot.active_index == 0


# ---------------------------------------------------------------------------
# 2. activate() wechselt Variante + Hooks
# ---------------------------------------------------------------------------

def test_activate_calls_hooks():
    slot = _make_slot("a", "b")
    exp_a: _TrackingExperiment = slot.variants[0].experiment  # type: ignore[assignment]
    exp_b: _TrackingExperiment = slot.variants[1].experiment  # type: ignore[assignment]

    slot.activate(1)

    assert slot.active_index == 1
    assert slot.active.experiment.id == "b"
    assert exp_a.deactivated == 1
    assert exp_b.activated == 1


def test_activate_same_index_is_noop():
    slot = _make_slot("a", "b")
    exp_a: _TrackingExperiment = slot.variants[0].experiment  # type: ignore[assignment]
    slot.activate(0)
    assert exp_a.deactivated == 0  # kein Aufruf


# ---------------------------------------------------------------------------
# 3. set_decision() setzt Decision auf aktiver Variante
# ---------------------------------------------------------------------------

def test_set_decision_updates_active():
    slot = _make_slot("a", "b")
    slot.set_decision(Decision.KEEP, notes="Fühlt sich gut an")
    assert slot.active.decision == Decision.KEEP
    assert slot.active.notes == "Fühlt sich gut an"


def test_set_decision_does_not_affect_other_variants():
    slot = _make_slot("a", "b")
    slot.set_decision(Decision.KEEP)
    slot.activate(1)
    assert slot.active.decision == Decision.UNDECIDED


# ---------------------------------------------------------------------------
# 4. UNDECIDED ist Default
# ---------------------------------------------------------------------------

def test_default_decision_is_undecided():
    slot = _make_slot("a")
    assert slot.active.decision == Decision.UNDECIDED


# ---------------------------------------------------------------------------
# 5. generate_decision_md() erzeugt valides Markdown
# ---------------------------------------------------------------------------

def test_generate_decision_md_contains_variant_ids():
    slot = _make_slot("variant_a", "variant_b")
    slot.activate(0)
    slot.set_decision(Decision.KEEP)
    slot.activate(1)
    slot.set_decision(Decision.REJECT)

    md = slot.generate_decision_md()

    assert "variant_a" in md
    assert "variant_b" in md
    assert "KEEP" in md
    assert "REJECT" in md


def test_generate_decision_md_starts_with_heading():
    exp = _TrackingExperiment("box_select", name="Box Select")
    slot = ExperimentSlot(VariantEntry(exp))
    md = slot.generate_decision_md()
    assert md.startswith("# Box Select")


# ---------------------------------------------------------------------------
# 6. write_decision_md() schreibt Datei
# ---------------------------------------------------------------------------

def test_write_decision_md_creates_file(tmp_path: Path):
    slot = _make_slot("a")
    path = slot.write_decision_md(tmp_path)
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "UNDECIDED" in content


def test_write_decision_md_creates_directory(tmp_path: Path):
    slot = _make_slot("a")
    nested = tmp_path / "experiments" / "select_box"
    slot.write_decision_md(nested)
    assert (nested / "decision.md").exists()


# ---------------------------------------------------------------------------
# 7. Keine Varianten → ValueError
# ---------------------------------------------------------------------------

def test_empty_slot_raises():
    with pytest.raises(ValueError):
        ExperimentSlot()


# ---------------------------------------------------------------------------
# 8. Ungültiger Index → IndexError
# ---------------------------------------------------------------------------

def test_invalid_index_raises():
    slot = _make_slot("a", "b")
    with pytest.raises(IndexError):
        slot.activate(99)


# ---------------------------------------------------------------------------
# 9. HUD: update_experiment() zeigt Decision-Status
# ---------------------------------------------------------------------------

def test_hud_shows_decision_status():
    hud = PlaygroundHUD()
    exp = _TrackingExperiment("box_select", name="Box Select", variant="A")
    hud.update_experiment(exp, decision="KEEP")
    assert "KEEP" in hud.experiment_line
    assert "[KEEP]" in hud.experiment_line


def test_hud_undecided_not_shown():
    hud = PlaygroundHUD()
    exp = _TrackingExperiment("box_select", name="Box Select")
    hud.update_experiment(exp, decision="UNDECIDED")
    assert "UNDECIDED" not in hud.experiment_line


def test_hud_no_decision_no_status():
    hud = PlaygroundHUD()
    exp = _TrackingExperiment("test", name="Test")
    hud.update_experiment(exp)
    # [id] ist immer im Format; kein zweites [...] für Status
    assert hud.experiment_line.count("[") == 1


# ---------------------------------------------------------------------------
# 10. PlaygroundApp: set_slot() + activate_variant()
# ---------------------------------------------------------------------------

def test_app_set_slot_sets_active_experiment():
    from playground.app import PlaygroundApp

    app = PlaygroundApp()
    slot = _make_slot("a", "b")
    app.set_slot(slot)
    assert app.active_experiment.id == "a"
    assert app.active_slot is slot


def test_app_activate_variant_switches():
    from playground.app import PlaygroundApp

    app = PlaygroundApp()
    slot = _make_slot("a", "b")
    app.set_slot(slot)
    app.activate_variant(1)
    assert app.active_experiment.id == "b"


def test_app_activate_variant_without_slot_raises():
    from playground.app import PlaygroundApp

    app = PlaygroundApp()
    with pytest.raises(RuntimeError):
        app.activate_variant(0)
