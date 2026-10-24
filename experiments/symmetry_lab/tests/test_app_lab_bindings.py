"""Lab-Kontext auf dem App-Pfad: genau eine Taste, Start-Prüfung, Start-Liste.

AD-013 H2 addendum, § Required tests, Lab-Seite: T-R1a, T-R1b, T-R1c, T-R1d — seit dem
Addendum 2026-10-24 (AD-SYM-04 A3) mit einem Eintrag (Shift+B): Shift+S (A1) und
Re-Symmetrize (A3, Default Alt+M; bis dahin die Lab-Taste M) sind GLOBAL-Tasten der App, das Lab
nutzt sie wie jede App-Taste.
Dazu (Slice 5, Ports aus dem gelöschten `test_lab_bindings.py`): Kontext und
Commands sind Lab-lokal, nicht in `mirai.interaction`. Die Enumeration der Binding-Einträge liest `BindingSet._defaults`/`_user` — nur
im Test; die Lab-Module selbst nutzen ausschließlich `command_for`/`set_default`.
"""

from __future__ import annotations

import pytest

from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction import input as input_module
from mirai.interaction.bindings import build_default_bindings
from mirai.interaction.input import GLOBAL_CONTEXT, KNIFE_CONTEXT, BindingSet

from symmetry_lab import lab_app
from symmetry_lab.lab_app import (
    LAB_KEY_ENTRIES,
    LabBindingConflict,
    gate_rows,
    start_lab,
    startup_listing,
)
from mirai.interaction.input import Input
from symmetry_lab.lab_bindings import (
    SYMMETRY_GATE_MODE,
    SYMMETRY_LAB_CONTEXT,
)

from ._app_lab_support import M, SHIFT_B, SHIFT_S, forbid_lab_calls  # noqa: F401

LAB_INPUTS = {SHIFT_B: SYMMETRY_GATE_MODE}
ALT_M = Input("key", "m", frozenset({"alt"}))


def _context_entries(bindings: BindingSet, context: str) -> dict:
    entries = {inp: c for (ctx, inp), c in bindings._defaults.items() if ctx == context}
    entries.update({inp: c for (ctx, inp), c in bindings._user.items() if ctx == context})
    return entries


def _all_inputs(*binding_sets: BindingSet) -> set:
    return {
        inp
        for bs in binding_sets
        for table in (bs._defaults, bs._user)
        for (_ctx, inp) in table
    }


def test_lab_context_has_exactly_one_key_entry_and_global_knife_unchanged():
    """T-R1a: der Lab-Kontext enthält genau {Shift+B}, nur Tasten (seit 2026-10-24);
    nach dem Lab-Start lösen GLOBAL und KNIFE jede Eingabe exakt wie
    `build_default_bindings()` auf."""
    app = Application()
    start_lab(app)
    entries = _context_entries(app.bindings, SYMMETRY_LAB_CONTEXT)
    assert entries == LAB_INPUTS
    assert all(inp.kind == "key" for inp in entries)
    assert {e.input for e in LAB_KEY_ENTRIES} == set(LAB_INPUTS)

    reference = build_default_bindings()
    inputs = _all_inputs(app.bindings, reference)
    assert set(LAB_INPUTS) <= inputs
    for inp in inputs:
        for context in (GLOBAL_CONTEXT, KNIFE_CONTEXT):
            assert app.bindings.command_for(inp, context) == reference.command_for(inp, context), (
                inp,
                context,
            )
    for inp, command in LAB_INPUTS.items():
        assert app.bindings.command_for(inp, SYMMETRY_LAB_CONTEXT) == command
    # Alles andere fällt im Lab-Kontext auf GLOBAL zurück.
    for inp in inputs - set(LAB_INPUTS):
        assert app.bindings.command_for(inp, SYMMETRY_LAB_CONTEXT) == reference.command_for(inp)
    # Shift+S und Alt+M kommen über den GLOBAL-Fallback als Befehle der App an (AD-SYM-04 A1/A3);
    # M ist im Lab frei (in `src/main.py` die Morph-Lab-Brücke, die das Lab nicht installiert).
    assert app.bindings.command_for(SHIFT_S, SYMMETRY_LAB_CONTEXT) == cmd.SYMMETRY_CYCLE
    assert app.bindings.command_for(ALT_M, SYMMETRY_LAB_CONTEXT) == cmd.RESYMMETRIZE
    assert app.bindings.command_for(M, SYMMETRY_LAB_CONTEXT) is None


def test_lab_keys_are_free_by_default():
    """T-R1b (Teil 1): jede Lab-Taste löst in GLOBAL und KNIFE zu None auf."""
    reference = build_default_bindings()
    for inp in LAB_INPUTS:
        assert reference.command_for(inp) is None
        assert reference.command_for(inp, KNIFE_CONTEXT) is None


@pytest.mark.parametrize("layer", ["user", "default"])
@pytest.mark.parametrize("context", [GLOBAL_CONTEXT, KNIFE_CONTEXT])
@pytest.mark.parametrize("inp", [SHIFT_B], ids=["shift_b"])
def test_startup_raises_when_a_lab_key_is_bound(inp, context, layer):
    """T-R1b: eine Belegung einer Lab-Taste in GLOBAL oder KNIFE (User- oder
    Default-Ebene) lässt den Lab-Start laut scheitern, ohne Lab-Einträge."""
    app = Application()
    if layer == "user":
        app.bindings.bind(inp, cmd.UNDO, context=context)
    else:
        app.bindings.set_default(inp, cmd.UNDO, context=context)
    with pytest.raises(LabBindingConflict) as info:
        start_lab(app)
    assert context in str(info.value)
    assert _context_entries(app.bindings, SYMMETRY_LAB_CONTEXT) == {}


def test_startup_raises_with_user_global_binding_on_shift_b():
    """T-R1b (der benannte Fall, seit 2026-10-24 auf Shift+B statt M): User-GLOBAL-Bindung auf
    eine Lab-Taste → Start wirft."""
    app = Application()
    app.bindings.bind(SHIFT_B, cmd.SET_SHADED)
    with pytest.raises(LabBindingConflict):
        start_lab(app)


def test_shift_s_is_no_lab_key_and_a_user_binding_on_it_does_not_stop_the_lab():
    """Seit 2026-10-14 prüft die Start-Prüfung Shift+S nicht mehr: es ist eine App-Taste wie W,
    eine User-Umbelegung gilt im Lab wie in der App."""
    assert SHIFT_S not in {entry.input for entry in LAB_KEY_ENTRIES}
    app = Application()
    app.bindings.bind(SHIFT_S, cmd.SET_SHADED)
    start_lab(app)
    assert app.bindings.command_for(SHIFT_S, SYMMETRY_LAB_CONTEXT) == cmd.SET_SHADED


def test_lab_uses_the_one_binding_set(monkeypatch):
    """T-R1c: das Lab hält `app.bindings` per Identität; der Lab-Start legt kein
    weiteres `BindingSet` an."""
    app = Application()
    created = []
    original_init = BindingSet.__init__

    def counting_init(self, *args, **kwargs):
        created.append(self)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(BindingSet, "__init__", counting_init)
    bindings = app.bindings
    lab = start_lab(app)
    assert created == []
    assert lab.app.bindings is bindings
    assert app.pointer._bindings is bindings
    assert not any(isinstance(v, BindingSet) for v in vars(lab).values())


def test_startup_listing_names_every_entry_and_every_gate_row():
    """T-R1d: die Start-Liste enthält jeden Lab-Eintrag und jede Gate-Zeile (seit
    Slice 3 mit der Vorschau-Zeile; deren Prüfung und die Esc-Zeile:
    `test_app_lab_preview.py`; seit Slice 4 die E5-Zeilen MARK/BLOCK statt der
    1b-Zeile „C abgelehnt", Prüfung: `test_app_lab_gate.py`)."""
    lines = startup_listing()
    text = "\n".join(lines)
    for entry in LAB_KEY_ENTRIES:
        assert entry.describe() in text
    for row in gate_rows():
        assert row.describe() in text
    assert len(gate_rows()) == 3  # seit AD-SYM-04 A3 ohne Vorschau-Zeile
    assert lab_app.block_text("Knife") not in text  # `C` geht seit 3b durch, der Knife-Kontext seit 6c
    assert "ReSymmetrize" in text and "SymmetryGateMode" in text
    assert "App-Taste Shift+S -> SymmetryCycle" in text  # die App-Tasten werden benannt (H2-R3)
    assert "App-Taste Alt+M -> ReSymmetrize" in text
    # Seit Slice 4 tun alle Lab-Tasten etwas.
    assert not any("noch nicht verfügbar" in line for line in lines)


# -- Lab-lokal (Ports aus `test_lab_bindings.py`, Slice 5) --------------------------


def test_context_defined_in_lab_not_in_mirai_interaction():
    assert SYMMETRY_LAB_CONTEXT == "symmetry_lab"
    assert "symmetry_lab" not in vars(input_module).values()


def test_lab_commands_defined_in_lab_not_in_commands():
    """Das Lab-Command ist ein Lab-String, kein Production-Command (Plan §3.2); der
    Symmetrie-Zyklus ist seit 2026-10-14 einer (AD-SYM-04 A1), Re-Symmetrize seit 2026-10-24 (A3)."""
    assert SYMMETRY_GATE_MODE not in vars(cmd).values()
    assert cmd.SYMMETRY_CYCLE in vars(cmd).values()
    assert cmd.RESYMMETRIZE in vars(cmd).values()
