"""Support declarations for symmetric topology operations (AD-SYM-03 §2.5, D-b).

A declaration says "a coordinator exists for this resolved operation": one static table per
kind of key, in the module that will hold the coordinators, so the entry *is* the implementation
and cannot drift from it. Three keys exist today:

- the `C` operation contexts (`CContext`: Split, Edge Connect, Vertex Connect, Knife - all four declared
  since slice 6c);
- the removal commands (`Delete`, `Dissolve`, `DissolveNoCleanup`);
- the Extrude command (`commands.EXTRUDE`, slice 7): a live gesture, like the Knife, so its entry is a
  *planner* `(mesh, faces) -> plan` that `Application` runs at `begin` and hands to the unchanged tool.

Transforms keep `Operation.supports_symmetry`; there the Operation itself mirrors.

AD-SYM-03 slices 3b/3c/4/6c: the `C` table holds the Connect and Split coordinators (Split, Edge
Connect, Vertex Connect), the Knife's commit coordinator (`mirai.symmetric_knife`) and the removal table the three removal coordinators, all in `mirai.symmetric_ops`;
each removal coordinator serves all three component modes. Readers are the Symmetry
Lab, which derives its gate row and MARK warning from the keys (AD-013 H2 amendment of
2026-10-08, H2-R4 (h)), and `Application`, which runs the coordinator of a declared context
whenever a symmetry definition is set (for a removal command, with the mode as a runtime argument,
not as a key; for Extrude, the planner at `begin`). Nobody installs anything at runtime and the tables hold
no gate data (H2-R6). The module imports the coordinators, so it depends on `mirai.symmetric_ops`
(and through it on `mirai.topology`), never on `application`. It lives apart from
`symmetry_coordination` because that module depends only on `core` and `mirai.symmetry`.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Any, Mapping

from .interaction import commands
from .symmetric_extrude import plan_extrude
from .symmetric_knife import coordinate_knife
from .symmetric_ops import (
    coordinate_delete,
    coordinate_dissolve,
    coordinate_dissolve_no_cleanup,
    coordinate_edge_connect,
    coordinate_split,
    coordinate_vertex_connect,
)
from .topology.contextual_c import CContext

#: Resolved `C` context -> coordinator. Split, Edge Connect and Vertex Connect take `(mesh, canonical
#: selection ids) -> result` and run inside the caller's one transaction; the Knife (slice 6c) is a session:
#: its coordinator is `(mesh, session path, session_before) -> KnifeResolution`, which `Application` hands
#: the session at `begin` and the tool runs at commit - declared like the others, the entry is the switch.
C_CONTEXT_COORDINATORS: Mapping[CContext, Any] = MappingProxyType(
    {
        CContext.SPLIT: coordinate_split,
        CContext.EDGE_CONNECT: coordinate_edge_connect,
        CContext.VERTEX_CONNECT: coordinate_vertex_connect,
        CContext.KNIFE: coordinate_knife,
    }
)

#: Removal command constant (`mirai.interaction.commands`) -> coordinator
#: `(mesh, SelectionMode, ids) -> new faces`. Keyed per command, not per component mode (AD-013 H2
#: amendment, "Removal"): a mode-keyed declaration would need a mode-keyed gate refusal, which is
#: not decided (G-9). Each of the three coordinates in every component mode.
REMOVAL_COORDINATORS: Mapping[str, Any] = MappingProxyType(
    {
        commands.DELETE: coordinate_delete,
        commands.DISSOLVE: coordinate_dissolve,
        commands.DISSOLVE_NO_CLEANUP: coordinate_dissolve_no_cleanup,
    }
)

#: Extrude command constant (`mirai.interaction.commands`) -> planner `(mesh, faces) -> SymmetricExtrudePlan`
#: (`mirai.symmetric_extrude`, slice 7). The planner refuses before any mutation (`SymmetryRefusal`); the plan
#: it returns is what the unchanged `ExtrudeTool` is handed at `begin`. Keyed per command like the removal
#: table; the entry is the switch (D-b), the table holds no gate data (H2-R6).
EXTRUDE_COORDINATORS: Mapping[str, Any] = MappingProxyType(
    {
        commands.EXTRUDE: plan_extrude,
    }
)


def declared_c_contexts() -> frozenset[CContext]:
    """The `C` contexts that have a coordinator (read on every call, never cached)."""
    return frozenset(C_CONTEXT_COORDINATORS)


def declared_removal_commands() -> frozenset[str]:
    """The removal commands that have a coordinator (read on every call, never cached)."""
    return frozenset(REMOVAL_COORDINATORS)


def declared_extrude_commands() -> frozenset[str]:
    """The Extrude commands that have a planner (read on every call, never cached)."""
    return frozenset(EXTRUDE_COORDINATORS)
