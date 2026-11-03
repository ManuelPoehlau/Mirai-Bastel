"""GUI Stage 1 / Phase A1 - the read-only state display (HUD) of the Production window.

Stage 1 (2026-10-23) replaced the console-only status with an always-visible display; Phase A1 (2026-11-03,
docs/design/GUI_Bestandsaufnahme.md section 7, "Stufe 1b" in docs/design/GUI_STAGE1_HUD.md) re-weights it into a
compact status strip and adds two read-only viewport marks: the current bone's name and a permanent XYZ
orientation triad. Look, texts, layout and keys are `PROVISIONAL` (Discovery, M5).

Data path (one direction, Core -> Viewport -> window): `hud_state(app)` reads public `Application`
state into a frozen `HudState`; `hud_rows` turns it into text rows. The HUD owns no app state and no app
input; the only state here is its own (visible, strip position, detail, triad corner and size - session
variants, not saved). Key hints come from the binding layer (`BindingSet.inputs_for`), never from literals, so a
`keymap.json` rebinding shows up here.

Rows have a tier. Badges (posed + bound, invalid keymap) come first; the primary rows are the mode (Vertex /
Edge / Face / Object / Pose in one row, the morph editing view as a suffix), the tool or running gesture, and
every setting that is *not at its default* (Axis, Space, Pivot, Sym, Soft, SubD) plus the current morph target
and bone when they exist and, Phase A3 (2026-11-03, "Stufe 1c"), the weight view while it is on ("Weights · Jaw",
"Weights · — (no rig)"; the Soft entry then says its preview is hidden); the secondary rows (Display, View, Look,
Region, Targets, Rig, Fixed) show in the "full" detail. A key hint of a command `HudState.unavailable` lists (AD-027 section 3.3, `can_run` for source "ui")
is dimmed.

Change detection: `Hud.update` builds the snapshot every frame (a handful of attribute reads, no
mesh walk) and compares it with the one the drawables were built from; pyglet labels are rebuilt
only when it, the window size or a variant changed - orbit/zoom touch none of them. The triad and the bone tag are
not part of it: they reuse three lines / three labels / one label and only move them (`OrientationTriad`,
`BoneTag`), and only when their inputs changed.

Strip variants (open Artist question E4, switchable at runtime, window commands, not saved): position `bottom` /
`top`, detail `compact` / `full`. `H` is plain show / hide. The triad sits in a viewport corner (`bottom-left` /
`top-right`, two sizes) and keeps clear of the strip: `Hud.inset_top` / `inset_bottom` tell it how much room the
strip takes.

No pyglet import at module level (pattern `scene_menu.py` / `playground/hud.py`): the state logic is
headless-testable; drawing builds lazily and quietly does nothing without pyglet or a GL context.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from mirai.interaction import commands
from mirai.interaction.input import MORPH_CONTEXT, SUBD_CONTEXT, WINDOW_CONTEXT, BindingSet
from mirai.interaction.session import RunContext
from mirai.subdivision.preview import VIEW_CAGE, VIEW_ISO, VIEW_OFF, key_label
from mirai.symmetry_axis import current_axis

#: Strip variants (session switches, `HUD_POSITION_TOGGLE` / `HUD_DETAIL_TOGGLE`).
POSITIONS: tuple[str, ...] = ("bottom", "top")
DETAILS: tuple[str, ...] = ("compact", "full")
#: Triad variants (`TRIAD_CORNER_TOGGLE` / `TRIAD_SIZE_TOGGLE`): the corner and the axis length in pixels.
TRIAD_CORNERS: tuple[str, ...] = ("bottom-left", "top-right")
TRIAD_SIZES: dict[str, int] = {"S": 26, "M": 40}

LINE_HEIGHT = 18
PADDING = 6
GAP = 14
FONT_SIZE = 10

_BG = (18, 20, 26, 200)
_LABEL = (135, 145, 160, 255)
_VALUE = (225, 230, 240, 255)
#: A value that is "on" (constraint set, symmetry, soft, SubD, a running interaction, the current mode).
_ON = (255, 205, 110, 255)
_KEYS = (110, 150, 200, 255)
#: A key hint of a command `can_run` refuses right now.
_KEYS_DIM = (72, 82, 98, 255)
_STATUS = (240, 236, 200, 255)
#: Badges (posed + bound, invalid keymap): a warm warning on its own background.
_WARN = (255, 232, 205, 255)
_WARN_BG = (170, 70, 30, 235)

_MODE_NAMES = {"VERTEX": "Vertex", "EDGE": "Edge", "FACE": "Face", "OBJECT": "Object"}
#: The mode row: the four selection modes and pose mode (a controller state, AD-028 section 8.2), one row.
MODE_CHOICES: tuple[str, ...] = ("Vertex", "Edge", "Face", "Object", "Pose")
_TOOL_NAMES = {
    commands.MOVE: "Move",
    commands.ROTATE: "Rotate",
    commands.SCALE: "Scale",
    commands.EXTRUDE: "Extrude",
    commands.LOOP_SLIDE: "Loop Slide",
    commands.SMOOTH: "Smooth",
    commands.RELAX: "Relax",
    commands.INSET: "Inset",
    commands.BEVEL: "Bevel",
}
#: In pose mode W/E/R pose the current bone ("Bone · Rotate").
_POSE_TOOLS = (commands.MOVE, commands.ROTATE, commands.SCALE)
_SUBD_VIEWS = {VIEW_OFF: "off", VIEW_CAGE: "cage", VIEW_ISO: "isolines"}


@dataclass(frozen=True)
class HudState:
    """What the HUD shows, read from the app (immutable, compared as the change signature)."""

    mode: str
    tool: str
    #: The interaction that owns the keys right now ("Move", "Knife", ...), None = none.
    active: Optional[str]
    constraint: Optional[str]
    #: Transform orientation (WP Toolbox Gaps C1): "world" / "normal".
    space: str
    symmetry: Optional[str]
    display: str
    soft_on: bool
    soft_radius_percent: int
    soft_curve: str
    subd_view: str
    subd_level: int
    subd_lines: bool
    #: Polygroups: the active group (None = no group yet), its face count, how many groups, whether the colours show.
    region: Optional[str]
    region_faces: int
    region_count: int
    region_tint: bool
    group_mask: bool
    #: Worklight name and the active Look row with its value (AD-024 section 8).
    light: str
    look: str
    #: Morph target (AD-025 Phase 3): the current target's name · weight · base / editing view; None = no target.
    morph: Optional[str]
    #: AD-025 Phase 4: every target with its weight, the current one in brackets; None = fewer than two.
    morph_targets: Optional[str]
    status: str
    status_serial: int
    #: AD-013 addendum 2026-10-28: why `config/keymap.json` was not loaded (None = loaded, missing or not asked).
    keymap_problem: Optional[str] = None
    #: 2026-10-28 (Manu A1): the session's constraint lifetime, "one-shot" / "sticky".
    constraint_mode: str = "one-shot"
    #: Working Pivot (2026-10-28, `mirai.pivot`): "off" / "on" / "placing" / "off · placed" / "other object".
    pivot: str = "off"
    #: WP Ortho / Views (V-1/V-2): "Persp" / "Ortho" / "Front · Ortho" ... (`Application.view_text`).
    view: str = "Persp"
    #: AD-027 section 3.3: the hinted commands `Application.can_run` refuses right now (source "ui", no
    #: selection-dependent stage). Their key hints are dimmed (Phase A1, Engineering item 4).
    unavailable: frozenset = frozenset()
    #: AD-028 section 8.5: the rig - current bone · n bones · rest / posed · pose mode; None = no rig.
    rig: Optional[str] = None
    #: Phase A1: pose mode is on (the fifth mode of the mode row).
    pose_mode: bool = False
    #: Phase A1: the current bone's name (what `7` / `8` and the pose gestures act on), None = no bone.
    bone: Optional[str] = None
    #: Phase A1: some bone has a pose; and the edit mesh is bound, so position / topology edits are refused
    #: (AD-028 section 7.1) - the warning badge.
    posed: bool = False
    pose_locked: bool = False
    #: Phase A1: the target whose editing view is open (AD-025 section 15), the suffix of the mode; None = none.
    morph_view: Optional[str] = None
    #: Phase A3: the weight view - None = off; else the bone whose share is shown, or "— (<why>)" = nothing to show.
    weights: Optional[str] = None


def hud_state(app) -> HudState:
    """The snapshot (read-only: attribute and property reads, nothing is set or recomputed)."""
    soft = app.soft_settings
    curve = f"custom p={soft.curve_power:g}" if soft.curve == "custom" else soft.curve
    pose_mode = app.pose_mode
    tool = _TOOL_NAMES.get(app.tweak_command, app.tweak_command)
    if pose_mode:
        tool = f"Bone · {tool}"
    command = app.transform_command
    if app.knife_active:
        active = "Knife"
    elif app.resymmetrize_preview is not None:
        active = "Re-Symmetrize"
    elif command is not None:
        active = _TOOL_NAMES.get(command) or app.gesture_label or command
        if command == commands.LOOP_SLIDE and app.selection.mode.name == "VERTEX":
            active = "Vertex Slide"  # G in vertex mode (2026-10-29)
        if pose_mode and command in _POSE_TOOLS:
            active = f"Bone · {active}"
        elif app.tweak_running:  # W/E/R held: the gesture is called Tweak (Manu A2, 2026-10-28)
            active = f"Tweak · {active}"
    else:
        active = None
    subd = app.subdivision
    return HudState(
        mode=_MODE_NAMES.get(app.selection.mode.name, app.selection.mode.name.capitalize()),
        tool=tool,
        active=active,
        constraint=app.axis_constraint,
        space=app.transform_orientation,
        symmetry=current_axis(app.scene.mesh),
        display=app.display.label,
        soft_on=soft.enabled,
        soft_radius_percent=soft.radius_percent,
        soft_curve=curve,
        subd_view=subd.view,
        subd_level=subd.level,
        subd_lines=subd.lines_shown,
        region=app.active_region,
        region_faces=app.active_region_faces,
        region_count=app.region_count,
        region_tint=app.display.region_tint,
        group_mask=app.group_mask,
        light=app.display.light_label,
        look=app.look_text,
        morph=app.morph_status_text(),
        morph_targets=app.morph_targets_text(),
        status=app.status_message,
        status_serial=app.status_serial,
        keymap_problem=None if app.keymap_load is None else app.keymap_load.problem,
        constraint_mode=app.constraint_mode,
        pivot=_pivot_text(app),
        view=app.view_text,
        unavailable=_unavailable(app),
        rig=app.rig_status_text(),
        pose_mode=pose_mode,
        bone=app.current_bone_name,
        posed=app.posed,
        pose_locked=app.edit_mesh_posed_and_bound,
        morph_view=app.morph_editing_target_name,
        weights=app.weight_view_text,
    )


_UI = RunContext("ui", operands=False)


def _unavailable(app) -> frozenset:
    return frozenset(command for command in _HINTED_APP_COMMANDS if app.can_run(command, _UI) is not None)


def _pivot_text(app) -> str:
    if app.pivot_placing:
        return "placing"
    if app.active_pivot is not None:
        return "on"
    pivot = app.working_pivot
    if pivot is None:
        return "off"
    if pivot.object_id != app.scene.edit_object_id:
        return "other object"
    return "off · placed"


# -- key hints (binding layer) ------------------------------------------------------------------

#: Per HUD row: the commands whose first key is shown, and the binding context they resolve in.
_HINT_COMMANDS: dict[str, tuple[tuple[str, ...], Optional[str]]] = {
    "Mode": (
        (commands.SET_VERTEX_MODE, commands.SET_EDGE_MODE, commands.SET_FACE_MODE, commands.SET_OBJECT_MODE,
         commands.POSE_MODE),
        None,
    ),
    "Tool": ((commands.MOVE, commands.ROTATE, commands.SCALE), None),
    "Axis": (
        (commands.CONSTRAIN_AXIS_X, commands.CONSTRAIN_AXIS_Y, commands.CONSTRAIN_AXIS_Z, commands.CONSTRAINT_MODE_TOGGLE),
        None,
    ),
    "Space": ((commands.TOGGLE_TRANSFORM_SPACE,), None),
    "Pivot": ((commands.PIVOT_PLACE,), None),
    "Sym": ((commands.SYMMETRY_CYCLE, commands.RESYMMETRIZE, commands.SEAM_TO_PLANE), None),
    "Display": ((commands.CYCLE_DISPLAY_MODE, commands.TOGGLE_WIREFRAME_OVERLAY), None),
    "View": ((commands.TOGGLE_ORTHO,), None),
    "Soft": ((commands.SOFT_TOGGLE,), None),
    "SubD": ((commands.SUBD_CYCLE_VIEW,), SUBD_CONTEXT),
    "Region": ((commands.REGION_NEW, commands.REGION_NEXT, commands.REGION_NAME, commands.TOGGLE_REGION_TINT), None),
    "Look": (
        (commands.LOOK_ROW_PREV, commands.LOOK_ROW_NEXT, commands.LOOK_VALUE_DEC, commands.LOOK_VALUE_INC),
        None,
    ),
    "Morph": ((commands.MORPH_NEW, commands.MORPH_EDIT_TOGGLE, commands.MORPH_WEIGHT_DRAG), MORPH_CONTEXT),
    "Targets": ((commands.MORPH_NEXT, commands.MORPH_PREVIOUS), MORPH_CONTEXT),
    "Rig": (
        (commands.POSE_MODE, commands.POSE_TOGGLE_REST, commands.BONE_ADD, commands.WEIGHTS_FROM_GROUP,
         commands.WEIGHT_SET),
        None,
    ),
    "Bone": ((commands.BONE_NEXT, commands.WEIGHT_SET), None),
    "Weights": ((commands.WEIGHT_VIEW_TOGGLE,), None),
    "Rest": ((commands.POSE_TOGGLE_REST,), None),
    # Window commands (never an app command): the strip's own footer.
    "HUD": ((commands.TOGGLE_HUD,), WINDOW_CONTEXT),
    "Strip": ((commands.HUD_POSITION_TOGGLE,), WINDOW_CONTEXT),
    "Detail": ((commands.HUD_DETAIL_TOGGLE,), WINDOW_CONTEXT),
    "Triad": ((commands.TRIAD_CORNER_TOGGLE, commands.TRIAD_SIZE_TOGGLE), WINDOW_CONTEXT),
}


#: The hinted commands `Application` runs (the window's own rows are not app commands).
_HINTED_APP_COMMANDS: tuple[str, ...] = tuple(
    name for names, context in _HINT_COMMANDS.values() if context != WINDOW_CONTEXT for name in names
)

_ARROWS = {"UP": "↑", "DOWN": "↓", "LEFT": "←", "RIGHT": "→"}


def _first_key(bindings: BindingSet, name: str, context: Optional[str]) -> str:
    bound = [inp for inp in bindings.inputs_for(name, context) if inp.kind == "key"]
    if not bound:
        return ""
    label = key_label(bound[0])
    return _ARROWS.get(label, label)


def key_hint(bindings: BindingSet, command_names: tuple[str, ...], context: Optional[str] = None) -> str:
    """`1/2/3/4`, `W/E/R`, `Shift+S`: the simplest key bound to each command, joined; a command
    without a key is left out (a rebinding to the mouse or an unbind shows as a missing key)."""
    keys = (_first_key(bindings, name, context) for name in command_names)
    return "/".join(key for key in keys if key)


def key_hints(bindings: BindingSet) -> dict[str, str]:
    """All row hints at once; the bindings are fixed after the app start (no hot reload)."""
    return {row: key_hint(bindings, names, context) for row, (names, context) in _HINT_COMMANDS.items()}


def key_hint_parts(bindings: BindingSet) -> dict[str, tuple[tuple[str, str], ...]]:
    """The same hints as (key, command) pairs per row: the strip dims the keys of unavailable commands."""
    parts = {}
    for row, (names, context) in _HINT_COMMANDS.items():
        keys = ((_first_key(bindings, name, context), name) for name in names)
        parts[row] = tuple((key, name) for key, name in keys if key)
    return parts


# -- rows (pure text) ---------------------------------------------------------------------------

BADGE = "badge"
PRIMARY = "primary"
SECONDARY = "secondary"


@dataclass(frozen=True)
class HudRow:
    label: str
    value: str
    keys: str
    on: bool = False
    #: BADGE (warning, always shown), PRIMARY (the strip) or SECONDARY (only in the "full" detail).
    tier: str = PRIMARY
    #: A primary row whose value is its default: shown in the "full" detail only (the strip lists what deviates).
    quiet: bool = False
    #: The key hints as (text, dimmed) - dimmed = the command is in `HudState.unavailable`; () = only `keys`.
    key_parts: tuple[tuple[str, bool], ...] = ()
    #: The mode row: all choices, the chosen one is highlighted; `value` holds the chosen one and the suffix.
    choices: tuple[str, ...] = ()
    chosen: str = ""
    suffix: str = ""


def hud_rows(
    state: HudState, hints: dict[str, str], parts: Optional[dict[str, tuple[tuple[str, str], ...]]] = None
) -> list[HudRow]:
    """The state as display rows: badges first, then the mode and tool, the settings (quiet at their default),
    the current target / bone, then the secondary rows. `parts` (`key_hint_parts`) lets the key hints dim."""

    def row(label: str, value: str, on: bool = False, tier: str = PRIMARY, quiet: bool = False, **extra) -> HudRow:
        key_parts = tuple((key, command in state.unavailable) for key, command in (parts or {}).get(label, ()))
        return HudRow(label, value, hints.get(label, ""), on, tier, quiet, key_parts, **extra)

    tool = state.tool if state.active is None else f"{state.active} (running)"
    axis = state.constraint.upper() if state.constraint else "free"
    if state.constraint and len(state.constraint) == 2:
        axis += " plane"
    axis += f" · {state.constraint_mode}"
    soft = (
        f"on · {state.soft_radius_percent} % · {state.soft_curve}" if state.soft_on else "off"
    )
    if state.soft_on and state.weights is not None:
        soft += " · preview hidden (weights view)"  # Phase A3: the weight view owns the display
    if state.subd_view == VIEW_OFF:
        subd = "off"
    else:
        subd = f"{_SUBD_VIEWS.get(state.subd_view, state.subd_view)} · L{state.subd_level}"
        if not state.subd_lines:
            subd += " · lines hidden"
    chosen = "Pose" if state.pose_mode else state.mode
    suffix = f"target {state.morph_view!r}" if state.morph_view is not None else ""
    rows: list[HudRow] = []
    if state.pose_locked:  # posed and bound: the refusal is announced before it happens (AD-028 section 7.1)
        rest_key = hints.get("Rest", "")
        rows.append(HudRow("Pose", f"Pose · {rest_key} = rest" if rest_key else "Pose · mesh posed and bound",
                           "", True, BADGE))
    if state.keymap_problem is not None:  # loud and lasting, unlike the status line
        rows.append(HudRow("Keymap", "Keymap invalid · defaults active - see console", "", True, BADGE))
    rows += [
        row("Mode", chosen + (f" · {suffix}" if suffix else ""), True, choices=MODE_CHOICES, chosen=chosen,
            suffix=suffix),
        row("Tool", tool, on=state.active is not None),
        row("Axis", axis, on=state.constraint is not None,
            quiet=state.constraint is None and state.constraint_mode == "one-shot"),
        row("Space", state.space.capitalize(), on=state.space != "world", quiet=state.space == "world"),
        row("Pivot", state.pivot, on=state.pivot in ("on", "placing"), quiet=state.pivot == "off"),
        row("Sym", state.symmetry.upper() if state.symmetry else "off", on=state.symmetry is not None,
            quiet=state.symmetry is None),
        row("Soft", soft, on=state.soft_on, quiet=not state.soft_on),
        row("SubD", subd, on=state.subd_view != VIEW_OFF, quiet=state.subd_view == VIEW_OFF),
    ]
    if state.morph is not None:  # only a mesh with a morph target gets the row (AD-025 Phase 3)
        rows.append(row("Morph", state.morph, on=True))
    if state.bone is not None:  # only a scene with a rig and a bone: the one 7 / 8 and the pose gestures act on
        rows.append(row("Bone", f"{state.bone!r} · {'posed' if state.posed else 'rest'}",
                        on=state.pose_mode or state.posed))
    rows.append(row("Weights", state.weights if state.weights is not None else "off",
                    on=state.weights is not None and not state.weights.startswith("—"), quiet=state.weights is None))
    rows += [
        row("Display", state.display, tier=SECONDARY),
        row("View", state.view, on=state.view != "Persp", tier=SECONDARY),
        row(
            "Region",
            (
                f"{state.region} · {state.region_faces} faces · {state.region_count} "
                f"group{'s' if state.region_count != 1 else ''} · colours {'on' if state.region_tint else 'off'}"
                if state.region is not None
                else f"no groups · colours {'on' if state.region_tint else 'off'}"
            ) + (" · group mask on" if state.group_mask else ""),
            on=state.region_faces > 0,
            tier=SECONDARY,
        ),
        row("Look", f"{state.light} · {state.look}", tier=SECONDARY),
    ]
    if state.morph_targets is not None:  # several targets (AD-025 Phase 4)
        rows.append(row("Targets", state.morph_targets, on=True, tier=SECONDARY))
    if state.rig is not None:  # only a scene with a rig gets the row (AD-028 section 8.5)
        rig_parts = state.rig.split(" · ")
        rows.append(row("Rig", state.rig, on="posed" in rig_parts or "pose mode" in rig_parts, tier=SECONDARY))
    # AD-013 addendum 2026-10-28: the modifier grammar is no binding; it is listed read-only.
    rows.append(HudRow("Fixed", FIXED_ROW, "", tier=SECONDARY))
    return rows


def strip_rows(rows: list[HudRow], detail: str) -> list[HudRow]:
    """What the strip shows: the badges and the primary rows that deviate; "full" adds everything else."""
    if detail == "full":
        return list(rows)
    return [r for r in rows if r.tier == BADGE or (r.tier == PRIMARY and not r.quiet)]


#: The "Fixed" row: `bindings.FIXED_MODIFIER_RULES` in short (the full sentences are printed at start).
FIXED_ROW = "Shift fine / view snap · Ctrl snap · Alt orbit / through"


def footer_hint(hints: dict[str, str], detail: str) -> str:
    """The strip's own key hints (from the bindings): the last segment of the strip."""
    pairs = (
        [("Detail", "more"), ("HUD", "HUD")]
        if detail == "compact"
        else [("Strip", "strip top/bottom"), ("Detail", "less"), ("Triad", "triad corner/size"), ("HUD", "HUD")]
    )
    return " · ".join(f"{hints[key]}: {text}" for key, text in pairs if hints.get(key))


# -- the HUD ------------------------------------------------------------------------------------


class Hud:
    """Visibility, strip variants, change detection and the (lazy) pyglet drawing."""

    def __init__(
        self, bindings: BindingSet, position: str = POSITIONS[0], detail: str = DETAILS[0], visible: bool = True
    ) -> None:
        _check(position, POSITIONS, "position")
        _check(detail, DETAILS, "detail")
        self.hints = key_hints(bindings)
        self.hint_parts = key_hint_parts(bindings)
        self._position = position
        self._detail = detail
        self._visible = bool(visible)
        self._state: Optional[HudState] = None
        self._size: tuple[int, int] = (0, 0)
        #: What the drawables were built from (state, variants, size); None = not built.
        self._built_key: Optional[tuple] = None
        #: How tall the built strip is (0 = nothing drawn): the room the triad keeps clear.
        self._strip_height = 0
        self.rebuilds = 0
        #: Builds the drawables (a test swaps in a GL-free stand-in to check the layouts).
        self.make_builder = _Builder
        # Lazy pyglet objects.
        self._batch = None
        self._drawables: list = []

    @property
    def visible(self) -> bool:
        return self._visible

    @property
    def position(self) -> str:
        return self._position

    @property
    def detail(self) -> str:
        return self._detail

    @property
    def state(self) -> Optional[HudState]:
        """The last snapshot `update` took (None before the first visible update)."""
        return self._state

    def toggle(self) -> bool:
        """`H`: show / hide. Returns whether the strip is shown now."""
        self._visible = not self._visible
        return self._visible

    def toggle_position(self) -> str:
        """Session variant: the strip at the bottom <-> the top of the window."""
        self._position = POSITIONS[(POSITIONS.index(self._position) + 1) % len(POSITIONS)]
        return self._position

    def toggle_detail(self) -> str:
        """Session variant: compact (what deviates) <-> full (every row)."""
        self._detail = DETAILS[(DETAILS.index(self._detail) + 1) % len(DETAILS)]
        return self._detail

    @property
    def inset_top(self) -> int:
        """Pixels the strip covers at the top of the window (0 = hidden or at the bottom)."""
        return self._strip_height if self._visible and self._position == "top" else 0

    @property
    def inset_bottom(self) -> int:
        return self._strip_height if self._visible and self._position == "bottom" else 0

    @property
    def needs_rebuild(self) -> bool:
        return self._visible and self._state is not None and self._key() != self._built_key

    def update(self, app, width: int, height: int) -> bool:
        """Takes the snapshot (only while visible). True = the drawables must be rebuilt."""
        if not self._visible:
            return False
        self._state = hud_state(app)
        self._size = (int(width), int(height))
        return self.needs_rebuild

    def _key(self) -> tuple:
        return (self._state, self._position, self._detail, self._size)

    # -- drawing ------------------------------------------------------------------------------

    def draw(self) -> None:
        """Over the viewport (depth off, blending on, like the scene menu); rebuilds the labels only
        when `update` saw a change."""
        if not self._visible or self._state is None:
            return
        if self.needs_rebuild:
            self._rebuild()
        if self._batch is None:
            return
        from pyglet import gl

        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        self._batch.draw()

    def _rebuild(self) -> None:
        self._built_key = self._key()
        self.rebuilds += 1
        for item in self._drawables:
            item.delete()
        self._drawables = []
        self._batch = None
        self._strip_height = 0
        try:
            builder = self.make_builder(self._drawables)
            self._batch = builder.batch
            rows = strip_rows(hud_rows(self._state, self.hints, self.hint_parts), self._detail)
            self._strip_height = _layout_strip(
                builder, rows, self._state.status, footer_hint(self.hints, self._detail), self._position,
                *self._size,
            )
        except Exception:
            # No pyglet / no GL context: the app runs on without a HUD (console status stays).
            self._batch = None
            self._drawables = []
            self._strip_height = 0


def _check(value: str, allowed: tuple[str, ...], what: str) -> None:
    if value not in allowed:
        raise ValueError(f"Unknown HUD {what} {value!r}; expected one of {allowed}.")


class _Builder:
    """Labels and background rectangles in one batch (strip background first, badges over it, text on top)."""

    def __init__(self, sink: list) -> None:
        from pyglet import graphics

        self.batch = graphics.Batch()
        self.sink = sink
        self.back = graphics.Group(order=0)
        self.mid = graphics.Group(order=1)
        self.front = graphics.Group(order=2)

    def label(self, text: str, x: float, y: float, color) -> object:
        from pyglet import text as _text

        label = _text.Label(
            text, x=x, y=y, anchor_x="left", anchor_y="baseline", font_size=FONT_SIZE,
            color=color, batch=self.batch, group=self.front,
        )
        self.sink.append(label)
        return label

    def rect(self, x: float, y: float, width: float, height: float, color=_BG, badge: bool = False) -> None:
        from pyglet import shapes

        group = self.mid if badge else self.back
        self.sink.append(shapes.Rectangle(x, y, width, height, color=color, batch=self.batch, group=group))


def _key_runs(row: HudRow) -> list[tuple[str, bool]]:
    """The row's key hint as runs of equal availability: `[1/2/3/4/` bright, `5]` dim."""
    if not row.keys:
        return []
    if not row.key_parts:
        return [(f"[{row.keys}]", False)]
    runs: list[list] = []
    for key, dim in row.key_parts:
        if runs and runs[-1][1] == dim:
            runs[-1][0] += f"/{key}"
        else:
            runs.append([key, dim])
    texts = [[text, dim] for text, dim in runs]
    for index, entry in enumerate(texts):
        if index < len(texts) - 1:
            entry[0] += "/"
    texts[0][0] = "[" + texts[0][0]
    texts[-1][0] += "]"
    return [(text, dim) for text, dim in texts]


#: Space after a label inside a segment, and between the modes of the mode row.
_ITEM_GAP = 4
_CHOICE_GAP = 9


def _segment(b: _Builder, row: HudRow) -> list[tuple[object, int]]:
    """The labels of one strip segment, in drawing order, each with the gap to the next one."""
    if row.tier == BADGE:
        return [(b.label(row.value, 0, 0, _WARN), 0)]
    items: list[tuple[object, int]] = []
    if row.choices:  # the mode row: the label, every mode (the chosen one lit), the suffix
        items.append((b.label(row.label, 0, 0, _LABEL), _ITEM_GAP))
        items += [(b.label(choice, 0, 0, _ON if choice == row.chosen else _LABEL), _CHOICE_GAP)
                  for choice in row.choices]
        if row.suffix:
            items.append((b.label(f"· {row.suffix}", 0, 0, _ON), _ITEM_GAP))
    else:
        items += [(b.label(row.label, 0, 0, _LABEL), _ITEM_GAP),
                  (b.label(row.value, 0, 0, _ON if row.on else _VALUE), _ITEM_GAP)]
    items += [(b.label(text, 0, 0, _KEYS_DIM if dim else _KEYS), _ITEM_GAP) for text, dim in _key_runs(row)]
    items[-1] = (items[-1][0], 0)
    return items


def _layout_strip(
    b: _Builder, rows: list[HudRow], status: str, footer: str, position: str, width: int, height: int
) -> int:
    """The status strip: full width at the bottom or top of the window; the rows as segments (wrapped onto more
    lines when the window is too narrow), the status message on the last line, the strip's own key hints right
    of it when they fit there, else as the last segment. Returns the strip's height in pixels."""
    segments = [(row.tier, _segment(b, row)) for row in rows]
    status_label = b.label(status, PADDING, 0, _STATUS)
    footer_label = b.label(footer, 0, 0, _KEYS) if footer else None
    footer_beside_status = (
        footer_label is not None
        and PADDING + status_label.content_width + 2 * GAP + footer_label.content_width <= width - PADDING
    )
    if footer_label is not None and not footer_beside_status:
        segments.append((PRIMARY, [(footer_label, 0)]))
    lines: list[list] = [[]]
    x = PADDING
    for tier, parts in segments:
        seg_width = sum(item.content_width + gap for item, gap in parts)
        if lines[-1] and x + seg_width > width - PADDING:
            lines.append([])
            x = PADDING
        lines[-1].append((x, tier, parts, seg_width))
        x += seg_width + GAP
    strip_height = (len(lines) + 1) * LINE_HEIGHT + 2 * PADDING
    origin = height - strip_height if position == "top" else 0
    b.rect(0, origin, width, strip_height)
    for index, line in enumerate(lines):
        base = origin + strip_height - PADDING - (index + 1) * LINE_HEIGHT + 5
        for x, tier, parts, seg_width in line:
            if tier == BADGE:
                b.rect(x - 4, base - 4, seg_width + 8, LINE_HEIGHT - 2, color=_WARN_BG, badge=True)
            cursor = x
            for item, gap in parts:
                item.x, item.y = cursor, base
                cursor += item.content_width + gap
    base_status = origin + PADDING + 5
    status_label.y = base_status
    if footer_beside_status:
        footer_label.x, footer_label.y = width - PADDING - footer_label.content_width, base_status
    return strip_height


# -- viewport marks: the orientation triad and the current bone's name -----------------------------------------
#
# Both are read-only overlays in window pixels, drawn after the strip. They own a few pyglet objects that are
# created once and only moved (never rebuilt per frame); `moves` counts the frames that actually changed them.

TRIAD_MARGIN = 14
#: Room for the axis letters beyond the axis tip.
TRIAD_LABEL_ROOM = 14
#: An axis seen end-on (shorter than this fraction of its length on screen) puts its letter next to the centre.
TRIAD_END_ON = 0.2
TRIAD_THICKNESS = 2
_TRIAD_NEAR_ALPHA = 255
_TRIAD_FAR_ALPHA = 140
_WORLD_AXES = (("X", (1.0, 0.0, 0.0)), ("Y", (0.0, 1.0, 0.0)), ("Z", (0.0, 0.0, 1.0)))


def _axis_rgb(name: str) -> tuple[int, int, int]:
    """The axis colours of the transform gizmo (`viewport.gizmo.COLOR_X/Y/Z`), as bytes."""
    from mirai.viewport import gizmo

    colour = {"X": gizmo.COLOR_X, "Y": gizmo.COLOR_Y, "Z": gizmo.COLOR_Z}[name]
    return tuple(int(round(c * 255)) for c in colour[:3])


def triad_axes(camera) -> list[tuple[str, float, float, float]]:
    """(name, right, up, depth) per world axis: its unit vector in the camera's frame - `right` and `up` are the
    screen components (the view rotation only, no perspective), `depth` > 0 points away from the viewer. Front
    ortho (yaw 0, pitch 0): X = (1, 0), Y = (0, 1), Z = (0, 0) pointing at the viewer."""
    forward, right, up = camera.basis()

    def dot(a, b):
        return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

    return [(name, dot(axis, right), dot(axis, up), dot(axis, forward)) for name, axis in _WORLD_AXES]


def triad_center(
    corner: str, length: int, width: int, height: int, inset_top: int = 0, inset_bottom: int = 0
) -> tuple[float, float]:
    """The triad's centre in window pixels: in its corner, clear of the strip (`Hud.inset_top` / `inset_bottom`)."""
    reach = length + TRIAD_LABEL_ROOM
    if corner == "top-right":
        return width - TRIAD_MARGIN - reach, height - inset_top - TRIAD_MARGIN - reach
    return TRIAD_MARGIN + reach, inset_bottom + TRIAD_MARGIN + reach


def triad_label_offset(right: float, up: float, length: int) -> tuple[float, float]:
    """Where an axis letter sits relative to the centre: just past the tip, or beside the centre for an axis
    that points at / away from the viewer."""
    size = math.hypot(right, up)
    if size < TRIAD_END_ON:
        return 9.0, 9.0
    return right * length + right / size * 9.0, up * length + up / size * 9.0


class _TriadParts:
    """Three line shapes and three labels in one batch, created once."""

    def __init__(self) -> None:
        from pyglet import graphics, shapes, text

        self.batch = graphics.Batch()
        self.lines = [
            shapes.Line(0, 0, 0, 0, thickness=TRIAD_THICKNESS, color=(*_axis_rgb(name), 255), batch=self.batch)
            for name, _ in _WORLD_AXES
        ]
        self.labels = [
            text.Label(name, x=0, y=0, anchor_x="center", anchor_y="center", font_size=FONT_SIZE + 1,
                       color=(*_axis_rgb(name), 255), batch=self.batch)
            for name, _ in _WORLD_AXES
        ]

    def draw(self) -> None:
        from pyglet import gl

        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        self.batch.draw()


class OrientationTriad:
    """The permanent XYZ orientation triad (Phase A1, E8): the world axes turned by the camera's view rotation,
    small, in a fixed viewport corner, always drawn (gestures, pose mode, snapped ortho views), not clickable.
    Session variants: corner (`bottom-left` / `top-right`) and size (`S` / `M`). Per frame: nothing when the
    camera, window, strip and variants are unchanged, else three lines and three labels are moved."""

    def __init__(self, corner: str = TRIAD_CORNERS[0], size: str = "M", visible: bool = True) -> None:
        _check(corner, TRIAD_CORNERS, "triad corner")
        if size not in TRIAD_SIZES:
            raise ValueError(f"Unknown triad size {size!r}; expected one of {tuple(TRIAD_SIZES)}.")
        self._corner = corner
        self._size = size
        self.visible = bool(visible)
        self.moves = 0
        #: Creates the drawables (a test swaps in a GL-free stand-in).
        self.make_parts = _TriadParts
        self._parts = None
        self._failed = False
        self._key: Optional[tuple] = None
        self._alpha: Optional[tuple] = None
        self._anchor: Optional[tuple] = None
        #: The last placement (name, tip, letter) in window pixels - for tests and the layout check.
        self.placement: list[tuple[str, tuple[float, float], tuple[float, float]]] = []

    @property
    def corner(self) -> str:
        return self._corner

    @property
    def size(self) -> str:
        return self._size

    @property
    def length(self) -> int:
        return TRIAD_SIZES[self._size]

    def toggle_corner(self) -> str:
        self._corner = TRIAD_CORNERS[(TRIAD_CORNERS.index(self._corner) + 1) % len(TRIAD_CORNERS)]
        return self._corner

    def toggle_size(self) -> str:
        sizes = tuple(TRIAD_SIZES)
        self._size = sizes[(sizes.index(self._size) + 1) % len(sizes)]
        return self._size

    def update(self, camera, width: int, height: int, inset_top: int = 0, inset_bottom: int = 0) -> bool:
        """Moves the drawables to the camera's current view. True = something was moved."""
        key = (camera.yaw, camera.pitch, self._corner, self._size, int(width), int(height), inset_top, inset_bottom)
        if key == self._key:
            return False
        self._key = key
        length = self.length
        cx, cy = triad_center(self._corner, length, int(width), int(height), inset_top, inset_bottom)
        axes = triad_axes(camera)
        self.placement = []
        for name, right, up, _ in axes:
            dx, dy = triad_label_offset(right, up, length)
            self.placement.append((name, (cx + right * length, cy + up * length), (cx + dx, cy + dy)))
        parts = self._ensure_parts()
        if parts is None:
            return False
        self.moves += 1
        alpha = tuple(_TRIAD_FAR_ALPHA if depth > 0.05 else _TRIAD_NEAR_ALPHA for _, _, _, depth in axes)
        if self._anchor != (cx, cy):
            self._anchor = (cx, cy)
            for line in parts.lines:
                line.position = (cx, cy)
        for line, label, (_, tip, letter) in zip(parts.lines, parts.labels, self.placement):
            line.x2, line.y2 = tip
            label.x, label.y = letter
        if alpha != self._alpha:
            self._alpha = alpha
            for line, label, a in zip(parts.lines, parts.labels, alpha):
                line.opacity = a
                label.opacity = a
        return True

    def _ensure_parts(self):
        if self._parts is None and not self._failed:
            try:
                self._parts = self.make_parts()
            except Exception:
                self._failed = True  # no pyglet / no GL context: the app runs on without a triad
        return self._parts

    def draw(self, camera, width: int, height: int, inset_top: int = 0, inset_bottom: int = 0) -> None:
        if not self.visible:
            return
        self.update(camera, width, height, inset_top, inset_bottom)
        if self._parts is not None:
            self._parts.draw()


#: The current bone's colour (`controllers.skeleton.COLOR_BONE_CURRENT`, orange) as bytes.
_BONE_RGB = (255, 170, 60)
_BONE_TAG_OFFSET = (10.0, 8.0)


class _TagParts:
    """One label on a dark plate, created once."""

    def __init__(self) -> None:
        from pyglet import graphics, shapes, text

        self.batch = graphics.Batch()
        back, front = graphics.Group(order=0), graphics.Group(order=1)
        self.plate = shapes.Rectangle(0, 0, 10, LINE_HEIGHT - 2, color=_BG, batch=self.batch, group=back)
        self.label = text.Label("", x=0, y=0, anchor_x="left", anchor_y="center", font_size=FONT_SIZE,
                                color=(*_BONE_RGB, 255), batch=self.batch, group=front)

    def draw(self) -> None:
        from pyglet import gl

        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        self.batch.draw()


class BoneTag:
    """The current bone's name at its posed head (Phase A1, item 5), in pose mode and in the component modes while
    a rig exists - the answer to "on which bone does `8` write". One label and its plate, reused and moved."""

    def __init__(self) -> None:
        self.moves = 0
        self.text_sets = 0
        self.make_parts = _TagParts
        self._parts = None
        self._failed = False
        self._shown = False
        self._name: Optional[str] = None
        self._at: Optional[tuple[float, float]] = None
        #: The last screen position of the name (None = hidden) - for tests.
        self.position: Optional[tuple[float, float]] = None

    @property
    def shown(self) -> bool:
        return self._shown

    @property
    def name(self) -> Optional[str]:
        return self._name

    def update(self, tag, camera, width: int, height: int) -> bool:
        """`tag` = `Application.current_bone_tag()`. True = the drawables changed."""
        point = None
        if tag is not None:
            screen = camera.project_to_screen(tag[1], int(width), int(height))
            if screen is not None and 0 <= screen[0] <= width and 0 <= screen[1] <= height:
                point = (screen[0] + _BONE_TAG_OFFSET[0], screen[1] + _BONE_TAG_OFFSET[1])
        self.position = point
        if point is None:
            changed = self._shown
            self._shown = False
            return changed
        parts = self._ensure_parts()
        if parts is None:
            return False
        name = tag[0]
        changed = not self._shown
        self._shown = True
        if name != self._name:
            self._name = name
            parts.label.text = name
            parts.plate.width = parts.label.content_width + 8
            self.text_sets += 1
            changed = True
        if self._at is None or abs(point[0] - self._at[0]) >= 0.5 or abs(point[1] - self._at[1]) >= 0.5:
            self._at = point
            parts.label.x, parts.label.y = point[0] + 4, point[1]
            parts.plate.position = (point[0], point[1] - (LINE_HEIGHT - 2) / 2)
            changed = True
        if changed:
            self.moves += 1
        return changed

    def _ensure_parts(self):
        if self._parts is None and not self._failed:
            try:
                self._parts = self.make_parts()
            except Exception:
                self._failed = True
        return self._parts

    def draw(self, tag, camera, width: int, height: int) -> None:
        self.update(tag, camera, width, height)
        if self._shown and self._parts is not None:
            self._parts.draw()
