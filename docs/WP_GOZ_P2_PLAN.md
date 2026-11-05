# WP GoZ P2 — polygroups ↔ regions, then n-gons (plan, 2026-11-05)

**Status:** P2a IMPLEMENTED (2026-11-05, container-tested; E2 done on the reference PC, §2), P2b open. Builds on [AD-029](architecture/AD-029-ZBRUSH-GOZ-BRIDGE.md) (P1,
implemented and tested on the reference PC: send, return, confirm, Ctrl+Z, symmetry fix). Decisions below are Manu's
(2026-11-05) unless marked `PROVISIONAL`. Order (Manu): **P2a polygroups first, then P2b n-gons.**

## Kurzfassung für Manu (Deutsch)

- **P2a Polygruppen:** Mirais Gruppen gehen beim Senden als ZBrush-Polygruppen mit. Bei der Rückgabe kommen
  Gruppen-Änderungen mit derselben Bestätigung wie die Punkte, als **ein** Undo-Schritt. Unveränderte Gruppen behalten
  ihren Namen, neue heißen „Group N“. Flächen ohne Gruppe bilden in ZBrush eine Restgruppe; bleibt sie unverändert,
  sind sie in Mirai wieder ohne Gruppe.
- **PC-Test E2 erledigt (2026-11-05):** ZBrush übernimmt die gesendeten Gruppen und gibt ihre Nummern unverändert
  zurück; eine in ZBrush neu gebildete Gruppe kommt mit einer neuen Nummer. P2a ist danach gebaut (§3).
- **Offen für dich:** Hast du in E2 Schritt 4 (`--import-polygroups`) ausgeführt? Aus den Captures geht es nicht
  hervor. Wenn nein, braucht Mirais Eintragung keine Zusatzoption; wenn ja, sollte der Praxistest zeigen, ob die Gruppen
  auch ohne sie in ZBrush erscheinen.
- **P2b N-Gons:** Mirai zerlegt N-Gons **nur in der gesendeten Datei**, möglichst in Vierecke. Dein Mirai-Mesh
  behält seine N-Gons; zurück kommen nur die Punkte (und die Gruppen). Werden die Teile eines N-Gons in ZBrush
  unterschiedlich gefärbt, bekommt das N-Gon die Gruppe mit dem größten Flächenanteil.

## 1. Facts this plan rests on

| Fact | Source |
|---|---|
| GoZ GROUPS block: tag 40001, one `uint16` id per face. | SDK (`experiments/goz_probe/README.md` §2.1) |
| **ZBrush gives a mesh sent without GROUPS one random group id for all faces** (46984, 10123, 21735, 63238, 12322 …), and keeps that id for the Tool across returns. | `tests/fixtures/goz/*` (2026-11-05, read in this plan) |
| An OBJ-imported Tool without `g` records returns GROUPS 0 for all faces. | E1 T2 capture A |
| Mirai: `FaceRegions` on the Mesh — named face sets, journaled, saved; Core allows overlap, the app's group rule puts a face in one group (`mirai.regions.grouped`); new topology inherits regions (`regions.inherit_into`, already called inside `_mesh_transaction`). | AD-REGIONS-01, `src/mirai/regions.py` |
| `GoZ_Info.txt` options `IMPORT_POLYGROUPS`, `GROUP_NSIDED_POLYS` exist; effect untested. | SDK |
| Mirai's n-gon triangulation (ear clipping) lives in `viewport/derived.py` (`triangulate_mesh_face`); `interop` must not import `viewport` — the glue hands it in (as `SymmetryInfo` does). | code |
| P1 refuses n-gons at the send (D4 proposal). | AD-029 §3 |

## 2. Open uncertainty → E2 (reference PC, before P2a code)

Does ZBrush 2022.0.8 **use** the GROUPS block of a file it imports from an app, and does it **return our ids
unchanged**? Prepared (container-tested, 46 probe tests): `probe_send.py --groups bands` (ids 101–104 by height),
`install_probe_app.py --import-polygroups` (the SDK option, second variant). Steps: E1 README §6 T8.
Outcomes and what P2a does:

**Result (Manu, reference PC, 2026-11-05; captures `20261105-2231…` to `…2236…`):** row 1. Both sends (`E1_C_P1_G`,
`E1_C_P1_G1`) came back with every face's id unchanged (101: 56, 102: 50, 103: 168, 104: 50; per face equal to the
send log). After a regroup in ZBrush 12 faces of 104 came back as **3225** (a new id ZBrush chose), every other face
unchanged, points bit-identical. → ids are the link. Not recorded: whether step 4 (`IMPORT_POLYGROUPS = TRUE`) was
run before the second send (the first send's return already carried 101–104); Mirai's `install.py` writes no such
option — the practical test (§6) shows whether the groups appear in ZBrush without it.

| E2 result | P2a |
|---|---|
| ZBrush shows 4 groups and returns 101–104 unchanged | ids are the link (manifest: id ↔ region name) |
| ZBrush shows groups only with `IMPORT_POLYGROUPS = TRUE` | `install.py` writes that option (re-install + restart once) |
| ZBrush renumbers the groups | link by face sets (an unchanged face set = the same group), not by id |
| ZBrush ignores GROUPS completely | P2a send-only is impossible; report, ask Manu |

## 3. P2a — polygroups ↔ regions (decided; IMPLEMENTED 2026-11-05)

Built as below in `interop/goz/format.py` (GROUPS block), `bridge.py` (`send_groups`, `plan_groups`, `REST_GROUP`),
`manifest.py` (`sent_groups`, `group_names`, `rest_group`, `group_overlaps`, `zbrush_groups`, fingerprint `regions`),
`zbrush_bridge.py` (naming via `mirai.regions.new_group_name`) and `Application.apply_goz_return`. Tests:
`tests/test_goz_format.py` / `tests/test_goz_bridge.py` (§ polygroups) on the E2 captures
(`tests/fixtures/goz/zb2022_E2_*`). Additions beyond the text below: after an applied return ZBrush's ids become the
baseline (`zbrush_groups`, like `zbrush_points`) and a new id keeps its `Group N` name, so further painting without a
resend joins that group; a P1 manifest on disk (no `regions` in its fingerprint, no `sent_groups`) plans positions only.
A new object (topology changed, conflict, foreign SubTool) does not take ZBrush's groups yet.

**Send:** each group (app rule: one group per face; a face in several regions → the first in region order,
`PROVISIONAL`, its other memberships recorded in the manifest) gets an id; faces in no region get one **rest id**.
Ids avoid 0 and stay stable per object in a session (`PROVISIONAL`: 1…N in region order, rest = 0xFFFE). Manifest:
id → region name, rest id, the sent per-face ids, overlaps.

**Return (same topology only):** per face the returned id.
- ZBrush's random single default id cannot occur for our sends (we always send GROUPS); for a return whose ids are
  all one value that we never sent → ignore groups, positions only (`PROVISIONAL`).
- Unchanged assignment (every face's id = sent id) → regions untouched (overlaps kept).
- Changed: id known → that region's name; rest id → no region; new id → `Group N` (`regions.new_group_name`). The new
  `FaceRegions` is written with the positions **in the same `_mesh_transaction`** (one Undo step; Manu: "Mit
  übernehmen"). Status: "groups: 3 changed, 1 new".
- A face's other (overlap) memberships: kept if its group did not change, dropped otherwise (`PROVISIONAL`).
- A groups-only change (no point moved) is an `IN_PLACE` plan (renamed from `POSITIONS`) with zero points.
- Fingerprint: add the region hash (a Mirai region edit since the send = conflict, like positions).
- Symmetry fix (AD-029 §6) is unaffected.

**Tests:** fixtures from E2 (ZBrush's returns with changed groups); unchanged, recolour, new group, rest group
painted, groups-only return, Undo restores regions and positions together, conflict on a Mirai region edit.

## 4. P2b — n-gons (decided)

**Send:** every face with > 4 corners is split **in the file only**, preferring quads (Manu: "Möglichst Vierecke"):
a deterministic split into quads plus at most one triangle, without new points (so the point list and the index ↔
`VertexId` map stay as in P1). Proposal: walk the boundary from a fixed start corner and cut off quads along
diagonals from the ear-clipping triangulation where two adjacent triangles form a convex quad; fall back to the
triangles for concave cases. The split must be a pure function of the boundary and positions at send time; the
manifest stores per n-gon its `FaceId` and the sent piece indices.

**Return:** topology = the sent pieces exactly → positions map back by point index as in P1 (no recombination is
needed: Mirai's faces never changed, only points move). Any other topology → `TOPOLOGY_CHANGED` (new object, with
the pieces, as today).

**Groups on n-gons:** the pieces get the n-gon's group id. If the pieces come back with different ids, the n-gon takes
the id with the **largest area share** of its pieces (Manu); the status counts such n-gons.

**Tests:** a Mirai mesh with n-gons (Knife / Dissolve result, concave 6-gon), split determinism, quads preferred,
no new points, round trip through a fixture with moved points, area-majority rule, topology change → new object.

## 5. Not in P2

UVs (send / back), polypaint, masks, several SubTools in one step, morph targets as `b + d`, D6 backup.

## 6. Acceptance

All P1 acceptance criteria (AD-029 §8) stay green; the new tests above; reference-PC practical test: a WIP file with
n-gons and groups → ZBrush → recolour + sculpt → GoZ → one confirm → groups and points in Mirai, Ctrl+Z restores
both, n-gons still n-gons.
