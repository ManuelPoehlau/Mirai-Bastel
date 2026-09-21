"""Transform — Variant 4: Hold-Key Hover (AD-016 D4).

Tap Q/W/E (movement below CLICK_THRESHOLD at key release):
    Sets the current tool only. No execution.

Hold Q/W/E + move mouse + release key:
    Executes the chosen tool and commits on key release.

Target (captured once at key press, not re-evaluated during drag):
    - Selection exists → the selection is transformed (like Blender G).
    - No selection → the element under the cursor at key-press time is the
      target (temp selection, cleared after commit/cancel — reuses the Tweak
      temp-target mechanism from _target.py).

ESC cancels as usual.

This is the former Tweak V1 (TweakV1HoldKey) behavior, re-owned by Transform
as decided by AD-016. Product verdict pending (KEEP / ITERATE / REJECT / UNKNOWN).
"""

from playground.experiment import Experiment


class HoldKeyHoverVariant(Experiment):
    id = "transform"
    name = "Transform"
    variant = "V4-HoldKeyHover (tap=set tool, hold+drag=execute)"
    activation = "hold_key_hover"

    def __init__(self, app) -> None:
        self._app = app

    def activate(self) -> None:
        pass

    def deactivate(self) -> None:
        pass
