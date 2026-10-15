"""Edge-Loop-/Edge-Ring-Erkennung (AP-05) — forwards to the production implementation.

Moved to `src/mirai/topology/loop_ring.py` (2026-10-15, loop tools promoted into the app);
this module keeps the Playground's import path so there is one implementation.
"""

from mirai.topology.loop_ring import (  # noqa: F401
    LoopRingError,
    Traversal,
    edge_loop,
    edge_ring,
)
