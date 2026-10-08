"""pytest plugin for T-R5c (AD-013 H2 addendum, WP-SYM-LAB-03 H2): installs a
`CommandGate` on every new `Application`. Loaded only by
`tests/test_command_gate.py` in a subprocess (`-p tests._inert_gate_plugin`),
never by the normal suite.

`MIRAI_GATE_MODE`:
- `inert`: allow-list = every command constant in `mirai.interaction.commands`,
  refused = {an unused sentinel command} (review CLAUDE-002 N7) — the check
  runs on every key and click but must change nothing;
- `empty`: an empty allow-list (negative control: everything is refused);
- `contexts`: the inert gate plus every `C` operation context in
  `refused_contexts` (negative control of the context check, H2 amendment
  T-R5c+: the contextual-C and Knife tests must fail);
- anything else: no gate (baseline).

The `inert` gate also carries `refused_contexts = {}` (T-R5c+): the context check
runs on every `C` that reaches `_connect_command` but must change nothing.

`MIRAI_GATE_COUNT_FILE` (optional): receives how often the gate was consulted
with a gate installed, to prove the check path actually ran.
`MIRAI_CONTEXT_COUNT_FILE` (optional): the same for the context check
(`_context_refuses`), to prove that path executed too.
"""

from __future__ import annotations

import os

SENTINEL = "T-R5c-UnusedSentinelCommand"

_calls = 0
_context_calls = 0


def command_constants() -> frozenset[str]:
    from mirai.interaction import commands

    return frozenset(
        value for name, value in vars(commands).items() if name.isupper() and isinstance(value, str)
    )


def pytest_configure(config) -> None:
    import tests._bootstrap  # noqa: F401

    from mirai.application import Application, CommandGate
    from mirai.topology.contextual_c import CContext

    mode = os.environ.get("MIRAI_GATE_MODE", "")
    if mode == "inert":
        gate = CommandGate(
            refused={SENTINEL: "sentinel refused"},
            allowed=command_constants(),
            not_allowed_text="not allowed",
            refused_contexts={},
        )
    elif mode == "contexts":
        gate = CommandGate(
            refused={SENTINEL: "sentinel refused"},
            allowed=command_constants(),
            not_allowed_text="not allowed",
            refused_contexts={
                ctx: "context refused"
                for ctx in (
                    CContext.SPLIT,
                    CContext.EDGE_CONNECT,
                    CContext.VERTEX_CONNECT,
                    CContext.KNIFE,
                )
            },
        )
    elif mode == "empty":
        gate = CommandGate(allowed=frozenset(), not_allowed_text="not allowed")
    else:
        return

    original_init = Application.__init__
    original_check = Application._gate_refuses
    original_context_check = Application._context_refuses

    def init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.command_gate = gate

    def check(self, command):
        global _calls
        if self.command_gate is not None and command is not None:
            _calls += 1
        return original_check(self, command)

    def context_check(self, context):
        global _context_calls
        if self.command_gate is not None:
            _context_calls += 1
        return original_context_check(self, context)

    Application.__init__ = init
    Application._gate_refuses = check
    Application._context_refuses = context_check


def pytest_unconfigure(config) -> None:
    for variable, value in (
        ("MIRAI_GATE_COUNT_FILE", _calls),
        ("MIRAI_CONTEXT_COUNT_FILE", _context_calls),
    ):
        path = os.environ.get(variable)
        if path:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(str(value))
