"""Lab control state: HUD rows, value steps, presets, A/B and light drag.

GL-free and window-free so every control path is testable headless. The
window (`lab_window.py`) only translates pyglet events into calls here and
renders `hud_lines()`; the store only ever sees `resolve(state.displayed_rig())`.

Semantics fixed by the handoff (WP-SHADE-LAB-01 Slice 1, E6/E7/E12/E13/E14):
- Presets (F1–F4) replace the edited rig and end A/B.
- B toggles the display between the edited rig and "Heute" (toggle, not
  hold — AD-013 A3 press/hold is open).
- Any edit while A/B shows "Heute" returns to the edited rig and applies the
  edit there (never to "Heute").
- After any edit the preset name reads "angepasst".

Implementation choices not fixed by the handoff (documented in the README):
- Switching "Fill-Kopplung" from coupled to free copies the current coupled
  angles into the free fill angles, so the fill does not jump.
- Switching "Bezugsraum" keeps the az/el numbers; the light therefore jumps
  to the same angles in the other frame.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from .lab_rig import (
    AMBIENT_MAX,
    AMBIENT_MIN,
    ELEVATION_MAX,
    ELEVATION_MIN,
    KELVIN_MAX,
    KELVIN_MIN,
    PRESET_HEUTE,
    PRESET_ORDER,
    PRESETS,
    RATIO_STEPS,
    SPACE_CAMERA,
    SPACE_WORLD,
    WRAP_MAX,
    WRAP_MIN,
    LightRig,
    wrap_degrees,
)

EDITED_NAME = "angepasst"

KEY_INTENSITY_MIN, KEY_INTENSITY_MAX = 0.0, 2.0
#: LMB light drag: degrees per pixel (E13 "Licht ziehen").
DRAG_DEGREES_PER_PIXEL = 0.5


@dataclass(frozen=True)
class Row:
    """One HUD parameter row."""

    id: str
    label: str
    #: (rig, direction, fine) -> new rig
    step: Callable[[LightRig, int, bool], LightRig]
    #: rig -> display text
    format: Callable[[LightRig], str]
    #: rig -> False when the row does not apply (greyed out, E14)
    applies: Callable[[LightRig], bool]


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _numeric(field: str, coarse: float, fine: float, lo: float, hi: float):
    def step(rig: LightRig, direction: int, is_fine: bool) -> LightRig:
        delta = (fine if is_fine else coarse) * direction
        value = round(_clamp(getattr(rig, field) + delta, lo, hi), 6)
        return rig.with_(**{field: value})

    return step


def _angle(field: str, coarse: float, fine: float):
    def step(rig: LightRig, direction: int, is_fine: bool) -> LightRig:
        delta = (fine if is_fine else coarse) * direction
        return rig.with_(**{field: round(wrap_degrees(getattr(rig, field) + delta), 6)})

    return step


def _step_space(rig: LightRig, direction: int, is_fine: bool) -> LightRig:
    return rig.with_(space=SPACE_WORLD if rig.space == SPACE_CAMERA else SPACE_CAMERA)


def _step_coupling(rig: LightRig, direction: int, is_fine: bool) -> LightRig:
    if rig.fill_coupled:
        az, el = rig.effective_fill_angles()
        return rig.with_(fill_coupled=False, fill_azimuth=az, fill_elevation=el)
    return rig.with_(fill_coupled=True)


def _step_ratio(rig: LightRig, direction: int, is_fine: bool) -> LightRig:
    try:
        index = RATIO_STEPS.index(rig.fill_ratio)
    except ValueError:
        index = RATIO_STEPS.index(2.0)
    index = int(_clamp(index + direction, 0, len(RATIO_STEPS) - 1))
    return rig.with_(fill_ratio=RATIO_STEPS[index])


def format_ratio(ratio: Optional[float]) -> str:
    if ratio is None:
        return "aus"
    return f"{ratio:g}:1"


def _always(rig: LightRig) -> bool:
    return True


def _fill_on(rig: LightRig) -> bool:
    return rig.fill_enabled


def _fill_free(rig: LightRig) -> bool:
    return rig.fill_enabled and not rig.fill_coupled


def _fmt_deg(field: str):
    return lambda rig: f"{getattr(rig, field):+.1f}°"


def _fmt_fill_angle(index: int):
    def fmt(rig: LightRig) -> str:
        value = rig.effective_fill_angles()[index]
        suffix = "  (gekoppelt)" if rig.fill_coupled else ""
        return f"{value:+.1f}°{suffix}"

    return fmt


ROWS: tuple[Row, ...] = (
    Row("space", "Bezugsraum", _step_space,
        lambda r: "Kamera" if r.space == SPACE_CAMERA else "Welt", _always),
    Row("key_azimuth", "Key Azimut", _angle("key_azimuth", 15.0, 1.0),
        _fmt_deg("key_azimuth"), _always),
    Row("key_elevation", "Key Höhe",
        _numeric("key_elevation", 5.0, 1.0, ELEVATION_MIN, ELEVATION_MAX),
        _fmt_deg("key_elevation"), _always),
    Row("key_intensity", "Key Stärke",
        _numeric("key_intensity", 0.05, 0.01, KEY_INTENSITY_MIN, KEY_INTENSITY_MAX),
        lambda r: f"{r.key_intensity:.2f}", _always),
    Row("key_kelvin", "Key Temperatur",
        _numeric("key_kelvin", 500.0, 100.0, KELVIN_MIN, KELVIN_MAX),
        lambda r: f"{r.key_kelvin:.0f} K", _always),
    Row("key_wrap", "Key Weichheit",
        _numeric("key_wrap", 0.1, 0.02, WRAP_MIN, WRAP_MAX),
        lambda r: f"{r.key_wrap:.2f}", _always),
    Row("fill_ratio", "Verhältnis Key:Fill", _step_ratio,
        lambda r: f"{format_ratio(r.fill_ratio)}  (Fill {r.fill_intensity:.2f})", _always),
    Row("fill_coupled", "Fill-Kopplung", _step_coupling,
        lambda r: "gekoppelt" if r.fill_coupled else "frei", _fill_on),
    Row("fill_azimuth", "Fill Azimut", _angle("fill_azimuth", 15.0, 1.0),
        _fmt_fill_angle(0), _fill_free),
    Row("fill_elevation", "Fill Höhe",
        _numeric("fill_elevation", 5.0, 1.0, ELEVATION_MIN, ELEVATION_MAX),
        _fmt_fill_angle(1), _fill_free),
    Row("fill_kelvin", "Fill Temperatur",
        _numeric("fill_kelvin", 500.0, 100.0, KELVIN_MIN, KELVIN_MAX),
        lambda r: f"{r.fill_kelvin:.0f} K", _fill_on),
    Row("fill_wrap", "Fill Weichheit",
        _numeric("fill_wrap", 0.1, 0.02, WRAP_MIN, WRAP_MAX),
        lambda r: f"{r.fill_wrap:.2f}", _fill_on),
    Row("ambient", "Grundhelligkeit",
        _numeric("ambient", 0.05, 0.01, AMBIENT_MIN, AMBIENT_MAX),
        lambda r: f"{r.ambient:.2f}", _always),
)

ROW_IDS: tuple[str, ...] = tuple(row.id for row in ROWS)


@dataclass(frozen=True)
class HudLine:
    """One HUD text line; `style` ∈ {"title", "normal", "active", "inactive", "warning"}."""

    text: str
    style: str = "normal"


class LabState:
    """Edited rig + preset name + A/B flag + active HUD row."""

    def __init__(self, preset: str = PRESET_HEUTE) -> None:
        self.rig: LightRig = PRESETS[preset]
        self.preset_name: str = preset
        self.ab_active: bool = False
        self.active_row: int = 0
        self.hud_visible: bool = True
        #: Bumped on every change that affects the image or the HUD text.
        self.revision: int = 0

    # -- what is on screen -----------------------------------------------------

    def displayed_rig(self) -> LightRig:
        return PRESETS[PRESET_HEUTE] if self.ab_active else self.rig

    def displayed_name(self) -> str:
        return PRESET_HEUTE if self.ab_active else self.preset_name

    # -- actions -------------------------------------------------------------------

    def apply_preset(self, name: str) -> None:
        self.rig = PRESETS[name]
        self.preset_name = name
        self.ab_active = False
        self.revision += 1

    def apply_preset_index(self, index: int) -> None:
        self.apply_preset(PRESET_ORDER[index])

    def toggle_ab(self) -> None:
        self.ab_active = not self.ab_active
        self.revision += 1

    def toggle_hud(self) -> None:
        self.hud_visible = not self.hud_visible
        self.revision += 1

    def select_row(self, direction: int) -> None:
        self.active_row = (self.active_row + direction) % len(ROWS)
        self.revision += 1

    def step_active(self, direction: int, fine: bool = False) -> None:
        self.step_row(ROWS[self.active_row].id, direction, fine)

    def step_row(self, row_id: str, direction: int, fine: bool = False) -> None:
        row = ROWS[ROW_IDS.index(row_id)]
        self._edit(row.step(self.rig, direction, fine))

    def drag_light(self, dx: float, dy: float) -> None:
        """LMB drag (E13): dx → key azimuth, dy → key elevation, in the current frame."""
        rig = self.rig
        self._edit(rig.with_(
            key_azimuth=round(wrap_degrees(rig.key_azimuth + dx * DRAG_DEGREES_PER_PIXEL), 6),
            key_elevation=round(_clamp(rig.key_elevation + dy * DRAG_DEGREES_PER_PIXEL,
                                       ELEVATION_MIN, ELEVATION_MAX), 6),
        ))

    def _edit(self, new_rig: LightRig) -> None:
        # E13: an edit while A/B shows "Heute" returns to the edited rig.
        self.ab_active = False
        if new_rig != self.rig:
            self.rig = new_rig
            self.preset_name = EDITED_NAME
        self.revision += 1

    # -- HUD text (E14) --------------------------------------------------------------

    def hud_lines(self, frame_ms: Optional[float] = None) -> list[HudLine]:
        rig = self.displayed_rig()
        ab = "B: Vergleich „Heute“ AKTIV" if self.ab_active else "B: Vergleich aus"
        lines = [HudLine(f"Preset: {self.displayed_name()}   |   {ab}", "title")]
        for index, row in enumerate(ROWS):
            marker = "▶" if index == self.active_row else " "
            text = f"{marker} {row.label:<20} {row.format(rig)}"
            if not row.applies(rig):
                style = "inactive"
            elif index == self.active_row:
                style = "active"
            else:
                style = "normal"
            lines.append(HudLine(text, style))
        total = rig.exposure_sum()
        if total > 1.0 + 1e-9:
            lines.append(HudLine(f"Summe Licht {total:.2f} > 1 — Überbelichtung möglich", "warning"))
        else:
            lines.append(HudLine(f"Summe Licht {total:.2f}", "normal"))
        if frame_ms is not None:
            lines.append(HudLine(f"Frame {frame_ms:.1f} ms", "normal"))
        return lines
