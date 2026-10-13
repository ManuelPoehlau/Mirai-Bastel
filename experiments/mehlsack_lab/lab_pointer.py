"""Click vs drag of one LMB press (Slice 3 E24, AD-019), pyglet-free.

The rule of `mirai.interaction.pointer.PointerGestures`, with its threshold read from there
(`CLICK_THRESHOLD_PX`, Manhattan sum of all motion deltas — no copied number):

- only a drag bound   → the drag starts at once (no dead zone),
- only a click bound  → a click at the release below the threshold, otherwise nothing,
- both bound          → undecided until the threshold (→ drag) or the release (→ click),
- nothing bound       → swallowed.

One lab-local difference, on purpose: when the threshold is reached, the motion events seen
so far are handed back **one by one** (`PointerGestures` hands back one summed delta). The
lab's drag maps every event at the anchor's current position (`screen_delta_to_world` is not
linear), so replaying the events keeps an LMB drag bit-identical to Slices 1–2b, where the
drag began at the press.
"""

from __future__ import annotations

from typing import Optional

from mirai.interaction.pointer import CLICK_THRESHOLD_PX


class PointerPress:
    def __init__(self, click_action: Optional[str], drag_action: Optional[str],
                 threshold: float = CLICK_THRESHOLD_PX) -> None:
        self.click_action = click_action
        self.drag_action = drag_action
        self.threshold = threshold
        self.moved = 0.0
        self.dragging = drag_action is not None and click_action is None
        self._pending: list[tuple[float, float]] = []

    def motion(self, dx: float, dy: float) -> list[tuple[float, float]]:
        """The drag steps to run now: none while undecided, all buffered events at the
        threshold, then each event as it comes."""
        self.moved += abs(dx) + abs(dy)
        if self.dragging:
            return [(dx, dy)]
        if self.drag_action is None:
            return []  # click only: motion counts for the threshold
        self._pending.append((dx, dy))
        if self.moved < self.threshold:
            return []
        self.dragging = True
        steps, self._pending = self._pending, []
        return steps

    def release(self) -> Optional[str]:
        """The click action if this press is a click, else None."""
        if self.dragging or self.click_action is None or self.moved >= self.threshold:
            return None
        return self.click_action
