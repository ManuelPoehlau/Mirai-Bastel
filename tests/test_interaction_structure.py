"""AD-027 §6 E5: the structure the interaction layer restructuring left behind, checked from the code.

(i)   `Application.__init__` sets no modal field: every field is in the non-modal set of AD-027 §3.1 below
      (modal state lives in the slot's sessions and hold keys);
(ii)  `controllers/` and `interaction/session.py` import nothing from `mirai.application`, and a controller reaches
      the app only through `AppServices`' public members (`services.py` alone holds `_app`);
(iii) every command has exactly one handler in the command table; the rest are named here with where they run;
(iv)  `can_run` is pure: two calls give the same answer and change no observation.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

import tests._bootstrap  # noqa: F401
from mirai import application as application_module
from mirai.application import Application
from mirai.interaction import commands
from mirai.interaction.input import Input
from mirai.interaction.session import RunContext
from tests import interaction_trace as trace

_SRC = Path(application_module.__file__).resolve().parent

#: AD-027 §3.1: what `Application` may hold besides the slot - by kind. A new field belongs to one of these kinds
#: (or to a controller); a modal one (non-default only while an interaction runs) belongs in a session or hold key.
NON_MODAL_FIELDS = {
    # document state and the core structures
    "scene", "selection", "history", "_selection_undo_stack", "_selection_redo_stack", "_last_undo_redo_mesh_step",
    # construction and wiring: the slot, the services, the controllers, the command table, mode policies (stage 7)
    "interaction", "_services", "_gestures", "_objects", "_symmetry", "_morph", "_knife", "_pointer_tools",
    "_handlers", "_mode_policies", "tool_manager", "bindings", "keymap_load",
    # view state: camera, display, the viewport and its sinks and caches, picking
    "camera", "display", "viewport", "viewport_width", "viewport_height", "_look_row_index", "_pick_cache",
    "gpu_picking", "subdivision", "morph", "surface_chain", "_soft_overlay", "_soft_bands", "_soft_shading_overlay",
    "_soft_shading", "_mask_overlay", "_tints_seen", "gizmo_enabled", "_gizmo_cache", "_gizmo_frame_cache",
    # input tracking and the hover (AD-019 `PointerGestures` included: navigation owns no keys, H2-R2)
    "pointer", "_cursor", "_press_point", "_shift_held", "_ctrl_held", "_alt_held", "coalesce_hover", "_hover_stale",
    # navigation and views
    "_orbit_virtual", "_view_name", "_ortho_auto",
    # sticky settings
    "_soft", "gizmo_size_name", "tweak_command", "group_mask",
    # protection state per object (Mask, Hide, the active Polygroup) - not mesh data, no History
    "_masks", "_hiddens", "_active_regions",
    # the status line and the AD-013 H2 host hooks
    "status_message", "status_serial", "command_gate", "_hover_suspended",
}

#: Commands that are not `Application`'s to run from the table, and where they run instead.
NOT_IN_TABLE = {
    # the window's own keys (`src/main.py`)
    **{command: "window" for command in commands.WINDOW_COMMANDS},
    # pointer clicks and drags (AD-019 `PointerGestures` -> `_execute_click` / `_execute_drag`)
    commands.SELECT: "click", commands.SELECT_ADD: "click", commands.SELECT_REMOVE: "click",
    commands.SELECT_TOGGLE: "click", commands.REGION_CLICK: "click",
    commands.SELECT_DRAG: "drag", commands.SELECT_DRAG_ADD: "drag", commands.TWEAK: "drag",
    commands.ORBIT: "navigation", commands.PAN: "navigation", commands.ZOOM: "navigation",
    # resolved by the Knife session in its own context (AD-017)
    commands.KNIFE_COMMIT: "knife", commands.KNIFE_LIFT: "knife", commands.KNIFE_MIRROR_VARIANT: "knife",
    # bound or declared, no `Application` handler (a key press returns False, as before)
    commands.CLEAR_SELECTION: "none", commands.SPLIT_EDGE: "none", commands.ARTICULATION_RESTORE: "none",
}


def _class(module, name: str) -> ast.ClassDef:
    tree = ast.parse(inspect.getsource(module))
    return next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name)


def test_i_application_init_sets_only_non_modal_fields() -> None:
    init = next(f for f in _class(application_module, "Application").body
                if isinstance(f, ast.FunctionDef) and f.name == "__init__")
    fields = set()
    for node in ast.walk(init):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            for target in node.targets if isinstance(node, ast.Assign) else [node.target]:
                if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self":
                    fields.add(target.attr)
    assert fields - NON_MODAL_FIELDS == set(), "a new Application field: modal state belongs in the slot (AD-027 §3.1)"
    assert NON_MODAL_FIELDS - fields == set(), "stale entries in NON_MODAL_FIELDS"


def _layer_files() -> list[Path]:
    return sorted((_SRC / "controllers").glob("*.py")) + [_SRC / "interaction" / "session.py"]


@pytest.mark.parametrize("path", _layer_files(), ids=lambda p: p.name)
def test_ii_the_layer_imports_nothing_of_the_application(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not (module == "application" or module.endswith(".application")), (path.name, module)
            assert not any(alias.name == "application" for alias in node.names), path.name
        if isinstance(node, ast.Import):
            assert not any(alias.name.endswith("application") for alias in node.names), path.name


@pytest.mark.parametrize("path", sorted((_SRC / "controllers").glob("*.py")), ids=lambda p: p.name)
def test_ii_controllers_use_only_public_services(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        if path.name != "services.py":
            assert node.attr != "_app", f"{path.name}: only AppServices holds the app"
        owner = node.value
        named_services = (isinstance(owner, ast.Name) and owner.id == "services") or (
            isinstance(owner, ast.Attribute) and owner.attr == "services"
        )
        if named_services:
            assert not node.attr.startswith("_"), f"{path.name}: services.{node.attr}"


def test_iii_every_command_has_exactly_one_handler() -> None:
    app = Application()  # the table asserts one handler per command while it is built
    every = {value for name, value in vars(commands).items() if name.isupper() and isinstance(value, str)}
    table = set(app._handlers)
    assert table & set(NOT_IN_TABLE) == set()
    assert table | set(NOT_IN_TABLE) == every, "a command without a handler or a NOT_IN_TABLE entry"


_CONTEXTS = (RunContext("key", Input("key", "w")), RunContext("api"), RunContext("click"), RunContext("drag"),
             RunContext("wheel"), RunContext("ui", operands=False))


class _PurityDriver(trace.Driver):
    """After every event: every command from every source, asked twice - the same answer, the same observation as
    before the questions."""

    def _record(self, label, call):
        result = super()._record(label, call)
        app = self.app
        before = trace.observe(app, result)
        first = [app.can_run(command, ctx) for command in _EVERY for ctx in _CONTEXTS]
        second = [app.can_run(command, ctx) for command in _EVERY for ctx in _CONTEXTS]
        assert first == second, label
        assert trace.observe(app, result) == before, label
        return result


_EVERY = sorted({value for name, value in vars(commands).items() if name.isupper() and isinstance(value, str)})


@pytest.mark.parametrize("name", ["v1_pivot_then_move_esc", "knife_session", "wer_constraint_modifiers", "morph_view",
                                  "object_gestures_mirror_pair", "resymmetrize", "box_paint_lasso"])
def test_iv_can_run_is_pure(name: str) -> None:
    scene, script = trace.SCRIPTED[name]
    script(_PurityDriver(scene))
