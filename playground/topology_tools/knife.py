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
        print("[KNIFE] session begin (start=none, path_edges=0, state captured)")

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
        # Temporary [KNIFE] diagnosis logging (AD-017 edge targeting)
        print(f"[KNIFE] current_start={'none' if self._start is None else f'vertex:{int(self._start)}'} "
              f"target_kind={kind}")

        if kind == "vertex":
            vid = target.get("vertex_id")
            if vid is None or not self._mesh.is_valid_vertex(vid):
                print(f"[KNIFE] rejected: vertex target not a valid vertex ({vid!r})")
                return False
            if self._start is None:
                # First click — set start, no mesh mutation
                self._push_step()
                self._start = vid
                print(f"[KNIFE] current_start=vertex:{int(vid)} (first click, no mesh mutation)")
                return True
            # Connect start → vid (push step BEFORE mutation so undo restores pre-click state)
            self._push_step()
            eid = connect_in_shared_face(self._mesh, self._start, vid)
            if eid is None:
                self._step_stack.pop()  # nothing changed — discard the step
                print(f"[KNIFE] connect FAILED vertex:{int(self._start)} -> vertex:{int(vid)} "
                      f"(no shared face or adjacent in all shared faces)")
                return False
            prev_start = self._start
            self._path_edges.append(eid)
            self._start = vid
            print(f"[KNIFE] connect vertex:{int(prev_start)} -> vertex:{int(vid)} new edge:{int(eid)}; "
                  f"path_edges={len(self._path_edges)}; current_start=vertex:{int(vid)}")
            return True

        if kind == "edge":
            eid = target.get("edge_id")
            t = target.get("t", 0.5)
            if eid is None or not self._mesh.is_valid_edge(eid):
                print(f"[KNIFE] EdgePoint resolution FAILED — edge target not a valid edge ({eid!r})")
                return False
            if not (0.0 < t < 1.0):
                print(f"[KNIFE] EdgePoint resolution FAILED — t={t!r} not in (0.0, 1.0)")
                return False
            print(f"[KNIFE] resolving EdgePoint edge:{int(eid)} t={t:.6f}")

            if self._start is None:
                # First click on edge — split at t, start = new vertex
                self._push_step()
                try:
                    new_v, _, _ = self._mesh.split_edge(eid, t)
                except Exception as exc:
                    print(f"[KNIFE] split_edge FAILED edge:{int(eid)} t={t:.6f}: "
                          f"{type(exc).__name__}: {exc}")
                    raise
                self._start = new_v
                print(f"[KNIFE] split_edge -> vertex:{int(new_v)}; "
                      f"current_start=vertex:{int(new_v)} (first click on edge)")
                return True

            # With start: edge must not be incident to start, and must share a face with start
            va, vb = self._mesh.edge_vertices(eid)
            if va == self._start or vb == self._start:
                print(f"[KNIFE] rejected: edge:{int(eid)} is incident to current_start vertex:{int(self._start)}")
                return False
            start_faces = set(
                f for e in self._mesh.vertex_edges(self._start)
                for f in self._mesh.edge_faces(e)
            )
            edge_faces = set(self._mesh.edge_faces(eid))
            if not (start_faces & edge_faces):
                print(f"[KNIFE] rejected: edge:{int(eid)} (faces={sorted(int(f) for f in edge_faces)}) "
                      f"shares no face with current_start vertex:{int(self._start)} "
                      f"(faces={sorted(int(f) for f in start_faces)})")
                return False

            # Save step state before any mutation for this click
            self._push_step()
            try:
                new_v, _, _ = self._mesh.split_edge(eid, t)
            except Exception as exc:
                print(f"[KNIFE] split_edge FAILED edge:{int(eid)} t={t:.6f}: "
                      f"{type(exc).__name__}: {exc}")
                raise
            print(f"[KNIFE] split_edge -> vertex:{int(new_v)} (edge:{int(eid)} t={t:.6f})")
            conn_eid = connect_in_shared_face(self._mesh, self._start, new_v)
            if conn_eid is None:
                # Unexpected failure — restore the step we just pushed
                step = self._step_stack.pop()
                failed_start = step.start_before
                self._mesh.load_state(step.state_before)
                self._start = step.start_before
                self._path_edges = list(step.path_edges_before)
                print(f"[KNIFE] connect FAILED vertex:{'none' if failed_start is None else int(failed_start)} "
                      f"-> vertex:{int(new_v)} (edge split rolled back)")
                return False
            prev_start = self._start
            self._path_edges.append(conn_eid)
            self._start = new_v
            print(f"[KNIFE] connect vertex:{int(prev_start)} -> vertex:{int(new_v)} new edge:{int(conn_eid)}; "
                  f"path_edges={len(self._path_edges)}; current_start=vertex:{int(new_v)}")
            return True

        print(f"[KNIFE] rejected: unsupported target kind={kind!r} (no cut)")
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
            print("[KNIFE] undo_step: nothing to undo")
            return False
        step = self._step_stack.pop()
        self._mesh.load_state(step.state_before)
        self._start = step.start_before
        self._path_edges = list(step.path_edges_before)
        print(f"[KNIFE] undo_step: restored; "
              f"current_start={'none' if self._start is None else f'vertex:{int(self._start)}'}; "
              f"path_edges={len(self._path_edges)}")
        return True

    def _on_update(self, **kwargs) -> None:
        pass

    def _on_commit(self) -> Any:
        """Commit the session. Returns MeshStateCommand or None if nothing changed."""
        current_state = self._mesh.export_state()
        if current_state == self._session_before:
            print(f"[KNIFE] commit: state unchanged (session_before == now, "
                  f"path_edges={len(self._path_edges)}) -> no history, no cut")
            return None

        # Filter path_edges to only currently valid edges
        valid_path = [e for e in self._path_edges if self._mesh.is_valid_edge(e)]
        print(f"[KNIFE] commit: state changed; path_edges={len(self._path_edges)} "
              f"valid_connecting_edges={[int(e) for e in valid_path]} -> 1 history entry")

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
        print(f"[KNIFE] cancel: restoring pre-session state; path_edges={len(self._path_edges)} discarded")
        self._mesh.load_state(self._session_before)
        self._step_stack.clear()
        self._path_edges = []
        self._start = None
