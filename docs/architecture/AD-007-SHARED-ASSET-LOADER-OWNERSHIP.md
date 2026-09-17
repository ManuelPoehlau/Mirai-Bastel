# AD-007 — Shared Asset & Loader Ownership (Head Basemesh + OBJ Loader)

**Status:** DECIDED ✓ (ownership model and destination both confirmed)
**Date:** 2026-09-17
**Owner:** Manu (Project Owner)
**Scope:** `experiments/rigging-skinning-morphing/meshes/head_basemesh.obj` (+ `.mtl`, `.blend`),
`experiments/rigging-skinning-morphing/loaders/obj_loader.py`

---

## Question

Who owns the head basemesh asset and its OBJ loader — the rigging experiment (where they
physically live today), the Playground (which is the only thing that loads them at runtime), or a
neutral shared location? Both are referenced by three independent path constants
(`rigging/viewport_adapter.py`, `lab/_paths.py`, `playground/_paths.py`) pointing at the same file.

(Full evidence base: `docs/Ownershi_Lifecycle_Audit_V1_Integration_Lab_Playground.md` §10, Q-C/Q-D;
`docs/FINAL_AUDIT _shared_Infrastructure.md` F-1, F-6.)

## Decision

**Option C — neutraler, geteilter Ort.** Weder der Playground noch das Rigging-Experiment ist
Eigentümer des Kopf-Assets oder des Loaders.

Artist's own reasoning (verbatim in intent): the head does not "belong" to the Playground and does
not belong to the rigging experiment either — it is used by both, so it should not be filed under
either one. Made as a gut call, with explicit acknowledgment that the technical trade-offs between
options A/B/C were hard to weigh from the artist's side.

## Concretization (confirmed 2026-09-17)

The repository already declares a structural placeholder for exactly this purpose:
[`examples/`](../../examples/README.md) — *"Beispielmodelle und kleine reproduzierbare Szenarien
für Entwicklung und Tests"* — currently empty except for its README. Using it avoids inventing a
new top-level location (consistent with the project's "implement little, assume much" principle
and the Shared-Infrastructure audit's caution against inventing new structural layers for small
pieces).

- **Asset** (`head_basemesh.obj` + `.mtl` companion; `.blend` source stays wherever is easiest —
  it's provenance, not consumed by code) → `examples/`
- **Loader** (`obj_loader.py`, ~60 LOC, zero Core/Viewport/pyglet coupling) → travels with the
  asset, rather than staying behind in rigging alone. Splitting loader and asset ownership would
  recreate the same "two owners for one chain" problem this decision exists to resolve (Playground's
  load path is Helper → Loader → Asset).

Exact subfolder layout inside `examples/` (flat vs. `examples/meshes/` + `examples/loaders/`, etc.)
is an implementation detail, not a product decision — to be settled at execution time.

## Consequences (not yet executed)

1. **No files are moved by this entry.** Per explicit instruction, all physical moves from this and
   the other AD-00x decisions are batched into one cleanup pass at the end, not executed
   incrementally.
2. When executed: all three existing path constants (`rigging/viewport_adapter.py:48`,
   `lab/_paths.py:40`, `playground/_paths.py:45`) need updating to the new location.
3. Rigging remains free to *use* the asset as a research subject (it is still active research per
   `CHARACTER_SYSTEMS_RESEARCH.md`) — this decision only changes where the file lives, not who may
   read it.
4. The loader's documented zero-dependency contract (no Core/Viewport/pyglet imports) should be
   preserved at its new location — that property is *why* it was shareable in the first place.
5. This is independent of `AD-006` (V1 Viewport retirement) but lands in the same batched cleanup
   pass, since both touch `experiments/rigging-skinning-morphing/`.
