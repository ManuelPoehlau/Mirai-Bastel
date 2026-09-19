# Input Binding Config — Artist Truth

**Status:** Experimental / isolated tool. Not wired into the Mirai-Bastel runtime.
**Scope:** Capture Manu's *desired* interaction language for Mirai-Bastel as
explicit, versionable data — independent of what the current implementation
happens to do.

## What this is

A small, standalone Tkinter application. You select a function ("Move",
"Extrude", "Orbit", …), press a key or mouse combination, and that binding
is recorded as **Artist Truth** — regardless of what the current runtime
does with that same key today.

```
Artist Truth
    transform.move
          |
    future translation (does not exist yet)
          |
    runtime command "Move"
```

This tool only produces the top layer. The translation step is future work
and is explicitly out of scope here.

## What this is NOT

- **Not** a hotkey editor for the running application. Nothing here is read
  by `src/mirai/interaction/`, `playground/`, or any `keymap.json`.
- **Not** a runtime validator. If you assign the same key to two different
  functions, it is reported as a conflict but **always accepted** — this is
  a design tool, not a constraint checker.
- **Not** a replacement for `INPUT_WIRING_MAP.md`. That document is left
  untouched by this tool. Whether the two should later be merged, whether
  one should generate the other, or whether they stay separate is an open
  question to decide once this tool has proven useful — not decided here.

## Semantic IDs are self-owned

Every function has a stable dotted id such as `transform.move`,
`topology.extrude`, `selection.set_vertex_mode`. These ids belong to this
tool (`inventory.py`), not to `src/mirai/interaction/commands.py`.

Where a matching production command currently exists, its name is stored
as `runtime_ref` — purely informational, shown in the UI as a reference
column, never imported or validated against the actual module. A function
with `runtime_ref: null` (not yet implemented anywhere) is fully usable.
If the runtime vocabulary is renamed or restructured later, this file does
not need to change.

## Files

| File | Purpose |
|---|---|
| `app.py` | The Tkinter GUI. Run with `python app.py`. |
| `inventory.py` | Initial seed list of artist-facing functions (id, label, category, optional `runtime_ref`). Pure data, no runtime imports. |
| `storage.py` | Loads/saves `artist_input_truth.json`. Adds newly-introduced `inventory.py` entries on load without ever deleting or overwriting an existing binding. |
| `artist_input_truth.json` | **The actual Artist Truth data.** Created automatically on first run. This is the file to commit/version. |

## Running it

```
cd tools/input_binding_config
python app.py
```

Requires only the Python standard library (`tkinter`), no extra
dependencies.

## Using it

1. Click a function row (or use the search box to find one).
2. Click **"Bindung erfassen"** (or double-click the row, or press Enter).
3. Press the desired key or mouse combination. `Esc` cancels.
4. The binding is saved immediately to `artist_input_truth.json`.

Conflicts (the same binding assigned to more than one function) are shown
inline in the row (highlighted) and summarized at the bottom of the window.
They are informational only — nothing is blocked.

## `artist_input_truth.json` shape

```json
{
  "artistTruthVersion": 1,
  "note": "...",
  "bindings": [
    {
      "id": "transform.move",
      "label": "Move",
      "category": "Transform",
      "binding": "W",
      "runtime_ref": "Move",
      "notes": ""
    }
  ]
}
```

## Explicitly out of scope for this tool

Per the implementation decision this tool was built under:

- `src/mirai/interaction/commands.py`, `bindings.py`, `input.py`
- `playground/window.py`, `playground/input_adapter.py`, `playground/command_handler.py`
- any `keymap.json` (production keymap format/loader)
- `INPUT_WIRING_MAP.md`

None of these are read, imported, or modified by this tool.

## Function inventory — deliberately excluded categories

`inventory.py` does not include "Transform Interaction Variants" (Tweak
V1–V4 etc.) or "Experiment / Playground Controls" (KEEP/ITERATE/REJECT,
variant cycling). Those are active Three-Role-UX-System / Playground
research surfaces, not stable artist-facing product functions.
