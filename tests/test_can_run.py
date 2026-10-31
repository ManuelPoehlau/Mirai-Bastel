"""AD-027 §3.3 (M2): one `can_run` answers keys, clicks, drags, the wheel, `dispatch_command` and the HUD.

E5 (iv), the purity of `can_run`, is `test_interaction_structure.py`'s. This file pins that each path asks the same check: the gated `dispatch_command` refuses
what the key refuses (a held gesture, a Knife session, the Re-Symmetrize preview, mode `4`, a host gate), the
Knife still lets view state through (AD-027 V8) and the HUD gets the refused hinted commands as data.
"""

from __future__ import annotations



import tests._bootstrap  # noqa: F401
from tests import interaction_trace as trace
from hud import HudState, hud_state
from mirai.application import CommandGate
from mirai.interaction import commands
from mirai.interaction.input import Input
from mirai.interaction.session import Refusal, RunContext

def _key(value: str, *mods: str) -> Input:
    return Input("key", value, frozenset(mods))


def test_unbound_input_is_never_refused():
    app = trace.make_app("cube")
    app.command_gate = CommandGate(allowed=frozenset())
    assert app.can_run(None, RunContext("key")) is None


def _select_one_vertex(driver):
    driver.click(*driver.targets("vertex", visible=True, limit=1)[0])
    assert driver.app.selection.vertices


def test_dispatch_command_refuses_what_a_held_gesture_refuses():
    driver = trace.Driver("cube")
    _select_one_vertex(driver)
    app = driver.app
    driver.key_down(_key("w"))
    assert app.interaction_owner == "transform"
    serial = app.status_serial
    for command in (commands.SET_FACE_MODE, commands.CONNECT, commands.SYMMETRY_CYCLE, commands.PIVOT_PLACE):
        assert app.can_run(command, RunContext("key")) == Refusal(None)
        assert app.dispatch_command(command) is False
    assert app.selection.mode.name == "VERTEX"
    assert app.status_serial == serial  # silent, as the key
    # Allowed underneath: view state, Soft settings, Undo while only armed.
    assert app.can_run(commands.SET_WIREFRAME, RunContext("api")) is None
    assert app.can_run(commands.UNDO, RunContext("key")) is None
    driver.nudge(10, 0)  # begun: Undo and K are refused now
    assert app.can_run(commands.UNDO, RunContext("api")) == Refusal(None)
    assert app.can_run(commands.TOGGLE_TRANSFORM_SPACE, RunContext("key")) == Refusal(None)
    driver.key_up("w")


def test_knife_session_lets_view_state_through_and_nothing_else():
    """V8: the API's Wireframe during a Knife session keeps working; a mode switch does not."""
    driver = trace.Driver("cube")
    app = driver.app
    driver.tap(_key("c"))
    assert app.knife_active
    assert app.dispatch_command(commands.SET_WIREFRAME) is True
    assert app.dispatch_command(commands.SET_FACE_MODE) is False
    assert app.selection.mode.name == "VERTEX"
    assert app.can_run(commands.KNIFE_COMMIT, RunContext("api")) is None
    assert app.can_run(commands.SOFT_TOGGLE, RunContext("wheel")) == Refusal(None)


def test_resymmetrize_preview_refuses_with_its_hint():
    driver = trace.Driver("subd_sym")
    _select_one_vertex(driver)
    app = driver.app
    driver.tap(_key("m", "alt"))
    assert app.interaction_owner == "resymmetrize"
    mesh_before = app.scene.mesh.export_state()
    assert app.dispatch_command(commands.CONNECT) is False
    assert app.status_message.startswith("Vorschau aktiv")
    assert app.scene.mesh.export_state() == mesh_before
    assert app.can_run(commands.SELECT_DRAG, RunContext("drag")) == Refusal(None)
    assert app.dispatch_command(commands.TOGGLE_ORTHO) is True
    assert app.interaction_owner == "resymmetrize"


def test_object_mode_text_reaches_the_api():
    app = trace.make_app("objects")
    assert app.selection.mode.name == "OBJECT"
    assert app.dispatch_command(commands.SYMMETRY_CYCLE) is False
    assert app.status_message.startswith("Object mode:")
    assert app.scene.mesh.symmetry_definition is None


def test_host_gate_answers_key_and_api_alike():
    """AD-013 H2 addendum 2026-10-30: `dispatch_command` consults the `CommandGate` (stage 2)."""
    app = trace.make_app("cube")
    app.command_gate = CommandGate(refused={commands.SET_WIREFRAME: "gated"})
    serial = app.status_serial
    assert app.dispatch_command(commands.SET_WIREFRAME) is False
    assert (app.status_message, app.status_serial) == ("gated", serial + 1)
    wireframe = app.bindings.inputs_for(commands.SET_WIREFRAME)
    if wireframe:
        assert app.key_press(wireframe[0]) is False
        assert (app.status_message, app.status_serial) == ("gated", serial + 2)
    assert app.display.label != "Wireframe"


def test_hidden_stage_is_skipped_without_operands():
    """Stage 5 reads selection and hover; the HUD's per-frame question skips it."""
    driver = trace.Driver("hidden")  # two vertices hidden
    driver.click(3.0, 3.0)  # empty space: nothing selected, so C would start the Knife
    app = driver.app
    assert not app.selection.vertices
    refusal = app.can_run(commands.CONNECT, RunContext("key"))
    assert refusal is not None and refusal.text.startswith("Knife: hidden geometry")
    assert app.can_run(commands.CONNECT, RunContext("ui", operands=False)) is None


def test_hud_state_lists_the_refused_hinted_commands():
    app = trace.make_app("objects")  # mode 4
    state = hud_state(app)
    assert isinstance(state.unavailable, frozenset)
    assert commands.SYMMETRY_CYCLE in state.unavailable
    assert commands.MOVE not in state.unavailable
    idle = hud_state(trace.make_app("cube"))
    assert commands.SYMMETRY_CYCLE not in idle.unavailable
    assert "unavailable" in HudState.__dataclass_fields__
