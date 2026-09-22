"""Connect Lab — Discovery-Varianten für die Connect-Semantik.

Siehe docs/research/topology/CONNECT_NONQUAD_DISCOVERY.md §6.
Familie "connect": Tab bis connect, dann M zum Wechseln der Variante.
Taste C bleibt Connect; die aktive Variante bestimmt nur die Semantik.
"""

from __future__ import annotations

from playground.topology_tools.connect_edges import connect_selected_edges


def active_connect_fn(slots: dict):
    """Connect-Funktion der aktiven "connect"-Variante.

    Fällt auf die Baseline zurück, wenn die Familie nicht registriert ist
    (AD-013 A2: Lab-Override, Baseline bleibt unverändert).
    """
    slot = slots.get("connect") if slots else None
    if slot is None:
        return connect_selected_edges
    return getattr(slot.active_experiment, "connect_fn", connect_selected_edges)
