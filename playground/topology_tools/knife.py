"""Knife session tool — incremental explicit path cutting (AD-017 §1.7).

Modal tool. Headless-testable (no window code).
History: in-session mutations are NOT pushed to global history.
Commit: pushes exactly one MeshStateCommand; selects the connecting-edge path.
Cancel / Esc: restores pre-session state; nothing pushed.
In-session undo: removes only the most recent cut step.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core import EdgeId, VertexId
from core.operations.topology import MeshStateCommand
from core.selection import Selection, SelectionMode
from mirai.interaction.tool import Tool

from playground.topology_tools.topology_points import connect_in_shared_face


@dataclass
class _KnifeStep:
    state_before: Any
    start_before: VertexId | None
    path_edges_before: list[EdgeId]


class KnifeTool(Tool):
    """Knife modal tool.

    Usage lifecycle:
      knife = KnifeTool()
      knife.activate()
      knife.begin(mesh=..., scene=..., selection=...)
      # during session:
      knife.hover(target)   # preview, no mutation
      knife.click(target)   # may mutate mesh
      knife.undo_step()     # remove most recent cut step
      # end session:
      knife.commit()        # push one history entry, apply residue
      # or:
      knife.cancel()        # restore pre-session state, no history
    """

    def _on_activate(self) -> None:
        self._mesh = None
        self._scene = None
        self._selection = None
        self._session_before: Any = None
        self._start: VertexId | None = None
        self._path_edges: list[EdgeId] = []
        self._step_stack: list[_KnifeStep] = []

    def _on_begin(self, mesh=None, scene=None, selection=None, **_) -> None:
        self._mesh = mesh
        self._scene = scene
        self._selection = selection
        self._session_before = mesh.export_state()
        self._start = None
        self._path_edges = []
        self._step_stack = []

    def hover(self, target: dict) -> dict:
        """Return preview info without mutating the mesh.

        target: {"kind": "vertex", "vertex_id": ...}
                {"kind": "edge", "edge_id": ..., "t": float}
                {"kind": "face", "face_id": ...}  — invalid target
                {"kind": "outside"}
        Returns: {"valid": bool, "target": target, "start": self._start}
        """
        kind = target.get("kind") if target else None
        if kind == "vertex":
            return {"valid": True, "target": target, "start": self._start}
        if kind == "edge":
            eid = target.get("edge_id")
            t = target.get("t", 0.5)
            if eid is not None and self._mesh.is_valid_edge(eid) and 0.0 < t < 1.0:
                if self._start is not None:
                    va, vb = self._mesh.edge_vertices(eid)
                    if va == self._start or vb == self._start:
                        return {"valid": False, "target": target, "start": self._start}
                return {"valid": True, "target": target, "start": self._start}
        return {"valid": False, "target": target, "start": self._start}

    def click(self, target: dict) -> bool:
        """Process a click. Returns True if accepted, False if rejected (no-op)."""
        kind = target.get("kind") if target else None

        if kind == "vertex":
            vid = target.get("vertex_id")
            if vid is None or not self._mesh.is_valid_vertex(vid):
                return False
            if self._start is None:
                # First click — set start, no mesh mutation
                self._push_step()
                self._start = vid
                return True
            # Connect start → vid (push step BEFORE mutation so undo restores pre-click state)
            self._push_step()
            eid = connect_in_shared_face(self._mesh, self._start, vid)
            if eid is None:
                self._step_stack.pop()  # nothing changed — discard the step
                return False
            self._path_edges.append(eid)
            self._start = vid
            return True

        if kind == "edge":
            eid = target.get("edge_id")
            t = target.get("t", 0.5)
            if eid is None or not self._mesh.is_valid_edge(eid):
                return False
            if not (0.0 < t < 1.0):
                return False

            if self._start is None:
                # First click on edge — split at t, start = new vertex
                self._push_step()
                new_v, _, _ = self._mesh.split_edge(eid, t)
                self._start = new_v
                return True

            # With start: edge must not be incident to start, and must share a face with start
            va, vb = self._mesh.edge_vertices(eid)
            if va == self._start or vb == self._start:
                return False
            start_faces = set(
                f for e in self._mesh.vertex_edges(self._start)
                for f in self._mesh.edge_faces(e)
            )
            edge_faces = set(self._mesh.edge_faces(eid))
            if not (start_faces & edge_faces):
                return False

            # Save step state before any mutation for this click
            self._push_step()
            new_v, _, _ = self._mesh.split_edge(eid, t)
            conn_eid = connect_in_shared_face(self._mesh, self._start, new_v)
            if conn_eid is None:
                # Unexpected failure — restore the step we just pushed
                step = self._step_stack.pop()
                self._mesh.load_state(step.state_before)
                self._start = step.start_before
                self._path_edges = list(step.path_edges_before)
                return False
            self._path_edges.append(conn_eid)
            self._start = new_v
            return True

        return False

    def _push_step(self) -> None:
        self._step_stack.append(_KnifeStep(
            state_before=self._mesh.export_state(),
            start_before=self._start,
            path_edges_before=list(self._path_edges),
        ))

    def undo_step(self) -> bool:
        """Remove the most recent cut step. Returns True if a step was undone."""
        if not self._step_stack:
            return False
        step = self._step_stack.pop()
        self._mesh.load_state(step.state_before)
        self._start = step.start_before
        self._path_edges = list(step.path_edges_before)
        return True

    def _on_update(self, **kwargs) -> None:
        pass

    def _on_commit(self) -> Any:
        """Commit the session. Returns MeshStateCommand or None if nothing changed."""
        current_state = self._mesh.export_state()
        if current_state == self._session_before:
            return None

        # Filter path_edges to only currently valid edges
        valid_path = [e for e in self._path_edges if self._mesh.is_valid_edge(e)]

        cmd = MeshStateCommand(
            mesh=self._mesh,
            before_state=self._session_before,
            after_state=current_state,
            description="Knife",
        )
        self._scene.history.push(cmd)

        # Residue (AD-017, DECIDED): select the connecting-edge path, switch to Edge mode
        self._selection.mode = SelectionMode.EDGE
        self._selection.clear()
        self._selection.add(set(valid_path))

        return cmd

    def _on_cancel(self) -> None:
        """Restore pre-session state. Nothing pushed to history."""
        self._mesh.load_state(self._session_before)
        self._step_stack.clear()
        self._path_edges = []
        self._start = None
