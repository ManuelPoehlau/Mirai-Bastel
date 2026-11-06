# WP GoZ P3 — UVs, textures, morph targets (plan, 2026-11-06)

**Status:** P3a, P3b and the P3c core IMPLEMENTED (2026-11-06, container-tested; E3 done on the reference PC, §2).
Open: the layer route of P3c (§5) and the practical test (§8). Builds on [AD-029](architecture/AD-029-ZBRUSH-GOZ-BRIDGE.md) (P1) and
[WP_GOZ_P2_PLAN](WP_GOZ_P2_PLAN.md) (groups, n-gons, done), [AD-026](architecture/AD-026-FACE-CORNER-UVS-AND-TEXTURE.md)
(face-corner UVs, one texture per object) and [AD-025](architecture/AD-025-TOPOLOGY-PROVENANCE-AND-POINT-LAYERS.md)
(morph targets = relative offsets, J-3). Decisions below are Manu's (2026-11-06) unless marked `PROVISIONAL`.

## Kurzfassung für Manu (Deutsch)

- **UVs:** Mirai schickt seine UVs mit. Ändert ZBrush sie (z. B. UV Master), kommen sie mit den Punkten und Gruppen
  zurück — gleiche Bestätigung, **ein** Undo-Schritt (deine Wahl „Mit übernehmen“).
- **Textur:** Eine in ZBrush gemachte Textur (z. B. aus Polypaint) kommt mit GoZ zurück. Mirai legt eine **Kopie neben
  die Szene** (`<Szene>_textures/`, ohne gespeicherte Szene in `goz/textures/`), das Objekt zeigt sie an.
- **Morph-Targets:** Dein Wunsch ist „Basis + Morph-Layer“ in ZBrush. GoZ selbst kann keine Layer übertragen (es
  überträgt nur ein Mesh pro SubTool und gibt immer den sichtbaren Zustand zurück, alle eingeschalteten Layer
  eingerechnet). Darum prüft E3, ob ZBrush ein Target per *Import* in einen Layer aufnimmt. Sicher geht in jedem Fall:
  Basis und jedes Target als eigenes SubTool, die Rückgabe weiß, was Basis und was Target ist.
- **E3 erledigt (2026-11-06):** UVs kommen ungespiegelt an und zurück, UV Master liefert neue UVs, eine Textur aus
  Polypaint kommt als TIFF (auf dem Kopf gespeichert, Mirai dreht die Kopie um), Basis und Target kommen in einem Senden
  an, und ein Target lässt sich per *Import* in einen Layer laden; der Layer überlebt erneutes Senden.
- **Gebaut:** UVs hin und zurück, Textur zurück (PNG-Kopie neben der Szene), Basis + jedes Target als eigenes SubTool;
  ein in ZBrush gesculptetes Target kommt nur in sein Target zurück. **Noch nicht gebaut:** der Layer-Weg (§5) — dazu
  eine Rückfrage an dich.

## 1. Facts this plan rests on

| Fact | Source |
|---|---|
| GoZ UV blocks: `25001` UV4_LIST (4 × (u, v) float32 per face), `25002` UV3; FLAGS bits `UV_FLIP_U` 512, `UV_FLIP_V` 1024, `IMAGE_FLIP_V` 2048; map paths `45001` texture, `50001` normal, `55001` displacement (strings). | SDK (`experiments/goz_probe/README.md` §2.1) |
| Which V direction ZBrush 2022.0.8 expects in UV4 and returns, what a triangle's 4th pair is, whether UV Master's new UVs come back in the block. | **unknown → E3** |
| Whether a GoZ return carries a texture path (and where the image lies, which format, flipped or not). AD-026: ZBrush's *Texture → Export* stores images upside down (Flip V before export). | **unknown → E3** |
| `GoZBrushFromApp -tmap` made ZBrush act on the active Tool instead of the listed file (E1 T5.2): never on a mesh send. Sending a texture *to* ZBrush therefore has no known safe path. | E1 §10a |
| GoZ carries one mesh per SubTool, no layer or morph data (SDK tag list). Layers reach ZBrush only via plugins or *Tool → Import* of a same-topology mesh while a layer records (forum practice, untested here); a GoZ return is the visible state with every active layer applied. | SDK; ZBrushCentral (§7) |
| Mirai: UVs per face corner, one map per mesh, journaled (`Mesh.face_uvs`, `set_face_uvs`); texture = `SceneObject.texture` (a path, **not** journaled today). | AD-026, `src/core/mesh.py`, `src/core/scene.py` |
| Mirai: a morph target is a `LayerKind.VECTOR` point layer of offsets `d` to the base; editing a target writes `d' = p − b` (`TargetView.translate`). The manifest already fingerprints every layer. | AD-025, `src/mirai/morph_targets.py`, `interop/goz/manifest.py` |

## 2. E3 (reference PC, before P3 code)

Prepared (container-tested): `make_meshes.py` writes mesh C's corner UVs and a deterministic bump target (`C.sent.json`
`uvs`, `target_bump`, `C_bump.obj`); `probe_send.py --uvs as-is|flip-v`, `--target bump` (base `E1_C_P1_B` + target
`E1_C_P1_T` in **one** transfer); the receiver classifies returned UVs (identical / V flipped / U flipped / other),
fits a target weight (0 = base, 1 = target, a layer at 50 % = 0.5; axis raw, bridge or ZBrush's OBJ placement) and
copies every map image a file names. Steps: E1 README §6 T9.

| Question | Read from | P3 consequence |
|---|---|---|
| U1 V direction of UV4 | T9.1 + T9.2 (`UVs je Fläche …` line) | send / read with or without `1 − v` |
| U2 ZBrush keeps our UVs | T9.1 Morph UV view | P3a send works |
| U3 UV Master's UVs come back | T9.3 (`other` faces) | P3a return |
| X1 texture path in the return | T9.4 (`TEXTURE_MAP_PATH`, copied image) | P3b possible / format / flip |
| M1 two objects in one send | T9.5 | targets as SubTools |
| M2 a target as a ZBrush layer | T9.6 (weight 1 / 0 / 0.5 with the layer at 100 % / off / 50 %) | P3c layer route |
| M3 layers survive a resend | T9.7 | whether Mirai may resend a base that has layers |

**Result (Manu, reference PC, 2026-11-06; captures `20261106-0947…` to `…1003…`, order as in T9):**

| # | Result |
|---|---|
| U1/U2 | Head sent with UV4 (`--uvs as-is`): returned UVs identical to the sent ones (max 3e-8, float32); ZBrush's own GoZ of the OBJ import also equals the OBJ `vt`. → GoZ's UV4 = OBJ `vt` convention, **no flip** either way. |
| U3 | *UV Master → Unwrap*: all 324 faces come back with new UVs (u 0.002–0.998, v 0.002–0.770), points bit-identical. |
| X1 | *New From Polypaint* then GoZ: a TEXTURE_MAP_PATH block names `…/GoZProjects/Default/<Tool>_TXTR.tif`: an uncompressed baseline TIFF, 2048², RGB 8 bit, one strip (12.6 MB). Sampled at the UVs it matches the returned polypaint (MRGB block, byte order B, G, R, mask) with **file row 0 = v 0** (mean difference 4.6 of 765; with V flipped 378) — stored bottom-up, as AD-026 says. |
| M1 | `--target bump`: both objects of one transfer arrived as their own Tools; base and target came back bit-identical (target = `b + d` on all 326 points). |
| M2 | `C.obj` imported, *Layers → New*, *Tool → Import* `C_bump.obj`: the layer holds the target exactly (weight 1.0000, rest 5.7e-7 = float32 under ZBrush's OBJ placement); with the layer slider at 0.5 the return is `b + 0.5 d` exactly. Notable: the GoZ with the layer **switched off** still returned the full target (weight 1.0000). Manu repeated it on 2026-11-06 with the slider at 0 (ZBrush then switches the eye off by itself): again the **target state**. So a layered Tool never returns the pure base by GoZ. |
| M3 | Resend of that Tool with the layer not recording: the layer survived (Manu). The final GoZ after the resend was not captured. |

## 3. P3a — UVs (decided: „Mit übernehmen“; IMPLEMENTED 2026-11-06)

Built as below (`format.py` UV4/UV3, `bridge.plan_uvs`, `Manifest.sent_uvs` / `zbrush_uvs`, fingerprint `uvs`, the
apply writes `set_face_uvs` in the same `_mesh_transaction`); a new object from a return takes ZBrush's UVs too.

**Send:** when every face has UVs, a UV4 block with the corner UVs (convention by U1); n-gon pieces take their
corners' UVs from the n-gon. A mesh with only some faces mapped: no block, status says so (`PROVISIONAL`).
Manifest: the sent UVs per piece; fingerprint adds a UV hash (a Mirai UV edit since the send = conflict, like groups).

**Return (same topology):** compare per sent piece; changed faces get the returned UVs, written with points and groups
in the **same `_mesh_transaction`** (one Undo step). An n-gon takes each corner's UV from its pieces; pieces that
disagree at a shared corner (cannot happen for one seamless n-gon) → keep Mirai's UVs for that n-gon, report it
(`PROVISIONAL`). A return without UV block keeps Mirai's UVs. UVs-only change = `IN_PLACE`. After an apply ZBrush's
UVs become the baseline (as `zbrush_points` / `zbrush_groups`).

## 4. P3b — texture back (decided: copy beside the scene; IMPLEMENTED 2026-11-06)

Built: `interop/goz/texture.py` decodes ZBrush's uncompressed TIFF (stdlib), flips it vertically (X1) and writes
`<object>_<hash>.png` — the 12.6 MB E3 image became a 233 KB PNG in 0.13 s; any other file is copied unchanged with a
warning. The glue copies at arrival; the plan treats a copy other than the object's texture as a change (a
texture-only return is appliable); the apply sets `SceneObject.texture` through `ObjectTextureCommand`, composed with
the mesh delta into one Undo step (`_mesh_transaction(companion=...)`).

If E3 shows a texture path: copy the image at arrival into `<scene stem>_textures/<object>_<n>.<ext>` beside the
saved scene, else `goz/textures/` (the file in ZBrush's project folder is overwritten by the next GoZ). The apply sets
`SceneObject.texture` to the copy. Today `texture` is not journaled: P3b adds it to the same Undo step (a small
composite History command around the `MeshDeltaCommand`, `PROVISIONAL` — design after E3). Image flip by X1.
**Sending** a texture to ZBrush stays out until a safe path is known (`-tmap` is not one).

## 5. P3c — morph targets (decided: base and targets; as ZBrush layers if possible)

**Core IMPLEMENTED (2026-11-06):** „An ZBrush senden“ sends the base and each morph target `b + d` (`<name>_<target>`,
own identifier) in one transfer; a target return writes `d' = p − b` for the moved points of that layer only
(symmetry fix on the target shape), one Undo step; after any apply the object's other SubTools are rebased (their
fingerprint follows, what ZBrush holds of them stays the baseline), so base and target returns can alternate without a
resend. Practical test 3 (Manu, 2026-11-06): works as expected.

The layer route below is **not built** (recommendation: drop it): a layer at 0 / switched off still comes back as
the target state (M2, repeated by Manu), so a Tool holding a target layer cannot give Mirai its base by GoZ, and the
layer import was only shown on an OBJ-imported Tool. The SubTool route covers sending, sculpting and returning base
and targets.

**Core, independent of E3:** a send may carry the base **and** its targets: each target `b + d` as its own SubTool
(`<name>_<target>`, one identifier each, one `GoZ_ObjectList` line each, M1). The manifest gets `representation`
`base` or `target:<LayerId>` per identifier (the audit's §8.1 field). Return of a target SubTool, same topology: `d' = p − b`
into that layer only (TargetView's rule), one Undo step; a return of the base: positions (targets follow, J-3) as
today. A target whose layer is gone since the send → new object.

**Layer route (only if M2 holds):** Mirai additionally writes each target as OBJ beside the send; ZBrush's layer
import (T9.6) puts them into layers of the base. Because a GoZ of the base returns the visible mix, its row then asks
what it is: „als Basis“ (all layers off) or „als Target <name>“ (only that layer, 100 %) — never guessed
(`PROVISIONAL`, wording after E3). M3 decides whether a resend of the base is allowed while ZBrush holds layers.

## 8. Practical test (Manu, reference PC)

1. Kopf mit UVs senden, in ZBrush *UV Master → Unwrap*, **GoZ**, übernehmen: Textur-Anzeige/UV-Ansicht in Mirai passt,
   `Strg+Z` nimmt die UVs zurück.
2. Polypaint, *Texture Map → New From Polypaint*, **GoZ**, übernehmen: die Textur steht richtig herum auf dem Kopf;
   die Kopie liegt in `<Szene>_textures/`.
3. Objekt mit einem Morph-Target senden: zwei SubTools/Tools in ZBrush. Das Target sculpten, **GoZ** auf dem Target,
   übernehmen: nur das Target ändert sich (Morph-Regler in Mirai), die Basis bleibt. Danach die Basis sculpten und
   **GoZ**: übernehmen ohne Konflikt.

**Practical test (Manu, 2026-11-06):** step 3 as expected. Steps 1–2 started from a Tool made in ZBrush (so the
return was offered as a new object): the new object had UVs but **no texture** — the new-object plans did not carry
the copied texture (fixed 2026-11-06, test `test_a_foreign_subtool_with_a_texture_becomes_a_textured_new_object`).
Note for the retest: an object selected in mode `4` shows its selection colour instead of its texture (AD-026
`PROVISIONAL`); the new object is selected after the add, so the texture shows once mode `4` is left.

## 6. Not in P3

Sending textures to ZBrush, normal / displacement maps, polypaint as vertex colours (Mirai has no colour storage),
masks, several UV maps, ZBrush's own morph target (`StoreMT`).

## 7. Sources (web, 2026-11-06)

[Maxon: Maya Blend Shapes plugin](https://help.maxon.net/zbr/en-us/Content/html/user-guide/zbrush-plugins/maya-blend-shapes/maya-blend-shapes.html)
(layers → blend shapes only through that plugin);
[ZBrushCentral: shape keys / subtools into 3D layers](https://www.zbrushcentral.com/t/can-i-turn-blender-shape-keys-or-subtools-into-3d-layers/352455),
[ZBrushCentral: import multi OBJs as layers](https://www.zbrushcentral.com/t/import-multi-objs-as-layers-help/205998)
(GoZ does not bring layers; layer import via plugin / import while recording). Forum statements are not verified for
ZBrush 2022.0.8 — that is what E3 T9.6 is for.
