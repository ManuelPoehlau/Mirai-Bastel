# Mirai ↔ ZBrush Bridge — Phase 0: Feasibility & Architecture Audit

**Status:** AUDIT (2026-11-05), discovery only. No code, no Core change, no keymap change. Not a decision and
not a spec. Every proposal below is `PROVISIONAL` until Manu decides (§10.3).
**Target:** ZBrush 2022.0.8 (Windows), GoZ, Mirai at `4601852` (branch `ccr-eaa6cd2b-06u6l4`).
**Builds on:** [AD-021](../architecture/AD-021-OBJECT-COMPONENT-MODEL.md) (objects, `ObjectId`),
[AD-023](../architecture/AD-023-INCREMENTAL-TOPOLOGY-SYNC-AND-HISTORY.md) (change journal),
[AD-025](../architecture/AD-025-TOPOLOGY-PROVENANCE-AND-POINT-LAYERS.md) (point layers, morph targets),
[AD-026](../architecture/AD-026-FACE-CORNER-UVS-AND-TEXTURE.md) (UVs; Manu's existing ZBrush OBJ round trip),
[AD-028](../architecture/AD-028-SKELETON-AND-SKINNING.md) (rig, weights, posed refusal),
[AD-REGIONS-01](../architecture/AD-REGIONS-01-FACE-REGIONS-STORAGE.md) (polygroups),
[CORE_V1_FREEZE](../architecture/CORE_V1_FREEZE.md) §7 (Core change rule).

**Labels.** Every finding carries one:
**[VERIFIED]** read in Mirai's code or in a primary source during this audit ·
**[PARTIALLY VERIFIED]** seen in a secondary source (a third-party GoZ implementation, a search summary of official
docs) or derived, but not confirmed against the official SDK or ZBrush 2022.0.8 itself ·
**[UNVERIFIED]** plausible, not checked · **[OPEN QUESTION]** needs an experiment or a decision.

**Research limits (important).** The official GoZ SDK PDF and download (`developers.maxon.net`), Maxon help
(`help.maxon.net`), ZBrushCentral and SideFX were **blocked by this session's network policy** (HTTP 403 at the proxy).
GoZ facts therefore come from (a) web-search summaries of those official pages and (b) reading the open-source
Blender add-on **GoB** (`github.com/JoseConseco/GoB`, GPL-2.0-or-later), a long-maintained reverse-engineered GoZ
client. GoB was read **as a format reference only**; nothing of it may be copied into Mirai (GPL, AGENTS.md §7a).
No ZBrush was available. Hence no GoZ fact below is [VERIFIED] against ZBrush 2022.0.8.

**Addendum 2026-11-05 (Phase 0b, E1 preparation).** The official SDK PDF and the download "ZBrush GoZ SDK 2022.0"
(`goz_sdk.zip`) were read first-hand. The source-labelled facts now live in
[`experiments/goz_probe/README.md`](../../experiments/goz_probe/README.md) §2, which takes precedence over §3 here. Corrections:
(1) a block header is `uint32 tag, uint32 size, uint32 count, float32 modifier` (not a `uint64` count); tag `0x1389` is
`GoZ_TAG_FLAGS` and `0x138A` is `GoZ_TAG_SUBDIV`, the mesh name is tag `1` (§3.3); n-gons are officially "not yet
supported"; mask16 `0xFFFF` = unmasked. (2) Identity: the SDK's "Unique object identifier" (`GoZMakeObjectPath.exe`, the
`GoZ_ObjectList.txt` line) links an app object to a SubTool, so identity is not by name only (§3.4, §7.1). (3) Registration:
`EDIT_COMMAND` / `LOCATE_COMMAND` / `INIT_COMMAND` may be `.bat`; the editing utility must reuse a running instance, so
Mirai needs a small helper (§4). (4) The two-poll file-stability rule of §7.6 is replaced by the E1 README §7 rule.
(5) The return-conflict fingerprint of §7.1 is extended there (§8.1: placement, morph representation, layer identity).
§3.1's "SDK not found" is superseded: the 2022.0 SDK exists. No ZBrush 2022.0.8 behaviour is verified yet; that is E1.

**Addendum 2026-11-05 (E1 done on the reference PC).** Result: [`experiments/goz_probe/README.md`](../../experiments/goz_probe/README.md)
§11. Verified on ZBrush 2022.0.8: Mirai can be registered as a GoZ app (`.bat` commands, visible after a ZBrush restart);
ZBrush starts the editing command after every GoZ, without arguments, with all files already complete; a running
Python process is notified through a helper and a ticket; Python → ZBrush works with `GoZMakeObjectPath` +
`GoZBrushFromApp` **without** `-tmap` (with it ZBrush returned whatever Tool was active); the GoZ round trip keeps
vertex order, face corner lists and unchanged points bit-identical. Triangles and open borders survive (mesh B).
**Subdivision:** after a Divide in ZBrush, GoZ returns the base topology with every point replaced by its one-step
Catmull-Clark vertex point and no subdivision record, so an unsculpted subdivided SubTool looks like an edit of every
point (a shrunk cage) - P1 needs a guard for it (§7.2, README §11). Orientation: a mesh sent in Mirai's frame shows in
ZBrush upside down and from behind, so the bridge sends `(x, −y, −z)` and reads back with the same map (self-inverse,
det +1); P1 confirms the flipped send once. D8 (register as a GoZ app) is technically
answered: yes.

---

## Kurzfassung für Manu (Deutsch)

- **Machbar: ja, mit Einschränkungen.** Eine Brücke Mirai → ZBrush → Mirai für **ein Objekt mit unveränderter
  Topologie** (nur Punkte verschoben) ist technisch gut machbar. Mirai hat fast alles schon: stabile Vertex-IDs,
  einen atomaren Änderungs-Weg mit genau einem Undo-Schritt (`_mesh_transaction`), UVs, Polygruppen (Regionen),
  Morph-Ziele und Gewichte, die an Vertex-IDs hängen, und einen OBJ-Weg, den du mit ZBrush schon benutzt (AD-026).
- **GoZ-SDK als Grundlage: nur teilweise.** Das „SDK“ ist im Kern ein **Dateiformat plus eine Ordner- und
  Text-Datei-Konvention** (C++-Beispielcode, PDF). Mirai braucht davon **keine kompilierte Komponente**: eine
  eigene, saubere Python-Lese/Schreib-Routine für das `.GoZ`-Format und das Starten von `GoZBrushFromApp.exe` reichen
  voraussichtlich. Das SDK ist die **Referenz**, nicht die Laufzeit-Abhängigkeit. Dass es mit 2022.0.8 so
  funktioniert, ist **nicht geprüft** (kein ZBrush hier, Maxon-Seiten im Container gesperrt).
- **Erste Version überträgt:** Positionen (gleiche Topologie), UVs hin (zurück nur prüfen), Polygruppen ↔ Regionen
  als zweiter Test. **Nicht** in Version 1: Polypaint zurück (Mirai hat keinen Farbspeicher), Masken dauerhaft,
  Subdivision-Stufen, ZBrush-Layer, Gewichte über Topologie-Änderungen.
- **Größte Risiken:** (1) Mirai-N-Gons — GoZ kennt nur Drei- und Vierecke; (2) ZBrush „repariert“ Geometrie und
  ändert so die Topologie unbemerkt; (3) Identität nur über den Namen in ZBrush; (4) Genauigkeit (GoZ speichert
  32-Bit-Floats, Mirai 64-Bit) und Mirais exakte Symmetrie-Paarung; (5) Rückgabe in eine Szene, die sich inzwischen
  geändert hat.
- **Nächster Schritt:** ein kleines Handshake-Experiment **auf deinem Windows-PC mit ZBrush 2022.0.8** (§8.1) —
  braucht deine Freigabe und das SDK-PDF/Download von dir. Danach ein Production-Prototyp (nur Positionen).
- **Deine Entscheidungen** (§10.3): u. a. ob eine Rückgabe automatisch übernommen oder erst bestätigt wird, was bei
  geänderter Topologie passiert (Vorschlag: nie ersetzen, nur als neues Objekt), und ob Mirai sich als eigene
  GoZ-App bei ZBrush einträgt.

---

## 1. Executive summary

1. **Feasible for a restricted first version.** A same-topology, positions-only round trip of one Mirai object
   through ZBrush 2022.0.8 is technically feasible with Mirai's existing infrastructure [VERIFIED for the Mirai side,
   PARTIALLY VERIFIED for the GoZ side]. Mirai already has: stable, never-reused vertex IDs (`core/ids.py`); a single
   atomic commit boundary with exact rollback and one Undo step (`Application._mesh_transaction`,
   `src/mirai/application.py:3140`); a world-space OBJ writer whose vertex order is the vertex-ID order
   (`src/mirai/obj_export.py`); and every attribute that must survive (morph offsets, skin weights, UVs, regions)
   keyed by `VertexId`/`FaceId`, so a positions-only write leaves them intact by construction.
2. **GoZ is a file protocol, not a library.** What the "GoZ SDK" provides, per every source reachable, is a binary
   file format (`.GoZ`, header `GoZb`), a C++ reader/writer class (`GoZ_Mesh`), demo projects, and a convention of
   text files in a shared public folder (`GoZ_ObjectList.txt`, `GoZ_Application.txt`, `GoZApps/<App>/…`) plus the
   ZBrush-side launcher `GoZBrushFromApp` [PARTIALLY VERIFIED]. An external Python application can implement all
   of that without compiling anything [PARTIALLY VERIFIED: GoB does exactly this in pure Python]. The SDK is the
   right **reference** for the format; it is not needed as a runtime dependency.
3. **ZBrush 2022.0.8 has no Python API** (introduced with ZBrush 2026.0 [PARTIALLY VERIFIED]). Automation on the
   ZBrush side is limited to GoZ itself and ZScript (`[FileNameSetNext] [IPress,Tool:Import]`, SubTool loops)
   [PARTIALLY VERIFIED]. The ZBrush → Mirai direction is always started by the artist pressing GoZ in ZBrush; Mirai
   can only *detect* the return (file watch). Mirai → ZBrush can be started from Mirai.
4. **Biggest Mirai risks:** n-gons (GoZ faces carry at most 4 corners), ZBrush's silent geometry repair, identity by
   SubTool name only, float32 quantisation against Mirai's exact position-based symmetry correspondence, and returns
   into a scene that changed since the send. All are handled by one rule: **the return is a plan computed and
   validated in full before anything is written; only a proven same-topology positions update is ever applied in
   place; everything else becomes a new object or a refusal** (§7).
5. **Recommendation: proceed with restrictions** (§10): first an approved, minimal handshake experiment on Manu's
   Windows PC (§8.1), then an isolated Production module for the positions-only round trip.

---

## 2. Existing Mirai infrastructure (traced in code)

### 2.1 Mesh data and serialization

| Finding | Where | Label |
|---|---|---|
| `Mesh` stores vertices/edges/faces in dicts keyed by opaque IDs; faces are ordered boundaries of any length (tris, quads, **n-gons**). Topology only through the query API. | `src/core/mesh.py:499` (`Mesh`), module docstring §1–4 | VERIFIED |
| IDs are monotonic, never reused in a session, serialized 1:1 with their counters; an ID is never an array index. | `src/core/ids.py` (`IdAllocator`), AD-001 | VERIFIED |
| `all_vertex_ids()` / `all_face_ids()` iterate in ascending ID order — the same after snapshot load or delta apply. IDs are **not contiguous** after deletions. | `src/core/mesh.py:989–995`, invariant comment in `Mesh.__init__` | VERIFIED |
| Whole-state JSON: `Mesh.export_state()` / `load_state()` (positions as float64, `symmetry`, `face_regions`, `point_layers`, `face_uvs`); `load_state` validates the whole state before the first write. | `src/core/mesh.py:2160`, `:2273` | VERIFIED |
| Scene file: `core/serialization.py` versions 2–7, written atomically by `Application.save_scene_file` (tmp file + `os.replace`). Selection, History, mask, hidden state and pose are **not** saved. | `src/core/serialization.py`, `src/mirai/application.py:953` | VERIFIED |
| CLAUDE.md: the change journal (`begin_change` / `end_change` / `rollback_change`, `MeshDeltaCommand`, `Mesh.watch()`) is the tool for history, rollback and derived data — not snapshots. | `src/core/mesh.py:2404–2570`, `src/core/operations/topology.py:64` | VERIFIED |

### 2.2 OBJ import/export (the existing ZBrush path)

| Finding | Where | Label |
|---|---|---|
| **Export:** `ObjectController.export_obj` writes the **document object** (the base's rest shape, never the morph editing view) in **world space** (`object_space.to_world`), atomically, one `o` record. `mesh_to_obj` writes `v` in vertex-ID order, `vt` deduplicated, `f v/vt`, no normals, polygons as they are (n-gons stay n-gons), `%.9g` precision. | `src/mirai/controllers/objects.py:345`, `src/mirai/obj_export.py:19` | VERIFIED |
| **Import:** `Application.import_obj` → `_load_obj` → `loaders.obj_loader.load_obj` → `scene_factory.mesh_from_obj_data` builds a **new** mesh (fresh IDs from 0) and adds it as a **new object** (one Undo step, `ObjectController.add_mesh_object`). Parse errors fly before the scene is touched. | `src/mirai/application.py:731`, `:784`; `src/mirai/scene_factory.py:179–230`; `src/mirai/controllers/objects.py:320` | VERIFIED |
| The OBJ parser ignores `o`, `g`, `s`, `vn` — so **ZBrush polygroups exported as `g` are dropped** on OBJ import today. | `examples/loaders/obj_loader.py:206` | VERIFIED |
| There is **no "update an existing object from a file" path**. Every import creates a new object. | (absence; `import_obj`, `add_reference`, `load_scene` are the only file entries) | VERIFIED |
| AD-026 already documents Manu's manual ZBrush OBJ round trip (UVs, texture, Flip V); its practical test B24 was pending at the time of writing of AD-026. | AD-026 header, §5, B24 | VERIFIED (doc); B24 outcome UNVERIFIED |
| UI: `src/obj_files.py` lists `obj/` in the SPACE menu (no OS dialogs, `PROVISIONAL`). | `src/obj_files.py` | VERIFIED |

### 2.3 Object identity

| Finding | Where | Label |
|---|---|---|
| `ObjectId` is monotonic per scene, never reused, saved with `object_id_counter`; restored by `Scene.from_objects`. Stable across save/load **of the same scene lineage**. | `src/core/ids.py` (`ObjectId`), `src/core/scene.py` (`Scene.from_objects`, `add_object`) | VERIFIED |
| There is **no scene-level persistent identity** (no UUID). Two unrelated scene files can both contain `ObjectId(3)`. Object names are not unique by contract (`unique_object_name` is a convenience). | `src/core/serialization.py` (`scene_to_dict` keys), `src/mirai/scene_objects.py:235` | VERIFIED |
| An element is only unique together with its object: `(ObjectId, VertexId)`. | `src/core/ids.py` docstring | VERIFIED |

### 2.4 Mesh update and replacement

| Finding | Where | Label |
|---|---|---|
| `Application._mesh_transaction(description, mutate)`: the one commit boundary. Journals the change, **rolls back exactly if `mutate` raises**, records nothing if unchanged, else pushes one `MeshDeltaCommand`, mirrors the selection, notifies viewport/pick cache. | `src/mirai/application.py:3140` | VERIFIED |
| `Application.apply_mesh_change` is the external-host entry: refused while an interaction runs (`RuntimeError`) and **refused while the bound mesh is posed** (AD-028 §7.1). | `src/mirai/application.py:3109–3138` | VERIFIED |
| Both act on `scene.mesh` = the **edit object's** mesh only. A return into a non-edit object needs an edit-object switch first (existing Q-5 gesture / `ObjectController.set_edit_object`) or a new controller entry. | `src/mirai/application.py:3159`, `src/mirai/controllers/objects.py:737` | VERIFIED |
| Positions-only writes (`set_vertex_position`) never touch topology, UVs, regions or point layers. | `src/core/mesh.py:713`; AD-026 §1.2; AD-025 §4.3 | VERIFIED |

### 2.5 Topology validation and vertex correspondence

| Finding | Where | Label |
|---|---|---|
| Mesh invariants are test-checked (`tests/mesh_invariants.py`, incl. UV invariant U1). | `tests/mesh_invariants.py` | VERIFIED |
| Correspondence is **by ID**, never by index: morph offsets, weights (point layers, packed by `VertexId` → slot) and UVs/regions (by `FaceId`). A file round trip by index therefore needs an explicit index ↔ ID map. | `src/core/layer_storage.py` docstring, `src/core/mesh.py` | VERIFIED |
| Provenance for new vertices (`origin`) exists only inside Mirai operations (AD-025); an external tool's new vertices have no provenance. | AD-025 §4.1 | VERIFIED |
| Symmetry correspondence is derived from **exact** mirrored positions (`vertex_correspondence`: dict lookup of the mirrored position). Any position change that is not exactly mirrored breaks a pair. `mirai/resymmetrize.py` exists to restore it. | `src/mirai/symmetry.py:118–143`, `src/mirai/resymmetrize.py` | VERIFIED |

### 2.6 Morph targets, rigging, rest pose

| Finding | Where | Label |
|---|---|---|
| A morph target is a `LayerKind.VECTOR` point layer of **offsets** relative to the base (Manu J-3 "relativ": targets follow later base edits). Every VECTOR layer counts as a morph target (`morph_target_ids`). | `src/mirai/morph_targets.py:1–40`, `:90` | VERIFIED |
| Weights (morph mix) are view state, not saved. The mesh positions are always the **rest/base** shape; the mix is evaluated separately (`morph_mix.MixSurface`). Export already sends the base (`document_object`). | `src/mirai/morph_targets.py` docstring, `src/mirai/morph_mix.py`, `src/mirai/controllers/objects.py:352` | VERIFIED |
| Editing a target is done on a transient **editing view** (`TargetView`); its gestures are translated into offsets `d = p − b` on the touched points, written into the base's layer in one recording (`TargetView.translate`). This is exactly the rule a "ZBrush-sculpted target" return needs. | `src/mirai/morph_targets.py:242–330` | VERIFIED |
| Rig: `Scene.rig` (bones, rest frames); weights = `LayerKind.WEIGHTS` point layer keyed by `BoneId`. Pose is view state (not saved). Posed bound mesh refuses all position/topology edits; bound placement is locked. | `src/core/rig.py`, `src/mirai/skinning.py`, AD-028 §3, §6, §7 | VERIFIED |
| Topology edits on layered meshes are fail-closed through `layer_declarations` (only declared operations, each with a rule for new points). An externally changed topology has no such rule. | `src/mirai/layer_declarations.py` | VERIFIED |

### 2.7 UVs, vertex colours, polygroups, masks

| Data | Mirai today | Label |
|---|---|---|
| UVs | Core face-corner UVs, one map per mesh, journaled, saved (AD-026). | VERIFIED |
| Vertex colours / Polypaint | **No storage.** Only overlay colours in the viewport. A colour as a VECTOR layer would be misread as a morph target (`morph_target_ids`). | VERIFIED |
| Polygroups | `FaceRegions` on the Mesh: **named** face sets, journaled, saved; the Core allows overlap, the app's group rule puts a face in one group (`regions.grouped`). Region tints are "ZBrush-like". | VERIFIED (`src/core/mesh.py:325–360`, `src/mirai/regions.py`) |
| Masks | `VertexMask` per object in `Application._masks`: values in (0, 1], **view state** — not mesh data, not in History, not saved, cleared on scene load. | VERIFIED (`src/mirai/mask.py`, `src/mirai/application.py:452`, `:691`) |
| Hidden | `HiddenSet`, view state like the mask. | VERIFIED (`src/mirai/hidden.py`) |

### 2.8 External process / file patterns

| Finding | Where | Label |
|---|---|---|
| **`src/morph_bridge.py`** is the precedent for an external bridge: writes a one-object scene file and starts the Morph Lab with `subprocess.Popen`, no pyglet import, no History entry, one-way. | `src/morph_bridge.py:1–60` | VERIFIED |
| Atomic writes via tmp file + `os.replace` (scene save, OBJ export). | `application.py:953`, `objects.py:345` | VERIFIED |
| A 60 Hz main-loop tick exists (`pyglet.clock.schedule_interval(_tick, 1/60)`), the natural place for a cheap mtime poll. No file watcher or thread exists today. | `src/main.py:787–797` | VERIFIED |
| Headless-testable "file module + label" pattern (`SceneFiles`, `ObjFiles`, `MorphBridge`): no pyglet, `Application` does the work. | `src/scene_files.py`, `src/obj_files.py` | VERIFIED |

### 2.9 Suitable location for an isolated module

Proposal [PROVISIONAL]: a new package **`src/interop/goz/`** (pure: no pyglet, no `Application` import), wired by a thin
`src/zbrush_bridge.py` beside `morph_bridge.py` / `obj_files.py` (the window-level glue), and one public
`Application` method for the apply step that runs inside `_mesh_transaction`. Nothing in `src/core/` changes for
the first version. Details in §6.

---

## 3. GoZ SDK 2022.0 — investigation and compatibility

### 3.1 Availability

| Finding | Label |
|---|---|
| The official source is Maxon Developers → Downloads (ZBrush GoZ SDK: C++ demo projects and source) and the PDF `developers.maxon.net/docs/zbrush/goz_sdk.pdf`. A Maxon SDK specialist states the GoZ SDK is the only ZBrush SDK. | PARTIALLY VERIFIED (search summaries of the official pages) |
| A package explicitly labelled **"GoZ SDK 2022.0"** was **not found** in reachable sources; the version label and its file list are unknown here. | OPEN QUESTION |
| The SDK is not in the repository and could not be downloaded (host blocked). Per scope, nothing was installed. | VERIFIED |

**Needed from Manu:** the SDK download (zip) and/or the PDF, or allow `developers.maxon.net` in the session's network
settings, so a later phase can check every format claim below against the official `GoZ_Mesh.h/.cpp` and `GoZ_Binary.h`.

### 3.2 What the SDK provides (as far as reachable)

| Item | Content | Label |
|---|---|---|
| File format | Binary `.GoZ`, one SubTool per file; header starts with `GoZb` (GoB writes `"GoZb 1.0 ZBrush GoZ Binary"` + six `.` = 32 bytes, then an object-count block). | PARTIALLY VERIFIED |
| C++ class `GoZ_Mesh` | Read a file into fields, fill fields and `writeMesh`. Header/tag definitions in `GoZ_Mesh.h/.cpp`, `GoZ_Binary.h`. | PARTIALLY VERIFIED |
| Folder convention | `[PUBLIC]/Pixologic/GoZBrush/` (ZBrush side: `GoZ_ObjectList.txt`, `GoZ_Application.txt`, `GoZ_ProjectPath.txt`, `GoZ_Config.txt`, launcher `GoZBrushFromApp`), `[PUBLIC]/Pixologic/GoZApps/<App>/` (per-app `GoZ_Info.txt`, `GoZ_Config.txt` with the app path, app-side scripts), `[PUBLIC]/Pixologic/GoZProjects/Default/` (the exchanged `.GoZ` files, `.ztn`). | PARTIALLY VERIFIED |
| Path for 2022.0.8 | `C:\Users\Public\Pixologic\…` (Pixologic era). Maxon's current docs list `C:\Users\Public\Documents\Maxon\GoZProjects\` for newer versions and the Pixologic paths for legacy ones. | PARTIALLY VERIFIED — must be confirmed on Manu's PC |
| Native parts | The SDK's samples are C++; the **protocol needs no native code** on the app side: a pure-Python client (GoB) reads/writes `.GoZ`, writes the text files and starts ZBrush. Only ZBrush's own `GoZBrushFromApp.exe` (shipped with ZBrush) is native, and it is called, not linked. | PARTIALLY VERIFIED |

### 3.3 GoZ file blocks (from the GoB reader/writer; to be checked against the SDK)

Each block: 4-byte tag, `uint32` length (including the 16-byte block header), `uint64` element count, payload.
Little-endian.

| Tag (bytes) | Content | Payload per element | Mirai mapping | Label |
|---|---|---|---|---|
| `89 13 00 00` | object name record, name prefixed `GoZMesh_` | ASCII/UTF-8 | object identity hint only | PARTIALLY VERIFIED |
| `8A 13 00 00` | subdivision record(s) | 4 × `uint32` | — (§4) | PARTIALLY VERIFIED, meaning OPEN |
| `11 27 00 00` | vertices | 3 × `float32` | `vertex_position` (float64) | PARTIALLY VERIFIED |
| `21 4E 00 00` | faces | 4 × `uint32`, 4th = `0xFFFFFFFF` for a triangle | **tris and quads only** | PARTIALLY VERIFIED |
| `A9 61 00 00` | UVs per face | 4 × (u, v) `float32` | `face_uvs` (per corner) | PARTIALLY VERIFIED |
| `B9 88 00 00` | Polypaint per vertex | 4 bytes (B, G, R, pad) | none (§2.7) | PARTIALLY VERIFIED |
| `32 75 00 00` | mask per vertex | `uint16`, stored as `(1 − mask)·65535` by GoB | `VertexMask` (view state) | PARTIALLY VERIFIED (inversion unconfirmed) |
| `41 9C 00 00` | polygroups per face | `uint16` id | `FaceRegions` | PARTIALLY VERIFIED |
| `C9 AF` / `D9 D6` / `51 C3` | texture / displacement / normal map **paths** | string | `SceneObject.texture` (diffuse only) | PARTIALLY VERIFIED |
| `00 00 00 00` | end | — | — | PARTIALLY VERIFIED |

Axis convention: GoB maps GoZ to Blender by `(x, y, z) → (x, z, −y)`, which equals OBJ's Y-up frame **rotated 180°
about X** (GoZ y = −y_obj, z = −z_obj); `GoZ_Info.txt` has `EXPORT_FLIP_Y/Z`, `IMPORT_FLIP_Y/Z` flags per app
[PARTIALLY VERIFIED, derived]. Mirai is Y-up like ZBrush's OBJ export (gollum imports upright, AD-026: "No V flip")
[PARTIALLY VERIFIED]. To confirm in E1 (§8.1).

### 3.4 Registration, transfer start, return, identity

| Question | Answer | Label |
|---|---|---|
| How an app registers | A folder `GoZApps/<AppName>/` with `GoZ_Info.txt` (`NAME`, `GOZ_VERSION = 1`, `EXTENSION = ".GoZ"`, flip flags) and `GoZ_Config.txt` (`PATH = "<app executable>"`); ZBrush lists it in *Preferences → GoZ* ("path to", Install, Force reinstall). `GoZ_Application.txt` names the currently chosen app. | PARTIALLY VERIFIED |
| App → ZBrush | App writes `.GoZ` (+ `.ztn` name file) to the project folder, lists the paths (without extension) in `GoZ_ObjectList.txt`, then starts `GoZBrushFromApp` (official path) — which opens ZBrush if needed and loads the listed objects as SubTools. GoB alternatively starts `ZBrush.exe <script.zsc>` with its own ZScript. | PARTIALLY VERIFIED |
| ZBrush → App | Artist presses **GoZ** (or All / Visible) in ZBrush; ZBrush writes the SubTools' `.GoZ` files and `GoZ_ObjectList.txt`, then launches/notifies the app per `GoZ_Config.txt`. A running app must **watch** `GoZ_ObjectList.txt` (GoB polls its mtime on a timer). | PARTIALLY VERIFIED |
| Which object comes back | Identified **only by name** (the `GoZMesh_<name>` record / file name). GoB matches an existing Blender object by name, then checks exact topology (vertex/face counts and the corner list) before updating positions in place; else rebuilds. Renaming the SubTool breaks the link. | PARTIALLY VERIFIED |
| Multiple objects | One `.GoZ` per SubTool, one line per object in `GoZ_ObjectList.txt`; "All"/"Visible" sends several. | PARTIALLY VERIFIED |
| What ZBrush sends for a subdivided SubTool | Sources agree the round trip is reliable only at the **lowest subdivision level**; whether 2022.0.8's GoZ sends the lowest or the current level, and what record `8A 13` carries, is not settled. | OPEN QUESTION (E1) |
| ZBrush's handling of a changed return | ZBrush asks to project details when topology/vertex order changed; ZBrush may "fix" bad geometry (n-gons, non-manifold) on import, so a later return differs even without edits. | PARTIALLY VERIFIED |
| Documented vs reverse-engineered | Folder/text-file roles and `GoZ_Mesh` are documented in the SDK PDF; block semantics beyond the class API, the mask inversion, the subdivision record and the exact launcher arguments are known here only from GoB. | PARTIALLY VERIFIED |

### 3.5 Compatibility with ZBrush 2022.0.8

| Finding | Label |
|---|---|
| 2022.0.8 (14 Mar 2023) is the final ZBrush 2022 patch; its notes mention no GoZ change. Third parties (Reallusion GoZ Plus) list 2022.0.8 as their minimum supported version, i.e. GoZ works there for them. | PARTIALLY VERIFIED |
| GoB's ZScript requires ZBrush ≥ 2021.0 and the `ZFileUtils` plugin DLL (ships with ZBrush). | PARTIALLY VERIFIED |
| That the SDK's version number matches 2022.0.8 proves nothing; only E1 on Manu's machine can. | OPEN QUESTION |
| Mirai's reference PC runs Windows 10 64-bit — the same machine can run ZBrush 2022 and Mirai side by side (GoZ is local-only). | VERIFIED (OS: `docs/architecture/REFERENCE_HARDWARE.md`); ZBrush on that GPU UNVERIFIED |

---

## 4. ZBrush 2022.0.8 automation

| Capability | What is realistic | Label |
|---|---|---|
| Python API | **Not available** (first shipped with ZBrush 2026.0; "first wave", no direct data access). Not used. | PARTIALLY VERIFIED |
| GoZ (App → ZBrush) | Mirai writes files + starts `GoZBrushFromApp.exe` with `subprocess` (pattern of `morph_bridge.py`). Fully automatic from Mirai. | PARTIALLY VERIFIED |
| GoZ (ZBrush → Mirai) | Always one artist click in ZBrush (GoZ button). Mirai detects it by polling `GoZ_ObjectList.txt` (mtime + size stable) in the main tick. No manual file handling for the artist. | PARTIALLY VERIFIED |
| ZScript | Can import a given file (`[FileNameSetNext,path] [IPress,Tool:Import]`), loop and select SubTools by name, insert SubTools, press interface buttons; can be passed to `ZBrush.exe` on the command line (GoB does). A ZScript **cannot** be triggered from outside a running ZBrush except by that start-up argument. A "Send to Mirai" button inside ZBrush would be a ZScript plug-in (optional, later). | PARTIALLY VERIFIED |
| Start ZBrush from Mirai | Yes (`GoZBrushFromApp` or `ZBrush.exe`), with the path from `GoZBrush/GoZ_Config.txt` or a setting. | PARTIALLY VERIFIED |
| Control a running ZBrush from Mirai | Only by GoZ file drops + `GoZBrushFromApp`; no RPC. | PARTIALLY VERIFIED |
| Mirai inside ZBrush's GoZ app list | Needs a `GoZApps/Mirai/` folder whose `GoZ_Config.txt` points to a Windows executable or script that, when ZBrush launches it with Mirai already running, does nothing harmful (Mirai is a `python src/main.py` process, not an `.exe`). How ZBrush 2022 invokes the target (arguments, working directory) is unknown. | OPEN QUESTION (E1) |
| Alternative without registration | Keep ZBrush's GoZ target on any installed app and let Mirai only *watch* the files ZBrush writes, or use ZBrush's normal OBJ export into Mirai's `obj/` folder (today's AD-026 path). | PARTIALLY VERIFIED |

---

## 5. Data exchange compatibility matrix

Classes: **D** directly supported · **C** requires conversion · **M** requires an additional mechanism ·
**U** unsupported / impractical.

| Data | Send Mirai → ZBrush | Return ZBrush → Mirai | Risks | Label |
|---|---|---|---|---|
| Vertex positions | **C** — float64 → float32, world space (placement applied, as `export_obj`), axis flip (§3.3), vertex-ID order → dense index, map stored in a manifest | **C** — same-topology only: index → `VertexId` via manifest, inverse placement and flip, float32 → float64; untouched vertices keep their float64 value (§7.3) | quantisation; asymmetric sculpt breaks exact symmetry pairs; placement inverse rounding | PARTIALLY VERIFIED |
| Topology | **C** — tris/quads as is; **n-gons must be split** (GoZ 4-corner limit) with a recorded split map, or the send refused | **M** — compare exactly against the sent topology (counts + corner lists); equal → in-place update allowed; different → never in place, only "import as new object" (existing `import_obj` path) | ZBrush geometry repair; ZRemesher/Dynamesh = new topology; n-gon split is a topology change on Mirai's side | PARTIALLY VERIFIED |
| Vertex colours / Polypaint | **U** (v1) — Mirai has nothing to send | **M** — no Mirai storage; needs a new colour data kind (Core extension under CORE_V1_FREEZE §7, own AD); a VECTOR layer is not an option (read as morph target) | scope creep into painting; per-vertex only, resolution-bound | VERIFIED (Mirai side) |
| UV coordinates | **D/C** — per-corner UVs map directly for tris/quads; n-gon split carries corner UVs; possible V flip | **C** — per-corner, same face correspondence only; v1: compare and report, apply only if artist opts in | UV flip conventions (AD-026 "Flip V" note); ZBrush UV Master creates new UVs = attribute change, not topology | PARTIALLY VERIFIED |
| Polygroups | **C** — region → `uint16` id per face; overlapping regions need a rule; names kept in the manifest | **C** — id per face → `FaceRegions` (journaled, one Undo step with positions); names from manifest, unknown ids → `Group N` | overlap/one-group rule; ZBrush auto-groups on import; names lost in GoZ | PARTIALLY VERIFIED |
| Masks | **C** — `VertexMask` → `uint16` (inverted?) | **C** — into the view-state mask only (no History, not saved — Mirai's mask semantics) | inversion unconfirmed; ZBrush masks a mesh whose topology differs (reported) | PARTIALLY VERIFIED |
| Multiple objects / SubTools | **D** — one `.GoZ` per object, one manifest entry each | **C** — per returned file an independent plan; partial success must be per object, never a half-applied object | name collisions; a new SubTool split in ZBrush (e.g. Split to Parts) = unknown object | PARTIALLY VERIFIED |
| Subdivision levels | **U** — Mirai's SubD is a derived preview of the cage (`mirai/subdivision`), not stored levels; send the cage (level 0) | **U/M** — a returned higher level is a different topology → new object; detail as displacement/normal map paths could be referenced later | which level GoZ 2022 sends | OPEN QUESTION |
| Sculpting layers | **U** | **U** — baked into the returned positions | artist expectation | PARTIALLY VERIFIED |
| Morph targets | **C** — send the base rest shape (default) or **one target as `b + d`** as a separate SubTool; never the evaluated mix | **C** — base: positions update (targets follow, J-3); target: `d' = p − b` written into that layer, `TargetView.translate`'s rule; ZBrush morph target / layer stack is not transferable | sending the mix by mistake; base sculpt moves every target too | VERIFIED (Mirai side) |
| Skin weights | **U** — ZBrush has no weights | **D** (same topology: untouched by a positions write, keyed by `VertexId`) / **U** (changed topology: no transfer; a later weight-projection feature) | return while posed must be refused (AD-028 §7.1) | VERIFIED (Mirai side) |
| Rest pose / rig | **D** — export sends the rest shape (pose is view state) | **D** — positions update edits the rest shape; bones unchanged; deformation follows | the artist sculpts a rest shape that fits the rig less well — artist matter, not data loss | VERIFIED |
| Symmetry definition, mirror pairs, material, texture path | not sent (texture path optional) | untouched by a positions write; symmetry *correspondence* may become partly unpaired | Re-Symmetrize exists | VERIFIED |

---

## 6. Proposed architecture

### 6.1 Principles

1. **No second mesh exchange system.** The bridge reuses: `mesh_to_obj`'s world-space/vertex-order conventions,
   `import_obj`/`add_mesh_object` for "new object", `_mesh_transaction` for in-place updates, the change journal for
   Undo, `TargetView`'s offset rule for targets, `morph_bridge`'s subprocess pattern. New code is only what GoZ needs:
   the binary format, the folder protocol, the manifest and the return plan.
2. **Isolated from the Core.** Version 1 needs **no `src/core/` change**. Polypaint would (later, own AD).
3. **Pure before effectful.** Parsing, validation and planning are pure functions over data; one small apply step
   mutates the scene.

### 6.2 Modules (`PROVISIONAL` names)

```text
src/interop/goz/
    format.py        read/write .GoZ  <->  GozMesh (positions f32, faces ≤4, optional uvs/polypaint/mask/groups)
                     clean-room from the SDK documentation; strict: unknown or short blocks -> error, never partial
    paths.py         GoZ folder layout (Pixologic vs Maxon root, configurable), GoZ_ObjectList read/write,
                     optional GoZApps/Mirai registration (only on explicit artist action)
    manifest.py      TransferManifest (JSON sidecar beside each .GoZ, written atomically): §7.1
    export.py        SceneObject + mesh -> (GozMesh, manifest): world space, axis flip, ID->index map, n-gon policy
    plan.py          (returned GozMesh, manifest, current scene) -> ReturnPlan: kind + findings; no mutation
src/zbrush_bridge.py window-level glue like morph_bridge.py / obj_files.py: menu rows, launching
                     GoZBrushFromApp.exe, the mtime poll called from main.py's tick, status lines
Application.apply_goz_return(plan)   the only mutating entry: positions (+ opted-in regions/UVs) inside
                     _mesh_transaction (one Undo step, exact rollback); or import as new object
tests/test_goz_*.py  headless: format round trip, manifest, every plan kind, apply + Undo, scene untouched
```

`src/interop/goz/` imports `core` only (plus `mirai.object_space` for placement); no pyglet, no `Application` —
headless-testable like `scene_files.py`.

### 6.3 Flow

**Send (Mirai → ZBrush):** artist chooses "Send to ZBrush" on the document object (SPACE menu row first; no key
until Manu approves one) → refused during an interaction → `export.py` builds `.GoZ` + manifest in the GoZ project
folder (atomic) → writes `GoZ_ObjectList.txt` → starts `GoZBrushFromApp.exe` (`subprocess.Popen`, no wait) → status
line. No History entry, scene unchanged.

**Return (ZBrush → Mirai):** artist presses GoZ in ZBrush → Mirai's tick sees `GoZ_ObjectList.txt` change → waits until
mtime/size are stable → reads every listed `.GoZ` and its manifest → `plan.py` builds one `ReturnPlan` per object →
the status/HUD shows the plans → **apply only on the artist's explicit command** (open decision D1) →
`apply_goz_return`.

### 6.4 ReturnPlan kinds

| Kind | Condition | Apply action |
|---|---|---|
| `POSITIONS` | manifest found, scene and object identity match, mesh unchanged since send, returned topology == sent topology | in-place positions (+ opted-in attributes), one Undo step |
| `CONFLICT` | as above but the Mirai mesh changed since the send (fingerprint differs) | none by default; artist may choose "import as new object" or an explicit overwrite (D3) |
| `TOPOLOGY_CHANGED` | identity matches, topology differs | never in place; "import as new object" beside the original (fresh IDs, no layers/weights) |
| `UNKNOWN_OBJECT` | no manifest / identity mismatch / renamed SubTool | "import as new object" only |
| `REFUSED_NOW` | interaction running, target posed and bound, object deleted | nothing; reason in status; plan can be retried |
| `INVALID` | file truncated, bad lengths, non-finite values | nothing; error in status |

---

## 7. Data integrity and topology safeguards

### 7.1 Object identity

- Names are insufficient (Mirai names are not unique; ZBrush matches by name; artists rename) [VERIFIED / PARTIALLY
  VERIFIED].
- **Transfer manifest** per sent object, stored beside the `.GoZ` (and kept by Mirai in memory): `transfer_id`
  (random UUID per send), `session_id` (random per Mirai process), scene file path (if any), `ObjectId`, object
  name, `representation` (`base` or `target:<LayerId>`), the **index → VertexId** and **face index → (FaceId,
  piece)** maps, sent topology hash, sent positions hash (float32 values), Mirai mesh fingerprint at send
  (topology hash + positions hash in float64 + layer meta), placement used, axis convention, n-gon split map,
  region id ↔ name map, timestamps.
- The GoZ object name carries a short readable suffix (`Head__m7f3a`) so a returned file finds its manifest even if
  the `.GoZ` file name changes; the manifest, not the name, decides.
- Matching rule: manifest found **and** the current scene is the one sent from (same `session_id`, or same scene file
  and object present) **and** the object's mesh still contains every mapped `VertexId`. Otherwise `UNKNOWN_OBJECT`.
- No Core change needed: `ObjectId` + session/scene-path is sufficient while Mirai stays open or reopens the same file.
  A persistent scene UUID (serialization addition) is only worth a CORE_V1_FREEZE §7 proposal if cross-session returns
  turn out to matter [OPEN QUESTION].

### 7.2 Topology

- **Same topology** = identical vertex count, face count and per-face corner index lists (rotation included), as GoB
  checks; plus no change on the Mirai side since the send. Only then are positions applied in place, through the
  manifest's index → `VertexId` map.
- **Changed topology** is never applied in place: no ID correspondence exists, AD-025 provenance is absent, morph
  offsets and weights would attach to wrong points (GoB's own comment states exactly this risk). It becomes a new
  object via the existing import path; the original stays untouched. Any later "transfer" (re-projection of weights,
  targets or UVs onto new topology) is a separate, explicit feature.
- **N-gons:** v1 refuses to send a mesh with faces of more than 4 corners (status names the count), unless Manu
  prefers split-and-recombine (D4). Split-and-recombine: split each n-gon by a deterministic rule, record the pieces,
  and on return accept the mesh as "same topology" only if exactly those pieces come back; recombine to the original
  `FaceId`s. Any deviation → `TOPOLOGY_CHANGED`.
- **ZBrush repair:** detected by the same exact comparison; no tolerance-based matching.

### 7.3 Precision

- GoZ positions are float32 [PARTIALLY VERIFIED]; Mirai stores float64 [VERIFIED]. Rule: for each vertex, if the
  returned float32 equals the float32 that was sent, **keep the original float64** (bit-exact for untouched points);
  only differing points are written. This keeps an un-sculpted region exact, keeps the Undo delta minimal (only moved
  points are journaled) and protects exact symmetry pairs where ZBrush did not move anything.
- Placement inverse (`object_space.to_object`) adds rounding only on moved points.
- The plan reports symmetry pairs before/after (`vertex_correspondence`); the artist can run Re-Symmetrize.

### 7.4 Morphs

- The bridge sends `mesh.vertex_position` (the base rest shape), never `MixSurface` output — exactly what
  `export_obj` does today [VERIFIED]. Sending a target sends `b + d` as its own SubTool with `representation =
  target:<lid>`; its return writes `d' = p − b` into that layer only (TargetView's rule), never into the base.
- A base return is a positions edit of the base: targets are relative and follow (J-3). The plan says so ("3 morph
  targets follow the new base") so this is never a surprise [VERIFIED semantics; UX wording PROVISIONAL].
- A target whose layer was deleted since the send → `UNKNOWN_OBJECT`.

### 7.5 Rigging

- Return into a posed, bound mesh → `REFUSED_NOW` (matches `apply_mesh_change`, AD-028 §7.1) [VERIFIED].
- Same topology: weights untouched (keyed by `VertexId`); bones and rest frames untouched [VERIFIED].
- Changed topology: new object without weights; the original keeps its binding [VERIFIED by construction].

### 7.6 Safety, atomicity, backups

- **Read fully, validate fully, then plan** — like `Mesh.load_state` ("validated whole before the first write").
  Truncated blocks, wrong lengths, counts that disagree with the manifest, NaN/inf → `INVALID`.
- **Wait for ZBrush to finish writing:** act only when `GoZ_ObjectList.txt` and every listed file have a stable mtime
  and size across two polls.
- **Apply atomically** inside `_mesh_transaction`: one recording, one `MeshDeltaCommand`, exact rollback if anything
  raises. Multi-object returns: one Undo step per object (each object atomic) or one compound step — D5.
- **Backup:** Undo covers the session. Before the first in-place apply in a session the bridge writes an automatic
  scene backup (existing atomic `save_scene_file` into e.g. `scenes/goz_backup/`) — proposal, D6.
- **Conflict detection:** the manifest fingerprint vs the current mesh (§6.4 `CONFLICT`).
- **Never touched by a return:** other objects, rig, mirror pairs, materials, symmetry definition, History before
  the step (§8.3 test).
- **Files:** Mirai never deletes ZBrush's files; it only writes its own `.GoZ`/manifest/`ObjectList` entries.

---

## 8. Minimal prototype plan

### 8.1 Experiment E1 — GoZ handshake probe (needs Manu's approval; Manu's Windows PC)

Purpose: replace every [PARTIALLY VERIFIED] GoZ fact needed for v1 with a measured one on ZBrush 2022.0.8.
Isolated in `experiments/goz_probe/` (no `src/` import of it, removed or archived after the result).

1. A standalone script writes a known mesh (a 2×2-quad plane and gollum_20k) as `.GoZ` + manifest, writes
   `GoZ_ObjectList.txt`, starts `GoZBrushFromApp.exe`. Record: does ZBrush 2022.0.8 open it, as which SubTool name,
   in which orientation (axis flip check with an asymmetric test mesh).
2. In ZBrush: move a few points, press GoZ. Record exactly which files ZBrush writes where, what it launches
   (`GoZ_Config.txt` of the chosen app; arguments), the returned vertex/face order, the subdivision record with and
   without subdivision levels, UV V direction, mask values, polygroup ids.
3. Repeat with: a triangle, an n-gon mesh (what does ZBrush do?), a mesh with polypaint/mask/groups painted in ZBrush.
4. Output: a short README with the observed protocol and the captured `.GoZ` files (as test fixtures).

Requires from Manu: approval, ~30 min at the reference PC, the GoZ SDK download/PDF (or `developers.maxon.net`
allowed in the session network settings) to cross-check the format.

### 8.2 Prototype P1 — positions-only round trip (Production, after E1)

Steps (the user's seven, mapped):

1. Select one mesh in Mirai — the document object (mode `4` selection or edit object, as `morph_bridge`).
2. Send — SPACE menu row "An ZBrush senden" (`PROVISIONAL`): `.GoZ` + manifest + `GoZ_ObjectList.txt` +
   `GoZBrushFromApp.exe`.
3. Modify in ZBrush — **manual**: Move/Standard brush on the base level, no topology tools.
4. Send back — **manual in ZBrush**: GoZ button (ZBrush's GoZ target must be one that writes the files; how Mirai is
   chosen there is E1's result).
5. Identify — `plan.py` with the manifest (§7.1).
6. Update — on the artist's command, `apply_goz_return` writes positions inside `_mesh_transaction`.
7. Verify — automated checks below.

Acceptance criteria (measurable):

| # | Criterion | How |
|---|---|---|
| A1 | Untouched vertices are bit-identical (float64) after the round trip; moved vertices equal the returned float32 after inverse placement within 1 ulp of float32 | test with captured fixture |
| A2 | `all_vertex_ids()`, `all_face_ids()`, every face boundary, UVs, regions, point layers (morph, weights) are identical before/after | test |
| A3 | Exactly one History entry; Undo restores the exact pre-return state, Redo re-applies | test (`MeshDeltaCommand`) |
| A4 | Every other object, rig, mirror pair, material, texture path, symmetry definition unchanged (`scene_to_dict` minus the target mesh's positions equal) | test |
| A5 | A changed-topology return never modifies the original; it yields a new object or nothing | test with fixture |
| A6 | A truncated/corrupt `.GoZ` changes nothing and reports `INVALID` | test |
| A7 | A return while posed or during an interaction changes nothing (`REFUSED_NOW`) | test |
| A8 | Return with a Mirai edit since the send → `CONFLICT`, nothing applied by default | test |
| A9 | gollum_20k: send and plan+apply each under 1 s in the container; reference-PC time measured, not claimed | measurement |
| A10 | Manu's practical check: the round trip feels like one workflow (no file handling) | Artist test |

Manual steps required by ZBrush 2022.0.8 (expected; E1 confirms): pressing GoZ in ZBrush for every return; once,
choosing the GoZ target app in *Preferences → GoZ* if Mirai registers itself.

### 8.3 Prototype P2 — Polypaint and Polygroups

- **Polygroups:** send regions as ids (manifest keeps names); return ids → regions in the same transaction as the
  positions, only when the artist opts in ("Polygruppen übernehmen"). Acceptance: same-topology return maps every
  face's group exactly; names of unchanged groups preserved; new ZBrush groups get `Group N`; one Undo step; Undo
  restores the old regions.
- **Polypaint:** read and report only ("Polypaint: 21 875 colours, not stored — Mirai has no vertex colours"). Storing
  it is a Core extension (new data kind, CORE_V1_FREEZE §7 checklist, own AD) and needs Manu's go (D7). Acceptance for
  P2: decoded colours match the fixture painted in E1.

---

## 9. Risks, dependencies, open questions

### 9.1 Risks for Mirai

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | Silent replacement of an object's mesh destroys IDs, morph offsets, weights | high | never in place unless exact topology match; new object otherwise (§7.2) |
| R2 | N-gons cannot travel through GoZ | high (Mirai creates n-gons routinely: Knife, Dissolve, Cap) | refuse or split-and-recombine with exact check (D4) |
| R3 | ZBrush changes topology silently (repair, auto-groups) | medium | exact comparison, `TOPOLOGY_CHANGED` |
| R4 | Identity by name in ZBrush | medium | manifest + fingerprint; name only a hint |
| R5 | float32 quantisation, exact-position symmetry | medium | untouched-vertex preservation (§7.3), symmetry report |
| R6 | Return into a changed scene | medium | fingerprint conflict detection |
| R7 | Undocumented GoZ details differ on 2022.0.8 | medium | E1 before any Production code; strict parser fails closed |
| R8 | GPL contamination from GoB | legal | clean-room implementation from the SDK docs; GoB only cited |
| R9 | Scope creep (painting, subdivision levels, layers) | medium | matrix §5 keeps them out of v1 |
| R10 | Windows-only paths and launcher; container cannot run ZBrush | low/organisational | headless tests on captured fixtures; reference-PC test for the handshake |

### 9.2 Dependencies

ZBrush 2022.0.8 with GoZ installed (Manu's PC); the GoZ SDK download/PDF (Manu or network allow-list); captured
`.GoZ` fixtures from E1 for headless tests. No new Python packages (stdlib `struct`, `array`, `json`, `subprocess`).

### 9.3 Unresolved technical questions

| # | Question | Label |
|---|---|---|
| Q1 | Exact block layout and semantics per the official `GoZ_Mesh.h` (esp. `8A 13`, mask inversion, polypaint alpha) | OPEN QUESTION |
| Q2 | GoZ root folder of 2022.0.8 on Manu's PC (`Public\Pixologic` vs `Public\Documents\Maxon`) | OPEN QUESTION |
| Q3 | How ZBrush 2022 launches/notifies the target app (arguments, behaviour when it is already running) and how Mirai (a Python script) can be a target | OPEN QUESTION |
| Q4 | Which subdivision level GoZ sends from a subdivided SubTool | OPEN QUESTION |
| Q5 | What ZBrush does with an n-gon received over GoZ | OPEN QUESTION |
| Q6 | Axis convention (180° about X) confirmed for Mirai's Y-up | OPEN QUESTION |
| Q7 | Does a persistent scene identity matter (return after a Mirai restart without the same file)? | OPEN QUESTION |
| Q8 | Return into a non-edit object: switch the edit object automatically or refuse? | OPEN QUESTION (technical, decided in P1) |

---

## 10. Recommendation

**Proceed with restrictions.**

1. **Feasible?** Yes for a same-topology, positions-first bridge; GoZ's file protocol is implementable from Python and
   Mirai's ID-based data model, atomic transaction and journal make the in-place update safe. Not verified on 2022.0.8
   yet (E1).
2. **GoZ SDK 2022.0 the right foundation?** As the **format and protocol reference**, yes; as a runtime dependency,
   no — no native component is needed. Its version label is not evidence of 2022.0.8 compatibility.
3. **First version transfers:** positions (same topology), the sent topology/UVs for display in ZBrush, polygroups ↔
   regions as opt-in (P2). Polypaint read-only. Masks, subdivision levels, layers, weights over topology changes:
   not in v1.
4. **Biggest architectural risks:** R1 (silent replacement), R2 (n-gons), R4 (identity), R5 (precision vs exact
   symmetry), R6 (conflicts).
5. **Next phase:** E1 handshake probe on the reference PC (approval needed), then P1 in `src/interop/goz/` with the
   acceptance criteria of §8.2, then P2.

### 10.1 Experiments requiring approval (not started)

- **E1** (§8.1) — isolated `experiments/goz_probe/`, needs Manu's PC and ZBrush. Nothing in `src/`.
- Optional **E0** (container only): once E1 delivers fixtures, a pure-Python reader test against them — no approval
  question beyond E1, listed for completeness.

### 10.2 Proposed documentation changes (not made in this audit)

| Where | Change |
|---|---|
| `docs/future_ideas/README.md` | one line: "[ZBrush-Brücke (Audit)](ZBRUSH_BRIDGE_AUDIT.md)" under *Bereiche* |
| `docs/ATELIER.md` §3 | one candidate line with link (only if Manu wants it on the list) |
| `docs/architecture/AD-026-FACE-CORNER-UVS-AND-TEXTURE.md` §7 | a link: the GoZ bridge as the successor of the manual OBJ round trip |
| `docs/architecture/SOURCE_ARCHITECTURE.md` | when P1 lands: the `src/interop/` package and its boundary (imports `core` only) |
| new `docs/architecture/AD-0xx-ZBRUSH-GOZ-BRIDGE.md` | when P1 starts: the decisions D1–D7 and the manifest/plan contract |

### 10.3 Decisions for Manu

| # | Decision | Agent's proposal                                          |
|---|---|-----------------------------------------------------------|
| D1 | Apply a returned mesh automatically, or only after a confirm command? | confirm (status shows the plan, one key/menu row applies) |
| D2 | Changed topology from ZBrush: import as new object, or also offer "replace" (losing morphs/weights)? | new object only in v1                                     |
| D3 | Conflict (Mirai edited since send): offer an explicit overwrite at all? | no overwrite in v1; new object                            |
| D4 | N-gons: refuse the send, or split and recombine? | refuse in P1, split-and-recombine in a later step         |
| D5 | Several SubTools returned: one Undo step per object or one for all? | one per object                                            |
| D6 | Automatic scene backup before the first in-place apply per session? | yes                                                       |
| D7 | Polypaint: should Mirai get vertex colours at all (Core extension)? | later, own AD                                             |
| D8 | Register Mirai as a GoZ app in ZBrush (writes into `C:\Users\Public\Pixologic\GoZApps`) or only watch files? | decide after E1                                           |
| D9 | Menu row first, key later — any key only after "Taste passt" (keymap rule) | menu row                                                  |
| D10 | Approve E1 and provide the GoZ SDK (or allow `developers.maxon.net`) | Approved                                                     |

---

## Sources

Mirai code and docs: as cited inline (paths and line numbers at `4601852`).

External (format/protocol, read through search summaries or the GoB source):

- Maxon, GoZ SDK documentation (PDF): <https://developers.maxon.net/docs/zbrush/goz_sdk.pdf> — not reachable from this
  session; content known from search summaries.
- Maxon Developers — Downloads: <https://developers.maxon.net/downloads/>; ZBrush SDK overview (forum):
  <https://developers.maxon.net/forum/topic/15246/zbrush-sdk-overview>; SDK download thread:
  <https://developers.maxon.net/forum/topic/15418/sdk-zbrush-download>
- Maxon help, About GoZ: <https://help.maxon.net/zbr/en-us/Content/html/user-guide/zbrush-other-programs/goz/about-goz/about-goz.html>;
  GoZ with non-supported applications: <https://help.maxon.net/zbr/en-us/Content/html/user-guide/zbrush-other-programs/goz/other-applications/other-applications.html>,
  <https://support.maxon.net/hc/en-us/articles/7945725232796-GoZ-with-Non-Supported-Applications>
- Maxon, ZBrush 2022.0.8 release notes (14 Mar 2023): <https://support.maxon.net/hc/en-us/articles/7943539514780-ZBrush-2022-0-8-March-14-2023>
- Maxon, ZBrush Python (2026.0+): <https://help.maxon.net/zbr/en-us/Content/html/reference-guide/zscript/zscript-python.html>,
  <https://developers.maxon.net/docs/zbrush/py/2026_0_0/manuals/man_getting_started.html>
- Reallusion GoZ Plus (ZBrush 2022.0.8 minimum): <https://www.cgchannel.com/2024/06/reallusion-launches-goz-plus>
- SideFX, Labs GoZ Export (attribute mapping): <https://www.sidefx.com/docs/houdini/nodes/sop/labs--goz_export.html>
- GoB (GPL-2.0-or-later, read as reference only): <https://github.com/JoseConseco/GoB> — `gob_export.py`,
  `gob_import.py`, `geometry.py`, `paths.py`, `Blender/GoZ_Info.txt`, `ZScripts/GoB_Import.txt`
