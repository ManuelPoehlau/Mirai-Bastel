# AD-029 — Mirai ↔ ZBrush bridge over GoZ (P1: positions, unchanged topology)

**Status:** IMPLEMENTED (P1, 2026-11-05), `PROVISIONAL` UI (SPACE rows, no key). Decisions D1, D11, D12, D13 by Manu
(2026-11-05); D2–D5 as the audit proposes, D6 open (see §7). Reference PC (Manu, 2026-11-05): send works and the head
shows upright (§8); returns through `Edit.bat` work (the P1 symmetry captures, §6). P2 (polygroups, n-gons incl. the
mirror-symmetric split) passed the practical test on 2026-11-06 ([plan](../WP_GOZ_P2_PLAN.md) §6).
**Builds on:** [ZBrush bridge audit](../future_ideas/ZBRUSH_BRIDGE_AUDIT.md) (§6–§8, decisions §10.3),
[E1 probe](../../experiments/goz_probe/README.md) (facts §2, completeness rule §7, fingerprint §8.1, results §10a/§11),
[AD-021](AD-021-OBJECT-COMPONENT-MODEL.md) (objects), [AD-023](AD-023-INCREMENTAL-TOPOLOGY-SYNC-AND-HISTORY.md)
(journal, one Undo step), [AD-025](AD-025-TOPOLOGY-PROVENANCE-AND-POINT-LAYERS.md) (layers by `VertexId`),
[AD-028](AD-028-SKELETON-AND-SKINNING.md) §7.1 (posed refusal). No `src/core/` change.

## Kurzfassung für Manu (Deutsch)

- **SPACE-Menü:** „An ZBrush senden“ schickt das Objekt nach ZBrush, aufrecht (`(x, −y, −z)`). Ein erneutes Senden
  desselben Objekts aktualisiert dasselbe Tool in ZBrush. Einmalig: „ZBrush: Mirai bei GoZ eintragen“, danach ZBrush
  neu starten und mit **R** neben GoZ „Mirai“ wählen.
- **Zurück:** In ZBrush **GoZ** drücken. Nach etwa 1–2 s meldet Mirai in der Statuszeile, was angekommen ist. Übernommen
  wird erst mit „ZBrush übernehmen: …“ im SPACE-Menü (D1), als **ein** Undo-Schritt. Unberührte Punkte bleiben
  bitgenau.
- **Geht nie in das Original:** geänderte Topologie, ein in Mirai seit dem Senden geändertes Objekt, eine fremde
  SubTool. Das wird nur als **neues Objekt** angeboten („ZBrush als neues Objekt: …“).
- **Unterteilt (D13):** Divide mit SMT ohne Cage wird zurückgehalten, mit Hinweis: unterste Stufe → Cage, oder SMT aus.
  Divide ohne SMT kommt bitgleich zurück. Nach Cage ist alles minimal verschoben: übernehmbar, mit Warnung.
- **Läuft Mirai nicht:** Die Rückgabe wartet, bis Mirai startet (D11).
- **Polygruppen (P2a, 2026-11-05):** Mirais Gruppen gehen als ZBrush-Polygruppen mit. In ZBrush umgefärbte Flächen
  kommen mit den Punkten zurück, gleiche Bestätigung, **ein** Undo-Schritt; eine in ZBrush neue Gruppe heißt „Group N“.
- **N-Gons (P2b, 2026-11-05):** werden nur in der gesendeten Datei zerlegt, möglichst in Vierecke. In Mirai bleiben
  sie N-Gons; zurück kommen die Punkte (und Gruppen). Bei eingeschalteter Symmetrie werden beide Hälften gleich
  (gespiegelt) zerlegt, N-Gons über der Mitte in sich symmetrisch.

## 1. Scope

In: one object per transfer; positions with the exact sent topology, in place; everything else as a new object; the
GoZ registration; the ZBrush → Mirai notification. Out (later, own steps): UVs back, polygroups ↔ regions (P2),
polypaint, masks, morph targets sent as `b + d`, several SubTools in one Undo step. (N-gons: P2b, below.)

**P2a (polygroups ↔ regions) is implemented** (2026-11-05, [`docs/WP_GOZ_P2_PLAN.md`](../WP_GOZ_P2_PLAN.md) §3, E2 result §2):
every send carries the regions as GoZ polygroups; a same-topology return brings group changes with the points, one
Undo step. **P2b (n-gons) is implemented** (2026-11-05, plan §4): a face with more than 4 corners is split **in the
file only**, preferring quads, without new points; the return maps back by point index and Mirai's n-gons stay
n-gons.

## 2. Packages and boundary

```text
src/interop/goz/        imports core + stdlib only (no pyglet, no Application, no experiments/)
    format.py           strict .GoZ reader / minimal writer (stdlib)
    files.py            GoZ folders, ANSI/CRLF list files, atomic writes, the completeness rule (stdlib)
    helper.py           run by GoZApps\Mirai\Edit.bat: snapshot + ticket into goz/inbox/ (stdlib, `python -I`)
    install.py          GoZApps\Mirai registration (stdlib)
    transfer.py         identifiers (GoZMakeObjectPath), writing a send, GoZBrushFromApp, the inbox (stdlib)
    manifest.py         transfer manifest + fingerprint (core)
    bridge.py           send build, return plan, subdivision signature (core; pure)
src/zbrush_bridge.py    window glue like obj_files.py: SPACE rows, tick, confirm (no pyglet)
Application.apply_goz_return(plan)   the only mutating entry
```

The format and protocol code is written from the official GoZ SDK 2022.0 description; no SDK or GoB code is copied.
The E1 probe's own format code was the starting point (same author, same rules); the probe stays in `experiments/` as
the reference until archived.

## 3. Send

Object: mode `4` → the one selected object, else the edit object; the base while a morph target's view is open
(never the mix, never the editing view). N-gons are split in the file only (P2b, `bridge.split_ngon`: ear clipping,
then quads where two triangles form one without a reflex corner; with Mirai's symmetry on, mirrored n-gons are split
alike and n-gons on the plane symmetrically, `bridge.split_ngons`, plan §4). Refused: an interaction running, no GoZ
folder, and — **before anything is written** — while ZBrush does not know Mirai yet: not registered, or registered but
not yet picked with **R** after a ZBrush restart (`install.known_to_zbrush`: ZBrush writes `GoZApps\Mirai\GoZ_Config.txt`
on that pick). Reason (Manu, 2026-11-05, reference PC): the first P1 send without registration wrote
`GoZ_Application.txt = Mirai` while `GoZApps\Mirai` did not exist, and the running ZBrush 2022.0.8 **crashed**; E1 never
showed it because `MiraiProbe` was always installed. Points: `to_goz(object_space.to_world(p))` with `to_goz(x, y, z) = (x, −y, −z)` (E1-Q6), float32, vertex-ID
order; faces as dense indices in face-ID order. Identifier: `GoZMakeObjectPath` for the first send of an object in a
session, reused afterwards (ZBrush updates the same Tool). Files (atomic): `<id>.GoZ` (the only file Mirai writes into
ZBrush's project folder; it carries a GROUPS block, P2a: region `k` → id `k`, faces in no region → `0xFFFE`),
`GoZ_ObjectList.txt`, `GoZ_Application.txt = Mirai`; then `GoZBrushFromApp.exe` **without
`-tmap`** (E1 T5.2), started as E1 started it (plain `Popen`). No
History entry. ZBrush's own preferences (*Import as SubTool*) are never changed.

## 4. Return

`Edit.bat` (no arguments, E1-Q2) runs `helper.py` with Mirai's Python: for every listed identifier the E1 §7 rule
— copy, strict parse, 1.0 s wall-clock quiet period, re-hash unchanged, exclusive-open diagnostic, back-off up to 10 s
— then one atomic ticket in `goz/inbox/`. The helper never starts Mirai (D11) and never writes a ZBrush file. Mirai's
tick (every 0.25 s) claims a ticket by moving it to `done/` (two windows never take the same one), verifies each
copy's sha256, parses it strictly and plans it; a newer return of the same identifier replaces a waiting one.

## 5. Identity and fingerprint

The manifest (in memory and in Mirai's own `goz/manifests/`, keyed by the identifier) holds `transfer_id`, `session_id`, the scene file path, `ObjectId`, name,
GoZ identifier, the index ↔ `VertexId`/`FaceId` maps, the sent faces, the hash of the sent float32 points and the
fingerprint (E1 §8.1): topology hash (IDs + boundaries incl. rotation), float64 positions hash, placement (transform,
pivot, state), every point layer's meta and values hash (morph targets and weights), the rig hash, the face regions
hash (P2a; a Mirai group edit since the send is a conflict). P2a adds the sent group id per face, id → region name, the
rest id and the overlaps. The link holds when
the session is the same, or the current scene file is the one sent from (D11: a later Mirai start) and the object
exists. After an applied return the manifest takes the new fingerprint, so further sculpting without a resend plans
against the applied state. The session keeps every manifest version of an identifier (the send, then one per
applied return, at most 32): a return is planned against the newest version the object still matches, so after
**Ctrl+Z of an apply** the next GoZ links to the version before it and is offered again without a resend (Manu,
2026-11-05: it used to be a conflict). Only a real Mirai edit since then is a conflict. A ticket from before this
Mirai started has only the newest version (on disk).

## 6. Plan kinds (`bridge.ReturnKind`) and the apply

| Kind | When | Row / action |
|---|---|---|
| `IN_PLACE` | linked, topology identical, fingerprint identical, some point or group id differs | „ZBrush übernehmen“: moved points and changed regions (P2a), `_mesh_transaction`, one Undo step. `cage_like` (≥ 95 % moved, each by ≤ 2e-4 × extent; T7c: 7.8e-5): a warning in the status line (D13), still appliable |
| `UNCHANGED` | as above, no point and no group id differs | status only |
| `SUBDIVIDED` | every interior point = the one-step Catmull-Clark vertex point of the sent cage (tolerance 1e-5 × extent), some moved | status only, held, the hint names Cage and SMT off (D13); border points are not judged (ZBrush's border rule unmeasured) |
| `CONFLICT` | linked, topology identical, the Mirai object changed since the send | „ZBrush als neues Objekt“ (D3 proposal: no overwrite) |
| `TOPOLOGY_CHANGED` | counts or any corner list differ | „ZBrush als neues Objekt“ (D2 proposal) |
| `UNKNOWN_OBJECT` | no manifest, another session without the same scene file, the object gone | „ZBrush als neues Objekt“ |
| invalid | ticket says incomplete, hash or parse fails | status only |

**Mirror symmetry** (Manu, 2026-11-05): ZBrush's Smooth brush with X symmetry is not exactly symmetric — on the head
76 of 145 mirror pairs came back off by up to 0.0102 (0.2 % of its size) and 13 of 36 seam points off the plane, while
the Move brush stays bit-exact (captures `tests/fixtures/goz/zb2022_P1_*`). Mirai pairs points only by exact mirrored
position, so they showed as unpaired. While the object's Mirai symmetry is on, every pair or seam point a return
touched whose deviation is at most **1 % of the object's size** is made exact inside the same Undo step: a pair gets
the mean of its two sides, a seam point goes onto the plane (`bridge.symmetrize_positions`; pairs and the mirror map
come from `mirai.symmetry` through the glue). Larger deviations stay and are reported. With Mirai's symmetry off a
return is taken exactly as ZBrush sends it. Mirai's own Re-Symmetrize is unchanged (exact, no tolerance).
After an applied return the manifest keeps ZBrush's points (`zbrush_points`), so a point ZBrush did not move since
then keeps Mirai's value — including a mirrored mean — instead of reading as moved again.

**Polygroups (P2a):** ZBrush keeps the sent ids per face and gives a group made there a new id (E2). A face whose id
differs from the last known one leaves every region and joins the one its id names; a new id becomes `Group N`
(`mirai.regions.new_group_name`), the rest id no region. Unchanged faces keep all memberships (overlaps). If every face
carries one id Mirai never sent, the groups stay untouched. The status line says „groups: N changed, M new“.

Untouched-point rule (audit §7.3): a returned point equal to the sent float32 bits keeps its float64; a moved one is
`to_object(from_goz(p))`. The plan is computed again at the confirm; if its kind changed since the arrival, nothing is
applied and the new verdict is shown. `apply_goz_return` refuses (status, nothing changed, the row stays) during an
interaction, while the mesh is posed and bound, while a morph target's view is open, and when the object is not the
edit object (audit Q8, `PROVISIONAL`: no silent edit-object switch). A new object gets fresh IDs, identity placement,
the name `<name> ZBrush`, and the usual Add-object Undo step.

## 7. Decisions

| # | Decision | State |
|---|---|---|
| D1 | confirm before applying | **Manu 2026-11-05: confirm** (SPACE row) |
| D2 | changed topology | audit proposal: new object only |
| D3 | conflict | audit proposal: no overwrite, new object |
| D4 | n-gons | P1: refused at the send. **P2b (Manu 2026-11-05):** split in the file only, „möglichst Vierecke“; an n-gon split across groups in ZBrush takes the group with the largest area share |
| D5 | several SubTools | one plan and one Undo step per object (each its own row) |
| D6 | automatic backup before the first in-place apply | **not built**; Undo covers the session (open) |
| D8 | register as a GoZ app | yes (E1-Q1), only on the artist's row |
| D9 | key | none; menu rows only, a key after "Taste passt" |
| D11 | Mirai not running | **Manu 2026-11-05: the ticket waits** |
| D12 | app name | **Manu 2026-11-05: `GoZApps\Mirai`, `NAME = "Mirai"`** |
| Sym | ZBrush returns with small mirror deviations | **Manu 2026-11-05:** made exact automatically, threshold 1 % of the size, only while Mirai's symmetry is on |
| P2a | polygroups ↔ regions | **Manu 2026-11-05:** with the points, same confirm, one Undo step; unchanged groups keep their names, new ones are „Group N“ (WP_GOZ_P2_PLAN §3) |
| D13 | a return from a divided SubTool | **Manu 2026-11-05 (after T7b/T7c):** smoothed (SMT, no Cage) → held with a hint; Cage → appliable with a warning; without SMT → bit-identical, nothing special |

## 8. Verification

Test-verified (container, Linux, 2026-11-05): `tests/test_goz_format.py` (format fail-closed, flip, n-gon split (convex, Knife point, concave L / notch),
plans on the ZBrush 2022.0.8 captures of the head and of mesh B with ID gaps, the subdivision signature on the T7
capture, T7b bit-identical, the T7c Cage warning, the completeness rule incl. a file changing in the quiet period, helper as `python -I` without pyglet or
`core`, inbox claimed once, registration refusing a foreign folder; P2a: GROUPS block, send ids / rest / overlaps, the
E2 captures unchanged and regrouped, known / rest / new ids, a region edit as conflict) and `tests/test_goz_bridge.py`
(A1–A8 on the app path with fake ZBrush utilities; P2a: regroup + sculpt as one Undo step, groups-only, conflict,
Undo of a group apply; P2b: n-gons sent split, sculpt back, still n-gons, one Undo step). Captures used: `tests/fixtures/goz/README.md`.
Measured (container, A9): gollum_20k (21 875 points): send 0.15 s, helper 0.19 s + 1 s settle, arrival + plan
0.48 s (one frame blocked), confirm (re-plan + apply) 0.41 s. Reference PC: not measured.
Reference PC (Manu, 2026-11-05, ZBrush 2022.0.8): after registering, restarting ZBrush and picking Mirai with **R**,
the send works and the head shows **upright** — the `(x, −y, −z)` map is confirmed, and so is the
`known_to_zbrush` signal (`GoZApps\Mirai\GoZ_Config.txt`). Before that fix, a send without registration crashed ZBrush
(§3). The real `Edit.bat` → helper → Mirai return path delivered the P1 symmetry captures (`tests/fixtures/goz/zb2022_P1_*`).
P2 practical test (Manu, 2026-11-06): groups and n-gons round trip as planned; with the mirror-symmetric split every
mirror pair came back in Mirai even after strong smoothing over many split n-gons.

## 9. Practical test (Manu, reference PC)

1. SPACE → „ZBrush: Mirai bei GoZ eintragen“, ZBrush neu starten, **R** → „Mirai“.
2. Kopf laden, SPACE → „An ZBrush senden“: steht der Kopf aufrecht, von vorn?
3. Move-Pinsel, **GoZ**: Statuszeile in Mirai, SPACE → „ZBrush übernehmen: …“, Strg+Z / Strg+Y.
4. Weiter sculpten, **GoZ** ohne neues Senden: wieder „übernehmen“ (kein Konflikt).
5. In Mirai etwas ändern, dann **GoZ**: nur „als neues Objekt“.
6. Fühlt sich das wie ein Arbeitsablauf an (A10)?
7. (P2a) Kopf mit ein paar Gruppen senden: zeigt ZBrush sie als Polygruppen (*Polyframe*, `Shift+F`)? Ein paar Flächen
   umgruppieren (maskieren, `Strg+W`) und sculpten, **GoZ**: Statuszeile „groups: … changed, 1 new“, übernehmen; die
   neue Gruppe heißt „Group N“, `Strg+Z` nimmt Gruppen und Punkte gemeinsam zurück.
8. (P2b) Eine Datei mit N-Gons (Knife / Dissolve, auch ein konkaves) senden: Sieht die Fläche in ZBrush sauber aus
   (Vierecke, keine Löcher, keine umgedrehten Teile)? Sculpten, ein N-Gon teilweise umfärben, **GoZ**, übernehmen: die
   N-Gons sind in Mirai noch N-Gons, `Strg+Z` nimmt alles zurück.
