"""Playground Command Handler — routes semantic commands to operations.

Receives Input → Command through BindingSet, then dispatches to:
1. Experiment-aware handlers (variant-dependent behavior)
2. ToolManager for modal tools (Move, Rotate, Scale, LoopSlide, Extrude)
3. Direct operations (scene mutations: split_edge, connect_edges, etc.)
4. Display/state changes

Preserves input precedence and state machine integrity:
- ESC cascades through active interactions (articulation → loop_slide → extrude → tweak → transform)
- Variant-dependent activation models (transform hold/press/press_drag_click, tweak v1-v4, extrude hold/lmb)
- Experiment family focus determines topology context bindings
- No state corruption: operations cancel cleanly, history contracts respected

Tested as unit (command resolution, state checks); integration testing via
Playground window tests.
"""

from __future__ import annotations

from typing import Callable, Optional

from core.selection import SelectionMode
from mirai.interaction import commands as cmd
from mirai.interaction.tool_manager import ToolManager
from mirai.interaction.routing import tool_for_command


class PlaygroundCommandHandler:
    """Routes commands to Playground operations with precedence and variant awareness."""

    def __init__(self, app, window) -> None:
        """Initialize handler with app context and window reference.

        Args:
            app: PlaygroundApp instance (scene, camera, selection, display_state, slots, etc.)
            window: PlaygroundWindow instance (state machines, VBO builders, HUD, etc.)
        """
        self.app = app
        self.window = window
        self.tool_manager = ToolManager()

    # --- Command Dispatch (Entry Point) ------------------------------------

    def handle_command(self, command: str) -> bool:
        """Process a command with full precedence and context awareness.

        Args:
            command: Command string (e.g., "Move", "SplitEdge")

        Returns:
            True if command was handled, False if unknown/unsupported
        """
        if command is None:
            return False

        # WP-AP-INPUT-FIX-01: Whitelist of safe commands for Playground dispatch.
        # §1: Fixed precedence bug that silenced Playground-only state machines.
        # §2-§4: Re-enabled MOVE/ROTATE/SCALE after key rebinding (now W/E/R in Playground).
        # These commands are safe because their new keys (W/E/R) don't conflict with
        # Playground variant cycling (Q) or other operations.
        SAFE_COMMANDS = {
            cmd.UNDO, cmd.REDO,
            cmd.SET_VERTEX_MODE, cmd.SET_EDGE_MODE, cmd.SET_FACE_MODE,
            cmd.CYCLE_DISPLAY_MODE, cmd.TOGGLE_WIREFRAME_OVERLAY,
            cmd.SPLIT_EDGE,
            cmd.MOVE, cmd.ROTATE, cmd.SCALE,  # Re-enabled in §2-§4
        }
        if command not in SAFE_COMMANDS:
            return False

        # Dispatch by command category. Precedence is implicit: handlers can
        # check state and return False to defer, allowing fallthrough.
        # (Currently no fallthrough; each handler is responsible for its scope.)

        # Scene loading
        if self._handle_scene_commands(command):
            return True

        # History
        if self._handle_history_commands(command):
            return True

        # Interaction: selection, transform, tools
        if self._handle_interaction_commands(command):
            return True

        # Navigation
        if self._handle_navigation_commands(command):
            return True

        # Display
        if self._handle_display_commands(command):
            return True

        # Topology
        if self._handle_topology_commands(command):
            return True

        # Selection/Component modes
        if self._handle_selection_mode_commands(command):
            return True

        return False

    # --- Scene Commands ---------------------------------------------------

    def _handle_scene_commands(self, command: str) -> bool:
        """Handle scene loading commands (not production commands, Playground-only)."""
        # Scene loading is not in production commands, so we don't handle it here.
        # Kept for future extension if scene load becomes a command.
        return False

    # --- History Commands ------------------------------------------------

    def _handle_history_commands(self, command: str) -> bool:
        """Handle undo/redo commands."""
        if command == cmd.UNDO:
            self.app.undo()
            self.app.scene.selection.clear()
            self.window._rebuild_vbo()
            self.window._hud.update_action("Undo")
            self.window._update_hud()
            return True
        elif command == cmd.REDO:
            self.app.redo()
            self.app.scene.selection.clear()
            self.window._rebuild_vbo()
            self.window._hud.update_action("Redo")
            self.window._update_hud()
            return True
        return False

    # --- Interaction Commands (Transform, Tweak, etc.) -------------------

    def _handle_interaction_commands(self, command: str) -> bool:
        """Handle modal interaction commands (Move, Rotate, Scale, etc.)."""
        if command == cmd.MOVE:
            return self._activate_transform("move")
        elif command == cmd.ROTATE:
            return self._activate_transform("rotate")
        elif command == cmd.SCALE:
            return self._activate_transform("scale")
        elif command == cmd.CANCEL:
            return self._handle_cancel()
        elif command == cmd.CLEAR_SELECTION:
            if self.app.viewport is not None:
                self.app.scene.selection.clear()
                self.window._rebuild_selection_vbo()
                self.window._update_hud()
            return True
        return False

    def _activate_transform(self, tool_type: str) -> bool:
        """Activate transform tool based on variant and current state."""
        # Determine activation model from active transform variant
        slot = self.app.slots.get("transform")
        if slot is None:
            return False

        model = getattr(slot.active_experiment, "activation", "hold")

        if model == "hold":
            # Hold activation: key down → activate/create tool
            from playground.transformer import create_tool_for_type
            self.window._transform_key_down = tool_type[0]  # 'm'/'r'/'s'
            self.app.active_tool = create_tool_for_type(tool_type)
        elif model == "press_mode":
            # Press mode: key press → toggle mode
            from playground.transformer import create_tool_for_type
            if self.window._transform_mode_on:
                # Already in mode: commit if started, then clear
                if self.window._transform_started and self.app.active_tool is not None:
                    from playground.transformer import commit_transform
                    commit_transform(self.app.active_tool)
                    self.window._sync_after_transform()
                self.window._clear_transform_state()
            else:
                # Enter mode
                self.window._transform_key_down = tool_type[0]
                self.window._transform_mode_on = True
                self.app.active_tool = create_tool_for_type(tool_type)
        elif model == "press_drag_click":
            # Press-drag-click: same as press_mode for key press
            from playground.transformer import create_tool_for_type
            if self.window._transform_mode_on:
                if self.window._transform_started and self.app.active_tool is not None:
                    from playground.transformer import commit_transform
                    commit_transform(self.app.active_tool)
                    self.window._sync_after_transform()
                self.window._clear_transform_state()
            else:
                self.window._transform_key_down = tool_type[0]
                self.window._transform_mode_on = True
                self.app.active_tool = create_tool_for_type(tool_type)

        self.window._update_hud()
        return True

    def _handle_cancel(self) -> bool:
        """Handle ESC cascading cancellation with proper precedence."""
        # Precedence (top = highest): articulation → loop_slide → extrude → tweak → transform → close

        # Articulation restore
        if self.window._articulation_state is not None:
            self.window._articulation_state.restore()
            self.window._articulation_state = None
            self.window._articulation_dragging = False
            self.window._rebuild_vbo()
            self.window._hud.update_action("Articulation cancelled")
            self.window._update_hud()
            return True

        # Loop slide cancel
        if self.window._loop_slide_tool is not None:
            from playground.transformer import cancel_transform
            cancel_transform(self.window._loop_slide_tool)
            self.window._loop_slide_tool = None
            self.window._rebuild_vbo()
            self.window._hud.update_action("Loop Slide cancelled")
            self.window._update_hud()
            return True

        # Extrude cancel
        if self.window._extrude_tool is not None:
            from playground.transformer import cancel_transform
            cancel_transform(self.window._extrude_tool)
            self.window._extrude_tool = None
            self.window._rebuild_vbo()
            self.window._rebuild_selection_vbo()
            self.window._hud.update_action("Extrude cancelled")
            self.window._update_hud()
            return True

        # Tweak cancel
        if self.window._tweak_active:
            from playground.transformer import cancel_transform
            if self.window._tweak_started and self.window._tweak_tool is not None:
                cancel_transform(self.window._tweak_tool)
            self.window._sync_after_transform()
            if self.window._tweak_temp_target:
                from playground.experiments.tweak._target import clear_temp_target
                clear_temp_target(self.app.scene.selection)
                self.window._tweak_temp_target = False
                self.window._rebuild_selection_vbo()
            self.window._clear_tweak_gesture()
            self.window._hud.update_action("Tweak cancelled")
            self.window._update_hud()
            return True

        # Tweak V1 armed state
        if self.window._tweak_v1_key is not None:
            self.window._tweak_v1_key = None
            self.window._tweak_v1_moved = 0.0
            return True

        # Tweak V3 armed state
        if self.window._tweak_v3_key is not None:
            self.window._tweak_v3_key = None
            self.window._tweak_v3_lmb = False
            return True

        # Transform cancel
        if self.window._transform_key_down is not None or self.window._transform_mode_on:
            if self.window._transform_started and self.app.active_tool is not None:
                from playground.transformer import cancel_transform
                cancel_transform(self.app.active_tool)
                self.window._sync_after_transform()
            self.window._clear_transform_state()
            self.window._hud.update_action("Transform cancelled")
            self.window._update_hud()
            return True

        # No active interaction: close window
        return False

    # --- Navigation Commands (Camera) ------------------------------------

    def _handle_navigation_commands(self, command: str) -> bool:
        """Handle camera navigation commands."""
        # Navigation is currently handled in mouse events, not keyboard.
        # Could extend if needed for keyboard shortcuts.
        return False

    # --- Display Commands ------------------------------------------------

    def _handle_display_commands(self, command: str) -> bool:
        """Handle display mode and visibility commands."""
        if command == cmd.CYCLE_DISPLAY_MODE:
            slot = self.app.slots.get("presentation")
            if slot is not None:
                self.app.activate_variant("presentation", (slot.active_index + 1) % slot.variant_count)
            else:
                self.app.display_state.cycle()
            self.window._update_hud()
            return True
        elif command == cmd.TOGGLE_WIREFRAME_OVERLAY:
            self.app.display_state.toggle_wireframe_overlay()
            self.window._update_hud()
            return True
        elif command == cmd.SET_SHADED:
            from mirai.viewport.display import DisplayMode
            self.app.display_state.mode = DisplayMode.SHADED
            self.window._update_hud()
            return True
        elif command == cmd.SET_FLAT_SHADED:
            from mirai.viewport.display import DisplayMode
            self.app.display_state.mode = DisplayMode.FLAT_SHADED
            self.window._update_hud()
            return True
        elif command == cmd.SET_WIREFRAME:
            from mirai.viewport.display import DisplayMode
            self.app.display_state.mode = DisplayMode.WIREFRAME
            self.window._update_hud()
            return True
        return False

    # --- Topology Commands -----------------------------------------------

    def _handle_topology_commands(self, command: str) -> bool:
        """Handle topology operations (split, connect, loop operations, extrude)."""
        if command == cmd.SPLIT_EDGE:
            return self._topology_split_edge()
        elif command == cmd.COLLAPSE:
            return self._topology_collapse()
        elif command == cmd.CONNECT:
            return self._topology_connect()
        elif command == cmd.EDGE_LOOP:
            return self._topology_loop_select()
        elif command == cmd.EDGE_RING:
            return self._topology_ring_select()
        elif command == cmd.LOOP_INSERT:
            return self._topology_loop_insert()
        elif command == cmd.LOOP_SLIDE:
            return self._topology_loop_slide()
        elif command == cmd.EXTRUDE:
            return self._topology_extrude()
        elif command == cmd.ARTICULATION_RESTORE:
            return self._articulation_restore()
        return False

    def _topology_split_edge(self) -> bool:
        """Split selected edge (K in edge mode)."""
        from playground.topology_ops import split_selected_edge

        sel = self.app.scene.selection
        if sel.mode is not SelectionMode.EDGE or len(sel.edges) != 1:
            return False

        restored = self.window._articulation_auto_restore()
        (edge_id,) = sel.edges
        split_selected_edge(self.app.scene, edge_id)
        sel.clear()
        self.window._rebuild_vbo()
        action = "Split Edge (articulation restored)" if restored else "Split Edge"
        self.window._hud.update_action(action)
        self.window._update_hud()
        return True

    def _topology_collapse(self) -> bool:
        """Collapse edge (not yet implemented in Playground)."""
        # Production command defined but no Playground implementation yet.
        # TODO: Implement collapse operation.
        return False

    def _topology_connect(self) -> bool:
        """Connect vertices (vertex mode) or edges (edge mode)."""
        from playground.topology_tools.connect_edges import (
            connect_selected_edges,
            TopologyToolError as _ConnectEdgesError,
        )

        sel = self.app.scene.selection
        if sel.mode is not SelectionMode.EDGE or len(sel.edges) < 2:
            return False

        restored = self.window._articulation_auto_restore()
        try:
            new_edges = connect_selected_edges(self.app.scene, set(sel.edges))
            sel.clear()
            sel.add(set(new_edges))
            self.window._rebuild_vbo()
            action = "Connect Edges (articulation restored)" if restored else "Connect Edges"
            self.window._hud.update_action(action)
        except _ConnectEdgesError as exc:
            self.window._hud.update_action(str(exc))
        self.window._update_hud()
        return True

    def _topology_loop_select(self) -> bool:
        """Select edge loop (Shift+L in edge mode)."""
        from playground.topology_tools.loop_ring import (
            edge_loop,
            LoopRingError as _LoopRingError,
        )

        sel = self.app.scene.selection
        if sel.mode is not SelectionMode.EDGE or len(sel.edges) < 1:
            return False

        start = next(iter(sel.edges))
        try:
            traversal = edge_loop(self.app.scene.mesh, start)
            sel.clear()
            sel.add(traversal.as_set())
            self.window._rebuild_selection_vbo()
            self.window._hud.update_action(
                f"Loop Select — {len(traversal.edges)} Edges"
                + (" (closed)" if traversal.closed else "")
            )
        except _LoopRingError as exc:
            self.window._hud.update_action(str(exc))
        self.window._update_hud()
        return True

    def _topology_ring_select(self) -> bool:
        """Select edge ring (Shift+R in edge mode)."""
        from playground.topology_tools.loop_ring import (
            edge_ring,
            LoopRingError as _LoopRingError,
        )

        sel = self.app.scene.selection
        if sel.mode is not SelectionMode.EDGE or len(sel.edges) < 1:
            return False

        start = next(iter(sel.edges))
        try:
            traversal = edge_ring(self.app.scene.mesh, start)
            sel.clear()
            sel.add(traversal.as_set())
            self.window._rebuild_selection_vbo()
            self.window._hud.update_action(
                f"Ring Select — {len(traversal.edges)} Edges"
                + (" (closed)" if traversal.closed else "")
            )
        except _LoopRingError as exc:
            self.window._hud.update_action(str(exc))
        self.window._update_hud()
        return True

    def _topology_loop_insert(self) -> bool:
        """Insert edge loop (I in edge mode)."""
        from playground.topology_tools.loop_insert import (
            loop_insert,
            LoopInsertError as _LoopInsertError,
        )

        sel = self.app.scene.selection
        if sel.mode is not SelectionMode.EDGE or len(sel.edges) < 1:
            return False

        restored = self.window._articulation_auto_restore()
        start = next(iter(sel.edges))
        try:
            new_edges = loop_insert(self.app.scene, start)
            sel.clear()
            sel.add(set(new_edges))
            self.window._rebuild_vbo()
            suffix = " (articulation restored)" if restored else ""
            self.window._hud.update_action(f"Loop Insert — {len(new_edges)} Edges{suffix}")
        except _LoopInsertError as exc:
            self.window._hud.update_action(str(exc))
        self.window._update_hud()
        return True

    def _topology_loop_slide(self) -> bool:
        """Begin loop slide operation (G in edge mode)."""
        from playground.topology_tools.loop_slide import (
            LoopSlideTool,
            LoopSlideError as _LoopSlideError,
        )

        sel = self.app.scene.selection
        if sel.mode is not SelectionMode.EDGE or len(sel.edges) < 1:
            return False

        if self.window._loop_slide_tool is not None:
            return False

        restored = self.window._articulation_auto_restore()
        tool = LoopSlideTool(self.app.scene, self.app.camera)
        try:
            tool.activate()
            tool.begin(edge_ids=set(sel.edges))
            self.window._loop_slide_tool = tool
            suffix = " (articulation restored)" if restored else ""
            self.window._hud.update_action(f"Loop Slide — drag mouse, G to release = commit, ESC = cancel{suffix}")
        except _LoopSlideError as exc:
            tool.deactivate()
            self.window._hud.update_action(str(exc))
        self.window._update_hud()
        return True

    def _topology_extrude(self) -> bool:
        """Begin extrude operation (E in face mode)."""
        from playground.topology_tools.extrude import ExtrudeTool
        from playground.selector import pick_component

        sel = self.app.scene.selection
        if sel.mode is not SelectionMode.FACE or self.window._extrude_tool is not None:
            return False

        if self.app.viewport is None:
            return False

        restored = self.window._articulation_auto_restore()
        if len(sel.faces) >= 1:
            face_ids = set(sel.faces)
        else:
            mesh = self.app.viewport.render_mesh.mesh
            hit = pick_component(
                self.app.camera,
                mesh,
                sel,
                self.window._last_mouse_x,
                self.window._last_mouse_y,
                self.window.width,
                self.window.height,
            )
            if hit is None or sel.mode is not SelectionMode.FACE:
                return False
            face_ids = {hit}

        tool = ExtrudeTool(self.app.scene, self.app.camera)
        tool.activate()
        tool.begin(face_ids=face_ids)
        self.window._extrude_tool = tool
        self.window._rebuild_vbo()
        self.window._rebuild_selection_vbo()
        n = len(face_ids)
        action = f"Extrude ({n} faces)" if n > 1 else "Extrude"
        restore_note = " (articulation restored)" if restored else ""
        self.window._hud.update_action(f"{action}{restore_note} — move mouse to set distance, release E = commit, ESC = cancel")
        self.window._update_hud()
        return True

    def _articulation_restore(self) -> bool:
        """Restore articulation to rest pose (F key)."""
        if self.window._articulation_state is not None:
            self.window._articulation_state.restore()
            self.window._articulation_state = None
            self.window._articulation_dragging = False
            self.window._rebuild_vbo()
            self.window._hud.update_action("Articulation restored")
            self.window._update_hud()
            return True
        return False

    # --- Selection/Component Mode Commands --------------------------------

    def _handle_selection_mode_commands(self, command: str) -> bool:
        """Handle component mode and selection behavior commands."""
        if command == cmd.SET_VERTEX_MODE:
            if self.app.viewport is not None:
                sel = self.app.scene.selection
                sel.mode = SelectionMode.VERTEX
                sel.clear()
                self.window._rebuild_selection_vbo()
                self.window._update_hud()
            return True
        elif command == cmd.SET_EDGE_MODE:
            if self.app.viewport is not None:
                sel = self.app.scene.selection
                sel.mode = SelectionMode.EDGE
                sel.clear()
                self.window._rebuild_selection_vbo()
                self.window._update_hud()
            return True
        elif command == cmd.SET_FACE_MODE:
            if self.app.viewport is not None:
                sel = self.app.scene.selection
                sel.mode = SelectionMode.FACE
                sel.clear()
                self.window._rebuild_selection_vbo()
                self.window._update_hud()
            return True
        return False
