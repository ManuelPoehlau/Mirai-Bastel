"""P1b state, keys and entry point (headless)."""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

from lookdev_eye_lab import lab_state as ls
from lookdev_eye_lab import refraction_gl as rg

LAB = Path(__file__).resolve().parents[1]


def test_refraction_state_defaults_to_p1():
    state = rg.RefractionState()
    base = ls.LabState()
    for field in dataclasses.fields(ls.LabState):
        assert getattr(state, field.name) == getattr(base, field.name), field.name
    assert state.refraction == "V1" and not state.refraction_active


def test_refraction_is_active_only_for_v2_v3_outside_t_a():
    assert rg.RefractionState(refraction="V2", technique="T-C").refraction_active
    assert rg.RefractionState(refraction="V3", technique="T-D").refraction_active
    assert not rg.RefractionState(refraction="V3", technique="T-A").refraction_active
    assert rg.RefractionState(refraction="V2").variant == "T-C_V2"
    assert rg.RefractionState(refraction="V1").variant == "T-C_C2"


def test_p1_keys_keep_the_refraction_state():
    state = rg.RefractionState(refraction="V3")
    for name, (_text, action) in ls.KEYS.items():
        new = action(state, False)
        assert isinstance(new, rg.RefractionState) and new.refraction == "V3", name


def test_run_refraction_parser_and_keys():
    sys.path.insert(0, str(LAB))
    try:
        import run_refraction
    finally:
        sys.path.remove(str(LAB))
    args = run_refraction.build_parser().parse_args([])
    assert args.refraction == "V2" and args.technique == "T-C"
    assert set(run_refraction.REFRACTION_KEYS) == {"8", "9", "0"}
    assert not set(run_refraction.REFRACTION_KEYS) & set(ls.KEYS)  # no clash with P1's keys
