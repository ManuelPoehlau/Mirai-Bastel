"""GUI Stage 1 — the read-only state display (HUD) of the Production window (2026-10-23).

Handoff "GUI Stufe 1 — Zustandsanzeige (read-only HUD)": replaces the console-only status
(`main.run`, kept there as a fallback) with an always-visible display of the app state - selection
mode, current tool, axis/plane constraint, symmetry, display mode, Soft Selection, SubD preview and
the last status message. Look, texts and both layouts are `PROVISIONAL` (Discovery, M5).

Data path (one direction, Core -> Viewport -> window): `hud_state(app)` reads public `Application`
state into a frozen `HudState`; `hud_rows` turns it into text. The HUD owns no app state and no app
input; the only state here is its own (visible, layout variant). Key hints come from the binding
layer (`BindingSet.inputs_for`), never from literals, so a `keymap.json` rebinding shows up here.

Change detection: `Hud.update` builds the snapshot every frame (a handful of attribute reads, no
mesh walk) and compares it with the one the drawables were built from; pyglet labels are rebuilt
only when it, the window size or the layout changed - orbit/zoom touch none of them.

Layout variants (open Artist question, switchable at runtime):
- `bar`    - variant A: a bottom bar, state segments on one line (two if narrow), the status below.
- `corner` - variant B: a panel in the top-left viewport corner, one row per item, status under it.
`H` (Input Truth `application.toggle_hud`, binding context `window`) steps bar -> corner -> hidden
-> bar while both variants are on trial; after Manu's verdict it becomes a plain show/hide.

No pyglet import at module level (pattern `scene_menu.py` / `playground/hud.py`): the state logic is
headless-testable; drawing builds lazily and quietly does nothing without pyglet or a GL context.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from mirai.interaction import commands
from mirai.interaction.input import SUBD_CONTEXT, WINDOW_CONTEXT, BindingSet
from mirai.subdivision.preview import VIEW_CAGE, VIEW_ISO, VIEW_OFF, key_label
from mirai.symmetry_axis import current_axis

#: Layout variants, in the order `H` steps through them (`None` = hidden).
VARIANTS: tuple[str, ...] = ("bar", "corner")

LINE_HEIGHT = 18
PADDING = 6
GAP = 14
FONT_SIZE = 10

_BG = (18, 20, 26, 200)
_LABEL = (135, 145, 160, 255)
_VALUE = (225, 230, 240, 255)
#: A value that is "on" (constraint set, symmetry, soft, SubD, a running interaction).
_ON = (255, 205, 110, 255)
_KEYS = (110, 150, 200, 255)
_STATUS = (240, 236, 200, 255)

_MODE_NAMES = {"VERTEX": "Vertex", "EDGE": "Edge", "FACE": "Face", "OBJECT": "Object"}
_TOOL_NAMES = {
    commands.MOVE: "Move",
    commands.ROTATE: "Rotate",
    commands.SCALE: "Scale",
    commands.EXTRUDE: "Extrude",
    commands.LOOP_SLIDE: "Loop Slide",
    commands.SMOOTH: "Smooth",
    commands.RELAX: "Relax",
}
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
    #: Worklight name and the active Look row with its value (AD-024 §8).
    light: str
    look: str
    status: str
    status_serial: int


def hud_state(app) -> HudState:
    """The snapshot (read-only: attribute and property reads, nothing is set or recomputed)."""
    soft = app.soft_settings
    curve = f"custom p={soft.curve_power:g}" if soft.curve == "custom" else soft.curve
    if app.knife_active:
        active = "Knife"
    elif app.resymmetrize_preview is not None:
        active = "Re-Symmetrize"
    elif app.transform_command is not None:
        active = _TOOL_NAMES.get(app.transform_command, app.transform_command)
    else:
        active = None
    subd = app.subdivision
    return HudState(
        mode=_MODE_NAMES.get(app.selection.mode.name, app.selection.mode.name.capitalize()),
        tool=_TOOL_NAMES.get(app.tweak_command, app.tweak_command),
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
        light=app.display.light_label,
        look=app.look_text,
        status=app.status_message,
        status_serial=app.status_serial,
    )


# -- key hints (binding layer) ------------------------------------------------------------------

#: Per HUD row: the commands whose first key is shown, and the binding context they resolve in.
_HINT_COMMANDS: dict[str, tuple[tuple[str, ...], Optional[str]]] = {
    "Mode": (
        (commands.SET_VERTEX_MODE, commands.SET_EDGE_MODE, commands.SET_FACE_MODE, commands.SET_OBJECT_MODE),
        None,
    ),
    "Tool": ((commands.MOVE, commands.ROTATE, commands.SCALE), None),
    "Axis": ((commands.CONSTRAIN_AXIS_X, commands.CONSTRAIN_AXIS_Y, commands.CONSTRAIN_AXIS_Z), None),
    "Space": ((commands.TOGGLE_TRANSFORM_SPACE,), None),
    "Sym": ((commands.SYMMETRY_CYCLE, commands.RESYMMETRIZE), None),
    "Display": ((commands.CYCLE_DISPLAY_MODE, commands.TOGGLE_WIREFRAME_OVERLAY), None),
    "Soft": ((commands.SOFT_TOGGLE,), None),
    "SubD": ((commands.SUBD_CYCLE_VIEW,), SUBD_CONTEXT),
    "Region": ((commands.REGION_NEW, commands.REGION_NEXT, commands.REGION_NAME, commands.TOGGLE_REGION_TINT), None),
    "Look": (
        (commands.LOOK_ROW_PREV, commands.LOOK_ROW_NEXT, commands.LOOK_VALUE_DEC, commands.LOOK_VALUE_INC),
        None,
    ),
    "HUD": ((commands.TOGGLE_HUD,), WINDOW_CONTEXT),
}


_ARROWS = {"UP": "↑", "DOWN": "↓", "LEFT": "←", "RIGHT": "→"}


def key_hint(bindings: BindingSet, command_names: tuple[str, ...], context: Optional[str] = None) -> str:
    """`1/2/3/4`, `W/E/R`, `Shift+S`: the simplest key bound to each command, joined; a command
    without a key is left out (a rebinding to the mouse or an unbind shows as a missing key)."""
    keys = []
    for name in command_names:
        bound = [inp for inp in bindings.inputs_for(name, context) if inp.kind == "key"]
        if bound:
            label = key_label(bound[0])
            keys.append(_ARROWS.get(label, label))
    return "/".join(keys)


def key_hints(bindings: BindingSet) -> dict[str, str]:
    """All row hints at once; the bindings are fixed after the app start (no hot reload)."""
    return {row: key_hint(bindings, names, context) for row, (names, context) in _HINT_COMMANDS.items()}


# -- rows (pure text) ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HudRow:
    label: str
    value: str
    keys: str
    on: bool = False


def hud_rows(state: HudState, hints: dict[str, str]) -> list[HudRow]:
    """The state as display rows (both layouts show the same rows)."""
    tool = state.tool if state.active is None else f"{state.active} (running)"
    axis = state.constraint.upper() if state.constraint else "free"
    if state.constraint and len(state.constraint) == 2:
        axis += " plane"
    soft = (
        f"on · {state.soft_radius_percent} % · {state.soft_curve}" if state.soft_on else "off"
    )
    if state.subd_view == VIEW_OFF:
        subd = "off"
    else:
        subd = f"{_SUBD_VIEWS.get(state.subd_view, state.subd_view)} · L{state.subd_level}"
        if not state.subd_lines:
            subd += " · lines hidden"
    return [
        HudRow("Mode", state.mode, hints.get("Mode", "")),
        HudRow("Tool", tool, hints.get("Tool", ""), on=state.active is not None),
        HudRow("Axis", axis, hints.get("Axis", ""), on=state.constraint is not None),
        HudRow("Space", state.space.capitalize(), hints.get("Space", ""), on=state.space != "world"),
        HudRow("Sym", state.symmetry.upper() if state.symmetry else "off", hints.get("Sym", ""),
               on=state.symmetry is not None),
        HudRow("Display", state.display, hints.get("Display", "")),
        HudRow("Soft", soft, hints.get("Soft", ""), on=state.soft_on),
        HudRow("SubD", subd, hints.get("SubD", ""), on=state.subd_view != VIEW_OFF),
        HudRow(
            "Region",
            (
                f"{state.region} · {state.region_faces} faces · {state.region_count} "
                f"group{'s' if state.region_count != 1 else ''} · colours {'on' if state.region_tint else 'off'}"
                if state.region is not None
                else f"no groups · colours {'on' if state.region_tint else 'off'}"
            ),
            hints.get("Region", ""),
            on=state.region_faces > 0,
        ),
        HudRow("Look", f"{state.light} · {state.look}", hints.get("Look", "")),
    ]


# -- the HUD ------------------------------------------------------------------------------------


class Hud:
    """Visibility, layout variant, change detection and the (lazy) pyglet drawing."""

    def __init__(self, bindings: BindingSet, variant: str = VARIANTS[0], visible: bool = True) -> None:
        if variant not in VARIANTS:
            raise ValueError(f"Unknown HUD variant {variant!r}; expected one of {VARIANTS}.")
        self.hints = key_hints(bindings)
        self._variant = variant
        self._visible = bool(visible)
        self._state: Optional[HudState] = None
        self._size: tuple[int, int] = (0, 0)
        #: What the drawables were built from (state, variant, size); None = not built.
        self._built_key: Optional[tuple] = None
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
    def variant(self) -> str:
        return self._variant

    @property
    def state(self) -> Optional[HudState]:
        """The last snapshot `update` took (None before the first visible update)."""
        return self._state

    def toggle(self) -> Optional[str]:
        """`H`: bar -> corner -> hidden -> bar (Discovery). Returns the variant now shown, None = hidden."""
        if not self._visible:
            self._visible, self._variant = True, VARIANTS[0]
        else:
            index = VARIANTS.index(self._variant) + 1
            if index < len(VARIANTS):
                self._variant = VARIANTS[index]
            else:
                self._visible = False
        return self._variant if self._visible else None

    def set_variant(self, variant: str) -> None:
        if variant not in VARIANTS:
            raise ValueError(f"Unknown HUD variant {variant!r}; expected one of {VARIANTS}.")
        self._variant = variant

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
        return (self._state, self._variant, self._size)

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
        try:
            builder = self.make_builder(self._drawables)
            self._batch = builder.batch
            rows = hud_rows(self._state, self.hints)
            if self._variant == "bar":
                _layout_bar(builder, rows, self._state.status, self.hints.get("HUD", ""), *self._size)
            else:
                _layout_corner(builder, rows, self._state.status, self.hints.get("HUD", ""), *self._size)
        except Exception:
            # No pyglet / no GL context: the app runs on without a HUD (console status stays).
            self._batch = None
            self._drawables = []


class _Builder:
    """Labels and background rectangles in one batch (background group drawn first)."""

    def __init__(self, sink: list) -> None:
        from pyglet import graphics

        self.batch = graphics.Batch()
        self.sink = sink
        self.back = graphics.Group(order=0)
        self.front = graphics.Group(order=1)

    def label(self, text: str, x: float, y: float, color) -> object:
        from pyglet import text as _text

        label = _text.Label(
            text, x=x, y=y, anchor_x="left", anchor_y="baseline", font_size=FONT_SIZE,
            color=color, batch=self.batch, group=self.front,
        )
        self.sink.append(label)
        return label

    def rect(self, x: float, y: float, width: float, height: float) -> None:
        from pyglet import shapes

        self.sink.append(shapes.Rectangle(x, y, width, height, color=_BG, batch=self.batch, group=self.back))


def _layout_bar(b: _Builder, rows: list[HudRow], status: str, hud_key: str, width: int, height: int) -> None:
    """Variant A: full-width bottom bar; the rows as segments (wrapped onto a second line when the
    window is too narrow), the status message and the H hint on the last line."""
    segments = []
    for row in rows:
        parts = [b.label(row.label, 0, 0, _LABEL), b.label(row.value, 0, 0, _ON if row.on else _VALUE)]
        if row.keys:
            parts.append(b.label(f"[{row.keys}]", 0, 0, _KEYS))
        segments.append(parts)
    lines: list[list] = [[]]
    x = PADDING
    for parts in segments:
        seg_width = sum(item.content_width for item in parts) + 4 * (len(parts) - 1)
        if lines[-1] and x + seg_width > width - PADDING:
            lines.append([])
            x = PADDING
        lines[-1].append((x, parts))
        x += seg_width + GAP
    bar_height = (len(lines) + 1) * LINE_HEIGHT + 2 * PADDING
    b.rect(0, 0, width, bar_height)
    for index, line in enumerate(lines):
        base = bar_height - PADDING - (index + 1) * LINE_HEIGHT + 5
        for x, parts in line:
            for item in parts:
                item.x, item.y = x, base
                x += item.content_width + 4
    base_status = PADDING + 5
    b.label(status, PADDING, base_status, _STATUS)
    if hud_key:
        hint = b.label(f"{hud_key}: HUD", 0, base_status, _KEYS)
        hint.x = width - PADDING - hint.content_width


def _layout_corner(b: _Builder, rows: list[HudRow], status: str, hud_key: str, width: int, height: int) -> None:
    """Variant B: a panel in the top-left corner, one row per item (label | value | keys), the
    status message and the H hint under it."""
    top = height - PADDING
    labels, values, keys = [], [], []
    for index, row in enumerate(rows):
        y = top - PADDING - (index + 1) * LINE_HEIGHT + 5
        labels.append(b.label(row.label, 0, y, _LABEL))
        values.append(b.label(row.value, 0, y, _ON if row.on else _VALUE))
        keys.append(b.label(row.keys, 0, y, _KEYS))
    x_label = 2 * PADDING
    x_value = x_label + max(item.content_width for item in labels) + GAP
    x_keys = x_value + max(item.content_width for item in values) + GAP
    for group, x in ((labels, x_label), (values, x_value), (keys, x_keys)):
        for item in group:
            item.x = x
    panel_width = x_keys + max(item.content_width for item in keys) + 2 * PADDING - PADDING
    y_status = top - PADDING - (len(rows) + 1) * LINE_HEIGHT - 1
    footer = b.label(status, x_label, y_status, _STATUS)
    hint = b.label(f"{hud_key}: HUD" if hud_key else "", x_label, y_status - LINE_HEIGHT, _KEYS)
    panel_width = max(panel_width, x_label + max(footer.content_width, hint.content_width) + PADDING)
    panel_height = (len(rows) + 2) * LINE_HEIGHT + 2 * PADDING + 2
    b.rect(PADDING, top - panel_height, min(panel_width, width - 2 * PADDING), panel_height)
