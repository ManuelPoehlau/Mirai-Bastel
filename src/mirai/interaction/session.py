"""The interaction slot (AD-027 §3.2): one running session, the held keys beside it, one routing rule.

A **session** is an interaction that runs over several events and owns some input while it runs (the
Re-Symmetrize preview, later the Knife, a held W/E/R, a drag selection). At most one runs. A **hold
key** is a held key that changes what the pointer does (Working Pivot, Lasso, Light, Morph weight);
several may be held and a session may start while one is held. Modes (component mode, object mode, a
morph target's editing view) are not sessions: `can_run` reads them, they own no input.

Precedence is fixed by kind, not by start order (AD-027 §1.1, V1-V7), and lives only in
`InteractionSlot.route`:

1. **grab** - a session that `grabs(event)` decides the event alone;
2. **hold claims**, in rank order;
3. **session** - `session.handle(event)`;
4. **hold background**, in rank order;
5. **idle** - whatever the caller does when everything answered `PASS`.

A key press takes the command path after the grab: the caller resolves it through the `BindingSet` and
asks `can_run(command, RunContext(...))`, whose stages include the running session's `allows`.

The slot knows no window, no panel and no `Application` (it imports nothing from `mirai.application`):
a UI hit-test may sit in front of the caller's pointer entries (AD-027 §3.5, C2). No session assumes it
sees every pointer event - only every event of a press it took.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, Union

from . import commands
from .input import Input


class _Pass:
    """`PASS`: "not mine" - routing continues with the next stage."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "PASS"

    def __bool__(self) -> bool:
        raise TypeError("PASS has no truth value: compare with `is PASS`")


PASS = _Pass()

#: What `handle`, `claims`, `background`, `grab` and `route` return: the event's outcome, or `PASS`.
Outcome = Union[bool, _Pass]


@dataclass(frozen=True)
class Refusal:
    """Why a command may not run now. `text` None = silent (no status line)."""

    text: Optional[str] = None


#: A refusal without a status line.
SILENT = Refusal(None)


@dataclass(frozen=True)
class RunContext:
    """Where a command comes from (AD-027 §3.3). `source`: "key" | "click" | "drag" | "wheel" | "ui" |
    "api". `operands` False skips the selection-dependent stage (the HUD asks every frame)."""

    source: str
    input: Optional[Input] = None
    operands: bool = True


# -- events (small, frozen) ----------------------------------------------------------------------


@dataclass(frozen=True)
class KeyPress:
    input: Input


@dataclass(frozen=True)
class KeyRelease:
    input: Input


@dataclass(frozen=True)
class Press:
    """A mouse button went down at (x, y); the pointer resolver (AD-019) has not decided click / drag."""

    input: Input
    x: Optional[float]
    y: Optional[float]


@dataclass(frozen=True)
class Drag:
    """One drag step the pointer resolver produced (`command` = its resolved drag command)."""

    command: str
    dx: float
    dy: float


@dataclass(frozen=True)
class Release:
    """A mouse button went up; `click` = the click command the resolver produced, None = no click."""

    button: str
    x: float
    y: float
    click: Optional[str] = None


@dataclass(frozen=True)
class Motion:
    x: float
    y: float
    dx: float = 0.0
    dy: float = 0.0


@dataclass(frozen=True)
class Wheel:
    input: Input
    command: Optional[str]


@dataclass(frozen=True)
class Modifiers:
    """Shift / Ctrl / Alt held changed (the window's report)."""

    shift: bool
    ctrl: bool
    alt: bool


@dataclass(frozen=True)
class Hover:
    """A re-pick of the hover at the cursor."""

    x: float
    y: float


@dataclass(frozen=True)
class Leave:
    """The cursor left the window."""


@dataclass(frozen=True)
class Command:
    """A command that concerns the running session (Cancel, Undo while only armed, a constraint key)."""

    command: str
    context: RunContext


Event = Union[KeyPress, KeyRelease, Press, Drag, Release, Motion, Wheel, Modifiers, Hover, Leave, Command]


# -- protocols --------------------------------------------------------------------------------------


class Session(Protocol):
    #: The AD-013 H2 `interaction_owner` value ("transform" | "knife" | "resymmetrize"); None for the
    #: pointer-only sessions.
    owner: Optional[str]
    #: What the HUD shows as running ("Move", "Knife", ...).
    label: Optional[str]
    #: True for a session that grabs input (keys among it: the Knife, the Re-Symmetrize preview): its `allows`
    #: alone answers `can_run` (stage 1). False: its `allows` is stage 6, after the host and mode gates.
    exclusive: bool

    def grabs(self, event: Event) -> bool:
        """True = this event is the session's alone, before hold keys and gates."""

    def allows(self, command: str, ctx: RunContext) -> Optional[Refusal]:
        """May `command` run underneath this session (a stage of `can_run`)? Pure."""

    def handle(self, event: Event) -> Outcome:
        """Key, pointer, modifier, hover and command events."""

    def cancel(self) -> bool:
        """Esc, shutdown: the exact prior state, no history entry."""

    def commit(self) -> bool:
        """The normal end: at most one history entry."""


class HoldKey(Protocol):
    command: str
    key: str

    def claims(self, event: Event) -> Outcome:
        """Before the session (Pivot: LMB press / drag / release, Cancel, hover)."""

    def background(self, event: Event) -> Outcome:
        """After the session (Light, Morph weight: motion)."""

    def release(self) -> bool:
        """Its key went up."""


# -- the slot ---------------------------------------------------------------------------------------


class InteractionSlot:
    """One running session and the held keys in their fixed rank (`HOLD_RANK`)."""

    #: Hold keys by command, in the order they see an event (AD-027 §3.2: Pivot, Lasso, Light, Morph weight).
    HOLD_RANK: tuple[str, ...] = (
        commands.PIVOT_PLACE, commands.LASSO_ARM, commands.LIGHT_DRAG, commands.MORPH_WEIGHT_DRAG,
    )

    def __init__(self) -> None:
        self.session: Optional[Session] = None
        self._holds: dict[str, HoldKey] = {}

    @property
    def owner(self) -> Optional[str]:
        """The running session's `interaction_owner` value (None = none, or a pointer-only session)."""
        return None if self.session is None else self.session.owner

    @property
    def holds(self) -> tuple[HoldKey, ...]:
        return tuple(self._holds[c] for c in self.HOLD_RANK if c in self._holds)

    def start(self, session: Session) -> None:
        assert self.session is None, f"slot busy: {self.session!r}"
        self.session = session

    def end(self, session: Session) -> None:
        assert self.session is session, f"{session!r} is not the running session"
        self.session = None

    def hold(self, hold: HoldKey) -> None:
        assert hold.command in self.HOLD_RANK, hold.command
        self._holds[hold.command] = hold

    def unhold(self, hold: HoldKey) -> None:
        if self._holds.get(hold.command) is hold:
            del self._holds[hold.command]

    def grab(self, event: Event) -> Outcome:
        """Stage 1 only (the key path continues with `can_run`)."""
        session = self.session
        if session is not None and session.grabs(event):
            return session.handle(event)
        return PASS

    def route(self, event: Event) -> Outcome:
        """Stages 1-4; `PASS` = idle (stage 5 is the caller's)."""
        outcome = self.grab(event)
        if outcome is not PASS:
            return outcome
        holds = self.holds
        for hold in holds:
            outcome = hold.claims(event)
            if outcome is not PASS:
                return outcome
        session = self.session
        if session is not None:
            outcome = session.handle(event)
            if outcome is not PASS:
                return outcome
        for hold in holds:
            outcome = hold.background(event)
            if outcome is not PASS:
                return outcome
        return PASS

    def allows(self, command: str, ctx: RunContext) -> Optional[Refusal]:
        """The running session's `allows` (None without a session)."""
        session = self.session
        return None if session is None else session.allows(command, ctx)
