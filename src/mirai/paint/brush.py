"""The paint dab and the stroke buffer (AD-037 §8 Phase 2; audit 2026-11-18 §4.2 principles 3-5, §6.2).

**Settings** (`BrushSettings`, view state of the Paint Room, not saved, no Undo): the tool (Paint, Erase, Pick), the radius
as a step of `RADIUS_STEPS_PERCENT` - a **world** radius in percent of the painted object's bounding radius (P-7, like Soft
and Brush O-3) -, the colour, opacity, flow, hardness and the falloff curve, and whether the dab is mirrored across the
mesh's symmetry plane. All values `PROVISIONAL` (agent-set).

**Falloff.** A texel at distance `d` from the dab centre (radius `r`, `x = d / r`) is covered with `curve(t)`, where
`t = 1` inside the hardness plateau (`x <= hardness`) and `t = (1 - x) / (1 - hardness)` outside it; the curves are the
Soft Selection's formulas (`soft_selection.influence.CURVES`: smooth, sphere, root, sharp, linear) in array form
(`CURVE_ARRAYS`, pinned equal by a test).

**Opacity vs. flow** (the stroke buffer, principle 4). Within one stroke a per-texel coverage `S` accumulates every dab as
`S <- S + (1 - S) * flow * falloff` (so a flow below 1 builds up where dabs overlap, up to 1), and the layer shows the
stroke's start pixels with the colour over them at `opacity * S` - opacity caps what one stroke can lay down and does not
build up inside it. Erase reduces the layer's alpha the same way. The stroke keeps a copy of the layer at its start, so
every dab recomputes from the same start pixels (Esc is the recorder's exact restore, `PaintStore.StrokeRecorder.cancel`).

**Blend** (Normal, straight alpha, 8 bit, P-12/P-16): `a = s + a0 (1 - s)`, `c = (k s + c0 a0 (1 - s)) / a`, rounded.

**Jitter, scatter, spray** (Phase 4b, AD-037 §13) live in `dynamics` too (`StrokeDynamics`); a cluster's stamps
write once through `dab_product`.

**Tip and dynamics** (Phase 4a, AD-037 §12): every brush has a tip (`TipSettings`): the **round tip** (no alpha - the
falloff above, unchanged) or an **alpha tip** (`alpha` = an alpha id, `mirai.paint.alpha`; the Kreismaske multiplies
the falloff in, off by default, P-19). `dynamics` (`mirai.paint.dynamics.StrokeDynamics`) holds the spacing in world arc
length (P-18) and the orientation. Both default to "today's round brush". A cluster of several stamps combines in one
write as `S <- 1 - (1 - S) * prod(1 - flow_k * c_k)` (`PaintStroke.dab_product`; the stroke buffer's `S + (1 - S) * f`
is order-independent, so this is the same as applying them one by one).
"""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass

import numpy as np

from .dynamics import ALPHA_SPACING, ROUND_SPACING, StrokeDynamics

TOOL_PAINT = "paint"
TOOL_ERASE = "erase"
TOOL_PICK = "pick"
TOOLS = (TOOL_PAINT, TOOL_ERASE, TOOL_PICK)
TOOL_LABELS = {TOOL_PAINT: "Malen", TOOL_ERASE: "Radieren", TOOL_PICK: "Pipette"}

#: `PROVISIONAL` (agent-set): brush radius steps in percent of the bounding radius (P-7). The probe's rows 1 / 3 / 5 / 10 %
#: are steps; 3 % is the start (P-A's bar row).
RADIUS_STEPS_PERCENT: tuple[float, ...] = (0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 15.0)
DEFAULT_RADIUS_STEP = RADIUS_STEPS_PERCENT.index(3.0)
#: `PROVISIONAL`: opacity steps of the opacity wheel (Alt+wheel in the room, P-6), in percent.
OPACITY_STEPS_PERCENT: tuple[int, ...] = (5, 10, 15, 20, 25, 30, 40, 50, 60, 70, 80, 90, 100)


def _smooth(t):
    return t * t * (3.0 - 2.0 * t)


def _sphere(t):
    return np.sqrt(np.maximum(0.0, 2.0 * t - t * t))


def _root(t):
    return np.sqrt(t)


def _sharp(t):
    return t * t


def _linear(t):
    return t


#: The Soft Selection curves (`soft_selection.influence.CURVES`, the same formulas) on arrays; `custom` is not offered
#: (its exponent is a Soft setting).
CURVE_ARRAYS = {"smooth": _smooth, "sphere": _sphere, "root": _root, "sharp": _sharp, "linear": _linear}
CURVE_LABELS = {"smooth": "Weich", "sphere": "Kugel", "root": "Rund", "sharp": "Spitz", "linear": "Linear"}


@dataclass(frozen=True)
class TipSettings:
    """The brush tip (module docstring): `alpha` None = the round tip."""

    alpha: str | None = None
    kreismaske: bool = False

    @property
    def round(self) -> bool:
        return self.alpha is None


@dataclass(frozen=True)
class BrushSettings:
    tool: str = TOOL_PAINT
    radius_step: int = DEFAULT_RADIUS_STEP
    colour: tuple[float, float, float] = (0.55, 0.18, 0.16)
    opacity: float = 1.0
    flow: float = 1.0
    hardness: float = 0.5
    curve: str = "smooth"
    mirror: bool = True
    tip: TipSettings = TipSettings()
    dynamics: StrokeDynamics = StrokeDynamics()

    def __post_init__(self) -> None:
        if self.tool not in TOOLS:
            raise ValueError(f"brush tool one of {TOOLS}, got {self.tool!r}")
        if not 0 <= self.radius_step < len(RADIUS_STEPS_PERCENT):
            raise ValueError(f"radius step out of range: {self.radius_step}")
        if self.curve not in CURVE_ARRAYS:
            raise ValueError(f"curve one of {tuple(CURVE_ARRAYS)}, got {self.curve!r}")
        for name in ("opacity", "flow", "hardness"):
            value = getattr(self, name)
            if not (isinstance(value, (int, float)) and math.isfinite(value) and 0.0 <= value <= 1.0):
                raise ValueError(f"{name} must lie in [0, 1], got {value!r}")
        if len(self.colour) != 3 or not all(0.0 <= c <= 1.0 for c in self.colour):
            raise ValueError(f"colour must be three values in [0, 1], got {self.colour!r}")
        if not isinstance(self.tip, TipSettings) or not isinstance(self.dynamics, StrokeDynamics):
            raise ValueError("tip must be TipSettings and dynamics StrokeDynamics")

    @property
    def radius_percent(self) -> float:
        return RADIUS_STEPS_PERCENT[self.radius_step]

    def world_radius(self, bounding_radius: float) -> float:
        return bounding_radius * self.radius_percent / 100.0

    def with_(self, **changes) -> "BrushSettings":
        if "colour" in changes:
            changes["colour"] = tuple(float(min(max(c, 0.0), 1.0)) for c in changes["colour"])
        for name in ("opacity", "flow", "hardness"):
            if name in changes:
                changes[name] = float(min(max(changes[name], 0.0), 1.0))
        if "radius_step" in changes:
            changes["radius_step"] = max(0, min(int(changes["radius_step"]), len(RADIUS_STEPS_PERCENT) - 1))
        return dataclasses.replace(self, **changes)

    def with_tip(self, tip: TipSettings) -> "BrushSettings":
        """Another tip; switching between the round and an alpha tip sets that kind's default spacing (a spray keeps
        its own)."""
        if tip.round == self.tip.round or self.dynamics.spray:
            return dataclasses.replace(self, tip=tip)
        spacing = ROUND_SPACING if tip.round else ALPHA_SPACING
        return dataclasses.replace(self, tip=tip, dynamics=dataclasses.replace(self.dynamics, spacing=spacing))

    def with_opacity_step(self, delta: int) -> "BrushSettings":
        """The next / previous opacity step (clamped)."""
        steps = OPACITY_STEPS_PERCENT
        current = self.opacity * 100.0
        if delta > 0:
            higher = [s for s in steps if s > current + 1e-6]
            value = higher[0] if higher else steps[-1]
        else:
            lower = [s for s in steps if s < current - 1e-6]
            value = lower[-1] if lower else steps[0]
        return self.with_(opacity=value / 100.0)

    def status_text(self) -> str:
        tool = TOOL_LABELS[self.tool]
        if self.tool == TOOL_PICK:
            return f"Paint: {tool}"
        text = (f"Paint: {tool} - Radius {self.radius_percent:g} %, Deckkraft {self.opacity * 100:.0f} %, "
                f"Fluss {self.flow * 100:.0f} %")
        if self.tip.round or self.tip.kreismaske:
            text += f", Härte {self.hardness * 100:.0f} %, Kurve {CURVE_LABELS[self.curve]}"
        if not self.tip.round:
            from .alpha import alpha_name

            text += f", Spitze {alpha_name(self.tip.alpha)}"
        text += f", Abstand {self.dynamics.spacing * 100:.0f} %"
        dyn = self.dynamics
        if dyn.spray:
            text += f", Spray {dyn.spray_density}"
        if dyn.scattered or dyn.jitter_rotation or dyn.jitter_size or dyn.jitter_flow:
            text += ", Streuung"
        return text


def falloff(x: np.ndarray, hardness: float, curve: str) -> np.ndarray:
    """Coverage in [0, 1] at normalized distances `x = d / r` (module docstring); 0 at and beyond 1."""
    x = np.asarray(x, dtype=np.float64)
    if hardness >= 1.0:
        t = (x < 1.0).astype(np.float64)
    else:
        t = np.clip((1.0 - x) / (1.0 - hardness), 0.0, 1.0)
    return np.where(x < 1.0, CURVE_ARRAYS[curve](t), 0.0)


def blend_paint(start: np.ndarray, colour: tuple[float, float, float], strength: np.ndarray) -> np.ndarray:
    """`start` (n, 4) uint8 RGBA with `colour` laid over at `strength` (n,) in [0, 1] (Normal, straight alpha)."""
    s = np.asarray(strength, dtype=np.float32)[:, None]
    a0 = start[:, 3:4].astype(np.float32) / 255.0
    c0 = start[:, :3].astype(np.float32)
    k = np.asarray(colour, dtype=np.float32)[None, :] * 255.0
    a = s + a0 * (1.0 - s)
    with np.errstate(invalid="ignore", divide="ignore"):
        c = np.where(a > 0.0, (k * s + c0 * a0 * (1.0 - s)) / np.maximum(a, 1e-12), c0)
    out = np.empty_like(start)
    out[:, :3] = np.clip(np.rint(c), 0, 255).astype(np.uint8)
    out[:, 3] = np.clip(np.rint(a[:, 0] * 255.0), 0, 255).astype(np.uint8)
    return out


def blend_erase(start: np.ndarray, strength: np.ndarray) -> np.ndarray:
    """`start` (n, 4) with its alpha reduced by `strength` (n,) in [0, 1]; the colour stays."""
    s = np.asarray(strength, dtype=np.float32)
    out = start.copy()
    out[:, 3] = np.clip(np.rint(start[:, 3].astype(np.float32) * (1.0 - s)), 0, 255).astype(np.uint8)
    return out


class PaintStroke:
    """One stroke on one layer through a `StrokeRecorder` (module docstring): `dab(texels, coverage)` per dab, then the
    recorder's `commit()` / `cancel()` (the caller's)."""

    def __init__(self, recorder, settings: BrushSettings) -> None:
        self.recorder = recorder
        self.settings = settings
        layer = recorder.store.pixels(recorder.obj, recorder.name)
        self.height, self.width = layer.shape[:2]
        self.start = layer.reshape(-1, 4).copy()  # the stroke's start pixels (every dab recomputes from them)
        self.cover = np.zeros(self.width * self.height, dtype=np.float32)
        self.dabs = 0

    def dab(self, texels: np.ndarray, coverage: np.ndarray, unique: bool = False) -> int:
        """One dab: `coverage` (n,) = falloff of the texels (flow is applied here); `unique` = no texel twice (one
        footprint; a dab with its mirror can share texels at the plane). Returns the texels written."""
        texels = np.asarray(texels, dtype=np.int64)
        if texels.size == 0:
            return 0
        if not unique:
            texels, coverage = self.merge_coverage(texels, coverage)  # a texel in a dab and its mirror counts once
        coverage = np.asarray(coverage, dtype=np.float32)
        settings = self.settings
        cover = self.cover[texels]
        cover = cover + (1.0 - cover) * (settings.flow * coverage)
        self.cover[texels] = cover
        strength = settings.opacity * cover
        start = self.start[texels]
        if settings.tool == TOOL_ERASE:
            values = blend_erase(start, strength)
        else:
            values = blend_paint(start, settings.colour, strength)
        self.recorder.write_texels(texels, values)
        self.dabs += 1
        return int(texels.size)

    def dab_product(self, texels: np.ndarray, product: np.ndarray) -> int:
        """A cluster of stamps in one write: `product` (n,) = `prod(1 - flow_k * c_k)` per texel (unique texels), so
        `S <- 1 - (1 - S) * product` (module docstring). Returns the texels written."""
        texels = np.asarray(texels, dtype=np.int64)
        if texels.size == 0:
            return 0
        cover = 1.0 - (1.0 - self.cover[texels]) * np.asarray(product, dtype=np.float32)
        self.cover[texels] = cover
        self._write(texels, cover)
        self.dabs += 1
        return int(texels.size)

    def _write(self, texels: np.ndarray, cover: np.ndarray) -> None:
        settings = self.settings
        strength = settings.opacity * cover
        start = self.start[texels]
        if settings.tool == TOOL_ERASE:
            values = blend_erase(start, strength)
        else:
            values = blend_paint(start, settings.colour, strength)
        self.recorder.write_texels(texels, values)

    def merge_coverage(self, texels: np.ndarray, coverage: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """`texels` with duplicates merged to their largest coverage (a dab and its mirror overlapping at the plane)."""
        texels = np.asarray(texels, dtype=np.int64)
        coverage = np.asarray(coverage, dtype=np.float32)
        if texels.size == 0:
            return texels, coverage
        order = np.lexsort((-coverage, texels))
        texels, coverage = texels[order], coverage[order]
        keep = np.r_[True, texels[1:] != texels[:-1]]
        return texels[keep], coverage[keep]
