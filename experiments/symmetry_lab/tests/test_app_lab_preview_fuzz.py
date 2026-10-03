"""T-R2g — Zufallsfolgen unter der offenen Re-Symmetrize-Vorschau (WP-SYM-LAB-03 Slice 3).

AD-013 H2, Required tests T-R2g (D1, H2-R2); Vorlage: Probe D1a der Review
CLAUDE-002 (Anhang), hier gegen das echte Gate, das echte `hover_suspended` und
das echte Lab statt der Emulation. Feste Seeds.

Ablauf je Seed: zufälliges Aufwärmen ohne Vorschau (Tasten über `lab_key_press`,
Maus über die `Application`-Eingänge; ohne C, damit die Topologie und damit die
Seiten der Seam bleiben), dann alles loslassen, Symmetrie X, ein Vertex per Klick,
M → Vorschau. Danach 300 zufällige Ereignisse — Tasten (alle gebundenen außer M und
Esc, dazu ungebundene), Klicks mit Modifiern, Drags, Releases, Bewegung, Mausrad,
Verlassen. Nach **jedem** Ereignis: Vorschau offen, `interaction_owner is None`, kein
aktives Tool, Hover `None`, Auswahl, History und Mesh unverändert, Gate = Vorschau-
Zeile. Am Ende schließt Esc die Vorschau ohne History-Eintrag.
"""

from __future__ import annotations

import random

import pytest

from mirai.interaction.input import Input

from symmetry_lab.lab_app import ROW_PREVIEW, lab_key_press

from ._app_lab_preview_support import (
    ONE,
    first_visible,
    side_vertices,
    state_snapshot,
    symmetry_to,
)
from ._app_lab_support import (  # noqa: F401
    ESC,
    HEIGHT,
    M,
    WIDTH,
    click,
    forbid_lab_calls,
    make_lab,
    screen,
)


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


#: Alle Tasten der Default-Bindings (GLOBAL), die Lab-Tasten und ein paar ungebundene.
BOUND_KEYS = [
    _key("1"), _key("2"), _key("3"),
    _key("z", "ctrl"), _key("y", "ctrl"),
    _key("w"), _key("e"), _key("r"),
    _key("x"), _key("y"), _key("z"),
    _key("x", "shift"), _key("y", "shift"), _key("z", "shift"),
    _key("a", "alt"), _key("c"), _key("d"), _key("d", "shift"),
    _key("s", "shift"), _key("b", "shift"),
]
UNBOUND_KEYS = [_key("q"), _key("a"), _key("b"), _key("enter"), _key("z", "ctrl", "shift")]
#: Aufwärmen ohne C (Connect/Knife ändern die Topologie und damit die Seiten).
WARMUP_KEYS = [k for k in BOUND_KEYS + UNBOUND_KEYS if k != _key("c")] + [ESC]
#: Unter der Vorschau: alles außer M (führt aus) und Esc (schließt).
PREVIEW_KEYS = BOUND_KEYS + UNBOUND_KEYS
MODIFIERS = [(), ("shift",), ("ctrl",), ("alt",), ("alt", "shift")]
BUTTONS = ["LEFT", "LEFT", "LEFT", "RIGHT", "MIDDLE"]


def _targets(app) -> list:
    return [screen(app, v) for v in sorted(app.scene.mesh.all_vertex_ids(), key=int)]


def _random_event(rng, app, lab, keys, held: set) -> None:
    targets = _targets(app)
    r = rng.random()
    if r < 0.35:
        inp = rng.choice(keys)
        lab_key_press(app, lab, inp)
        held.add(inp)
    elif r < 0.45 and held:
        inp = rng.choice(sorted(held, key=lambda i: (i.value, sorted(i.modifiers))))
        held.discard(inp)
        app.key_release(inp)
    elif r < 0.58:
        x, y = rng.choice(targets) if rng.random() < 0.7 else (rng.uniform(0, WIDTH), rng.uniform(0, HEIGHT))
        app.pointer_press(Input("mouse", rng.choice(BUTTONS), frozenset(rng.choice(MODIFIERS))), x, y)
    elif r < 0.68:
        d = rng.choice([1, 2, 10, 30])
        app.pointer_drag(rng.choice([-d, d]), rng.choice([-d, 0, d]), rng.uniform(0, WIDTH), rng.uniform(0, HEIGHT))
    elif r < 0.78:
        app.pointer_release(rng.choice(["LEFT", "RIGHT", "MIDDLE"]), rng.uniform(0, WIDTH), rng.uniform(0, HEIGHT))
    elif r < 0.92:
        x, y = rng.choice(targets) if rng.random() < 0.6 else (rng.uniform(0, WIDTH), rng.uniform(0, HEIGHT))
        app.pointer_motion(x, y, rng.uniform(-8, 8), rng.uniform(-8, 8))
    elif r < 0.97:
        app.pointer_scroll(Input("wheel", rng.choice(["UP", "DOWN"])))
    else:
        app.pointer_leave()


def _settle(app, lab, held: set) -> None:
    """Alles loslassen: Tasten, laufende Pointer-Geste, scharfer Transform."""
    for inp in sorted(held, key=lambda i: (i.value, sorted(i.modifiers))):
        app.key_release(inp)
    held.clear()
    while app.pointer.active:
        app.pointer_release(app.pointer.active_button, 0, 0)
    if app.interaction_owner is not None:
        lab_key_press(app, lab, ESC)
    assert app.interaction_owner is None


def _open_after_warmup(seed: int):
    rng = random.Random(seed)
    app, lab = make_lab("subd_cube")
    held: set = set()
    for _ in range(rng.randint(0, 60)):
        _random_event(rng, app, lab, WARMUP_KEYS, held)
    _settle(app, lab, held)
    lab_key_press(app, lab, ONE)
    symmetry_to(app, lab, "X")
    if seed % 2:
        # Constraint und Anzeige-Modus vor M dürfen bleiben (nur gelesen).
        lab_key_press(app, lab, _key("x"))
    source = first_visible(app, side_vertices(app, rng.randint(0, 1)))
    click(app, *screen(app, source))
    assert app.selection.vertices == {source}
    assert lab_key_press(app, lab, M) is True
    assert lab.preview_open
    return rng, app, lab


@pytest.mark.parametrize("seed", range(12))
def test_t_r2g_random_input_under_the_preview_changes_nothing(seed):
    rng, app, lab = _open_after_warmup(seed)
    before = state_snapshot(app)
    history = len(app.history)
    held: set = set()
    for step in range(300):
        _random_event(rng, app, lab, PREVIEW_KEYS, held)
        where = f"seed {seed}, Ereignis {step}"
        assert lab.preview_open, where
        assert app.interaction_owner is None, where
        assert app.tool_manager.active_tool is None, where
        assert app.selection.hovered is None, where
        assert app.command_gate is ROW_PREVIEW.gate, where
        assert app.hover_suspended is True, where
        assert state_snapshot(app) == before, where
    _settle(app, lab, held)
    assert lab_key_press(app, lab, ESC) is True
    assert not lab.preview_open
    assert len(app.history) == history
    assert state_snapshot(app) == before
    assert app.hover_suspended is False


def _first_violation(rng, app, lab, steps: int):
    before = state_snapshot(app)
    held: set = set()
    for step in range(steps):
        _random_event(rng, app, lab, PREVIEW_KEYS, held)
        if (
            app.interaction_owner is not None
            or app.tool_manager.active_tool is not None
            or app.selection.hovered is not None
            or state_snapshot(app) != before
        ):
            return step
    return None


def test_t_r2g_negative_control_finds_violations_without_gate_and_flag():
    """Negativkontrolle (wie D1a der Review): dieselben Folgen mit entferntem Gate
    und Hover-Flag direkt nach M verletzen die Invarianten — der Fuzz sieht es."""
    violated = 0
    for seed in range(12):
        rng, app, lab = _open_after_warmup(seed)
        app.command_gate = None
        app.hover_suspended = False
        if _first_violation(rng, app, lab, 300) is not None:
            violated += 1
    assert violated >= 10, violated
