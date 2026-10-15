"""Two-light worklight rig (Key + Fill) — now a re-export of production `viewport.light_rig`.

The rig was promoted into the app on 2026-10-15 (Manu: lighting from the lab into the app,
default "Raitt 2:1", camera/world switchable, "Warm/Kalt" as a preset). The code that lived here
(handoff WP-SHADE-LAB-01 Slice 1, E3/E5–E10/E12) moved unchanged to `src/viewport/light_rig.py`;
this module keeps the lab's import path so the lab, its controls and its tests run on the one
production source instead of a copy. See git history for the original file.
"""

from __future__ import annotations

from viewport.light_rig import *  # noqa: F401,F403
from viewport.light_rig import (  # noqa: F401  (explicit for readers and linters)
    HEUTE_KEY_AZIMUTH,
    HEUTE_KEY_ELEVATION,
    PRESET_HEUTE,
    PRESET_ORDER,
    PRESET_RAITT,
    PRESET_SOFTBOX,
    PRESET_WARM_COLD,
    PRESETS,
    LightRig,
    resolve,
    shade,
)
