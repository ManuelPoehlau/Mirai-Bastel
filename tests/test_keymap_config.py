"""`config/keymap.json` and the keymap rules of the AD-013 addendum 2026-10-28.

- Manu's repo keymap: where it lives, that it loads cleanly, that `Application` loads it (the Morph Lab:
  `experiments/morph_lab/tests/test_app_lab.py`);
- the validator: contexts `window` and `morph`, hold commands only on keys, unknown command names warn;
- the safe fallback: an invalid file never blocks the start - the defaults stay complete and the problem is
  loud (status line, `keymap_load`, HUD row "Keymap");
- the fixed modifier grammar is listed, never bound.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import tests._bootstrap  # noqa: F401
from tests._bootstrap import _REPO_ROOT

from hud import hud_rows, hud_state
from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.bindings import (
    FIXED_MODIFIER_RULES,
    KEYMAP_PATH,
    KNOWN_COMMANDS,
    build_default_bindings,
    check_keymap,
    load_keymap,
    load_keymap_overrides,
)
from mirai.interaction.input import (
    MORPH_CONTEXT,
    WINDOW_CONTEXT,
    BindingSet,
    Input,
    KeymapConfigError,
)


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


def _entry(context: str, kind: str, value: str, modifiers: list[str], command) -> dict:
    return {"context": context, "input": {"kind": kind, "value": value, "modifiers": modifiers}, "command": command}


def _write(tmp_path: Path, *entries: dict, raw: str | None = None) -> Path:
    path = tmp_path / "keymap.json"
    path.write_text(raw if raw is not None else json.dumps({"schemaVersion": 1, "bindings": list(entries)}),
                    encoding="utf-8")
    return path


# -- Manu's keymap in the repo ------------------------------------------------------------------


def test_the_keymap_lives_in_the_repo_under_config():
    assert KEYMAP_PATH == _REPO_ROOT / "config" / "keymap.json"
    assert KEYMAP_PATH.is_file()


def test_the_repo_keymap_loads_cleanly():
    """A typo in Manu's file shows up here before the app would only print it."""
    report = load_keymap(build_default_bindings(), KEYMAP_PATH)
    assert report.status == "loaded", report.problem
    assert report.warnings == ()
    data = json.loads(KEYMAP_PATH.read_text(encoding="utf-8"))
    assert report.entries == len(data["bindings"]) > 0
    for entry in data["bindings"]:
        assert set(entry) <= {"context", "input", "command", "set"}


def test_application_loads_the_keymap_given_and_only_then():
    assert Application().keymap_load is None
    app = Application(keymap_path=KEYMAP_PATH)
    assert app.keymap_load.status == "loaded"
    assert app.status_message == ""  # a clean load posts nothing


def test_a_rebinding_in_the_keymap_reaches_resolution_and_the_hud_hint(tmp_path):
    from hud import key_hints

    path = _write(
        tmp_path,
        _entry("global", "key", "j", [], cmd.MOVE),
        _entry("global", "key", "w", [], None),
        _entry("window", "key", "k", ["alt"], cmd.TOGGLE_HUD),
        _entry("window", "key", "h", [], None),
    )
    app = Application(keymap_path=path)
    assert app.bindings.command_for(_key("j")) == cmd.MOVE
    assert app.bindings.command_for(_key("w")) is None
    hints = key_hints(app.bindings)
    assert hints["Tool"] == "J/E/R"
    assert hints["HUD"] == "Alt+K"


# -- validator: contexts ------------------------------------------------------------------------


@pytest.mark.parametrize("context", [WINDOW_CONTEXT, MORPH_CONTEXT])
def test_window_and_morph_contexts_are_accepted(context):
    overlay = BindingSet.from_dict({"schemaVersion": 1, "bindings": [_entry(context, "key", "j", [], "X")]})
    assert overlay.user_entries() == ((context, _key("j"), "X"),)


def test_an_unknown_context_is_still_rejected():
    with pytest.raises(KeymapConfigError, match="context"):
        BindingSet.from_dict({"schemaVersion": 1, "bindings": [_entry("morph_lab", "key", "j", [], cmd.MOVE)]})


# -- validator: hold commands only on keys ------------------------------------------------------


@pytest.mark.parametrize("command", sorted(cmd.HOLD_COMMANDS))
@pytest.mark.parametrize("kind,value", [("mouse", "LEFT"), ("drag", "MIDDLE"), ("wheel", "UP")])
def test_a_hold_command_off_a_key_makes_the_file_invalid(tmp_path, command, kind, value):
    path = _write(tmp_path, _entry("global", kind, value, [], command))
    with pytest.raises(KeymapConfigError, match="Halte-Command"):
        load_keymap_overrides(build_default_bindings(), path)
    report = load_keymap(build_default_bindings(), path)
    assert report.status == "invalid" and "Halte-Command" in report.error


def test_the_hold_family_is_the_set_application_arms_on_a_key():
    assert cmd.HOLD_COMMANDS == {
        cmd.MOVE, cmd.ROTATE, cmd.SCALE, cmd.EXTRUDE, cmd.LOOP_SLIDE, cmd.SMOOTH, cmd.RELAX, cmd.INSET, cmd.BEVEL,
        cmd.LASSO_ARM, cmd.LIGHT_DRAG, cmd.MORPH_WEIGHT_DRAG, cmd.PIVOT_PLACE,
    }


def test_a_hold_command_on_another_key_and_an_unbind_on_a_pointer_are_fine(tmp_path):
    path = _write(
        tmp_path,
        _entry("global", "key", "j", ["alt"], cmd.MOVE),
        _entry("global", "drag", "LEFT", ["ctrl"], None),
    )
    bindings = build_default_bindings()
    assert load_keymap(bindings, path).status == "loaded"
    assert bindings.command_for(_key("j", "alt")) == cmd.MOVE
    assert bindings.command_for(Input("drag", "LEFT", frozenset({"ctrl"}))) is None


# -- validator: unknown commands warn -----------------------------------------------------------


def test_an_unknown_command_loads_and_warns(tmp_path):
    path = _write(tmp_path, _entry("global", "key", "j", [], "Moov"), _entry("global", "key", "k", [], cmd.SCALE))
    bindings = build_default_bindings()
    report = load_keymap(bindings, path)
    assert report.status == "loaded" and report.entries == 2
    assert len(report.warnings) == 1 and "Moov" in report.warnings[0]
    assert any("Moov" in line for line in report.messages())
    assert bindings.command_for(_key("j")) == "Moov"  # kept as a string, it just does nothing
    assert bindings.command_for(_key("k")) == cmd.SCALE
    assert check_keymap(BindingSet.from_json_file(path)) == list(report.warnings)


def test_known_commands_are_the_commands_module():
    assert {cmd.MOVE, cmd.TOGGLE_HUD, cmd.SAVE_SCENE, cmd.MORPH_NEXT, cmd.SUBD_CYCLE_VIEW} <= KNOWN_COMMANDS
    assert "HOLD_COMMANDS" not in KNOWN_COMMANDS and "Moov" not in KNOWN_COMMANDS


# -- safe fallback ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "{ kaputt",
        json.dumps({"schemaVersion": 2, "bindings": []}),
        json.dumps({"schemaVersion": 1, "bindings": [_entry("global", "key", "j", ["hyper"], cmd.MOVE)]}),
    ],
    ids=["json", "schema", "modifier"],
)
def test_an_invalid_keymap_starts_the_app_with_the_defaults_and_says_so_loudly(tmp_path, raw):
    path = _write(tmp_path, raw=raw)
    app = Application(keymap_path=path)

    assert app.keymap_load.status == "invalid"
    assert app.status_message == app.keymap_load.problem
    assert app.status_message.startswith("keymap.json ungültig - Standardbelegung aktiv")
    defaults = build_default_bindings()
    assert app.bindings.user_entries() == ()
    assert app.bindings.command_for(_key("w")) == defaults.command_for(_key("w")) == cmd.MOVE
    app.init_scene("cube")
    rows = {row.label: row for row in hud_rows(hud_state(app), {})}
    assert rows["Keymap"].on and "defaults" in rows["Keymap"].value


def test_an_invalid_file_applies_none_of_its_valid_entries(tmp_path):
    path = _write(
        tmp_path,
        _entry("global", "key", "j", [], cmd.SCALE),
        _entry("global", "wheel", "UP", [], cmd.MOVE),  # hold command off a key
    )
    bindings = build_default_bindings()
    assert load_keymap(bindings, path).status == "invalid"
    assert bindings.command_for(_key("j")) is None


def test_a_missing_keymap_is_quiet(tmp_path):
    app = Application(keymap_path=tmp_path / "nope.json")
    assert app.keymap_load.status == "missing" and app.keymap_load.problem is None
    assert app.keymap_load.messages() == []
    assert app.status_message == ""
    app.init_scene("cube")
    assert "Keymap" not in {row.label for row in hud_rows(hud_state(app), {})}


# -- fixed modifier grammar ---------------------------------------------------------------------


def test_the_fixed_modifier_rules_are_listed_and_not_bindable():
    assert {modifier for modifier, _rule in FIXED_MODIFIER_RULES} == {"Shift", "Ctrl", "Alt"}
    assert all(rule for _modifier, rule in FIXED_MODIFIER_RULES)
    # A modifier alone is no Input of any binding: the grammar cannot be moved by a keymap.
    defaults = build_default_bindings()
    for name in ("shift", "ctrl", "alt", "LSHIFT", "LCTRL", "LALT"):
        assert defaults.command_for(_key(name)) is None
