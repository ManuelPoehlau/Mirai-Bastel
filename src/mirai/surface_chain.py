"""The viewport's replacement surface as a chain of stages (AD-025 Phase 4, the §11 "evaluation location
and chain"; H5b: morph + SubD shown together). Names `PROVISIONAL`.

Before Phase 4 the viewport had one H7 slot (`Viewport.set_surface_provider`) and its two hosts, the morph
mix and the SubD preview, took turns: whoever held it kept it. The chain replaces the turn-taking without
changing the viewport: it is an additive layer *above* the H7 contract.

- **Stages** are ordinary H7 providers in a fixed order (the app's: morph, then SubD). A stage's input is
  the edit mesh, or the `surface_mesh` of the nearest earlier stage that has one — so SubD's stencils run
  on the mixed cage `b + Σ wᵢ·dᵢ` (its `sync(mesh, …)` simply attaches to that mesh and follows its
  journal; the SubD provider is unchanged). The chain's output is the last stage with a surface: a SubD
  surface, or the mix when SubD is off or refuses the topology (never a stale or wrong surface).
- **One wanted stage** sits in the slot itself, exactly as before (`viewport.surface_provider is
  subdivision.provider` with SubD alone; the morph provider with the mix alone) — every Phase 3 and SubD
  behaviour stays as it was without the other. **Two or more** sit in the slot as one `ChainedSurface`,
  which forwards the H7 attributes of its output stage (`replaces_wire`, `wire_follows_surface`,
  `surface_topology_changed`, the hidden faces and region tints) and the H7-E entry surfaces of every
  stage (the morph mix of the base beside its editing view).
- **Foreign hosts** (a lab that sets its own provider) keep the slot: the chain never replaces a provider
  it did not set, and `holds` / `can_take` say so to the stages, which report it as before.

Picking, selection, hover and every tool stay on the edit mesh (the rest-shape cage): the viewport never
picks on a replacement surface (H7), and no stage writes a scene mesh.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Optional


class ChainedSurface:
    """H7 provider of two or more stages (module docstring)."""

    def __init__(self, stages: Sequence) -> None:
        self.stages = tuple(stages)
        self.surface_mesh = None
        self._out = None

    @property
    def output_stage(self):
        """The stage whose surface the viewport draws (None = the edit mesh's own faces)."""
        return self._out

    def sync(self, mesh, selection) -> set:
        source, moved, out = mesh, set(), None
        for stage in self.stages:
            stage_moved = stage.sync(source, selection)
            if stage.surface_mesh is not None:
                source, moved, out = stage.surface_mesh, stage_moved, stage
        self._out = out
        self.surface_mesh = None if out is None else source
        return moved if out is not None else set()

    @property
    def dirty(self) -> bool:
        return any(getattr(stage, "dirty", False) for stage in self.stages)

    @dirty.setter
    def dirty(self, value: bool) -> None:
        for stage in self.stages:
            stage.dirty = value

    def _of_output(self, name: str, default):
        return getattr(self._out, name, default) if self._out is not None else default

    @property
    def surface_topology_changed(self) -> bool:
        return bool(self._of_output("surface_topology_changed", False))

    @property
    def replaces_wire(self) -> bool:
        return bool(self._of_output("replaces_wire", False))

    @property
    def wire_follows_surface(self) -> bool:
        return bool(self._of_output("wire_follows_surface", False))

    def _merged(self, name: str, empty):
        out = empty()
        for stage in self.stages:
            value = getattr(stage, name, None)
            if value:
                out.update(value)
        return out

    @property
    def entry_surfaces(self) -> dict:
        return self._merged("entry_surfaces", dict)

    @property
    def entry_moved(self) -> dict:
        return self._merged("entry_moved", dict)

    @property
    def entry_topology_changed(self) -> set:
        return self._merged("entry_topology_changed", set)

    def set_hidden(self, vertex_ids) -> None:
        for stage in self.stages:
            if hasattr(stage, "set_hidden"):
                stage.set_hidden(vertex_ids)

    @property
    def hidden_key(self):
        return (id(self._out), self._of_output("hidden_key", None))

    def hidden_surface_faces(self) -> frozenset:
        faces = self._of_output("hidden_surface_faces", None)
        return faces() if faces is not None else frozenset()

    def surface_face_tints(self, control_tints) -> dict:
        tints = self._of_output("surface_face_tints", None)
        return tints(control_tints) if tints is not None else {}


class SurfaceChain:
    """The app's coordinator of the viewport's H7 slot (module docstring). Stages say whether they want
    to be shown (`want`); the chain puts the right provider in the slot."""

    def __init__(self, stages: Sequence) -> None:
        self.stages = tuple(stages)
        self.viewport = None
        self._wanted: set = set()
        self._composite: Optional[ChainedSurface] = None

    def attach(self, viewport) -> None:
        """A new viewport: nothing is wanted yet (the stages say so again when they attach)."""
        self.viewport = viewport
        self._wanted = set()
        self._composite = None

    def _ours(self, provider) -> bool:
        return provider is None or provider is self._composite or provider in self.stages

    def can_take(self, stage) -> bool:
        """True when the slot is free or the chain's own (a foreign host keeps it)."""
        return self.viewport is None or self._ours(self.viewport.surface_provider)

    def want(self, stage, wanted: bool) -> bool:
        """Stage `stage` wants to be shown (or not any more); returns `holds(stage)`."""
        if wanted:
            self._wanted.add(stage)
        else:
            self._wanted.discard(stage)
        self._apply()
        return self.holds(stage) if wanted else False

    def wanted(self, stage) -> bool:
        return stage in self._wanted

    def later_stage_wanted(self, stage) -> bool:
        """True when a stage after `stage` is wanted (it reads `stage`'s surface)."""
        later = self.stages[self.stages.index(stage) + 1:]
        return any(s in self._wanted for s in later)

    def active(self) -> tuple:
        return tuple(s for s in self.stages if s in self._wanted)

    def provider(self):
        """What the slot should hold for the wanted stages (None, one stage, or the composite)."""
        active = self.active()
        if not active:
            return None
        if len(active) == 1:
            return active[0]
        if self._composite is None or self._composite.stages != active:
            self._composite = ChainedSurface(active)
        return self._composite

    def holds(self, stage) -> bool:
        """True when `stage` is shown: wanted and the slot holds the chain's provider with it."""
        vp = self.viewport
        if vp is None or stage not in self._wanted:
            return False
        current = vp.surface_provider
        return current is stage or (isinstance(current, ChainedSurface) and current is self._composite and stage in current.stages)

    def _apply(self) -> None:
        vp = self.viewport
        if vp is None or not self._ours(vp.surface_provider):
            return
        target = self.provider()
        if vp.surface_provider is not target:
            vp.set_surface_provider(target)
