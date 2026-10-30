"""AD-027 §3.2: the interaction slot - one session, ranked hold keys, the five-stage routing rule - and
the boundary of `mirai.controllers` (E5 (ii): no import of `mirai.application`, no underscore member of
`AppServices`)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import tests._bootstrap  # noqa: F401
from tests._bootstrap import _SRC
from mirai.controllers.services import AppServices
from mirai.interaction import commands
from mirai.interaction.input import Input
from mirai.interaction.session import (
    PASS,
    SILENT,
    InteractionSlot,
    KeyPress,
    Motion,
    Press,
    Refusal,
    RunContext,
)

LMB = Input("mouse", "LEFT")
W = Input("key", "w")


class _Session:
    owner = "test"
    label = "Test"
    exclusive = False

    def __init__(self, grab=(), answer=PASS, refusal=None):
        self.grab_types = grab
        self.answer = answer
        self.refusal = refusal
        self.seen = []

    def grabs(self, event):
        return isinstance(event, self.grab_types)

    def allows(self, command, ctx):
        return self.refusal

    def handle(self, event):
        self.seen.append(event)
        return self.answer

    def cancel(self):
        return True

    def commit(self):
        return True


class _Hold:
    def __init__(self, command, claim=PASS, background=PASS):
        self.command = command
        self.key = "k"
        self._claim = claim
        self._background = background
        self.seen = []

    def claims(self, event):
        self.seen.append(("claims", event))
        return self._claim

    def background(self, event):
        self.seen.append(("background", event))
        return self._background

    def release(self):
        return True


def test_pass_is_a_singleton_without_truth_value():
    assert PASS is type(PASS)()
    with pytest.raises(TypeError):
        bool(PASS)


def test_empty_slot_routes_everything_to_idle():
    slot = InteractionSlot()
    assert slot.owner is None
    assert slot.route(Press(LMB, 1.0, 2.0)) is PASS
    assert slot.grab(KeyPress(W)) is PASS
    assert slot.allows(commands.MOVE, RunContext("api")) is None


def test_one_session_at_a_time():
    slot = InteractionSlot()
    first = _Session()
    slot.start(first)
    assert slot.owner == "test"
    with pytest.raises(AssertionError):
        slot.start(_Session())
    with pytest.raises(AssertionError):
        slot.end(_Session())
    slot.end(first)
    assert slot.session is None


def test_grab_decides_before_hold_claims():
    """Stage 1 before stage 2 (the Knife's LMB beats a held Working Pivot, V6)."""
    slot = InteractionSlot()
    hold = _Hold(commands.PIVOT_PLACE, claim=True)
    slot.hold(hold)
    session = _Session(grab=(Press,), answer=False)
    slot.start(session)
    assert slot.route(Press(LMB, 0, 0)) is False
    assert hold.seen == []


def test_hold_claims_before_the_session():
    """Stage 2 before stage 3 (a held P places the pivot under an open preview or an armed W, V3 / V7)."""
    slot = InteractionSlot()
    hold = _Hold(commands.PIVOT_PLACE, claim=True)
    slot.hold(hold)
    session = _Session(answer=True)
    slot.start(session)
    assert slot.route(Press(LMB, 0, 0)) is True
    assert session.seen == []


def test_session_before_hold_background():
    """Stage 3 before stage 4 (motion drives a held W, not the held light, V5)."""
    slot = InteractionSlot()
    light = _Hold(commands.LIGHT_DRAG, background=True)
    slot.hold(light)
    session = _Session(answer=True)
    slot.start(session)
    assert slot.route(Motion(1, 1)) is True
    assert ("background", Motion(1, 1)) not in light.seen
    slot.end(session)
    assert slot.route(Motion(1, 1)) is True
    assert ("background", Motion(1, 1)) in light.seen


def test_holds_answer_in_fixed_rank_not_in_hold_order():
    """V4: Light before Morph weight whichever was held first."""
    slot = InteractionSlot()
    morph = _Hold(commands.MORPH_WEIGHT_DRAG, background=True)
    light = _Hold(commands.LIGHT_DRAG, background=True)
    slot.hold(morph)
    slot.hold(light)
    assert [h.command for h in slot.holds] == [commands.LIGHT_DRAG, commands.MORPH_WEIGHT_DRAG]
    assert slot.route(Motion(3, 0)) is True
    assert ("background", Motion(3, 0)) in light.seen
    assert ("background", Motion(3, 0)) not in morph.seen
    slot.unhold(light)
    assert slot.holds == (morph,)


def test_allows_is_the_running_sessions():
    slot = InteractionSlot()
    slot.start(_Session(refusal=Refusal("no")))
    assert slot.allows(commands.MOVE, RunContext("key")) == Refusal("no")
    assert SILENT.text is None


class _Press(_Session):
    owner = None
    label = None


def test_a_press_session_runs_beside_the_session():
    """AD-027 §7.1 (M5): a press session (owner None) lives from its LMB press to that release; a session may start
    while it runs (a Knife begun while LMB is held on a gizmo handle), and the press keeps its own events."""
    slot = InteractionSlot()
    press = _Press(answer=False, refusal=Refusal("press"))
    slot.start_press(press)
    assert slot.owner is None
    with pytest.raises(AssertionError):
        slot.start_press(_Press())
    with pytest.raises(AssertionError):
        slot.start_press(_Session())  # an owning session is never a press session
    session = _Session()
    slot.start(session)
    assert slot.owner == "test"
    assert slot.handle(Press(LMB, 0, 0)) is False  # stage 3: the session passed, the press session answered
    assert session.seen == [Press(LMB, 0, 0)] and press.seen == [Press(LMB, 0, 0)]
    assert slot.allows(commands.MOVE, RunContext("key")) == Refusal("press")
    slot.end(session)
    slot.end_press(press)
    assert slot.press is None and slot.allows(commands.MOVE, RunContext("key")) is None


def test_the_session_answers_before_the_press_session():
    slot = InteractionSlot()
    press = _Press(answer=False, refusal=Refusal("press"))
    session = _Session(answer=True, refusal=Refusal("session"))
    slot.start_press(press)
    slot.start(session)
    assert slot.handle(Motion(1, 1)) is True and press.seen == []
    assert slot.allows(commands.MOVE, RunContext("key")) == Refusal("session")


# -- E5 (ii): the controller boundary ---------------------------------------------------------------


def _modules():
    yield _SRC / "mirai" / "interaction" / "session.py"
    yield from sorted((_SRC / "mirai" / "controllers").glob("*.py"))


@pytest.mark.parametrize("path", list(_modules()), ids=lambda p: p.name)
def test_controllers_never_import_the_application(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert "application" not in module.split("."), f"{path.name}: from {module} import ..."
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert "application" not in alias.name.split("."), f"{path.name}: import {alias.name}"


@pytest.mark.parametrize(
    "path", [p for p in _modules() if p.name != "services.py"], ids=lambda p: p.name
)
def test_controllers_use_no_private_member_of_the_services(path: Path):
    """Controllers reach `AppServices` only through its public members (the bridge's `_app` is its own)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    public = {name for name in dir(AppServices) if not name.startswith("_")}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        base = node.value
        if (isinstance(base, ast.Attribute) and base.attr == "services") or (
            isinstance(base, ast.Name) and base.id == "services"
        ):
            assert node.attr in public, f"{path.name}: services.{node.attr}"
