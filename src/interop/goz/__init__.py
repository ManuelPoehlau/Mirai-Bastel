"""Mirai <-> ZBrush 2022.0.8 over GoZ (AD-029, P1: positions of one object with unchanged topology).

Modules (pure before effectful, audit §6.1):

- `format`   strict reader / minimal writer of the `.GoZ` binary format (stdlib only)
- `files`    GoZ folders and text files, atomic writes, the completeness rule (stdlib only)
- `helper`   what ZBrush's `Edit.bat` runs: snapshot + ticket into Mirai's inbox (stdlib only)
- `install`  the `GoZApps\\Mirai` registration (D12), only on the artist's explicit command (stdlib only)
- `manifest` the transfer manifest and the return-conflict fingerprint (core)
- `names`    Mirai's own SubTool names, stable over Mirai and ZBrush restarts (stdlib only)
- `bridge`   send (mesh -> file + manifest) and the return plan (core; no mutation)

The one mutating step is `Application.apply_goz_return` (one Undo step through `_mesh_transaction`).
"""
