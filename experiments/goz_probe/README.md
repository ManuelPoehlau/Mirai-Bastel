# E1 — GoZ handshake probe (ZBrush 2022.0.8 ↔ Python)

**Status:** DONE (2026-11-05, run on the reference PC; result §11). Was: ready to run, Approved by Manu (audit D10, commit `882b208`);
procedure confirmed by Manu 2026-11-05. The probe tools of §5 are written and tested headlessly in the container (§5.1).
Their Windows-only parts are reviewed but untested until the run.
**Type:** isolated experiment for one material uncertainty (AGENTS.md §7a): does GoZ in ZBrush 2022.0.8 behave as the
official SDK describes, and can Mirai be a GoZ target application?
**Parent:** [ZBrush bridge audit](../../docs/future_ideas/ZBRUSH_BRIDGE_AUDIT.md) (Phase 0, accepted at `73683d8`),
§8.1 (E1), §9.3 (Q1–Q6), §10.3 (D8).
**Not in scope:** any `src/` change, the Production bridge (P1), every optional attribute (polypaint, mask, groups,
UVs, maps), n-gons, multiple SubTools in one transfer.

> Boundary: probe code lives only in this folder. It may **read** `src/` (`core`, `mirai.scene_factory`,
> `mirai.obj_export`) to build the Mirai-like test mesh. Nothing in `src/` imports it. No GoB code (GPL) and no SDK
> source (Pixologic, all rights reserved) is copied. The format code is written from the facts in §2.

---

## Kurzfassung für Manu (Deutsch)

- **Worum es geht:** ein kleiner Handshake-Test auf deinem Windows-PC, ca. 40 Minuten. Er klärt, ob Mirai sich als
  GoZ-Ziel bei ZBrush 2022.0.8 eintragen kann, wie ZBrush das Ziel startet, und ob Dateien, Achsen, Maßstab und die
  Reihenfolge der Punkte und Flächen so ankommen, wie das offizielle SDK es beschreibt.
- **Von Maxon brauchst du nichts herunterzuladen.** Alles, was der Test aufruft, liefert ZBrush 2022.0.8 selbst mit. Das
  offizielle GoZ SDK 2022.0 habe ich gelesen (§2). Es kommt wegen seiner Lizenz nicht ins Repository.
- **Mirai selbst wird nicht angefasst.** Der Test benutzt eigene kleine Python-Skripte in diesem Ordner und einen
  Probe-Eintrag „Mirai Probe (E1)“ in ZBrushs GoZ-Liste, den du danach wieder löschen kannst.
- **Ablauf:** §6. Bestandsaufnahme → Probe-App eintragen → ZBrush → Python → laufendes Programm benachrichtigen →
  Python → ZBrush → kleine Änderung in ZBrush zurück. Am Ende schickst du den Ordner `captures/` (Commit) und die
  ausgefüllte Tabelle §9.
- **Deine Beteiligung:** §10.

---

## 1. Questions E1 answers

| # | Question | Decides |
|---|---|---|
| E1-Q1 | Can a folder `GoZApps/<App>/` with `.bat` commands register a Python program as a GoZ target in 2022.0.8? | D8, P1 architecture |
| E1-Q2 | How does ZBrush launch `EDIT_COMMAND` (arguments, working directory, environment, does it wait for it to exit)? | the helper's design |
| E1-Q3 | Can the launched helper notify an **already running** Python process safely, without a second instance? | the return notification |
| E1-Q4 | When the helper starts, are all `.GoZ` files and `GoZ_ObjectList.txt` complete? | the file-stability rule (§7) |
| E1-Q5 | GoZ root and project folder on Manu's PC (`C:\Users\Public\Pixologic\…` vs a Maxon path) | paths |
| E1-Q6 | Coordinate orientation and scale of GoZ files relative to OBJ / Mirai, and the `GoZ_TAG_FLAGS` ZBrush writes | axis conversion |
| E1-Q7 | Are vertex order and face corner lists preserved, in both directions, unchanged and after a Move-brush edit? | in-place update safety |
| E1-Q8 | Does Python → ZBrush work with `GoZMakeObjectPath` + `GoZBrushFromApp`, and does a resend update the linked SubTool? | identity, send path |
| E1-Q9 (optional) | Which geometry does GoZ send from a subdivided SubTool, and what does `GoZ_TAG_SUBDIV` contain? | P1 guard |

---

## 2. What is known, and from where

Source labels: **[SDK]** = read first-hand on 2026-11-05 in Maxon's official *GoZBrush SDK* PDF
(`developers.maxon.net/docs/zbrush/goz_sdk.pdf`, 32 pages) and the official download **"ZBrush GoZ SDK 2022.0"**
(`developers.maxon.net/downloads/goz_sdk.zip`, sha256
`50ceb446c2170e7226eaf261cbd6db2e96132f6c08476331281723ea483fc770`: `Sources/GoZ_Binary.h` dated 2023-10-27,
`GoZ_Mesh.*`, `GoZ_Utils.*`, Windows/Mac demo apps) · **[GoB]** = only from the reverse-engineered GPL Blender client
GoB (read, not copied) · **[PC]** = can only be confirmed on the reference PC with ZBrush 2022.0.8. The SDK's header
says © Pixologic 2010/2011. That it describes 2022.0.8 **exactly** is itself [PC].

### 2.1 File format

| Fact | Source |
|---|---|
| 32-byte file header: `GoZb` + 28 bytes of text; blocks start at offset 32. | [SDK] `GoZ_Binary.h` |
| Block header, 16 bytes: `uint32 tag`, `uint32 size` (incl. header), `uint32 iCount`, `float32 modifier` (0 if unused). Unknown blocks are skipped by `size`. | [SDK] (the audit's "uint64 count" came from GoB and is **wrong**) |
| Last block `GoZ_TAG_END_OF_FILE = 0`, 16 bytes. | [SDK] |
| Tags: `1` MESH (name, NUL-terminated, padded to 4 bytes) · `2` MATERIAL · `5001` FLAGS (`uint32`) · `5002` SUBDIV (`GoZ_SubDiv`: levels, current level, dynamic sharp/smooth) · `10001` POINT_LIST (3 × `float32`) · `10002` DPOINT_LIST (double, "not yet supported") · `20001` FACE4_LIST_FORMAT_1 (4 × int, triangle = 4th index −1, **preferred**) · `20002` FACE4 format 2 · `20003` FACE3_LIST · `25001` UV4_LIST (4 (u, v) per face) · `25002` UV3 · `30001` MASK8 · `30002` MASK16 (`0xFFFF` = unmasked, `0` = fully masked) · `35001` MRGB (material, r, g, b, 8 bit each, per vertex) · `40001` GROUPS (16-bit id per polygon) · `40002` CREASE · `45001`/`50001`/`55001` texture/normal/displacement map path. | [SDK] |
| **N-gons are "not yet supported"** (`GoZ_TAG_FACEN_LIST` commented out). | [SDK] |
| Typical order: header, MESH, FLAGS, POINT_LIST, FACE4, (UV4), MATERIAL, map paths, END. Point and face blocks start on 4-byte boundaries. | [SDK] |
| `GoZ_FLAGS`: `VERTEX_FLIP_X=1, _Y=2, _Z=4, SWITCH_YZ=8, POLY_FLIP_NORMALS=256, UV_FLIP_U=512, UV_FLIP_V=1024, IMAGE_FLIP_V=2048` — "used by ZBrush to control the content of GoZ file to fit the target application". | [SDK] |
| Change hints (`GoZ_HINT_*`, e.g. `TOPOLOGY_CHANGED`, `MESH_REPLACED`) exist only as an enum; the hints tag is "not yet supported". | [SDK] |
| Little-endian on Windows (native `fread` of structs on x86/x64). | [SDK] (inferred from the reader) |
| The audit's tag `89 13` "object name" is in fact `0x1389 = 5001` FLAGS; `8A 13` = `5002` SUBDIV; the name is tag `1`. GoB writes the name with a `GoZMesh_` prefix. Whether ZBrush 2022.0.8 needs or writes that prefix is unknown. | [SDK] correction · prefix [GoB] → [PC] |
| Axis convention: GoZ ≈ OBJ rotated 180° about X. | [GoB] only → [PC] (E1-Q6) |
| The SDK reader reads MASK16 but not MASK8 or SUBDIV; it skips unknown blocks. | [SDK] |

### 2.2 Folders and the exchange protocol

| Fact | Source |
|---|---|
| `[PIXOLOGIC_PUBLIC]` = `C:\Users\Public\Pixologic` on Windows; `GoZBrush\` (common files and utilities), `GoZApps\<App>\` (one per target app, max 32), `GoZProjects\Default\` (exchanged files). The SDK utilities hard-code `C:\Users\Public\Pixologic`. Newer ZBrush versions use a Maxon path. | [SDK]; which root 2022.0.8 uses → [PC] |
| `GoZBrush\GoZ_Config.txt` (PFF: `PATH` = ZBrush.exe, `IMPORT_AS_SUBTOOL`, `SHOW_HELP_WINDOW`). `PATH` is updated each time ZBrush starts, so ZBrush must have been launched once after installation. | [SDK] |
| `GoZ_ProjectPath.txt` (project folder, default `GoZProjects\Default`; changing it is "not tested at all"). | [SDK] |
| `GoZ_ObjectList.txt`: one line per object = full path of its file **without extension** (the "Unique object identifier"); an empty list is one empty line. | [SDK] |
| `GoZ_Application.txt`: the active target app. Changed in ZBrush with the **R** button next to the GoZ buttons, or by an app's own GoZ command. | [SDK] |
| **Identity:** `GoZMakeObjectPath.exe` turns a short name written to `GoZBrush\GoZ_ObjectPath.txt` into a unique identifier (it appends a number if needed) and writes it back into the same file. The app must keep the link object ↔ identifier itself. ZBrush keeps identifier ↔ SubTool, and a resend under the same identifier updates that SubTool. **Measured (captures, 2026-11-06):** of 29 calls 2 got a number (`E1_C1`, `E1_C_P1_G1`); `E1_A` stayed unnumbered 15 times although `E1_A.GoZ` lay in the folder — the number is not "a file of that name exists". Mirai no longer uses the tool (AD-029 §3). | [SDK], [PC] (corrects the audit's "identity only by name") |
| App → ZBrush: write `<identifier>.GoZ`, write `GoZ_ObjectList.txt`, run `GoZBrush\GoZBrushFromApp.exe` (it starts ZBrush only if not running and opens the listed objects). The demos pass `-tmap` ("transfer texture maps"). | [SDK] |
| ZBrush → App: the artist presses GoZ / All / Visible; ZBrush "saves all the SubTools required … to GoZ files, **then** it calls" the app's editing utility. | [SDK] — the ordering in 2022.0.8 → [PC] (E1-Q4) |
| `GoZLocateApp.exe <AppFolderName> "<pattern>"` writes `GoZ_AppPathList.txt` (searches the default program folders). | [SDK] |

### 2.3 Registration of a target application

| Fact | Source |
|---|---|
| The folder name is the app id: **no spaces, no tabs**. | [SDK] |
| `GoZ_Info.txt` (PFF): required `NAME`, `EXTENSION` (`".GoZ"`), `TAMPLATE` (sic; `"GoZ Complete Binary.GoZ"` from `<ZBrush>\ZStartup\ExportTamplates\`), `EDIT_COMMAND`; optional `GOZ_VERSION` (1), `LOCATE_COMMAND`, `INIT_COMMAND`, and import/export options `IMPORT_/EXPORT_FLIP_X/Y/Z`, `IMPORT_/EXPORT_SWITCH_YZ`, `…_FLIP_NORMALS`, `IMPORT_POLYGROUPS`, `GROUP_NSIDED_POLYS`, normal-map flips. | [SDK] |
| **`EDIT_COMMAND`, `LOCATE_COMMAND`, `INIT_COMMAND` may be `.exe` or `.bat`.** The official Windows demo uses three `.bat` files. | [SDK] |
| Locate utility: writes `GoZ_AppPathList.txt` in the app folder (one full path per line, or one empty line). Called on the first GoZ to a new app and when the user changes the version in Preferences. ZBrush then lets the user pick a path or Browse. | [SDK] |
| Install utility (`INIT_COMMAND`): installs files, must write `GoZ_InstallLog.txt` (empty = success, else an error text shown to the user). "Consider that it is called with administrator privileges, as ZBrush takes care to ask the user to login as a user with administrator privileges." | [SDK] → UAC behaviour [PC] |
| ZBrush writes `PATH` (the chosen application path) into `GoZApps\<App>\GoZ_Config.txt`. | [SDK] |
| An object arriving through `GoZBrushFromApp` becomes a **new Tool**, not a SubTool of the active Tool, while the GoZ preference *Import as SubTool* (`IMPORT_AS_SUBTOOL` in `GoZBrush\GoZ_Config.txt`) is off. It is the artist's ZBrush preference; the probe does not change it, and the bridge must not either (GoB rewrites it). | [SDK] preference; behaviour [PC] observed 2026-11-05 (Manu, T5.1) |
| **ZBrush lists a newly added `GoZApps\<App>\` folder only after a restart** (it was missing from the **R** list until ZBrush was restarted). | [PC] observed 2026-11-05 (Manu, T2.2) |
| Editing utility (`EDIT_COMMAND`): must use the active version, **must not launch a second instance but reuse the running one**, reads `GoZ_ObjectList.txt`. | [SDK] |
| Official Windows demo: the editing utility finds the app by its process, starts it with `ShellExecute` if it is not running, then sends it a window message (`WM_APP + 0x100`). The demo `.bat` simply runs the demo `.exe`. | [SDK] |
| Arguments and working directory ZBrush passes to the commands; whether ZBrush waits for them to exit; whether a `.bat` gets a console window; whether the Locate list may contain a non-`.exe` path. | [PC] (E1-Q2). The SDK's Locate example uses `..\..\GoZBrush\GoZLocateApp.exe`, which suggests the working directory is the app folder. |

### 2.4 Conclusion for registration (to be confirmed by E1)

- Mirai **can very likely be registered**: `EDIT_COMMAND` may be a `.bat`, and nothing requires a compiled program
  [SDK].
- **A small helper is necessary.** ZBrush launches a new process per GoZ; Mirai is a long-running `python src/main.py`
  window; the SDK requires reuse of the running instance. Planned design (`PROVISIONAL`): `EDIT_COMMAND` = `.bat` →
  runs a stdlib-only Python helper → the helper snapshots the transfer and drops an atomic **ticket file** into a
  Mirai-owned inbox → the running Mirai picks the ticket up in its existing main-loop tick. No ports, no sockets, no
  window messages. The helper never touches a Mirai scene. If Mirai is not running, the ticket waits.
- Whether the helper should **start** Mirai when it is not running (the SDK's expectation) is a decision: D11 in §10.
- E1 tests this with a stand-in listener (`probe_listener.py`) instead of Mirai.

---

## 3. Test meshes

All three are quads/triangles only (no n-gons, [SDK]: unsupported). Each is written by the probe both as OBJ (for
ZBrush's own import as a reference) and as GoZ (Python → ZBrush), with a sidecar JSON of the exact values sent.

| Id | Mesh | Size | Why |
|---|---|---|---|
| **A** | **Axis tripod**: three separate boxes, cross-section 0.1 × 0.1, from a common corner region offset from the origin: arm X `[0.20, 1.20] × [0.10, 0.20] × [0.05, 0.15]`, arm Y `[0.20, 0.30] × [0.25, 0.85] × [0.05, 0.15]`, arm Z `[0.20, 0.30] × [0.10, 0.20] × [0.20, 0.50]`. 8 vertices and 6 quads per box, deterministic order (box X, Y, Z; corners in binary order of (x, y, z) min/max), outward winding. | 24 v / 18 quads | No mirror symmetry and distinct arm lengths (1.0 / 0.6 / 0.3) plus a positive offset: every axis swap, sign flip, scale or translation change and every winding flip shows in the bounding box, the arm lengths and the face normals. Visually unambiguous: the longest arm is +X, the middle +Y, the shortest +Z. |
| **B** | **Mirai-like**: Mirai's own `sphere` primitive (`mirai.scene_factory.PRIMITIVES["sphere"]`, 482 v, 448 quads + 64 triangles) with 4 faces at one pole deleted through the Core (`Mesh.delete_faces`), so vertex and face IDs are no longer contiguous. Written in Mirai's vertex-ID order (as `mirai.obj_export.mesh_to_obj` does), with the index ↔ `VertexId` map in the sidecar. | ≈ 480 v | Triangles (4th index −1), an open border, Mirai's ID → dense-index mapping. |
| **C** | **Organic**: `examples/meshes/head_basemesh.obj` (326 v / 324 quads, has UVs; the rigging head). UVs are **not** sent in E1. | 326 v | Representative character topology, small enough for the capture to be committed. |

Optional, only if time allows: `examples/meshes/gollum_20k.obj` (21 875 v, itself exported by ZBrush 2022) for a timing
note. No n-gon mesh in E1.

---

## 4. Prerequisites (reference PC)

| Item | Detail |
|---|---|
| Windows 10 64-bit, user with administrator rights (the install step may ask for them) | REFERENCE_HARDWARE.md |
| **ZBrush 2022.0.8** installed, **started at least once** after installation ([SDK]: this sets `GoZBrush\GoZ_Config.txt` `PATH`) | Help → About shows 2022.0.8 |
| GoZ installed: `C:\Users\Public\Pixologic\GoZBrush\` contains `GoZBrushFromApp.exe`, `GoZMakeObjectPath.exe`, `GoZLocateApp.exe`, `GoZ_Config.txt` (if missing: ZBrush *Preferences → GoZ → Force Reinstall*) | step T0 checks it |
| `<ZBrush install>\ZStartup\ExportTamplates\GoZ Complete Binary.GoZ` exists | step T0 |
| Python 3.9+ (the one Mirai runs with); note its full path (`where python`) | the helper is called from ZBrush with an absolute path, not via `PATH` |
| This repository, up to date (`git pull`), containing the probe files of §5 | — |
| ~40 minutes; no other GoZ app transfer running; save open ZBrush work first | — |

**Files required from Maxon:** none beyond the ZBrush 2022.0.8 installation. The GoZ SDK 2022.0 is a reference
document. The agent has read it. It is not needed on the PC, and it is not put into the repository (its licence
reserves all rights).

---

## 5. Probe files

All Python is stdlib-only, Python 3.9+, and every script runs as `python -I experiments/goz_probe/<script>.py` (in
isolated mode it puts `experiments/` on `sys.path` itself). Windows paths go through `pathlib`. The format code is
written from §2.1; nothing is copied from GoB or the SDK. Each script has `--help`.

| File | Does |
|---|---|
| `goz_probe_format.py` | Strict reader (`parse_goz`, `read_goz`) and minimal writer (`encode_goz`: MESH, FLAGS, float32 POINT_LIST, FACE4 format 1, END with size field 0 as the SDK writer stores it). Decodes MESH, MATERIAL, map paths, FLAGS, SUBDIV, POINT_LIST, FACE4 format 1/2 and FACE3. Any other block is recorded as an anomaly and skipped by its size. **Fails closed** on bad magic, a truncated block header, a block running past the end of the file, a block smaller than its count needs, a face index outside the points, a missing END or bytes after it. A block *larger* than its count needs, or an END size field other than 0/16, is read and recorded as an anomaly (the SDK reader allows it). The writer refuses n-gons. `dump()` gives a readable block list, decoded flags, counts, bounding box, and the first/last points and faces. |
| `probe_common.py` | GoZ root detection (`--root`, `MIRAI_GOZ_ROOT`, `%PUBLIC%\Pixologic`, then Maxon locations) and folder paths. Readers for PFF and GoZ text files (UTF-8 → ANSI → latin-1). Writers: atomic files (tmp + `os.replace`) and GoZ list files (ANSI, CRLF). Process and exclusive-open checks (typed `kernel32` via `ctypes`). The privacy redaction (below). The sent-vs-received comparison: axis mapping by regression, or by bounding box when the points do not correspond; signed-permutation test; exact per-point float32 comparison; face identity, rotation and reversed winding. |
| `make_meshes.py` | Writes A, B, C (§3) through Mirai's Core `Mesh` and Mirai's own `mirai.obj_export.mesh_to_obj` as `meshes/<id>.obj`, plus `meshes/<id>.sent.json` (float64 positions, faces as dense indices, index ↔ VertexId / FaceId maps). Deterministic. Reads `src/` and `examples/` only. E3 (2026-11-06): C's sidecar also holds its corner UVs (`uvs`) and a bump target (`target_bump`), plus `C_bump.obj`. |
| `gozapp/MiraiProbe/` | Template of the GoZ app folder. `GoZ_Info.txt`: `NAME = "Mirai Probe (E1)"`, `EXTENSION = ".GoZ"`, `TAMPLATE = "GoZ Complete Binary.GoZ"`, `GOZ_VERSION = 1`, the three commands, **no** flip options, so ZBrush's raw convention is observed. `Locate.bat.in` writes one line, the full path of `probe_app.cmd`. `Init.bat.in` writes an empty `GoZ_InstallLog.txt`, nothing else. `Edit.bat.in` runs `<python> -I …\probe_receiver.py --root <root> --launched-by edit_command -- %*`. Each `.bat` first appends one line (date, time, arguments, cwd) to `captures\commands_log.txt`. |
| `probe_app.cmd` | The "application path" the Locate step offers and ZBrush stores as `PATH` in `GoZApps\MiraiProbe\GoZ_Config.txt`. It only logs and prints that it is the E1 stand-in. E1 records whether ZBrush accepts a non-`.exe` path and whether it ever runs it. |
| `install_probe_app.py` | `--inventory` (read-only, writes `captures/inventory.txt`). Default: install `GoZApps\MiraiProbe\`, filling in the absolute paths of this python, this repository and the GoZ root; `.bat` files are written in the console (OEM) code page with CRLF. Refuses an existing folder (`--replace` only for our own, recognised by the marker file `.mirai_goz_probe`). `--uninstall` removes only our folder. Never touches `GoZBrush\` or another app. |
| `probe_receiver.py` | What `Edit.bat` runs. Records first: start time, `argv` incl. what ZBrush passed, cwd, the parent-process chain (Windows toolhelp snapshot), selected environment variables. Then the GoZBrush text files. Per listed object: stat and sha256 at start, ms since its last write, exclusive open, a copy into `captures/<time>_receive/`. After the settle time (`--settle`, default 1.0 s wall clock) it stats and hashes again. Then a strict parse of the copy, the dump, and the comparison with the sent mesh (matched by an earlier `probe_send` identifier, else by counts, else by name). A ticket goes into `inbox/` only if `inbox/listener.lock` names a live process. Writes `receiver_log.json` and `dump.txt`. Starts nothing, edits or deletes no ZBrush file. On an internal error it writes `captures/receiver_error_<time>.txt`. E3: classifies returned UVs against the sent / OBJ UVs, fits a target weight (`target_bump`), copies every image a map-path block names. |
| `probe_listener.py` | Stand-in for a running Mirai: takes `inbox/listener.lock` (refuses while another live listener holds it, replaces a stale one), polls `inbox/` every 250 ms, verifies each ticket's copies by sha256, prints the latency, moves the ticket to `inbox/done/`, logs to `inbox/listener_log.txt`. Ctrl+C removes the lock. |
| `probe_send.py` | Python → ZBrush. `--mesh A|B|C`: the identifier via `GoZMakeObjectPath.exe`, or reused from an earlier send of the same mesh so the linked SubTool is updated (`--new-identifier` forces a new one). Then the `.GoZ` (checked by the strict reader before writing), `GoZ_ObjectList.txt`, `GoZ_Application.txt` = `MiraiProbe` (before/after logged; `--keep-application`), and `GoZBrushFromApp.exe -tmap` as in the official demo (`--no-tmap` without it). `--resend last|<capture>`: ZBrush's captured bytes back, refused if ZBrush has written a newer file (`--force`). `--name-style gozmesh` writes the name as `GoZMesh_E1_A` (as GoB does). `--dry-run` runs no program. Log: `captures/<time>_send_<what>/send_log.json`. E3: `--uvs as-is|flip-v` (UV4 block), `--target bump` (base + target as two objects in one transfer). |
| `probe_names.py` | T10 (2026-11-06): lists ZBrush's GoZ project folder (size, last write, header writer, MESH name, counts of every `.GoZ`) and Mirai's name registry `goz/manifests/names.json`; reads only. `--make NAME` (optional) asks `GoZMakeObjectPath.exe` once. Log: `captures/<time>_names/names_log.json`. |
| `captures/` | Output, committed by Manu after the run (small files; no gollum capture). |
| `tests/` | Headless tests (§5.1). The captured files become fixtures after E1. |

**Privacy.** Everything the probe writes to `captures/` and `inbox/` replaces the Windows user profile path
(`%USERPROFILE%`) and the user name as a path component (`%USERNAME%`), because the captures are committed to a public
repository. Computer name and user name are not recorded.

### 5.1 Verified in the container (Linux, Python 3.13, 2026-11-05)

`python -m pytest experiments/goz_probe/tests -q` → **39 passed** (not part of the default run, AGENTS.md §8a):

- format round trip, layout (4-byte alignment, NUL-padded name, triangle = −1), all fail-closed cases, unknown and
  oversized blocks, FACE4 format 2, FACE3 and SUBDIV decoding, n-gons refused;
- meshes deterministic; A has distinct extents (1.0 / 0.75 / 0.45), an offset from the origin and outward winding;
  B is 481 v / 508 f with 64 triangles and ID gaps; C matches its OBJ;
- comparison: identity is bit-identical; a 180° rotation about X is found exactly; an axis swap with scale is found
  from bounding boxes when the points are reordered; one moved vertex and reversed windings are counted;
- workflow on a fake GoZ root: install / replace / uninstall, a foreign app folder never touched, inventory writes
  nothing into the root; dry-run send → receive round trip; truncated and missing files reported, not parsed; ticket
  to a live listener, stale lock replaced, second listener refused; identifier reuse; resend refuses a newer ZBrush
  file; redaction keeps keys and words; every script runs with `-I --help` without importing pyglet.
- By hand: listener and receiver as **separate processes**: the ticket was picked up 0.5 s after the receiver started
  (settle 0.3 s + one poll).

**Not verifiable here:** anything ZBrush does; the `.bat` files under `cmd.exe`; the Windows-only `ctypes` paths
(process check, exclusive open, process chain, OEM code page). Those were reviewed only (explicit argument and return
types, x64 `PROCESSENTRY32W` layout). The receiver records an error value instead of failing if one of them breaks.

---

## 6. Windows-Testablauf für Manu (Deutsch)

Vorher: ZBrush-Arbeit speichern. Eine Eingabeaufforderung im Repository öffnen (`cd …\Mirai-Bastel`). Bei jedem
Schritt gilt: **Erwartung** = was passieren sollte; **Notieren** = was in die Tabelle §9 gehört; schlägt etwas fehl,
zusätzlich die Punkte aus §8.

### T0 — Bestandsaufnahme (nur lesen, 5 min)

1. ZBrush starten, *Help → About*: Version notieren. ZBrush wieder schließen.
2. `python -I experiments/goz_probe/install_probe_app.py --inventory` (nur lesen, schreibt nichts außer
   `captures/inventory.txt`): listet den GoZ-Ordner mit allen Unterordnern, den Inhalt der Textdateien in `GoZBrush\`, die
   vorhandenen `GoZApps\*\GoZ_Info.txt` und prüft die Vorlage in `ZStartup\ExportTamplates\`.
   - **Erwartung:** Wurzel `C:\Users\Public\Pixologic`, `GoZBrush\` mit den drei `.exe`, `GoZ Complete Binary.GoZ` gefunden.
   - **Notieren:** Wurzelpfad, ob ein `Maxon`-Ordner existiert, welche GoZ-Apps es schon gibt.

### T1 — Probe-App eintragen (3 min)

1. `python -I experiments/goz_probe/make_meshes.py` → `meshes/A.obj`, `B.obj`, `C.obj` (+ `.sent.json`).
2. `python -I experiments/goz_probe/install_probe_app.py` → legt `GoZApps\MiraiProbe\` an.
   - **Erwartung:** Meldung „installed“, keine Rechteabfrage (der Public-Ordner ist für Benutzer beschreibbar).
   - **Notieren:** ob Windows nach Administratorrechten gefragt hat.
   - **Wichtig:** Läuft ZBrush schon, **ZBrush danach neu starten**. ZBrush liest die GoZ-Apps nur beim Start ein
     (beobachtet 2026-11-05).

### T2 — ZBrush → Python (das Wichtigste, 10 min)

1. ZBrush starten. `Tool → Import` → `experiments\goz_probe\meshes\A.obj`, auf die Fläche ziehen, `T` (Edit).
2. Im Tool-Menü neben den GoZ-Knöpfen **R** drücken → „Mirai Probe (E1)“ wählen.
   - **Erwartung:** ZBrush ruft die Locate-Datei auf und zeigt eine Pfadliste mit einem Eintrag (`…\probe_app.cmd`) → wählen.
     Danach läuft die Install-Datei; vielleicht fragt Windows nach Administratorrechten (**zulassen**).
   - **Notieren:** genaue Dialogtexte (Screenshot), ob eine Rechteabfrage kam, ob ein Konsolenfenster aufging.
3. **GoZ** drücken.
   - **Erwartung:** kurz ein Konsolenfenster, ZBrush reagiert weiter. In `captures\<Zeit>\` liegen `receiver_log.json`,
     Kopien von `GoZ_ObjectList.txt` und der `.GoZ`-Datei sowie `dump.txt`. `dump.txt` zeigt die Blöcke 1 (Name),
     5001 (Flags), 10001 (24 Punkte), 20001 (18 Flächen), 0 (Ende) und die Zeilen **„Achsen (…): x_goz = …·x_sent …“**,
     **„Maßstab: …“**, **„Reihenfolge: same / …“**.
   - **Notieren:** die drei Zeilen; ob die Datei beim Start des Empfängers schon fertig war (`complete_at_start: true/false`,
     `exclusive_open: ok/blocked`, `changed_after_1s: False/True`, „geschrieben … ms vor dem Start“); Name der Datei im
     Projektordner. Kommt **kein** neuer `captures\<Zeit>_receive\`-Ordner: `captures\commands_log.txt` ansehen (hat ZBrush
     `Edit.bat` überhaupt aufgerufen?) und nach `captures\receiver_error_*.txt` schauen.
4. Dasselbe mit `B.obj` und `C.obj` (je Import, R ist schon gesetzt, GoZ).

### T3 — Ein laufendes Programm benachrichtigen (5 min)

1. Zweites Konsolenfenster: `python -I experiments/goz_probe/probe_listener.py` (läuft weiter).
2. In ZBrush auf A wieder **GoZ**.
   - **Erwartung:** Der Listener schreibt sofort „ticket …: 1 object, hashes ok“; kein zweiter Listener startet.
   - Bis zum Fix vom 2026-11-05 (Commit nach `9c4cec9`) stand hier fälschlich „hashes NOT ok“: Der Empfänger hatte den
     Pfad im Ticket durch den Datenschutz-Filter geschickt (`%USERPROFILE%\…`), der Listener fand die Kopie nicht.
     Ältere Tickets lassen sich nach `git pull` nachprüfen:
     `python -I experiments/goz_probe/probe_listener.py --recheck-done`.
3. **GoZ** zweimal schnell hintereinander.
   - **Erwartung:** zwei Tickets, jedes mit eigener, vollständiger Kopie.
   - **Notieren:** Zeit zwischen Klick und Ticket (der Listener zeigt sie), ob ZBrush während des Empfängers hängt.
4. Listener mit `Strg+C` beenden.

### T4 — Python → ZBrush, unverändert zurück (3 min)

1. `python -I experiments/goz_probe/probe_send.py --resend last`
   - **Erwartung:** ZBrush kommt nach vorn, **dieselbe** SubTool wird aktualisiert (keine neue, kein Dialog).
   - **Notieren:** neue SubTool oder Update? Dialog? Sichtbare Änderung (sollte keine sein)?

### T5 — Python → ZBrush, von Python geschrieben (7 min)

1. `python -I experiments/goz_probe/probe_send.py --mesh A`
   - **Erwartung:** ein **neues Tool** `E1_A…` (beobachtet 2026-11-05; eine SubTool wird es nur, wenn in den GoZ-Einstellungen
     „Import as SubTool“ an ist, die Probe ändert das nicht). Zum Vergleich Tool A aus T2 aktiv lassen und `E1_A` über
     *Tool → SubTool → Append* dazuholen: Es liegt **genau auf** A (SubTool-Transparenz an): längster Arm nach rechts (+X),
     mittlerer nach oben (+Y), kürzester nach vorn. Rechnerisch entscheidet T5.2 zusammen mit T2: Zeigen beide die
     Identität, liegen OBJ- und GoZ-Weg in ZBrush deckungsgleich; der Blick ist nur die Bestätigung.
   - **Notieren:** deckungsgleich / gespiegelt / gedreht / anders groß (Screenshot Front- und Seitenansicht).
   - **Wenn das neue Tool nicht das Dreibein ist** (z. B. ein Würfel mit seltsamem Namen, beobachtet 2026-11-05 mit
     `--style sdk`): nacheinander `--mesh A --style gozmesh --new-identifier` und `--mesh A --style zbrush --new-identifier`
     senden. Nach jedem Versuch in der Tool-Palette nachsehen, welches Tool neu ist und wie es aussieht, und es per **GoZ**
     zurückschicken. `--style zbrush` schreibt ZBrushs eigenes Byte-Layout (Test: reproduziert ZBrushs Datei aus T2
     bytegenau). Notieren, welche Stufe das Dreibein bringt. Erst danach weiter mit T5.2.
2. Ohne etwas zu ändern **GoZ** (Ziel ist noch „Mirai Probe (E1)“).
   - **Erwartung:** `dump.txt` meldet „Rundreise unverändert: Punkte bitgleich, Flächen gleich“.
3. Dasselbe mit `--mesh B` und `--mesh C`.

### T6 — Kleine Änderung in ZBrush zurück (5 min)

1. Auf der SubTool `E1_C…`: Move-Pinsel, zwei, drei Striche an der Nase. **Kein** Divide, kein Remesh, keine
   Topologie-Werkzeuge. **GoZ**.
   - **Erwartung:** gleiche Punkt- und Flächenzahl, gleiche Flächenlisten, „N Punkte geändert“ (eine plausible Zahl),
     alle anderen Punkte bitgleich.
2. Dasselbe auf `E1_B…` (mit Dreiecken und Loch).
   - **Notieren:** Zahlen aus `dump.txt`; ob ZBrush beim Import von B etwas „repariert“ hat (andere Zahlen schon in T5).

### T7 — nur wenn Zeit ist: Subdivision (5 min)

1. Auf `E1_C…`: `Strg+D` (eine Stufe), **GoZ** → `dump.txt`: Block 5002 und Punktzahl notieren.
2. Auf die unterste Stufe gehen (`Shift+D`), **GoZ** → wieder notieren.

### T7b / T7c — Divide ohne SMT und der Cage-Knopf (für D13, 2026-11-05, je 3 min)

Beide auf einem **frisch gesendeten** Kopf, damit der Vergleich gegen `meshes/C` stimmt:
`python -I experiments/goz_probe/probe_send.py --mesh C --axis bridge --new-identifier`.

- **T7b:** *Tool → Geometry*: **SMT aus**, `Strg+D` (eine Stufe), **GoZ**. Dann auf die unterste Stufe (`Shift+D`),
  **GoZ**. Erwartung (Hypothese): die Punkte kommen bitgleich zurück, weil ohne SMT nichts geglättet wird.
- **T7c:** Neu senden (wie oben), **SMT an**, `Strg+D`, **GoZ** (= T7, zur Kontrolle). Dann unterste Stufe, *Tool → Geometry →*
  **Cage**, **GoZ**. Frage: bringt Cage die gesendeten Punkte bitgleich zurück, nur auf float32 genau, oder nur ungefähr?

Notieren: welche Knöpfe in welcher Reihenfolge; die Uhrzeit jedes GoZ (die `captures\<Zeit>_receive\`-Ordner werden
danach von mir ausgewertet). Manu: T7b und T7c in genau der beschriebenen Reihenfolge ausgeführt (die letzten beiden sends und receives)

### T8 — E2: Polygruppen von Mirai nach ZBrush und zurück (für P2a, 2026-11-05, ~10 min)

Vorbereitet für [`docs/WP_GOZ_P2_PLAN.md`](../../docs/WP_GOZ_P2_PLAN.md) §2. Ziel-App mit **R** ist „Mirai Probe (E1)“.

1. `git pull`, dann
   `python -I experiments/goz_probe/probe_send.py --mesh C --axis bridge --groups bands`
   (Kopf mit vier waagerechten Gruppen-Bändern, IDs 101–104, eigenes Tool `E1_C_P1_G…`).
   - **Notieren:** Zeigt ZBrush vier Polygruppen (*Polyframe* an, `Shift+F`)? Screenshot.
2. Ohne etwas zu ändern **GoZ** → `dump.txt` Zeile `groups (id: faces)`: kommen 101–104 zurück?
3. In ZBrush eine Gruppe ändern (z. B. ein paar Flächen maskieren, `Strg+W`), **GoZ** → wieder `dump.txt`.
4. **Nur falls in 1. keine Gruppen sichtbar waren:**
   `python -I experiments/goz_probe/install_probe_app.py --replace --import-polygroups`, ZBrush neu starten, R → „Mirai
   Probe (E1)“, Schritte 1–3 wiederholen (mit `--new-identifier`).

Danach `captures/` mit `git add experiments/goz_probe/captures` committen und pushen.

### T9 — E3: UVs, Textur, Morph-Target (für P3, 2026-11-06, ~25 min)

Vorbereitet für [`docs/WP_GOZ_P3_PLAN.md`](../../docs/WP_GOZ_P3_PLAN.md) §2. Ziel-App mit **R** ist für diesen Test
wieder „Mirai Probe (E1)“ (danach zurück auf „Mirai“). Jeder Schritt mit GoZ schreibt einen `captures\<Zeit>_receive\`-
Ordner; bitte bei jedem Schritt die Uhrzeit notieren (oder die Reihenfolge einhalten).

0. `git pull`, dann einmal `python -I experiments/goz_probe/make_meshes.py` (neu: UVs und ein Buckel-Ziel für Mesh C,
   dazu `meshes\C_bump.obj`).
1. **UVs von Mirai:** `python -I experiments/goz_probe/probe_send.py --mesh C --axis bridge --uvs as-is`
   (Tool `E1_C_P1_UV…`). In ZBrush *Tool → UV Map → Morph UV* drücken: erscheint die flache Abwicklung des Kopfes
   (Gesicht, Ohren als Inseln)? Screenshot, dann *Morph UV* wieder aus. **GoZ** ohne Änderung.
2. **ZBrushs eigene Richtung:** `experiments\goz_probe\meshes\C.obj` über *Tool → Import* laden (eigenes Tool),
   **GoZ**. (Die Auswertung vergleicht ZBrushs UV-Block mit den `vt` der OBJ-Datei; daran sehe ich die V-Richtung.)
3. **UV Master:** zurück auf das Tool aus Schritt 1, *Zplugin → UV Master → Unwrap*, **GoZ**.
4. **Textur aus Polypaint:** auf demselben Tool etwas malen (z. B. *Color → FillObject* mit einer Farbe, dann ein paar
   Striche in einer anderen), *Tool → Texture Map → New From Polypaint*, **GoZ**. Notieren: Name und Ort, wenn ZBrush
   etwas anzeigt.
5. **Basis + Ziel:** `python -I experiments/goz_probe/probe_send.py --mesh C --axis bridge --target bump`. Notieren:
   kommen zwei Tools/SubTools an (`E1_C_P1_B…`, `E1_C_P1_T…`)? Beim Ziel ist vorne ein Buckel. Je einmal **GoZ** auf
   beiden.
6. **Layer-Versuch** (der Weg „Basis + Morph-Layer“): `meshes\C.obj` über *Tool → Import* als neues Tool laden.
   *Tool → Layers → New* (Layer nimmt auf, REC an), dann *Tool → Import* → `meshes\C_bump.obj`. Notieren: hat der Layer
   jetzt den Buckel (Layer-Auge aus/an, Regler)? Dann **GoZ** dreimal: Layer auf 1 (voll), Layer aus, Layer auf 0.5.
   Falls *Import* den Layer nicht füllt oder ZBrush eine Meldung zeigt: Screenshot und notieren, was passiert ist.
7. **Überlebt der Layer ein erneutes Senden?** Direkt nach Schritt 6, Layer **nicht** auf Aufnahme (REC aus), Regler
   bleibt auf 0.5: `python -I experiments/goz_probe/probe_send.py --resend last` (schickt die letzte Rückgabe, also den
   Stand mit Layer auf 0.5, an dasselbe Tool). Notieren: Ist der Layer noch da? Sieht der Buckel danach **stärker** aus
   (dann hat ZBrush das Gesendete als neue Basis genommen und den Layer obendrauf gerechnet)? Zum Schluss einmal
   **GoZ**.

Danach R wieder auf „Mirai“, `captures/` mit `git add experiments/goz_probe/captures` committen und pushen.

### T10 — Namen der SubTools (AD-029 §3, 2026-11-06, ~10 min)

Mit der echten Mirai-App (R steht auf „Mirai“), nicht mit der Probe. Prüft, dass Mirai seine SubTools jetzt selbst
benennt: lesbar, ohne angehängte Zahl, und über Neustarts hinweg gleich.

0. `git pull`. In ZBrush und Mirai nichts Altes offen lassen ist **nicht** nötig — gerade mit alten Dateien im Ordner
   soll es klappen. Einmal `python -I experiments/goz_probe/probe_names.py` (listet `GoZProjects\Default`, wer welche
   Datei geschrieben hat, und Mirais Namen).
1. Mirai: Kopf laden und als Szene speichern, ein Morph-Target anlegen, SPACE → „An ZBrush senden“. Notieren: Namen der
   Tools in ZBrush (erwartet `head_basemesh` und `head_basemesh_Target_1` — die `1` ist der Name des Targets
   „Target 1“, keine Zählnummer). Statuszeile: steht dort „sent as '…_2'“, lag eine fremde Datei gleichen Namens im
   Ordner (dann bitte Schritt 0 mitschicken).
2. In ZBrush auf dem Basis-Tool kurz mit Move ziehen, **GoZ**: Mirai bietet „ZBrush übernehmen“ an (nicht „not sent from
   Mirai“).
3. Mirai **beenden und neu starten**, dieselbe Szene öffnen, wieder senden: ZBrush aktualisiert **dieselben** Tools
   (kein neues Tool mit Zahl). Nochmal GoZ auf der Basis: „übernehmen“.
4. ZBrush **ohne Speichern neu starten**, R → „Mirai“, aus Mirai senden: die Tools heißen wieder genauso.
5. Nur falls in 1–4 doch eine Zahl auftaucht: `python -I experiments/goz_probe/probe_names.py --make head_basemesh`
   und die Ausgabe notieren (zeigt, was `GoZMakeObjectPath` gerade antworten würde; Mirai fragt es nicht mehr).

`captures/` (der `*_names`-Ordner) committen. Erwartung: kein „not sent from Mirai“, keine Zahl außer der eines
Target-Namens, keine neue Kopie beim erneuten Senden.

### T11 — Erneutes Senden von Basis + Targets in ein bestehendes Tool (2026-11-06, ~15 min)

**Bisher beobachtet (Manu, 2026-11-06).** Basis + 3 Targets gesendet (ein Tool, vier SubTools, Namen korrekt), ein
Target in ZBrush geändert, **GoZ**, in Mirai übernommen, dann die Basis in Mirai geändert und erneut gesendet:
- Lauf 1 (Dateiname `…Target_3_3`, Name in der Datei `…Target_3`): kein neues Tool; die Basis-SubTool hat die
  Basis-Änderung, heißt aber wie das letzte Target.
- Lauf 2 (beide Namen gleich): ZBrush legt **zusätzlich ein neues Tool** an (Namen korrekt; Basis und Target 1 ohne,
  Target 2 und 3 mit der Basis-Änderung). Im alten Tool hat die Basis die Basis-Änderung, heißt aber jetzt wie
  Target 1.

Mirai schreibt dabei nachweislich das Richtige: vier Dateien, Basis zuerst, jede unter ihrem Namen, alle mit der
Basis-Änderung, nur Target 3 zusätzlich mit seiner. Das Einspielen **mehrerer** Dateien in ein **bestehendes** Tool
macht ZBrush also anders, als die Namen sagen. E3 hat nur das erste Laden geprüft. Seit 2026-11-06 schreibt Mirai den
Namen in der Datei wie ZBrush selbst: `GoZMesh_<Name>` (bisher ohne Präfix).

**Hinweis aus GoB** (Blender-Bridge, gelesen 2026-11-06, Stand `464676b`): GoB hat 2020 genau dieses „Durcheinander
der SubTools“ gehabt. Erst löschte es vor dem Senden ZBrushs `.ZTL`-Dateien in `GoZProjects\Default` („remove ZTL
files since they mess up Zbrush importing subtools“, `e107ec5`), dann ersetzte es ZBrushs GoZ-Import ganz durch ein
eigenes ZScript, das SubTools im aktiven Tool **per exaktem Namen** sucht und dort importiert (`GoB_Import.txt`).
Verdacht also: ZBrush legt beim GoZ-Export eine `.ZTL` (das ganze Tool) neben die `.GoZ` und lädt sie beim nächsten
Senden wieder — daher das zusätzliche Tool mit altem Stand.

**Schritt 1 erledigt (Manu, 2026-11-06 15:09, `captures/20261106-150900_043_names`):** *Import as SubTool* ist an.
Neben Mirais vier `.GoZ` (15:07:47–48) liegen vier `<Name>.ztn` mit **derselben** Zeit und je **55 Byte** — genau die
Länge von `C:/Users/Public/Pixologic/GoZProjects/Default/SubD_Cube`, also zeigt vermutlich jede auf das Tool
`SubD_Cube`. Mirai schreibt keine `.ztn`: ZBrush legt sie beim Laden an. Beim GoZ von Target 3 (15:08:33) schrieb
ZBrush `SubD_Cube_Target_3.GoZ` und `.ztn` neu und eine Sekunde später `SubD_Cube.ztl` (271 KB): das **ganze Tool**,
benannt nach der obersten SubTool. Verdacht: beim nächsten Senden folgt ZBrush `.ztn` → `SubD_Cube.ztl` und lädt
diesen alten Stand als weiteres Tool. (Die Namen sind sauber: Target 3 hat inzwischen LayerId 4, der Name ist frei
geworden wie vorgesehen.)

**Schritte 1–3 erledigt (Manu, 2026-11-06 15:15, `captures/20261106-151522_094_names`):** jede `.ztn` enthält
`…\GoZProjects\Default\SubD_Cube`, auch die der drei Targets. Mit `SubD_Cube.ztl` im Ordner: wieder ein zusätzliches
Tool wie in Lauf 2. Mit der `.ztl` von Hand weggeschoben: kein neues Tool, aber **sechs** SubTools: `Target_1`
(war die Basis), `Target_1`, `Target_2`, `Target_3`, `Target_2`, `Target_3`. **Ergebnis:** ZBrushs eigener GoZ-Import
führt jede Datei über ihre `.ztn` zum Tool `SubD_Cube` und importiert sie in die SubTool **dieses Namens**: die Basis
richtig, Target 1 ebenfalls in die Basis (die dabei nach der Datei umbenannt wird), Target 2 und 3 finden keine
SubTool `SubD_Cube` mehr und werden angehängt; fehlt das Tool, lädt ZBrush es aus `SubD_Cube.ztl` (das zusätzliche
Tool). Mit *Import as SubTool* an kann ZBrushs GoZ also **mehrere SubTools eines Tools nicht aktualisieren** — auch ein
einzelnes Target nicht. Mit *Import as SubTool* aus wird jedes Objekt ein eigenes Tool, dessen `.ztn` auf sich selbst
zeigt (P3-Praxistest 3, E1-Resends: Aktualisieren funktioniert). Darum hat GoB den Import durch ein eigenes ZScript
ersetzt (Suche per SubTool-Namen).

**Nachtrag (Manu, 2026-11-06):** *Import as SubTool* ausgeschaltet — es kommen trotzdem SubTools. Zwei Erklärungen:
(A) die alten `.ztn` (alle → `SubD_Cube`) und `SubD_Cube.ztl` liegen noch da, ZBrush folgt ihnen und baut das alte
Tool wieder auf (die Einstellung gilt nur für Objekte ohne Verknüpfung); (B) eine Liste mit **mehreren** Objekten
landet bei ZBrush immer als SubTools in **einem** Tool, die Einstellung entscheidet nur, ob in das aktive oder in ein
neues (E3 T9.5 hat das nicht festgehalten). Test T11b (5 min):

1. ZBrush schließen. In `GoZProjects\Default` alle `SubD_Cube*`-Dateien (`.GoZ`, `.ztn`, `.ztl`) **von Hand** in
   einen Sicherungsordner verschieben.
2. ZBrush starten, *Import as SubTool* aus lassen, `python -I experiments/goz_probe/probe_names.py`: zeigt
   `GoZ_Config.txt` jetzt `FALSE`?
3. Aus Mirai senden. Notieren: vier Tools oder ein Tool mit vier SubTools? Dann wieder `probe_names.py`: steht bei den
   `.ztn` „own Tool“ (→ A) oder „SubTool of Tool 'SubD_Cube'“ (→ B)?

1. Nach dem **GoZ** aus ZBrush (dein Schritt „Target ändern > GoZ“): `python -I experiments/goz_probe/probe_names.py`.
   Notieren: die Zeile „ZBrush tool files (.ZTL/.ztn)“ und `GoZ_Config.txt` (*Import as SubTool*).
2. **Mit Mirai** (nach `git pull`), deinen Ablauf genau wie in Lauf 2. Notieren: neues Tool ja/nein, Name und Inhalt
   jeder SubTool, welche SubTool vor dem Senden aktiv war. Ist alles richtig → fertig.
3. Falls Schritt 1 `.ZTL`-Dateien mit Mirais Namen zeigt: denselben Ablauf noch einmal, aber **vor** dem Senden aus
   Mirai diese `.ZTL`-Dateien von Hand in einen anderen Ordner verschieben (nicht löschen; Mirai selbst fasst sie nicht
   an, AD-029 §3). Wird es dann richtig, ist die `.ZTL` die Ursache.
4. **Sonst mit der Probe** (R auf „Mirai Probe (E1)“). Jede Runde beginnt mit einem frischen Senden (neues Tool):
   `python -I experiments/goz_probe/probe_send.py --mesh C --axis bridge --target bump` → Tool mit `E1_C_P1_B…`
   und `E1_C_P1_T…`. Dann SubTool `…_T…` anklicken, ein Move-Strich, **GoZ**. Dann das erneute Senden; die Basis ist
   dabei um 3 Einheiten zur Seite verschoben, so sieht man, welche SubTool die Basis-Datei bekommt:
   - a. `… --target bump --again --shift-base 3` (Name ohne Präfix, Basis zuerst)
   - b. `… --target bump --again --shift-base 3 --style gozmesh` (Name mit `GoZMesh_`, wie Mirai jetzt)
   - c. wie b, plus `--base-last` (Basis zuletzt in der Liste)
   - d. wie b, aber vor dem Senden die **Basis**-SubTool anklicken
   (Die frische Runde vor b–d auch mit `--style gozmesh` senden.) Pro Runde notieren: neues Tool ja/nein, welche
   SubTool steht seitlich verschoben (= Basis-Datei), welche hat den Buckel (= Target-Datei), wie heißen sie.

Danach R wieder auf „Mirai“, `captures/` committen.

### T12 — Mirais Import-Skript für Basis + Targets (AD-029 §3, 2026-11-06, ~10 min)

T11b hat gezeigt: ZBrushs eigenes GoZ steckt mehrere Objekte immer in ein Tool und kann sie danach nicht richtig
aktualisieren. Mirai importiert ein Objekt mit Targets deshalb jetzt mit einem eigenen ZScript (wie GoB): es sucht
jede SubTool **über ihren Namen im aktiven Tool** und importiert dort. Objekte ohne Targets gehen wie bisher.

0. `git pull`, Mirai neu starten. Damit es sauber startet: ZBrush schließen, in `GoZProjects\Default` alle
   `SubD_Cube*`-Dateien von Hand in einen Sicherungsordner verschieben (auch `.ztn`/`.ztl`).
1. In Mirai einmal SPACE → „ZBrush: Mirai bei GoZ eintragen“ (schreibt das Skript nach
   `C:\Users\Public\Pixologic\GoZApps\Mirai\MiraiGoZ_Import.txt`). Steht die Zeile nicht im Menü (schon
   eingetragen), reicht ein Senden: Mirai legt die Datei an und sagt in der Statuszeile, was zu laden ist. Danach
   ZBrush starten (bei neu eingetragen: R → „Mirai“).
2. In ZBrush **ZScript > Load** → `…\GoZApps\Mirai\MiraiGoZ_Import.txt`. Notieren: Fehlermeldung? Liegt danach
   `MiraiGoZ_Import.zsc` im selben Ordner?
3. Mirai: SubD_Cube mit Targets senden. Erwartung: **ein neues Tool** `SubD_Cube` mit den SubTools `SubD_Cube`,
   `SubD_Cube_Target_1..3`; nach 1–2 s in Mirais Statuszeile „imported by Mirai's script - 1 as a new Tool, 3 added
   as SubTool (…)“.
4. In ZBrush `SubD_Cube_Target_3` ändern, **GoZ**, in Mirai übernehmen. In Mirai die Basis ändern, senden (das Tool
   `SubD_Cube` muss in ZBrush das **aktive** sein). Erwartung: kein neues Tool, weiterhin genau vier SubTools mit
   richtigen Namen, alle vier haben die Basis-Änderung, Target 3 zusätzlich seine; Statuszeile „4 updated“.
5. Noch einmal GoZ auf Target 3 und auf der Basis: kommen beide in Mirai richtig an?

Bei einem Fehler: Meldung von ZBrush (Screenshot), Mirais Statuszeile, und den Inhalt von
`GoZApps\Mirai\MiraiGoZ_Result.txt` notieren.

### Aufräumen

`python -I experiments/goz_probe/install_probe_app.py --uninstall` entfernt nur `GoZApps\MiraiProbe\`. In ZBrush mit **R**
wieder die gewohnte GoZ-App wählen. `captures\` committen (oder als Zip schicken) und die Tabelle §9 ausfüllen.

---

## 7. File-stability review: when is a transfer complete?

The audit's §7.6 rule ("stable mtime and size across two polls") is **not sufficient** and is replaced by this rule:

- **Why two 60 Hz polls fail:** two polls are ≈ 33 ms apart. ZBrush writes several files in sequence (each `.GoZ`,
  then or before the list). A large file can stall for longer than that (disk cache flush, antivirus scan holding the
  handle). On Windows, `LastWriteTime` can lag behind the data, and a file can have its final size before its
  content is written (pre-allocation). Unchanged mtime and size therefore prove nothing about the content.
- **Rule for P1 (`PROVISIONAL`, E1-Q4 confirms or refutes its first premise):**
  1. **Trigger = explicit signal, not a timer.** With registration: the launch of `EDIT_COMMAND`. [SDK]: ZBrush saves
     the SubTools *then* calls the editing utility. Without registration (watch-only fallback): a change of
     `GoZ_ObjectList.txt`, which only *starts* the checks below.
  2. **Snapshot:** read `GoZ_ObjectList.txt`; for every listed file record size, `mtime_ns` and sha256, and copy it into a
     Mirai-owned staging folder. Every further step works on the copy.
  3. **Structural completeness** of the copy (the strict reader of §5): magic, every block inside the file, sizes
     consistent with counts, END block last and exactly at EOF, required blocks present, counts plausible against the
     manifest.
  4. **Quiet period on the wall clock** (≥ 1.0 s, `time.monotonic`, not frames), then re-hash the original. The hash
     must equal the snapshot.
  5. **Windows exclusive-open check** (share mode 0) succeeds, i.e. no process still holds the file. Diagnostic only
     until E1 shows it is reliable (antivirus may also hold it briefly).
  6. Any failure → retry with back-off up to ~10 s, then "transfer incomplete" in the status line. Nothing is planned
     or applied. A newer GoZ (new list content) supersedes an unfinished one.
- E1 measures what the rule needs: helper start time vs. every file's `mtime_ns`, `complete_at_start`,
  `changed_after_1s`, `exclusive_open`.

---

## 8. Additional safeguards carried into P1

### 8.1 Return-conflict fingerprint (manifest, recorded at send, compared at return)

| Part | Content |
|---|---|
| Object identity | `transfer_id`, `session_id`, scene file path, `ObjectId`, object name at send, GoZ identifier (from `GoZMakeObjectPath`) |
| **Topology** | hash over the ascending `VertexId` list and the ascending `FaceId` list with each boundary as stored (rotation included); face count, vertex count; the dense index ↔ ID maps sent |
| **Positions** | hash of the float64 rest positions in ID order; separately the hash of the float32 values written to the file (for the untouched-vertex rule, audit §7.3) |
| **Placement** | `ObjectTransform` (translation, rotation rows, scale), pivot, object state; the axis/flip convention and `GoZ_Info` flags used for the send |
| **Morph representation and layer identity** | `representation` = `base` or `target:<LayerId>`; the mesh's whole point-layer meta (`LayerId`, name, kind, new-point rule, order); for a target send also the hash of that layer's offsets; for a base send also each target layer's offsets hash, because a base edit moves every relative target (J-3) and a target edited since the send is a conflict too |
| Rig binding (guard) | weights layer present (and its values hash), `Scene.rig` bone ids / rest frames hash |
| Opt-in attributes | UV hash and region hash only when the return may apply them |

Comparison at return: any difference between the current object and the manifest → `CONFLICT` (audit §6.4). A
different placement is a conflict, not something to silently compensate.

### 8.2 Other

- The receiver/helper copies before it reads (§7.2). A Mirai-side reader never parses ZBrush's live file.
- The helper never starts, edits or deletes anything outside its own inbox and capture folders.

---

## 9. Ergebnis-Tabelle (Manu füllt aus)

| # | Schritt | Ergebnis | Notiz |
|---|---|---|---|
| T0 | Version, GoZ-Wurzel, Vorlage gefunden | | |
| T1 | Installation ohne Rechteabfrage | | |
| T2.2 | Locate-Liste, Install-Schritt, Rechteabfrage, Konsolenfenster | | |
| T2.3 | Empfänger gestartet; Achsen / Maßstab / Reihenfolge; Datei fertig beim Start? | | |
| T2.4 | B und C ebenso | | |
| T3 | Ticket an laufenden Listener; Doppelklick; ZBrush hängt? | | |
| T4 | Resend aktualisiert dieselbe SubTool? | | |
| T5 | Python-Datei deckungsgleich mit OBJ-Import; Rundreise bitgleich (A, B, C) | | |
| T6 | Move-Pinsel: nur Positionen geändert (C, B) | | |
| T7 | (optional) Subdivision: welche Stufe kommt an | | |

### When a step fails, record

- a screenshot of every ZBrush dialog or note (exact text), and whether a console window appeared or stayed open;
- the newest `captures\<Zeit>\` folder (it contains `receiver_log.json`) or, if none was written, that fact;
- the content of `C:\Users\Public\Pixologic\GoZBrush\GoZ_ObjectList.txt`, `GoZ_Application.txt`, `GoZ_ProjectPath.txt`,
  `GoZApps\MiraiProbe\GoZ_Config.txt`, `GoZ_AppPathList.txt`, `GoZ_InstallLog.txt`;
- `dir /T:W /O:D C:\Users\Public\Pixologic\GoZProjects\Default` (file times);
- the ZBrush version, whether you are an administrator, whether antivirus reported anything;
- what you did just before (which button, which SubTool was active).

Then stop at that step. The rest depends on it.

---

## 10. What needs Manu

| # | Needs | Why |
|---|---|---|
| M1 | Run §6 on the reference PC (~40 min) and return `captures/` + table §9 | ZBrush 2022.0.8 exists only there; every [PC] fact |
| M2 | Accept that E1 writes `C:\Users\Public\Pixologic\GoZApps\MiraiProbe\` (removed with `--uninstall`) and that the install step may ask for admin rights | it is outside the repository |
| M3 | ~~Confirm this procedure~~ — confirmed 2026-11-05; tools written and container-tested (§5.1) | done |
| D11 | When ZBrush sends to Mirai while Mirai is **not** running: start Mirai, or leave the ticket until Mirai is started? | **Decided (Manu, 2026-11-05): leave the ticket.** The helper never starts Mirai; the next Mirai start picks the waiting ticket up. |
| D12 | Final GoZ app id/name for P1 | **Decided (Manu, 2026-11-05): folder `GoZApps\Mirai`, `NAME = "Mirai"`.** |
| D13 | A return from a SubTool that was divided in ZBrush | **Decided (Manu, 2026-11-05) after T7b/T7c:** the T7 case (Divide with SMT, every point smoothed) is **held** with a status line naming both ways out (lowest level → Cage, or Divide with SMT off); a Cage return (T7c: every point moved by a tiny amount) stays **appliable with a warning**. Built in P1 (AD-029 §6). |

Not needed from Manu: any Maxon download (§4), any decision on technical approaches inside E1.

---

## 10a. Observations (reference PC, 2026-11-05, captures on `main` up to `e9e50bb`)

| # | Observation | Source |
|---|---|---|
| T0 | Root `C:\Users\Public\Pixologic`; no Maxon folder; existing GoZ apps Cinema4D, Max, Maya, Photoshop. Python 3.14.2 (Windows). | `captures/inventory.txt` |
| T1/T2.2 | `MiraiProbe` appears in the **R** list only after a ZBrush restart. ZBrush runs `Locate.bat` with cwd = the app folder and `Init.bat` with cwd = `C:\WINDOWS\system32` (elevated, as the SDK says), both without arguments. | Manu; `captures/commands_log.txt` |
| T2.3 | ZBrush runs `Edit.bat` **without arguments**, cwd = the app folder. The identifier is the Tool name (`…\GoZProjects\Default\A`, forward slashes), the mesh name `GoZMesh_A` (ZBrush writes the `GoZMesh_` prefix). Header text `" 1.0 ZBrush GoZ Binary......"`. Blocks: MESH, FLAGS (0), POINT_LIST, FACE4 format 1, MRGB, MASK16, GROUPS, CREASE, END (size field 0). | `captures/2026…_receive/dump.txt` |
| T2.3 | **Complete at start:** every file was written 359–423 ms before `Edit.bat` started, parsed completely, opened exclusively and was unchanged after 1 s (6 of 6 transfers). It supports the SDK statement (save first, then call); 6 small files are not a proof for large ones. | receive logs |
| T2.3 | **Orientation, OBJ path:** `x_goz = x`, `y_goz = −y + 0.95`, `z_goz = −z + 0.55` (A's `ymin + ymax`, `zmin + zmax`): a 180° rotation about X through the bounding-box centre, residual 1.9e-8 (float32). Vertex order and face corner lists identical, winding kept (det +1). Whether the offset depends on the object (bounding-box centre) or on ZBrush's stored position is open → T5.2. | T2 dump of A |
| T3 | Every GoZ press started `Edit.bat`; the running listener got a ticket each time 1.06–1.25 s after the receiver started (1 s of it is the settle time); no second listener. ("hashes NOT ok" was a probe bug, fixed in `3475d25`.) | Manu |
| T4 | `--resend` of ZBrush's own file: the file was already byte-identical; `GoZBrushFromApp -tmap` exited 0 after 0.25 s. | `send_resend/send_log.json` |
| T5.1 | `GoZMakeObjectPath` returned `…\Default\E1_A` in 54 ms (exit 0); `GoZBrushFromApp -tmap` exited 0 after 0.6 s. ZBrush made a **new Tool** (GoZ preference *Import as SubTool* off). | `send_A/send_log.json`, Manu |
| T5.2 (`-tmap` phase, 12:41–16:54) | About 30 `probe_send` runs with `GoZBrushFromApp.exe -tmap` (styles sdk, gozmesh, zbrush; meshes A, B, C) mostly brought an 8-point placeholder cube (`GoZMesh_d54dgsd5gs52gsdg21456sd4g`, later `…4g1`) or the Tool active in ZBrush back, not the sent mesh. One exception: 13:15 `--style gozmesh` → 13:16 `E1_A` returned bit-identical. | send logs, receive dumps 12:48–13:56 |
| T5.2 (no `-tmap`, 16:57–17:47) | Every send without `-tmap` worked, with `--style sdk` **and** `--style gozmesh` (Manu: both work). **Cause: the `-tmap` argument**, which the probe had taken over as default from the SDK demo (`0b208e1` made it opt-in). Most plausible reading: with `-tmap` ZBrush acts on the *active* Tool (the demo transfers texture maps), so the result depended on which Tool was active — hence the "state" impression and the one success at 13:16. Neither the `GoZMesh_` prefix nor the extra blocks are required (an earlier entry here said the prefix was the cause; the later captures refute it). | send logs 16:57–17:47; receive dumps 17:27, 17:47 |
| T5.2 | **Python → ZBrush → Python is the identity:** A (17:27) and C (17:47, `--style sdk`) came back with `x' = x, y' = y, z' = z`, residual 0, points bit-identical (float32), face corner lists and order identical, `FLAGS` 0. | receive dumps 17:27, 17:47 |
| T5.2 vs T2 | Consequence: OBJ path and GoZ path do **not** place a mesh alike in ZBrush. OBJ → ZBrush → GoZ gives `y' = −y + (ymin+ymax)`, `z' = −z + (zmin+zmax)` (T2, mesh A only), GoZ → ZBrush → GoZ gives the identity, so a GoZ-sent mesh sits rotated 180° about X relative to the same mesh imported as OBJ. Which of the two ZBrush shows upright, and whether the OBJ offset is always the bounding-box centre (only A was measured), is **not settled**; the `GoZ_Info.txt` flip options (`EXPORT_/IMPORT_FLIP_Y/Z`) are the SDK's mechanism for it, their exact effect is untested. → first step of P1 (§11). | T2 and T5.2 dumps |
| T6 | Move brush on `E1_C` (17:34): counts, face lists and order unchanged; 101 points changed, 225 bit-identical. Larger edits on `E1_A` (17:29) and `E1_C1` (17:45) also kept counts and order; there the probe's axis fit fell back to the bounding box (correlation < 0.999), so it did not count points — a probe limitation, the data are in the captures. | receive dumps 17:29, 17:34, 17:45 |
| T6 (B) | Move edit on `E1_B` (18:10, Mirai sphere with 64 triangles, an open border and ID gaps): 481 / 508 unchanged, the 64 triangles come back as triangles (4th index −1), face corner lists and order identical; 12 points changed, 469 bit-identical. | receive dump 18:10 |
| T7 | `E1_C1` divided once in ZBrush (18:14, two GoZ presses, byte-identical files): GoZ sent the **base topology** (326 / 324, order and corner lists identical) and **no `GoZ_TAG_SUBDIV` block**, but **every point moved**: each equals the Catmull-Clark vertex point of one subdivision step of the sent cage (max deviation 5.1e-7 = float32; the limit position differs by up to 0.026). So a subdivided SubTool returns a *smoothed cage*, not the cage the artist sculpted, and nothing in the file says so. | receive dumps 18:14; computed against `meshes/C` |
| T7b | Head (`E1_C1`, sent 18:55 raw) divided once with **SMT off**, GoZ (18:57): all 326 points **bit-identical**, faces identical. One GoZ press only (the level it was sent from is not recorded). | receive 18:57 (`20261105-185718_469`) |
| T7c | Head (sent 18:57:58 raw) divided with **SMT on**, lowest level, **Cage**, GoZ (18:58): topology identical, **no point bit-identical**; deviation from the sent cage median 1.0e-5, 90 % ≤ 6.7e-5, max 4.1e-4 (head extent 5.2; T7 without Cage: max 0.19). Cage is a close, not an exact, reconstruction. | receive 18:58 (`20261105-185830_405`) |
| P1 symmetry | Head via P1, ZBrush X symmetry on: **Move** brush returns all 145 mirror pairs bit-exact; **Smooth** brush breaks 76 of 145 pairs (median 0.0056, max 0.0102 = 0.2 % of the head; thousands of float32 ulps, i.e. not rounding) and moves 13 of 36 seam points off the plane (max 0.0048). ZBrush's symmetric Smooth is not exact. → AD-029 §6 (made exact within 1 % while Mirai's symmetry is on). | `ticket_01793909441692885900_16724` (Move), `ticket_01793909578397887700_19924` (Smooth), Manu 2026-11-05 |
| P1 orientation | **Verified (Manu, 2026-11-05):** P1's send `(x, −y, −z)` of the head from Mirai's SPACE row shows it upright in ZBrush ("Kopf steht aufrecht, Senden klappt jetzt"). The T7b/T7c sends of 18:20–18:58 were still raw. | Manu |
| T5 (orientation) | A mesh sent unchanged (Mirai coordinates, `FLAGS` 0) shows in ZBrush **upside down and seen from behind** (head, Manu): rotated 180° about X relative to ZBrush's own view, matching T2's OBJ → GoZ result. | Manu, 2026-11-05 |
| T2–T6 | **Complete at start in every transfer** (17 receive captures): written 359–791 ms before `Edit.bat` started, parsed completely, exclusive open ok, unchanged after 1 s. | receive logs |
| T8 / E2 | Head sent with `--groups bands` (ids 101–104) twice (`E1_C_P1_G` 22:31, `E1_C_P1_G1` 22:33). Every return carried each face's sent id unchanged (per face equal to the send log). After a regroup in ZBrush (22:36) 12 faces of 104 came back as **3225**, everything else unchanged, points bit-identical. The groups were visible in ZBrush without `--import-polygroups` (step 4 not run, Manu 2026-11-05). → P2a links by id (WP_GOZ_P2_PLAN §2). | receive `20261105-223148_915`, `…223211_751`, `…223403_371`, `…223614_741` |
| T9 / E3 | UV4 sent as-is comes back identical (no flip; ZBrush's GoZ of the OBJ import equals its `vt`). UV Master returns new UVs on all faces. *New From Polypaint* → a TEXTURE_MAP_PATH `<Tool>_TXTR.tif` (uncompressed TIFF 2048² RGB, stored bottom-up: matches the MRGB polypaint, byte order B G R mask, with row 0 = v 0). `--target bump`: both objects arrive, bit-identical. Layer import of `C_bump.obj` into a recording layer: weight 1.0 (slider 1), 1.0 again with the layer switched off, 0.5 (slider 0.5); the layer survives a resend. → WP_GOZ_P3_PLAN §2. | receive `20261106-095115_060` … `…100117_305`, `send_resend 100330` |
| — | `captures/20261105-161526_255_send_A/send_log.json` is not valid JSON (a diagnostic of the reverted commit `d35a8a3` wrote into it); ignore it. | — |
| — | ZBrush's own untouched-mesh blocks: MRGB `ff ff ff 01` per vertex, MASK16 `ffff`, GROUPS 0, CREASE 0 (CREASE block size 16 + faces, not padded to 4). `encode_goz(style="zbrush")` reproduces the T2 file byte for byte (fixture `tests/fixtures/zbrush2022_0_8_obj_import_A.GoZ`). | T2 capture |
| T11b | Multi-object send with *Import as SubTool* off, clean folder: all `.ztn` still → SubD_Cube (Hypothesis B confirmed). ZBrush always groups a multi-object GoZ_ObjectList into one Tool with SubTools regardless of the setting. | `captures/20261106-155654_089_names` |

## 11. Result of E1 (2026-11-05)

**Status: DONE for the handshake; two small checks moved to the start of P1.** Evidence: §10a and `captures/`.

| Question | Answer | Label |
|---|---|---|
| E1-Q1 register Mirai as a GoZ target | **Yes.** A `GoZApps\MiraiProbe\` folder with `GoZ_Info.txt` and three `.bat` commands works; ZBrush lists it after a restart. | [PC] verified |
| E1-Q2 how ZBrush launches the target | `Edit.bat` after every GoZ press, **no arguments**, cwd = the app folder; `Locate.bat` once (cwd app folder); `Init.bat` elevated (cwd `system32`). | [PC] verified |
| E1-Q3 notify a running Python process | **Yes**, via helper → atomic ticket → polling listener; 1.06–1.25 s incl. 1 s settle; never a second instance. | [PC] verified |
| E1-Q4 files complete at the launch | **Yes in all 17 transfers** (written 0.36–0.79 s before the launch). The §7 rule (strict parse + wall-clock settle + re-hash) stays, at no cost for small meshes; large meshes unmeasured. | [PC] verified for ≤ 326 points |
| E1-Q5 GoZ root, project folder | `C:\Users\Public\Pixologic`, `GoZProjects\Default`; identifiers in ZBrush's list use forward slashes, ours backslashes — both work. | [PC] verified |
| E1-Q6 orientation and scale | GoZ round trip is the **identity** (scale 1, no offset, `FLAGS` 0). Mirai's frame (Y up, like OBJ) shows in ZBrush upside down and from behind, i.e. GoZ = Mirai rotated 180° about X. **Conversion for the bridge: send `(x, −y, −z)`, read back with the same map** (it is its own inverse, det +1, so winding stays; float32 sign flips are exact, so the untouched-point rule of audit §7.3 still holds). The OBJ path's extra offset (`ymin+ymax`, `zmin+zmax`, T2) only matters for lining up with OBJ-imported Tools, not for the bridge. | [PC] verified (unflipped view 2026-11-05; flipped P1 send upright, Manu 2026-11-05) |
| E1-Q7 vertex and face order | **Preserved** both ways (A, B, C: identical corner lists, unchanged points bit-identical, a Move-brush edit changes only positions; B's triangles and open border survive). | [PC] verified |
| E1-Q8 Python → ZBrush | **Yes** with `GoZMakeObjectPath` + `GoZBrushFromApp` **without `-tmap`**; identifiers are made unique by ZBrush (`E1_C1`); `--style sdk` suffices. A send arrives as a new Tool while *Import as SubTool* is off. | [PC] verified |
| E1-Q9 subdivision | After one Divide GoZ sends the base topology with **all points replaced by one-step Catmull-Clark vertex points** (float32-exact), no SUBDIV block; identical whether sent from level 1 or 2 (two presses, byte-identical). Higher-level detail does not come back. | [PC] verified (one Divide, head) |

**Carried into P1** (do first, small, on the reference PC):
1. *(Done 2026-11-05: Manu, P1 send of the head through Mirai's SPACE row: "Kopf steht aufrecht".)* Orientation: confirm once that a send with `(x, −y, −z)` shows the head upright and from the front (E1 showed the unflipped send upside down and from behind). Flip in the file, not via `GoZ_Info.txt` options (their effect is untested, and the file flip is exact and testable).
   Run (2026-11-05): `python -I experiments/goz_probe/probe_send.py --mesh C --axis bridge` writes C as `(x, −y, −z)` under
   its own identifier `E1_C_P1` (never updates the unflipped `E1_C…`); in ZBrush look at the front view, then press **GoZ**
   once (MiraiProbe still the target): the receiver must report `y' = −y`, `z' = −z` against the unflipped `C.sent.json`,
   bit-identical otherwise — i.e. reading back with the same map is the identity.
2. *(Done 2026-11-05: T7b/T7c measured, D13 decided, built in AD-029.)* Subdivision guard (from T7): a return whose every point equals the one-step Catmull-Clark vertex point of the sent cage is a *subdivided* SubTool, not an edit. P1 must detect it (compare with the vertex points of the manifest's sent cage) and refuse the in-place update with a status line, instead of silently shrinking the cage; the file carries no subdivision record. Mixed cases (Divide + sculpt) cannot be separated from a real edit by this test — a decision for Manu (D13).

**Rules for P1 that E1 established:** never name a GoZ application in `GoZ_Application.txt` that ZBrush does not know (P1's first send, 2026-11-05: ZBrush 2022.0.8 crashed on `Mirai` without `GoZApps\Mirai`; AD-029 §3); never call `GoZBrushFromApp` with `-tmap` for a mesh send; never rewrite the artist's ZBrush GoZ preferences (*Import as SubTool*); identity through `GoZMakeObjectPath` identifiers plus the manifest fingerprint (§8.1), because ZBrush can return a different object under a known name (the `-tmap` phase did exactly that); write `--style sdk` or `gozmesh` (both accepted; `zbrush` is byte-identical to ZBrush's own files if ever needed); keep the §7 completeness rule.

P1 (audit §8.2) is built: [AD-029](../../docs/architecture/AD-029-ZBRUSH-GOZ-BRIDGE.md), `src/interop/goz/`, captures copied to `tests/fixtures/goz/`. This folder stays as the GoZ reference (captures as fixtures) until P1 has its own, then it is archived like the other finished experiments (`experiments/README.md`).
