# AD-008 — Import, Mesh Geometry Queries & Camera Framing Become Production Capabilities

**Status:** DECIDED ✓ (ownership decided; exact module split left to execution time)
**Date:** 2026-09-17
**Owner:** Manu (Project Owner)
**Scope:** `src/mirai/` (new/extended), consumers in `experiments/mirai_bastel_integration_lab/adapters/obj_to_core.py`
and `experiments/rigging-skinning-morphing/viewport_adapter.py`, runtime consumer `playground/app.py`

---

## Question

Are OBJ→Scene construction, mesh geometry queries (`bounds`/`center`/`radius`), and camera framing
("zoom/fit to object") production/system capabilities that belong in `src/`, or are they Playground
research conveniences that should stay where they are (currently duplicated identically in two
experiment adapters)?

(Full evidence base: `docs/FINAL_AUDIT _shared_Infrastructure.md` §1 Q3, D-1/D-2/D-3, F-2/F-3/F-4/F-5.)

## Decision

**A — Produktion. Definitiv, keine Nice-to-haves.**

All three capabilities are accepted as production/system concerns, not experiment-local
convenience. Artist's own framing: these are not optional extras, they're needed regardless of
which application ends up using them.

## What moves where (destination confirmed at the cluster level; exact module split is an
execution-time implementation detail, not re-litigated here)

- **Mesh geometry queries** (`mesh_bounds`, `mesh_center_and_radius`) → `src/mirai/scene_factory.py`
  or a small sibling module next to it.
- **Camera framing** (`frame_camera_on_bounds`) → a method on `OrbitCamera`
  (`src/mirai/viewport/camera.py`) or a free function alongside it in `src/mirai/viewport/`.
- **OBJ→Scene construction** (`obj_data_to_core_mesh`, `obj_data_to_core_scene`,
  `build_core_scene_from_obj`) → `src/mirai/scene_factory.py`, next to the existing `create_cube`/
  `build_cube_scene`. Its own docstring already anticipates this: *"Baut ausschließlich über die
  öffentliche Core-Mutation-API … genau wie ein späteres Import-System das tun würde — deshalb liegt
  der Factory-Code in `mirai` und nicht im (gefrorenen) Core."*
- The **OBJ loader itself** (pure parser) is not re-decided here — see `AD-007`
  (moves to `examples/`, shared, not production).

## Consequences (not yet executed — batched into the end-of-round cleanup pass)

1. Two existing duplicate implementations (Lab `adapters/obj_to_core.py`,
   rigging `viewport_adapter.py`) become candidates for deletion once the production versions exist
   and both experiments are repointed at them. Not executed by this entry.
2. `playground/app.py` (`load_head()`, `_frame_camera`) becomes a consumer of `src/mirai` instead of
   the Lab adapter — removes one of the Playground's remaining experiment dependencies.
3. `docs/future_ideas/VIEWPORT_NAVIGATION.md`'s "Zoom to Object / Orbit around Object" entry moves
   from *deferred idea* to *implemented* once this lands — update at execution time, not now.
4. `src/core` is **not** touched by this decision — `Mesh` stays query/mutation-only per its
   documented freeze. `bounds`/`center`/`radius` operate on the Core's public query API from
   `src/mirai`, same pattern as `scene_factory.py` already uses.
5. The rigging adapter's dependency on the Core-V1 fork (`mirai_bastel_core`, not `src.core`) is a
   separate, still-open question (referenced in `AD-006`) — this decision does not resolve which
   Core the rigging experiment's own copy targets, only that the *production-core* version of these
   helpers now has a home in `src/`.
