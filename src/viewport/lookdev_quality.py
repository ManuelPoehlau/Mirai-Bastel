"""LookDev LD-3a quality manager (AD-040 §2–§4): the render configuration a LookDev frame draws, the room's activity
state and Auto - pure, no GL, no Core.

- `RenderConfig`: render fields only (Q1) - the effects a frame draws (a subset of the artist's allowed effects, Q2),
  the key map's size and its update policy while Interactive, the cube's sample count, and LD-3b's `samples` / `jitter`
  (1 / False in LD-3a).
- `resolve(tier, allowed, features, refine, state, idle_tier, drops, drag_updates)`: the one function that maps the
  tier, the allowed effects, the context's features, „In Ruhe verfeinern“ and the activity state to a `RenderConfig`
  (AD-040 §2.2 / §2.3). It can only switch an allowed effect off or raise a size / sample count; it never switches on an
  effect the artist switched off.
- `ActivityTracker`: Interactive → Settling → Refine(n) → Converged from the frame signature (`Viewport.
  lookdev_signature`), a held hint and the tick's dt (AD-040 §3.2). N = 1 in LD-3a.
- `AutoTier`: the interactive tier from measured GPU times of Interactive frames only (Q8), a moving p50, hysteresis and
  a pace limit (AD-040 §4.3).
- `IdleCeiling`: the 50 ms ceiling of an idle frame - drops the most expensive idle knob in a fixed order (§4.2).

Every tier name, threshold and label is `PROVISIONAL` until the LD-3a reference-PC run (AD-040 §11.1) calibrates it.
"""

from __future__ import annotations

import statistics
from collections import deque
from dataclasses import dataclass, field, fields, replace

from .lookdev_optics import LookdevEffects, effective

# -- names ----------------------------------------------------------------------------------------------------------

#: The interactive tier's choices (the panel's „Qualität (beim Arbeiten)“) and the tiers Auto moves between.
TIERS = ("auto", "hoch", "mittel", "entwurf")
AUTO_TIERS = ("hoch", "mittel", "entwurf")
#: The idle tier's choices („Ruhe-Qualität“, only with „In Ruhe verfeinern“).
IDLE_TIERS = ("hoch", "maximal")
TIER_LABELS = {"auto": "Auto", "hoch": "Hoch", "mittel": "Mittel", "entwurf": "Entwurf", "maximal": "Maximal"}

#: The activity states (AD-040 §3.2).
INTERACTIVE, SETTLING, REFINE, CONVERGED = "interactive", "settling", "refine", "converged"
STATES = (INTERACTIVE, SETTLING, REFINE, CONVERGED)
STATE_LABELS = {INTERACTIVE: "Interaktiv", SETTLING: "Interaktiv", REFINE: "Ruhe", CONVERGED: "Ruhe"}

#: The key map's update policies while Interactive (AD-040 §2.2, Q-LD3-1).
SHADOW_UPDATES = ("every", "every_2nd", "frozen")
SHADOW_UPDATE_LABELS = {"every": "jedes Frame", "every_2nd": "jedes 2. Frame", "frozen": "eingefroren"}
#: How many caster-only map changes in a row `KeyShadow.update` may postpone (None = until the policy changes).
SHADOW_DEFER = {"every": 0, "every_2nd": 1, "frozen": None}
#: Q-LD3-1 is open until the reference-PC run: Hoch / Mittel keep today's map (every frame) by default.
DEFAULT_DRAG_UPDATES = "every"

#: Sizes (AD-040 §2.2): the P3 map and cube, and Maximal's.
SHADOW_SIZE = 1024
SHADOW_SIZE_MAX = 2048
CUBE_SAMPLES = 64
CUBE_SAMPLES_MAX = 256

#: The waiting time before the room counts as quiet (F-R4) and its panel bounds, seconds.
WAIT_DEFAULT = 0.3
WAIT_MIN, WAIT_MAX = 0.1, 2.0

#: Auto (AD-040 §4.2 / §4.3, `PROVISIONAL`, Q-LD3-2): the GPU target per interactive frame, the step-up threshold,
#: the windows (frames) and the pace (seconds).
AUTO_TARGET_MS = 12.0
AUTO_UP_MS = 6.0
AUTO_DOWN_WINDOW = 30
AUTO_UP_WINDOW = 60
AUTO_PACE_S = 2.0

#: The idle frame's ceiling (AD-040 §4.2) and the knobs it drops, in order (LD-3b adds the jittered key in front).
IDLE_CEILING_MS = 50.0
IDLE_CEILING_FRAMES = 5
IDLE_DROPS = ("soft_shadow", "shadow_size")
IDLE_DROP_LABELS = {"soft_shadow": "Weicher Schatten", "shadow_size": "Schatten 2048²"}

#: The effects Entwurf switches off, and the ones Mittel does (AD-040 §2.2).
_ENTWURF_OFF = ("shadow", "eye_shadow", "thickness", "dual_lobe", "area_diffuse", "soft_shadow")
_MITTEL_OFF = ("soft_shadow",)


# -- the configuration ----------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class RenderConfig:
    """What one LookDev frame draws (render fields only, AD-040 Q1)."""

    effects: LookdevEffects
    shadow_size: int = SHADOW_SIZE
    shadow_updates: str = "every"
    cube_samples: int = CUBE_SAMPLES
    samples: int = 1
    jitter: bool = False

    def __post_init__(self) -> None:
        if self.shadow_updates not in SHADOW_UPDATES:
            raise ValueError(f"RenderConfig: shadow_updates one of {SHADOW_UPDATES}")

    @property
    def shadow_defer(self) -> int | None:
        return SHADOW_DEFER[self.shadow_updates]


def masked(effects: LookdevEffects, off) -> LookdevEffects:
    """`effects` with the names in `off` switched off (never one switched on)."""
    return replace(effects, **{name: False for name in off})


def intersect(a: LookdevEffects, b: LookdevEffects) -> LookdevEffects:
    """The effects on in both."""
    return LookdevEffects(**{name: bool(getattr(a, name)) and bool(getattr(b, name))
                             for name in LookdevEffects.names()})


def subset(a: LookdevEffects, b: LookdevEffects) -> bool:
    """Every effect on in `a` is on in `b` (AD-040 Q2)."""
    return all(getattr(b, name) for name in LookdevEffects.names() if getattr(a, name))


def resolve(tier: str, allowed: LookdevEffects, features=None, refine: bool = False, state: str = INTERACTIVE,
            idle_tier: str = "hoch", drops=(), drag_updates: str = DEFAULT_DRAG_UPDATES) -> RenderConfig:
    """AD-040 §2.2 / §2.3: the configuration for the interactive `tier` ("hoch" / "mittel" / "entwurf"; Auto's current
    one, never "auto"), the artist's `allowed` effects, the context's `features` (None = nothing known missing),
    „In Ruhe verfeinern“, the activity `state`, the idle tier and the idle knobs the ceiling dropped (`IDLE_DROPS`).

    - Refinement off: the tier in every state; Hoch is today's frame (S9 as allowed).
    - Refinement on: Interactive / Settling draw the tier without S9 (the idle-only rule, F-R3); Refine / Converged
      draw the idle tier (Hoch: as allowed; Maximal: the 2048² map, 256 cube samples) minus the dropped knobs.
    - `shadow_updates` is the tier's policy while Interactive only (Entwurf frozen, else `drag_updates`); "every" in
      every other state, so the first Settling frame brings the map up to date."""
    if tier not in AUTO_TIERS:
        raise ValueError(f"resolve: tier one of {AUTO_TIERS}, got {tier!r}")
    if idle_tier not in IDLE_TIERS:
        raise ValueError(f"resolve: idle tier one of {IDLE_TIERS}, got {idle_tier!r}")
    if state not in STATES:
        raise ValueError(f"resolve: state one of {STATES}, got {state!r}")
    if drag_updates not in SHADOW_UPDATES:
        raise ValueError(f"resolve: drag_updates one of {SHADOW_UPDATES}")
    base = effective(allowed, features)
    idle = refine and state in (REFINE, CONVERGED)
    if idle:
        effects = masked(base, ("soft_shadow",)) if "soft_shadow" in drops else base
        maximal = idle_tier == "maximal"
        size = SHADOW_SIZE_MAX if maximal and "shadow_size" not in drops else SHADOW_SIZE
        return RenderConfig(effects, size, "every", CUBE_SAMPLES_MAX if maximal else CUBE_SAMPLES)
    off = {"entwurf": _ENTWURF_OFF, "mittel": _MITTEL_OFF, "hoch": ()}[tier]
    if refine:
        off = tuple(off) + ("soft_shadow",)
    updates = "every"
    if state == INTERACTIVE:
        updates = "frozen" if tier == "entwurf" else drag_updates
    return RenderConfig(masked(base, off), SHADOW_SIZE, updates, CUBE_SAMPLES)


def reachable(tier: str, allowed: LookdevEffects, features=None, refine: bool = False, idle_tier: str = "hoch",
              drag_updates: str = DEFAULT_DRAG_UPDATES) -> tuple[RenderConfig, ...]:
    """AD-040 §5: every configuration the room can draw with these settings (with Auto every interactive tier, with
    refinement the idle tier and its drops) - the union `prepare_lookdev` compiles."""
    tiers = AUTO_TIERS if tier == "auto" else (tier,)
    out: list[RenderConfig] = []
    for t in tiers:
        for state in (INTERACTIVE, SETTLING):
            out.append(resolve(t, allowed, features, refine, state, idle_tier, (), drag_updates))
    if refine:
        for n in range(len(IDLE_DROPS) + 1):
            out.append(resolve(AUTO_TIERS[0], allowed, features, True, REFINE, idle_tier, IDLE_DROPS[:n],
                               drag_updates))
    seen, unique = set(), []
    for config in out:
        if config not in seen:
            seen.add(config)
            unique.append(config)
    return tuple(unique)


# -- the activity state ---------------------------------------------------------------------------------------------

def clamp_wait(seconds: float) -> float:
    return max(WAIT_MIN, min(WAIT_MAX, float(seconds)))


class ActivityTracker:
    """AD-040 §3.2. `step(signature, held, dt)` once per tick, before the frame is drawn; returns the state the frame
    draws in. A changed signature or `held` → Interactive in the same tick; an unchanged one → Settling; `wait` seconds
    of Settling → Refine(0); `samples` refine frames → Converged."""

    def __init__(self, wait: float = WAIT_DEFAULT, samples: int = 1) -> None:
        self.wait = clamp_wait(wait)
        self.samples = max(1, int(samples))
        self.state = INTERACTIVE
        self.n = 0  # refine frames drawn
        self.quiet = 0.0  # seconds of Settling
        self._signature = None
        self._started = False

    def reset(self) -> None:
        self.state, self.n, self.quiet = INTERACTIVE, 0, 0.0
        self._signature, self._started = None, False

    def step(self, signature, held: bool, dt: float) -> str:
        changed = not self._started or signature != self._signature
        self._signature, self._started = signature, True
        if changed or held:
            self.state, self.n, self.quiet = INTERACTIVE, 0, 0.0
            return self.state
        if self.state == INTERACTIVE:
            self.state, self.quiet = SETTLING, 0.0
        elif self.state == SETTLING:
            self.quiet += max(0.0, float(dt))
            if self.quiet + 1e-9 >= self.wait:
                self.state, self.n = REFINE, 0
        elif self.state == REFINE:
            self.n += 1
            if self.n >= self.samples:
                self.state = CONVERGED
        return self.state

    @property
    def idle(self) -> bool:
        return self.state in (REFINE, CONVERGED)


# -- Auto -----------------------------------------------------------------------------------------------------------

class AutoTier:
    """AD-040 §4.3: the interactive tier Auto draws. Fed only with the GPU times of Interactive frames drawn in the
    current tier (Q8); a moving p50 over `AUTO_DOWN_WINDOW` frames above the target steps down, a p50 below
    `AUTO_UP_MS` over `AUTO_UP_WINDOW` frames with the next tier's remembered p50 below the target steps up; at most one
    change per `AUTO_PACE_S`. Without a timer it holds Mittel."""

    def __init__(self, target_ms: float = AUTO_TARGET_MS, up_ms: float = AUTO_UP_MS) -> None:
        self.target_ms = float(target_ms)
        self.up_ms = float(up_ms)
        self.tier = AUTO_TIERS[0]
        self.available = True
        #: the last p50 measured in each tier this session (the step-up check)
        self.remembered: dict[str, float] = {}
        self._times: deque = deque(maxlen=AUTO_UP_WINDOW)
        self._last_change = None

    def reset(self) -> None:
        """A room entry: Hoch (today's frame) again; the session's remembered p50s stay."""
        self.tier = AUTO_TIERS[0] if self.available else "mittel"
        self._times.clear()
        self._last_change = None

    def unavailable(self) -> None:
        """No timer in this context: Mittel, no measurement."""
        self.available = False
        self.tier = "mittel"
        self._times.clear()

    @property
    def p50(self) -> float | None:
        times = list(self._times)[-AUTO_DOWN_WINDOW:]
        return statistics.median(times) if times else None

    def feed(self, ms: float, tier: str, now: float) -> bool:
        """One Interactive frame's GPU time, drawn in `tier` at `now` (seconds). True = the tier changed."""
        if not self.available or tier != self.tier:
            return False
        self._times.append(float(ms))
        recent = list(self._times)[-AUTO_DOWN_WINDOW:]
        if len(recent) < AUTO_DOWN_WINDOW:
            return False
        down_p50 = statistics.median(recent)
        self.remembered[self.tier] = down_p50
        if self._last_change is not None and now - self._last_change < AUTO_PACE_S:
            return False
        index = AUTO_TIERS.index(self.tier)
        if down_p50 > self.target_ms and index + 1 < len(AUTO_TIERS):
            return self._change(AUTO_TIERS[index + 1], now)
        if index > 0 and len(self._times) >= AUTO_UP_WINDOW and statistics.median(self._times) < self.up_ms:
            better = AUTO_TIERS[index - 1]
            if self.remembered.get(better, 0.0) < self.target_ms:
                return self._change(better, now)
        return False

    def _change(self, tier: str, now: float) -> bool:
        self.tier = tier
        self._times.clear()
        self._last_change = now
        return True

    def reason(self) -> str:
        """The status line's note: below Hoch why Auto is not one tier higher (that tier's remembered p50,
        „Auto: 14 ms > 12 ms“); at Hoch the current p50 („Auto: 8 ms“); „Auto“ before a measurement."""
        if not self.available:
            return "Auto aus – Zeitmessung nicht verfügbar"
        index = AUTO_TIERS.index(self.tier)
        above = self.remembered.get(AUTO_TIERS[index - 1]) if index > 0 else None
        if above is not None and above > self.target_ms:
            return f"Auto: {above:.0f} ms > {self.target_ms:.0f} ms"
        p50 = self.p50
        if p50 is None:
            p50 = self.remembered.get(self.tier)
        if p50 is None:
            return "Auto"
        if p50 > self.target_ms:
            return f"Auto: {p50:.0f} ms > {self.target_ms:.0f} ms"
        return f"Auto: {p50:.0f} ms"


# -- the idle ceiling -----------------------------------------------------------------------------------------------

@dataclass
class IdleCeiling:
    """AD-040 §4.2: idle frames above `IDLE_CEILING_MS` (p50 over `IDLE_CEILING_FRAMES` frames) drop the next knob of
    `IDLE_DROPS`; the drops stay until the quality settings change or the room is entered again (`reset`)."""

    limit_ms: float = IDLE_CEILING_MS
    drops: tuple = ()
    last_p50: float | None = None
    _times: list = field(default_factory=list)

    def reset(self) -> None:
        self.drops, self.last_p50, self._times = (), None, []

    def feed(self, ms: float) -> bool:
        """One idle frame's GPU time. True = a knob was dropped."""
        self._times.append(float(ms))
        if len(self._times) < IDLE_CEILING_FRAMES:
            return False
        self.last_p50 = statistics.median(self._times)
        self._times = []
        if self.last_p50 > self.limit_ms and len(self.drops) < len(IDLE_DROPS):
            self.drops = IDLE_DROPS[:len(self.drops) + 1]
            return True
        return False

    def note(self) -> str:
        if not self.drops:
            return ""
        names = ", ".join(IDLE_DROP_LABELS[d] for d in self.drops)
        return f"ohne {names}: {self.last_p50:.0f} ms > {self.limit_ms:.0f} ms"


# -- the status line ------------------------------------------------------------------------------------------------

def status_line(state: str, tier: str, auto: AutoTier | None, refine: bool, idle_tier: str,
                ceiling: IdleCeiling | None = None) -> str:
    """AD-040 §8.1: „Interaktiv – Mittel (Auto: 14 ms > 12 ms)“, „Ruhe – Maximal“, „Ruhe – Hoch“."""
    if state in (REFINE, CONVERGED):
        name = TIER_LABELS[idle_tier if refine else tier]
        note = ceiling.note() if refine and ceiling is not None else ""
        return f"Ruhe – {name}" + (f" ({note})" if note else "")
    text = f"Interaktiv – {TIER_LABELS[tier]}"
    if auto is not None:
        text += f" ({auto.reason()})"
    return text


def held_back(config: RenderConfig, allowed: LookdevEffects, features=None, tier: str = "auto",
              refine: bool = False, idle_tier: str = "hoch") -> dict[str, str]:
    """AD-040 §8.1: per effect that is in force (allowed, its feature present) but not drawn by `config`, where the
    settings draw it - „aktiv in: Hoch, Maximal“, „in Ruhe“ (refinement on, only the idle tier has it) or „aktiv in:
    keiner Stufe“ (a dropped idle knob)."""
    base = effective(allowed, features)
    out: dict[str, str] = {}
    for name in LookdevEffects.names():
        if not getattr(base, name) or getattr(config.effects, name):
            continue
        tiers = [t for t in (AUTO_TIERS if tier == "auto" else (tier,))
                 if getattr(resolve(t, allowed, features, refine, INTERACTIVE, idle_tier).effects, name)]
        idle = refine and getattr(resolve(AUTO_TIERS[0], allowed, features, True, REFINE, idle_tier).effects, name)
        if idle and not tiers:
            out[name] = f"in Ruhe ({TIER_LABELS[idle_tier]})"
            continue
        labels = [TIER_LABELS[t] for t in tiers] + ([TIER_LABELS[idle_tier] + " (Ruhe)"] if idle else [])
        out[name] = f"aktiv in: {', '.join(labels)}" if labels else "aktiv in: keiner Stufe"
    return out


def config_fields() -> tuple[str, ...]:
    """`RenderConfig`'s field names (AD-040 G-5: render fields only)."""
    return tuple(f.name for f in fields(RenderConfig))
