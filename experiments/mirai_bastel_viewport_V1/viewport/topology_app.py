"""Topology-Lab auf Basis des bestehenden V1-Viewports."""

from __future__ import annotations

import pyglet
from pyglet.window import key

from mirai_bastel_core import SelectionMode

from .app import ModelerWindow
from .topology_scene import build_topology_scene
from .topology_tools import (
    TopologyToolError,
    collapse_selected_edge,
    collapse_selected_edges,
    collapse_selected_vertices,
    connect_selected_edges,
    connect_selected_vertices,
    split_selected_edge,
)


class TopologyWindow(ModelerWindow):
    def __init__(self) -> None:
        super().__init__()
        self.scene = build_topology_scene()
        self.selection_mode = SelectionMode.EDGE
        self.scene.selection.mode = self.selection_mode
        self.scene.selection.clear()
        self._hovered_id = None
        self.scene.selection.hovered = None
        self._rebuild_geometry()
        self._set_topology_caption()

    def _set_topology_caption(self, message: str | None = None) -> None:
        text = "Topology Lab | V/E/F | S Split | K Collapse | C Connect V | Shift+C Connect E | Ctrl+Z/Y"
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

    def _run_topology_tool(self, symbol: int, modifiers: int) -> bool:
        try:
            if symbol == key.S and not (modifiers & key.MOD_SHIFT):
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

            if symbol == key.K and not (modifiers & key.MOD_SHIFT):
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

            if symbol == key.C and modifiers & key.MOD_SHIFT:
                if self.selection_mode != SelectionMode.EDGE or len(self.scene.selection.edges) < 2:
                    raise TopologyToolError("Connect Edges: mindestens 2 Edges auswählen.")
                selected = set(self.scene.selection.edges)
                created = connect_selected_edges(
                    self.scene, selected, on_restore=self._after_topology_restore
                )
                self._select_created_edges(created)
                self._hovered_id = None
                self._rebuild_geometry()
                self._set_topology_caption(f"Connect {len(selected)} Edges → {len(created)} Edges")
                return True

            if symbol == key.C and not (modifiers & key.MOD_SHIFT):
                if self.selection_mode != SelectionMode.VERTEX or len(self.scene.selection.vertices) < 2:
                    raise TopologyToolError("Connect Vertices: mindestens 2 Vertices auswählen.")
                selected = set(self.scene.selection.vertices)
                created = connect_selected_vertices(
                    self.scene, selected, on_restore=self._after_topology_restore
                )
                self._select_created_edges(created)
                self._hovered_id = None
                self._rebuild_geometry()
                self._set_topology_caption(f"Connect {len(selected)} Vertices → {len(created)} Edges")
                return True
        except TopologyToolError as exc:
            self._set_topology_caption(f"FEHLER: {exc}")
            return True
        return False

    def on_key_press(self, symbol, modifiers):
        if self._run_topology_tool(symbol, modifiers):
            return
        super().on_key_press(symbol, modifiers)
        if symbol in (key.V, key._1, key.E, key._2, key.F, key._3):
            self._set_topology_caption()


def main() -> None:
    TopologyWindow()
    pyglet.app.run()


if __name__ == "__main__":
    main()
