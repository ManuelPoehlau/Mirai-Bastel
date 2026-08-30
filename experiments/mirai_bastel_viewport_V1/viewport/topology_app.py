"""Topology-Lab auf Basis des bestehenden V1-Viewports.

Key-/Mouse-Routing läuft seit WP-01A über die Input-Mapping-Schicht; die
Topology-Commands liegen im Binding-Kontext "topology" (siehe
default_bindings.py). Es werden keine pyglet-Tasten mehr direkt im Window
verarbeitet.
"""

from __future__ import annotations

import pyglet

from mirai_bastel_core import SelectionMode

from . import commands as cmd
from .app import ModelerWindow
from .input_binding import TOPOLOGY_CONTEXT
from .topology_scene import build_topology_scene
from .topology_tools import (
    TopologyToolError,
    collapse_selected_edge,
    collapse_selected_edges,
    collapse_selected_vertices,
    connect_selected_edges,
    connect_selected_vertices,
    split_selected_edge,
    select_edge_loop,
    select_edge_ring,
)


class TopologyWindow(ModelerWindow):
    def __init__(self, scene=None) -> None:
        super().__init__()
        self.scene = scene if scene is not None else build_topology_scene()
        self.selection_mode = SelectionMode.EDGE
        self.scene.selection.mode = self.selection_mode
        self.scene.selection.clear()
        self._hovered_id = None
        self.scene.selection.hovered = None
        self._rebuild_geometry()
        self._set_topology_caption()

    def _binding_context(self) -> str:
        """Topology-Lab-Bindings; globale Fallbacks (V/E/F, Undo/Redo, ...) gelten weiter."""
        return TOPOLOGY_CONTEXT

    def _set_topology_caption(self, message: str | None = None) -> None:
        text = (
            f"Topology Lab | {self.display_state.label} | "
            "V/E/F | S Split | K Collapse | C Connect | L Loop | R Ring | "
            "Alt+A Select None | Ctrl+Z/Y | O Display | W Wire"
        )
        if message:
            text += f" | {message}"
        self.set_caption(text)

    def _after_topology_restore(self) -> None:
        self.scene.selection.clear()
        self.scene.selection.hovered = None
        self._hovered_id = None
        self._drag_mode = None
        self._active_move = None
        self._move_anchor_vertex = None
        self._rebuild_geometry()
        self._set_topology_caption()

    def _select_created_edges(self, edge_ids) -> None:
        """Select newly created edges and switch to Edge Mode.

        Connect Vertices creates edges, so keeping Vertex Mode while storing
        EdgeIds in the vertex selection would corrupt the Selection state.
        The result therefore becomes an explicit Edge selection.
        """
        self.scene.selection.clear()
        self.selection_mode = SelectionMode.EDGE
        self.scene.selection.mode = self.selection_mode
        self.scene.selection.set(set(edge_ids))

    def _dispatch_command(self, command) -> bool:
        if self._run_topology_command(command):
            return True
        handled = super()._dispatch_command(command)
        if handled and command in (
            cmd.SET_VERTEX_MODE,
            cmd.SET_EDGE_MODE,
            cmd.SET_FACE_MODE,
        ):
            self._set_topology_caption()
        return handled

    def _run_topology_command(self, command) -> bool:
        try:
            if command == cmd.SPLIT_EDGE:
                if self.selection_mode != SelectionMode.EDGE or len(self.scene.selection.edges) != 1:
                    raise TopologyToolError("Split Edge: genau 1 Edge auswählen.")
                old_edge = next(iter(self.scene.selection.edges))
                new_vertex, edge_a, edge_b = split_selected_edge(
                    self.scene, old_edge, on_restore=self._after_topology_restore
                )
                self.scene.selection.set({edge_a, edge_b})
                self._hovered_id = None
                self._rebuild_geometry()
                self._set_topology_caption(f"Split → Vertex {new_vertex}")
                return True

            if command == cmd.COLLAPSE:
                if self.selection_mode == SelectionMode.VERTEX:
                    selected = set(self.scene.selection.vertices)
                    if len(selected) < 2:
                        raise TopologyToolError("Collapse Vertices: mindestens 2 Vertices auswählen.")
                    survivors = collapse_selected_vertices(
                        self.scene, selected, on_restore=self._after_topology_restore
                    )
                    self.scene.selection.clear()
                    self.scene.selection.mode = SelectionMode.VERTEX
                    survivor = survivors[-1]
                    self.scene.selection.set({survivor})
                    self._hovered_id = survivor
                    self._rebuild_geometry()
                    self._set_topology_caption(f"Collapse {len(selected)} Vertices → Vertex {survivor}")
                    return True

                if self.selection_mode != SelectionMode.EDGE:
                    raise TopologyToolError("Collapse: Vertex oder Edge Mode verwenden.")

                selected = set(self.scene.selection.edges)
                if len(selected) == 0:
                    raise TopologyToolError("Collapse Edge: mindestens 1 Edge auswählen.")
                if len(selected) == 1:
                    old_edge = next(iter(selected))
                    survivor = collapse_selected_edge(
                        self.scene, old_edge, on_restore=self._after_topology_restore
                    )
                    self.scene.selection.clear()
                    self.selection_mode = SelectionMode.VERTEX
                    self.scene.selection.mode = self.selection_mode
                    self.scene.selection.set({survivor})
                    self._hovered_id = survivor
                    self._rebuild_geometry()
                    self._set_topology_caption(f"Collapse → Vertex {survivor}")
                    return True

                survivors = collapse_selected_edges(
                    self.scene, selected, on_restore=self._after_topology_restore
                )
                valid_survivors = [v for v in survivors if self.scene.mesh.is_valid_vertex(v)]
                self.scene.selection.clear()
                self.selection_mode = SelectionMode.VERTEX
                self.scene.selection.mode = self.selection_mode
                if valid_survivors:
                    survivor = valid_survivors[-1]
                    self.scene.selection.set({survivor})
                    self._hovered_id = survivor
                self._rebuild_geometry()
                self._set_topology_caption(f"Collapse {len(selected)} Edges")
                return True

            if command == cmd.CONNECT:
                if self.selection_mode == SelectionMode.VERTEX:
                    selected = set(self.scene.selection.vertices)
                    if len(selected) < 2:
                        raise TopologyToolError("Connect Vertices: mindestens 2 Vertices auswählen.")
                    element_label = "Vertices"
                    created = connect_selected_vertices(
                        self.scene, selected, on_restore=self._after_topology_restore
                    )
                elif self.selection_mode == SelectionMode.EDGE:
                    selected = set(self.scene.selection.edges)
                    if len(selected) < 2:
                        raise TopologyToolError("Connect Edges: mindestens 2 Edges auswählen.")
                    element_label = "Edges"
                    created = connect_selected_edges(
                        self.scene, selected, on_restore=self._after_topology_restore
                    )
                else:
                    raise TopologyToolError("Connect: Vertex oder Edge Mode verwenden.")
                self._select_created_edges(created)
                self._hovered_id = None
                self._rebuild_geometry()
                self._set_topology_caption(f"Connect {len(selected)} {element_label} → {len(created)} Edges")
                return True

            if command == cmd.EDGE_LOOP:
                if self.selection_mode != SelectionMode.EDGE or len(self.scene.selection.edges) != 1:
                    raise TopologyToolError("Edge Loop: genau 1 Edge auswählen.")
                start_edge = next(iter(self.scene.selection.edges))
                loop_edges, is_closed = select_edge_loop(self.scene, start_edge)
                self.scene.selection.clear()
                self.scene.selection.set(loop_edges)
                self._hovered_id = None
                self._rebuild_geometry()
                closed_text = " (geschlossen)" if is_closed else ""
                self._set_topology_caption(f"Edge Loop: {len(loop_edges)} Edges{closed_text}")
                return True

            if command == cmd.EDGE_RING:
                if self.selection_mode != SelectionMode.EDGE or len(self.scene.selection.edges) != 1:
                    raise TopologyToolError("Edge Ring: genau 1 Edge auswählen.")
                start_edge = next(iter(self.scene.selection.edges))
                ring_edges, is_closed = select_edge_ring(self.scene, start_edge)
                self.scene.selection.clear()
                self.scene.selection.set(ring_edges)
                self._hovered_id = None
                self._rebuild_geometry()
                closed_text = " (geschlossen)" if is_closed else ""
                self._set_topology_caption(f"Edge Ring: {len(ring_edges)} Edges{closed_text}")
                return True

        except TopologyToolError as exc:
            self._set_topology_caption(f"FEHLER: {exc}")
            return True
        return False


def main() -> None:
    TopologyWindow()
    pyglet.app.run()


if __name__ == "__main__":
    main()