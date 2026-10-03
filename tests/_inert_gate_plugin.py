"""pytest plugin for T-R5c (AD-013 H2 addendum, WP-SYM-LAB-03 H2): installs a
`CommandGate` on every new `Application`. Loaded only by
`tests/test_command_gate.py` in a subprocess (`-p tests._inert_gate_plugin`),
never by the normal suite.

`MIRAI_GATE_MODE`:
- `inert`: allow-list = every command constant in `mirai.interaction.commands`,
  refused = {an unused sentinel command} (review CLAUDE-002 N7) — the check
  runs on every key and click but must change nothing;
- `empty`: an empty allow-list (negative control: everything is refused);
- anything else: no gate (baseline).

`MIRAI_GATE_COUNT_FILE` (optional): receives how often the gate was consulted
with a gate installed, to prove the check path actually ran.
"""

from __future__ import annotations

import os

SENTINEL = "T-R5c-UnusedSentinelCommand"

_calls = 0


def command_constants() -> frozenset[str]:
    from mirai.interaction import commands

    return frozenset(
        value for name, value in vars(commands).items() if name.isupper() and isinstance(value, str)
    )


def pytest_configure(config) -> None:
    import tests._bootstrap  # noqa: F401

    from mirai.application import Application, CommandGate

    mode = os.environ.get("MIRAI_GATE_MODE", "")
    if mode == "inert":
        gate = CommandGate(
            refused={SENTINEL: "sentinel refused"},
            allowed=command_constants(),
            not_allowed_text="not allowed",
        )
    elif mode == "empty":
        gate = CommandGate(allowed=frozenset(), not_allowed_text="not allowed")
    else:
        return

    original_init = Application.__init__
    original_check = Application._gate_refuses

    def init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.command_gate = gate

    def check(self, command):
        global _calls
        if self.command_gate is not None and command is not None:
            _calls += 1
        return original_check(self, command)

    Application.__init__ = init
    Application._gate_refuses = check


def pytest_unconfigure(config) -> None:
    path = os.environ.get("MIRAI_GATE_COUNT_FILE")
    if path:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(str(_calls))
