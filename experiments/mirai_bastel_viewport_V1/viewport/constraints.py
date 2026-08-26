"""Temporäres Welt-Achs-/Ebenensystem für Viewport V1.

Bewusst unabhängig von Move/Rotate/Scale: Das Experiment beschreibt nur,
welche Weltachsen bzw. Weltebenen als Constraint ausgewählt sind.
"""

from enum import Enum


class Constraint(Enum):
    NONE = "none"
    X = "x"
    Y = "y"
    Z = "z"
    XY = "xy"
    YZ = "yz"
    XZ = "xz"


HOTKEY_CONSTRAINTS = {
    "x": Constraint.X,
    "y": Constraint.Y,
    "z": Constraint.Z,
    "shift+x": Constraint.XY,
    "shift+y": Constraint.YZ,
    "shift+z": Constraint.XZ,
}


def constraint_from_key(key: str, shift: bool = False) -> Constraint:
    """Mappt die temporären Experiment-Hotkeys auf eine Constraint."""
    normalized = key.lower()
    if normalized not in {"x", "y", "z"}:
        return Constraint.NONE
    return HOTKEY_CONSTRAINTS[f"{'shift+' if shift else ''}{normalized}"]
