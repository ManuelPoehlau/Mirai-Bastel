# Artist Input Truth (archived 2026-10-28)

Archived by Manu's decision of 2026-10-28 ([AD-013 addendum 2026-10-28](../../architecture/AD-013-CAPABILITY-PROMOTION-UX-OWNERSHIP.md#addendum-2026-10-28-the-active-bindingset-is-the-single-input-truth-manus-keymap-in-the-repo)):
the active BindingSet is the single source of input truth - code defaults (engineering, `PROVISIONAL`) under Manu's
repo-tracked [`config/keymap.json`](../../../config/keymap.json).

| File | Was | Note |
|---|---|---|
| [`Input_Mapping_Tool/`](Input_Mapping_Tool/) | `tools/Input_Mapping_Tool/` — Tkinter tool to record the Artist Input Truth | never runtime input |
| [`Input_Mapping_Tool/artist_input_truth.json`](Input_Mapping_Tool/artist_input_truth.json) | the Artist Input Truth (`artistTruthVersion` 1) | partly stale; historical reference only |
| [`INPUT_WIRING_MAP.md`](INPUT_WIRING_MAP.md) | `docs/design/INPUT_WIRING_MAP.md` — Manu's desired bindings, Playground input map (2026-09-18) | partly stale; historical reference only |

Historical reference, not a competing specification: a binding is Manu's when it is in `config/keymap.json`. The
addendum lists which documented decisions went into that file and which code defaults stay `PROVISIONAL`.
