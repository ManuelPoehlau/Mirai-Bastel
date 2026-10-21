"""AD-023 stage 2 + AD-022 for **Delete and its Undo / Redo only**, installed from the outside.

Nothing under `src/` is changed. `install(spec)` installs stage 1 (`topology_sync_stage1`, all four switches:
V0, V2, V3, H0 - every other op keeps that path) and then the stage-2 switches on top:

- `H1` - Delete (Entf in vertex, edge and face mode, no symmetry definition) records a `delta.DeltaCommand`
  instead of two whole-mesh snapshots; Undo / Redo apply the delta (`delta.py`).
- `V1` - the viewport patches its buffers from the delta's touched set instead of a full topology sync, also on
  Undo / Redo of the Delete (`render_patch.py`). Needs `H1` (the touched set comes from the delta).
- `GPU` - AD-022 B2-out: hover and click in face and vertex mode pick from an ID render of the `RenderMesh`
  buffers instead of the CPU `PickCache` (`gpu_pick.py`); edge mode and every other picker stay on the CPU.

`all` = `H1,V1,GPU`; `stage1` = stage 1 only (the reference of the previous measurement); `none` = today's code.
A Delete under a symmetry definition, Dissolve and every other op take the unchanged (stage-1) path.

The Undo path learns that the undone entry was a delta from the command itself (`DeltaCommand.on_applied`),
i.e. AD-023 U option (a)-like: no `HistoryStack` accessor (frozen Core) is needed.
"""

from __future__ import annotations

from topology_sync_stage1 import stage1

from topology_stage2_delete import delta as delta_mod
from topology_stage2_delete import gpu_pick, render_patch

ALL = ("H1", "V1", "GPU")
_originals: dict = {}
_active: frozenset = frozenset()
_stage1_on = False


def parse(spec: str) -> tuple[bool, frozenset]:
    """-> (stage 1 installed, stage-2 switches). `none`, `stage1`, `all` or a list like `H1,V1`."""
    s = spec.strip().lower()
    if s in ("none", "off", ""):
        return False, frozenset()
    if s == "stage1":
        return True, frozenset()
    if s == "all":
        return True, frozenset(ALL)
    parts = {p.strip().upper() for p in spec.split(",") if p.strip()}
    unknown = parts - set(ALL)
    if unknown:
        raise ValueError(f"unknown stage-2 switch(es): {sorted(unknown)}; known: {', '.join(ALL)}, stage1, none")
    if "V1" in parts and "H1" not in parts:
        raise ValueError("V1 needs H1 (the touched set comes from the delta)")
    return True, frozenset(parts)


def label(spec: str) -> str:
    on, switches = parse(spec)
    if not on:
        return "none"
    return "stage1" + ("+" + ",".join(s for s in ALL if s in switches) if switches else "")


def active() -> frozenset:
    return _active


# -- Application: Delete through a delta ------------------------------------------------------------------------


def _removal_command_h1(self, command: str) -> bool:
    import mirai.application as application
    from core.selection import SelectionMode

    original = _originals["_removal_command"]
    dissolve, _cleanup = application._REMOVAL_COMMANDS[command]
    selection, mesh = self.selection, self.scene.mesh
    mode = selection.mode
    ids = {SelectionMode.VERTEX: selection.vertices, SelectionMode.EDGE: selection.edges,
           SelectionMode.FACE: selection.faces}.get(mode)
    if dissolve or not ids or mesh.symmetry_definition is not None:
        return original(self, command)
    label_text = application.removal_label(mode, dissolve=False, cleanup=False)
    selection_before = self._selection_snapshot()
    try:
        delta, _ = delta_mod.capture_removal(
            mesh, mode, ids,
            lambda: application.apply_removal(mesh, mode, set(ids), dissolve=False, cleanup=False))
    except application.RemovalRefused as exc:
        self._set_status(f"{label_text}: {exc}")
        return False
    if delta.empty:
        self._set_status(f"{label_text}: nothing to do")
        return False
    self.history.push(delta_mod.DeltaCommand(mesh, delta, label_text, on_applied=self._stage2_delta_applied))
    selection.clear()
    self._record_selection_history(selection_before)
    self._pick_cache.invalidate()
    self._stage2_notify(delta, True)
    self._soft_preview_refresh()
    self._refresh_hover()
    self._set_status(label_text)
    return True


def _stage2_notify(self, delta, forward: bool) -> None:
    if self.viewport is None:
        return
    if "V1" in _active:
        self.viewport.on_topology_delta(delta, forward)
    else:
        self.viewport.on_topology_changed()


def _stage2_delta_applied(self, delta, forward: bool) -> None:
    self.__dict__["_stage2_last_delta"] = (delta, forward)


def _undo_redo_h1(self, command: str) -> bool:
    """`Application._undo_redo` with one change: an undone / redone delta notifies the viewport with its
    touched set (V1) instead of `on_topology_changed()`."""
    from mirai.interaction import commands

    can = self.history.can_undo() if command == commands.UNDO else self.history.can_redo()
    if not can:
        self._set_status(f"{command}: nothing to {command.lower()}")
        return False
    self.__dict__["_stage2_last_delta"] = None
    self.dispatch_command(command)
    if self._last_undo_redo_mesh_step:
        self._pick_cache.invalidate()
        last = self.__dict__.get("_stage2_last_delta")
        if last is not None:
            self._stage2_notify(*last)
        elif self.viewport is not None:
            self.viewport.on_topology_changed()
    self._set_status(command)
    self._refresh_hover()
    return True


def _pick_gpu(self, x: float, y: float):
    picker = self.__dict__.get("_stage2_gpu")
    if picker is None:
        picker = self.__dict__["_stage2_gpu"] = gpu_pick.GpuPicker()
    hit = picker.pick(self, x, y)
    if hit is gpu_pick.GpuPicker.CPU:
        return _originals["_pick"](self, x, y)
    return hit


# -- install / uninstall --------------------------------------------------------------------------------------


def install(spec: str) -> frozenset:
    global _active, _stage1_on
    from mirai.application import Application

    uninstall()
    on, switches = parse(spec)
    if on:
        stage1.install("all")
        _stage1_on = True
    patches = []
    if "H1" in switches:
        patches += [("_removal_command", _removal_command_h1), ("_undo_redo", _undo_redo_h1),
                    ("_stage2_notify", _stage2_notify), ("_stage2_delta_applied", _stage2_delta_applied)]
    if "GPU" in switches:
        patches.append(("_pick", _pick_gpu))
    for name, fn in patches:
        _originals[name] = Application.__dict__.get(name)
        setattr(Application, name, fn)
    if "V1" in switches or "GPU" in switches:
        # GPU reads the slot tables of render_patch; without V1 they simply never see a dead slot.
        render_patch.install()
    _active = switches
    return switches


def uninstall() -> None:
    global _active, _stage1_on
    from mirai.application import Application

    for name, original in _originals.items():
        if original is None:
            delattr(Application, name)
        else:
            setattr(Application, name, original)
    _originals.clear()
    render_patch.uninstall()
    if _stage1_on:
        stage1.uninstall()
        _stage1_on = False
    _active = frozenset()


def reset_stats() -> None:
    stage1.reset_stats()
    render_patch.reset_stats()
    gpu_pick.reset_stats()


def stats_text() -> str:
    return "\n".join((
        "  stage 1: " + stage1.STATS.text(),
        "  V1:      " + render_patch.STATS.text(),
        "  GPU:     " + gpu_pick.STATS.text(),
    ))
