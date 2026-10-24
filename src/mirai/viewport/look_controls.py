"""Look rows: the temporary value editing of the Worklight in the Production window (AD-024 §8).

GL-free and pyglet-free. The rows, their value steps and ranges are taken from the Viewport Shading Lab
(`experiments/viewport_shading_lab/lab_controls.py`, WP-SHADE-LAB-01 E7/E13/E14), so a step feels as
there; the Lab keeps its own copy (it imports nothing from `src/mirai`). Differences, `PROVISIONAL`:
the fine step is `Ctrl` (the Lab's `Shift` is the selection steps in Production), and a row that does
not apply (fill off, fill coupled) is refused instead of changed invisibly.

`Application.set_light` / `step_light` are the edit path; the keys (`↑`/`↓` row, `←`/`→` value) only
call them, and the later GUI (Stage 2 gate) calls the same setters. Light edits are view state, never
an Undo step (AD-024 §7).
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Callable, Optional

from viewport.light_rig import (
    AMBIENT_MAX,
    AMBIENT_MIN,
    ELEVATION_MAX,
    ELEVATION_MIN,
    KELVIN_MAX,
    KELVIN_MIN,
    RATIO_STEPS,
    SPACE_CAMERA,
    SPACE_WORLD,
    WRAP_MAX,
    WRAP_MIN,
    LightRig,
    wrap_degrees,
)

#: The Lab's key intensity range (`lab_controls.KEY_INTENSITY_MIN/MAX`).
KEY_INTENSITY_MIN, KEY_INTENSITY_MAX = 0.0, 2.0
#: The finite ratios (`None` = fill off is the step after the last).
_RATIOS = tuple(r for r in RATIO_STEPS if r is not None)
RATIO_MIN, RATIO_MAX = min(_RATIOS), max(_RATIOS)

LIGHT_FIELDS = frozenset(f.name for f in fields(LightRig))

_RANGES: dict[str, tuple[float, float]] = {
    "key_elevation": (ELEVATION_MIN, ELEVATION_MAX),
    "fill_elevation": (ELEVATION_MIN, ELEVATION_MAX),
    "key_intensity": (KEY_INTENSITY_MIN, KEY_INTENSITY_MAX),
    "key_kelvin": (KELVIN_MIN, KELVIN_MAX),
    "fill_kelvin": (KELVIN_MIN, KELVIN_MAX),
    "key_wrap": (WRAP_MIN, WRAP_MAX),
    "fill_wrap": (WRAP_MIN, WRAP_MAX),
    "ambient": (AMBIENT_MIN, AMBIENT_MAX),
}
_ANGLES = ("key_azimuth", "fill_azimuth")


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def clamp_light(rig: LightRig) -> LightRig:
    """`rig` with every value in the Lab's range (angles wrapped, the ratio in 1..8 or None).
    Raises `ValueError` for an unknown space (a typo is not a value to clamp)."""
    if rig.space not in (SPACE_CAMERA, SPACE_WORLD):
        raise ValueError(f"unknown light space {rig.space!r}")
    changes: dict = {name: _clamp(float(getattr(rig, name)), lo, hi) for name, (lo, hi) in _RANGES.items()}
    for name in _ANGLES:
        changes[name] = wrap_degrees(float(getattr(rig, name)))
    if rig.fill_ratio is not None:
        changes["fill_ratio"] = _clamp(float(rig.fill_ratio), RATIO_MIN, RATIO_MAX)
    changes["fill_coupled"] = bool(rig.fill_coupled)
    return rig.with_(**changes)


def step_ratio(ratio: Optional[float], direction: int) -> Optional[float]:
    """The next entry of `RATIO_STEPS` above (`direction` > 0) or below the current ratio; a ratio
    between two steps goes to the neighbouring step in that direction, the ends stay."""
    if ratio is None:
        return RATIO_STEPS[-1] if direction > 0 else _RATIOS[-1]
    if direction > 0:
        above = [r for r in _RATIOS if r > ratio + 1e-9]
        return above[0] if above else RATIO_STEPS[-1]
    below = [r for r in _RATIOS if r < ratio - 1e-9]
    return below[-1] if below else _RATIOS[0]


def format_ratio(ratio: Optional[float]) -> str:
    return "aus" if ratio is None else f"{ratio:g}:1"


@dataclass(frozen=True)
class LookRow:
    """One editable value: `step(rig, direction, fine) -> rig`, `format(rig) -> str`,
    `applies(rig)` False = the row has no effect right now (refused, shown as such)."""

    id: str
    label: str
    step: Callable[[LightRig, int, bool], LightRig]
    format: Callable[[LightRig], str]
    applies: Callable[[LightRig], bool]
    #: Why the row does not apply (status text).
    inactive_reason: str = ""


def _numeric(name: str, coarse: float, fine: float):
    lo, hi = _RANGES[name]

    def step(rig: LightRig, direction: int, is_fine: bool) -> LightRig:
        value = getattr(rig, name) + (fine if is_fine else coarse) * direction
        return rig.with_(**{name: round(_clamp(value, lo, hi), 6)})

    return step


def _angle(name: str, coarse: float, fine: float):
    def step(rig: LightRig, direction: int, is_fine: bool) -> LightRig:
        value = getattr(rig, name) + (fine if is_fine else coarse) * direction
        return rig.with_(**{name: round(wrap_degrees(value), 6)})

    return step


def _step_space(rig: LightRig, direction: int, is_fine: bool) -> LightRig:
    return rig.with_(space=SPACE_WORLD if rig.space == SPACE_CAMERA else SPACE_CAMERA)


def _step_coupling(rig: LightRig, direction: int, is_fine: bool) -> LightRig:
    # As the Lab: a coupled fill becomes free at the angles it had, so it does not jump.
    if rig.fill_coupled:
        az, el = rig.effective_fill_angles()
        return rig.with_(fill_coupled=False, fill_azimuth=az, fill_elevation=el)
    return rig.with_(fill_coupled=True)


def _step_fill_ratio(rig: LightRig, direction: int, is_fine: bool) -> LightRig:
    return rig.with_(fill_ratio=step_ratio(rig.fill_ratio, direction))


def _always(rig: LightRig) -> bool:
    return True


def _fill_on(rig: LightRig) -> bool:
    return rig.fill_enabled


def _fill_free(rig: LightRig) -> bool:
    return rig.fill_enabled and not rig.fill_coupled


def _deg(name: str):
    return lambda rig: f"{getattr(rig, name):+.1f}°"


def _fill_angle(index: int):
    def fmt(rig: LightRig) -> str:
        suffix = " (gekoppelt)" if rig.fill_coupled else ""
        return f"{rig.effective_fill_angles()[index]:+.1f}°{suffix}"

    return fmt


_FILL_OFF = "Fill ist aus (Verhältnis)"
_FILL_COUPLED = "Fill ist gekoppelt (Fill-Kopplung)"

#: The Lab's rows in the Lab's order (`lab_controls.ROWS`), with its coarse / fine steps.
LIGHT_ROWS: tuple[LookRow, ...] = (
    LookRow("space", "Licht Bezugsraum", _step_space,
            lambda r: "Kamera" if r.space == SPACE_CAMERA else "Welt", _always),
    LookRow("key_azimuth", "Key Azimut", _angle("key_azimuth", 15.0, 1.0), _deg("key_azimuth"), _always),
    LookRow("key_elevation", "Key Höhe", _numeric("key_elevation", 5.0, 1.0), _deg("key_elevation"), _always),
    LookRow("key_intensity", "Key Stärke", _numeric("key_intensity", 0.05, 0.01),
            lambda r: f"{r.key_intensity:.2f}", _always),
    LookRow("key_kelvin", "Key Temperatur", _numeric("key_kelvin", 500.0, 100.0),
            lambda r: f"{r.key_kelvin:.0f} K", _always),
    LookRow("key_wrap", "Key Weichheit", _numeric("key_wrap", 0.1, 0.02), lambda r: f"{r.key_wrap:.2f}", _always),
    LookRow("fill_ratio", "Verhältnis Key:Fill", _step_fill_ratio,
            lambda r: f"{format_ratio(r.fill_ratio)} (Fill {r.fill_intensity:.2f})", _always),
    LookRow("fill_coupled", "Fill-Kopplung", _step_coupling,
            lambda r: "gekoppelt" if r.fill_coupled else "frei", _fill_on, _FILL_OFF),
    LookRow("fill_azimuth", "Fill Azimut", _angle("fill_azimuth", 15.0, 1.0), _fill_angle(0), _fill_free,
            _FILL_COUPLED),
    LookRow("fill_elevation", "Fill Höhe", _numeric("fill_elevation", 5.0, 1.0), _fill_angle(1), _fill_free,
            _FILL_COUPLED),
    LookRow("fill_kelvin", "Fill Temperatur", _numeric("fill_kelvin", 500.0, 100.0),
            lambda r: f"{r.fill_kelvin:.0f} K", _fill_on, _FILL_OFF),
    LookRow("fill_wrap", "Fill Weichheit", _numeric("fill_wrap", 0.1, 0.02), lambda r: f"{r.fill_wrap:.2f}",
            _fill_on, _FILL_OFF),
    LookRow("ambient", "Grundhelligkeit", _numeric("ambient", 0.05, 0.01), lambda r: f"{r.ambient:.2f}", _always),
)

LIGHT_ROW_IDS: tuple[str, ...] = tuple(row.id for row in LIGHT_ROWS)


def light_row(row_id: str) -> LookRow:
    try:
        return LIGHT_ROWS[LIGHT_ROW_IDS.index(row_id)]
    except ValueError:
        raise KeyError(f"unknown light row {row_id!r}; expected one of {LIGHT_ROW_IDS}") from None
