# AD-036 — Eyes, teeth and lids on the rig: a bone link for rigid parts, gaze as a pose source, lids by weights

**Status:** **PROPOSED (2026-11-18); Artist decisions taken (Manu, 2026-11-18: "E1 ja, E2 ja, E3 ja, E4 go")** — E1–E4
as recommended, the Core go given (E4); E5 answered the same day: the teeth stay unbound for now (Manu binds them
later; the build delivers the capability), the ears are weighted (§16). **Next: the second opinion in the main project (§13), then the
build** — no code before it. Architecture Gate (Type C) after AD-028's bone tool 01/02; output of the gate: this AD.
**Mode (M5):** Architecture Gate. Small throw-away probes only (§8.1; not committed).
**Baseline:** `main` @ `939df8b` ("scenes: eye bones Auge_Links / Auge_Rechts"). `git log 939df8b..origin/main` is empty
(fetched 2026-11-18): nothing changed since the handoff. Every code fact below was read there (file:line).
**Answers:** the handoff questions 1–6 (eyes, teeth, lids following the rig); AD-021 §4.9 "rigid parts are Objects whose
`transform` a future parent (bone or object) drives"; AD-028 §5.3 / §15 "objects parented to bones and rigid parts";
AD-033 §4.3 / §11 "an eye parented to a head bone (AD-028), later".
**References (binding):** [AD-028](AD-028-SKELETON-AND-SKINNING.md) (S1–S8; §3.2, §5.1–§5.3, F-16, §7, §15, addenda
2026-11-17 / 2026-11-18) · [AD-021](AD-021-OBJECT-COMPONENT-MODEL.md) §4.3, §4.5, §4.9, §6.8 ·
[CORE_V1_FREEZE](CORE_V1_FREEZE.md) §7, §7.1 · [AD-033](AD-033-EYE-PREVIEW-IN-THE-WORKLIGHT.md) §4.3, §5.1, §11, §12, §14,
§17 · [AD-035](AD-035-SCLERA-COLOUR-MAP.md) · [AD-032](AD-032-PACKED-ARRAYS-NUMPY.md) ·
[REFERENCE_HARDWARE](REFERENCE_HARDWARE.md) §2, §4 · [MODELING_ON_DEFORMED_SURFACES](../design/MODELING_ON_DEFORMED_SURFACES.md)
§C, §16, R-8, R-11.
**Tags:** **[V]** verified in code at `939df8b` (file:line) · **[C]** measured or counted in the container (Linux, Python
3.13.18, NumPy 2.5.3 — not the pinned 2.2.6; a scratch probe outside the repository, re-runnable from §8.1) · **[D]** a
measurement recorded in a decided document (named) · **[H]** estimate or arithmetic. No number here is a reference-PC
number. `PROVISIONAL` marks every agent choice the Artist has not verified (names, texts, panel rows, tolerances).

## Kurzfassung für Manu (Deutsch)

**Worum es geht:** Augen, Zähne und später die Lider sollen dem Rig folgen — Kopf drehen, Kiefer öffnen, Augen drehen —,
ohne dass Undo, Topologie-Änderungen, Speichern/Laden, die Augen-Vorschau oder die Gewichte darunter leiden. Das ist
eine Vorlage zum Entscheiden; gebaut wird noch nichts.

**Empfehlung in einem Satz:** Starre Teile (Augen, Zähne) bekommen eine **Knochen-Verbindung** („dieses Objekt folgt
Knochen X“), die Lider bleiben Teil des Kopfes und bekommen **Gewichte** auf dem Augenknochen, und **in einer Pose
steuert der Blick die Augenknochen** — Augapfel und Lider bekommen so dieselbe Drehung.

**Was das für jedes Teil heißt:**

- **Zähne:** Oberzähne folgen dem Kopfknochen (im Testkopf ist das „Hals“), Unterzähne dem „Kiefer“. Ein Zahn bleibt ein
  normales Objekt: in Ruhe verschieben, drehen, duplizieren, spiegeln, Loops einfügen — wie heute. In einer Pose ist er
  gesperrt wie der Kopf (Ruhe ↔ Pose ist eine Taste).
- **Augen:** Jedes Auge folgt seinem Augenknochen. Hier geht nur die Verbindung: die Augen-Vorschau berechnet Iris und
  Hornhaut aus der Lage des ganzen Auges. Würde man den Augapfel Punkt für Punkt verformen, bliebe die Iris stehen.
- **Lider:** Gewichte am Kopf auf dem Augenknochen. Hoch/runter schauen: das Lid geht mit — gut. Zur Seite schauen: das
  Lid dreht sich mit, echte Lider tun das kaum. Bei großen Drehungen sinkt ein halb gewichteter Lidpunkt etwas in
  Richtung Augapfel (bei 30° etwa 0,45 mm an einem 12-mm-Auge). Dafür gibt es später bekannte Lösungen (ein eigener
  Lidknochen, der nur hoch/runter mitgeht; eine andere Rechenart für die Mischung); diese Vorlage verbaut keine davon.
  Das Lid-System selbst ist nicht Teil davon.
- **Blick (Kamera / Maus / Ziel):** In einer Pose dreht der Blick die Augenknochen, die Lider gehen mit. In Ruhe bleibt
  es wie heute: nur die Augäpfel drehen sich, die Lider bleiben — so kannst du weiter modellieren, während Gollum dich
  ansieht (E2).
- Der Lidschatten der Augen-Vorschau bleibt beim Kopf, nicht beim Augapfel — wie heute, auch wenn der Kopf sich dreht.
- **In einer Pose zeigt jedes Objekt die Pose**, nicht nur das bearbeitete (heute bleiben andere Objekte in Ruhe).

**Zu deiner Neigung „Zähne per Gewichte“:** Es kommt genau dasselbe heraus (gemessen: dieselben Punkte bis auf eine
Abweichung von 0,00000000000000006). Gewichte auf Zähnen hätten heute aber Nachteile: Ein Zahn mit Gewichten lässt sich
nicht duplizieren, kopieren oder spiegeln, und er ist festgesetzt (nicht mehr verschiebbar). Die Verbindung kostet pro
Pose-Schritt für alle sechs Teile zusammen etwa 0,06 ms (im Container), Gewichte kosten pro Zahnpunkt. Gewichte auf
Zähnen bleiben später möglich (z. B. wenn Zahnfleisch dazukommt) — nichts wird verbaut.

**Beim Lesen der Testszene gefunden:** 406 Punkte des Gollum-Kopfes hatten kein Gewicht, fast alle in den Ohren — bei
einer Kopfdrehung wären die Ohren stehen geblieben. Inzwischen sind sie gewichtet (2026-11-18); übrig sind 2 Punkte unten
am Hals, die stehen bleiben sollen. Die Regel: Was an keinem Knochen hängt, bleibt in jeder Pose an seinem Platz — bei
Punkten wie bei Objekten. Vorschlag: eine Ansicht „nicht gebunden“, die genau diese Punkte zeigt, und im Bone-Panel bei
jedem Objekt „folgt: Knochen …“.

**Kosten auf deinem PC:** nicht gemessen. Eine Kopfdrehung bewegt 2 276 der 2 278 Kopfpunkte (mit den Ohren). Nach den
Kiefer-Messungen erwarte ich „benutzbar, nicht flüssig“ (geschätzt 45–60 ms pro Schritt). Das liegt am Kopf selbst, nicht an Augen oder
Zähnen. Den Messlauf beschreibt §8.3.

**Datenformat:** ein neues Feld pro Objekt („folgt Knochen …“), Dateiformat 13 — eine Core-Änderung, die dein Go
braucht. Ältere Builds lehnen solche Dateien ab, statt die Verbindungen beim Speichern still zu verlieren.

**Deine Entscheidungen** (je eine Zeile; „ja“ = Empfehlung) — **beantwortet am 2026-11-18: „E1 ja, E2 ja, E3 ja, E4
go“; E5 offen** (§16):

- **E1 Zähne** per Knochen-Verbindung (wie die Augen), nicht per Gewichte. — *ja / Gewichte*
- **E2 Blick und Lider beim Modellieren:** Der Blick bewegt die Lider nur in einer Pose. In Ruhe drehen sich nur die
  Augäpfel (wie heute), und Modellieren bleibt möglich. — *ja / Lider immer mit dem Blick (dann ist Verschieben und
  Topologie am Kopf gesperrt, solange die Augen nicht geradeaus schauen)*
- **E3 Verbundene Teile in Ruhe verschieben:** erlaubt (Zähne nachjustieren), in einer Pose gesperrt. — *ja / immer
  gesperrt wie der gebundene Kopf*
- **E4 Core-Änderung:** das Feld „folgt Knochen“ am Objekt, Dateiformat 13. — *go / nein*
- **E5 Für das Testszenario:** Welche der vier Zähne (`tooth`, `tooth01`, `Zahn_1`, `Zahn_2`) sind oben, welche unten?
  Sollen die Ohren (heute ohne Gewicht) an den Hals? Ein eigener Kopfknochen zwischen Hals und Kiefer/Augen ist möglich,
  aber nicht nötig. — *beantwortet: Zähne bindest du später selbst, gebraucht wird nur die Möglichkeit; die Ohren sind
  gewichtet.*

**Zur Kenntnis (keine Frage):** Einen Fokus-Abstand für den Blick gibt es schon, als Ansichtswert (Standard 25
Augenradien ≈ 30 cm); er wird nicht gespeichert. Soll er gespeichert werden, geht das wie bei den Morph-Reglern in der
Ansicht der Szene, ohne Formatänderung (§5.6). Offen bleibt, ob beim Zielen die eigene Grundstellung jedes Auges
(3,8° nach außen) erhalten bleibt; heute schauen beide Augen genau auf den Punkt.

---

## 0. Inputs and what this AD does with them

**Artist (Manu, chat 2026-11-17/18; not yet recorded in a repo verdict — this AD records them as inputs):**

| Input | Here |
|---|---|
| Eyes get real bones; the eyelids **must follow the eye movement**; the lid system is later, but the architecture must allow it now | eye bones drive the eye objects (§4) and, through weights, the lid points (§6); gaze becomes a source of the eye bones' pose in a pose (§5) so the lids see every eye turn, also the gaze's (E2 for the modelling case) |
| Each eye's anatomical rest rotation (≈ 3.8° outward on the left eye) is individual and is the neutral pose: bone pose 0 = how the eye looks now | holds by construction: a link draws `S_b · T`, and at rest `S_b` is absent, i.e. exactly the identity (§4.2, F-1) |
| Vergence depends on the focus distance; gaze converges on one point; "no focus-distance value"; gaze is view state; keep in mind, not a build order | a focus value exists as view state (F-9); where a saved one would live: §5.6. No build order |
| Teeth: "wahrscheinlich eher per Skin Weights" — open | weighed honestly in §3; recommendation: the link (E1); weights stay possible (§3.4) |
| Bones are placed by hand (bone tool 01/02, built) | unchanged; the link uses the placed bones as they are |

**Engineering hypothesis of the handoff (to be tested, not assumed):** weights carry what deforms or blends; a rigid
whole-object follower may be cheaper through a per-object matrix; teeth either way; eyes probably need the matrix route.
**Result:** confirmed for eyes (forced by the eye pass, §3.2 F-7); for teeth the matrix route wins on cost and on
workflow (§3.2), weights give the same points (§8.1). **Refuted:** the handoff's "rest offset stored at link time so the
link does not move the object" — no offset is needed, because the rig's skin transforms are already rest-relative (§4.2).

## 1. Facts (verified at `939df8b`)

| # | Fact | Where |
|---|---|---|
| F-1 | Skin transforms are **rest-relative**: `S_root = B·L·B⁻¹`, `S_child = S_parent·(B·L·B⁻¹)`; a bone whose own and every ancestor's pose is identity has **no** transform (exact rest, no product formed); an identity bone under a posed parent takes the parent's transform as it is | [V] `src/mirai/skinning.py:121-158` |
| F-2 | Bound points are conjugated by the placement, `A_b = T⁻¹·S_b·T`, so a bound point's world position is `S_b·T·p`; a bound object's placement is locked (S6) | [V] `skinning.py:168-183`; `controllers/skeleton.py:1504-1528`; AD-028 §3.2, §7.2 |
| F-3 | The skin stage shows only the edit object and the morph base beside its editing view (`shown`); every other object draws its own rest mesh (AD-028 §5.3, F-16). The stage already keeps one surface **per object** (`_surfaces`) and returns non-edit ones as H7-E entry surfaces, and the viewport already draws an entry surface in place of an object entry, following its matrix | [V] `skinning.py:603-619`, `:641-672`; `src/viewport/viewport.py:631-660` |
| F-4 | Posed and bound: position and topology commands on the edit mesh are refused with the rest key in the text; mode `4` is left to the placement policy | [V] `skeleton.py:1486-1503` |
| F-5 | Non-edit objects are drawn by `sync_views` with `_drawn_matrix` (placement; an eye turned to the gaze point; a morph-view twin shifted); the edit object's matrix is its placement | [V] `src/mirai/controllers/objects.py:1254-1331`, `:1281`, `:1355-1373` |
| F-6 | Object picking in mode `4` (`pick`) projects each object's own mesh through `camera_for(obj)` = `ObjectSpaceCamera(camera, obj)`, which reads `obj.transform` live; the orbit focus stores the picked object's pivot in object space | [V] `objects.py:1527-1558`; `src/mirai/object_space.py:134-160`; `application.py:5229-5233` |
| F-7 | The eye pass computes all eye geometry in **eye-local space through the inverse model matrix** (`u_model_inv`); the lid shadow and lid band live in the eye's **rest frame**; `EyeDraw.rest_matrix` carries that frame, `rest_rotation` = `inverse(rest)·model`; the app passes the placement without the gaze as the rest matrix, and only while a gaze is on | [V] `src/viewport/eye_shaders.py:12`, `:585`, `:695-696`, `:366-386`, `:811`, `:819`; `src/viewport/eye_pass.py:69`, `:163-171`; `objects.py:1305-1307` |
| F-8 | An eye is never the edit object (Q-E5); Apply transform is refused for eyes ("its placement stays an object transform"); its shell is generated from its values | [V] `objects.py:1514`, `:1703-1708`; AD-033 §4.3 |
| F-9 | Gaze is view state (`DisplayState.eye_gaze`, not saved, no Undo). `aimed_transform` turns an eye about its centre from its **document** rest forward (+Z of its rotation) by the shortest rotation (no added roll), clamped to 50°. `focus` (25 sclera radii ≈ 30 cm at the reference eye) sets the mouse plane's and the gaze pad's distance; both eyes aim at one point, so vergence follows the target distance; in `camera` mode the camera's eye is the target | [V] `src/mirai/viewport/display.py:88-89`; `src/mirai/eye_gaze.py:30-43`, `:105-141`, `:167-206` |
| F-10 | `SceneObject.parent` is the **group** an object hangs in (a group has no placement; members keep absolute placements) | [V] `src/core/scene.py:443`, `:475-479`; AD-021 §6.8 |
| F-11 | Duplicate / Copy refuse a mesh with point layers (morph targets **or weights**); mirror copy of a weights mesh is refused (S8) | [V] `objects.py:1215-1227`; AD-028 §4 |
| F-12 | A bone gesture rotates the bone about its **posed head** | [V] `skeleton.py:211`; AD-028 §17.3 |
| F-13 | A rest edit of a bone (`edit_bone`) touches neither weights nor mesh; the rest display is bit-identical before and after | [V] `application.py:1238`; AD-028 addendum 2026-11-17 |
| F-14 | View state can travel in the scene file without a Core change: the `"view"` section (`mirai.view_state`), which since 2026-11-16 carries the morph sliders — no Undo, older builds ignore it | [V] `src/mirai/view_state.py:1-13`, `:78`, `:82-96` |
| F-15 | The scene format is chosen by content; current maximum 12; object fields `texture` (6), `hidden` / `parent` (8), `eye` (9–12) | [V] `src/core/serialization.py:101-146`, `:188-209` |
| F-16 | Symmetric weight writing is refused for an off-centre bone ("needs its mirror bone") | [V] AD-028 §8.4; MODELING_ON_DEFORMED_SURFACES §C |
| F-17 | Bones live in world space; there is no rig transform | [V] AD-028 §3.1 |
| F-18 | **Test scene** `scenes/Gollum_Head_rigging_test.mirai.json` (v12). Bones `Hals` (id 0, root; head at the neck base `(0, −0.118, −0.339)`, tail = `Kiefer`'s head = the jaw hinge), `Kiefer` (1), `Auge_Links` (5), `Auge_Rechts` (6), all children of `Hals`; each eye bone's head equals its eye object's translation (pivot 0) exactly, its tail lies on the eye's +Z (3.79° outward, to 4e-17), length 2 eye radii. **At `939df8b`:** `Gollum` 2,254 points, Skin layer with 1,848 stored values; **406 points unbound, 404 of them at \|x\| > 0.3** (the mesh spans \|x\| ≤ 0.49: the ears). **At `4aa4ae9` (Manu, 2026-11-18, ears weighted):** `Gollum` (edit object, identity placement) 2,278 points, Skin layer with 2,276 stored values (keys: Hals 1,995, Kiefer 628; 127 with an object share), the ears on `Hals`; **2 points unbound** — a mirrored pair at the neck base (y −0.264), where the rest is meant. Unchanged between both: four teeth (`tooth`, `tooth01`, `Zahn_1`, `Zahn_2`), 16 points each, at the mouth line (y 0.198–0.273), unbound, no parent, same placements; two eyes (3,330 points each, a mirror pair; object ids renumbered 2–8 at `4aa4ae9`) | [C] read from the file at both commits |

## 2. Decision in one screen (the recommendation, "H")

1. **Rigid parts follow a bone through a link on the object:** `SceneObject.bone: BoneId | None` (an additive Core field,
   format v13). The drawn placement of a linked object is `S_b ∘ T` — one similarity per object, no per-point work. **No
   stored offset:** `S_b` is rest-relative and exactly absent at rest (F-1), so linking never moves the object, and a rest
   edit of the bone leaves it bit-identical (as weighted meshes, F-13).
2. **Deforming parts keep weights:** the head (incl. the lids later) stays a bound mesh (AD-028 unchanged). Weights on a
   rigid part stay possible (Option A), but are not recommended for teeth (E1).
3. **Every object shows the pose** (F-16 lifted for display): linked objects by their drawn placement; bound non-edit
   objects by the skin stage's existing per-object surfaces (F-3). Picking in mode `4` follows what is drawn.
4. **Eyes** link to their own eye bone (head at the eyeball's centre, checked when linking). The eye pass's lid frame is
   the eye's placement carried by the eye bone's **parent** (the head), never by the eye's own turn.
5. **Gaze** stays view state. **In a pose** it is a source of the eye bones' pose (it replaces their manual channels while
   on), so eyeball and lid points see the same turn; **at rest** it turns the eye objects only, as today (E2).
6. **Lids** are head-mesh points weighted partly to the eye bone. Linear blending gives a correct up/down follow, a wrong
   sideways swing and a small inward sink; a later axis-limited lid bone or a dual-quaternion blend fixes these on the
   same data (§6). Nothing here designs the lid system.
7. **While posed** a linked object's placement and (as the edit object) its positions and topology are refused, like the
   bound mesh (S5); **at rest** its placement stays free (E3). Apply transform stays (it keeps the world shape).
8. **Unbound stays at rest** — points without weights and objects without a link. Made visible by an "unbound" weight view
   and a "follows" row per object (`PROVISIONAL`).
9. **Cost:** the link 0.06 ms per pose step for six objects [C]; the step a user sees is the bound head's per-point patch,
   as for the jaw (P-1). Reference-PC runs named in §8.3.

## 3. Options for rigid parts (Q1)

### 3.1 The candidates

| # | Option | In one line |
|---|---|---|
| **A** | **Weights 1.0 on a bound mesh** | each tooth (eye) mesh gets a Skin layer with `((bone, 1.0),)` on every point; the skin stage evaluates it; needs per-object evaluated display (F-16 lifted for non-edit bound objects) |
| **B** | **Bone link on the object** | `SceneObject.bone`; the drawn placement is `S_b ∘ T`; no per-point data, no per-point work |
| **H** | **Hybrid (recommended)** | B for every rigid part (eyes required, teeth recommended); weights for every deforming part (head, lids; later gums, tongue); per-object skinned display for bound non-edit objects (A's display half) built with it |
| B-off | B with a rest offset stored at link time (Maya's parent-inverse) | rejected: redundant with rest-relative `S_b` and stale after a rest edit (§4.2) |
| B-par | B through `SceneObject.parent` (a bone or an object as parent) | rejected: `parent` means group membership with no placement of its own (F-10); one field, two meanings |
| B-rig | B stored in the rig (`Rig.links: ObjectId → BoneId`) | rejected: the object is what follows; duplicate / delete / paste of objects would have to edit the rig |

### 3.2 What each means and costs

| | **A — weights 1.0** | **B — link** | **H — hybrid** |
|---|---|---|---|
| **Eyes** | **not possible:** the eye pass draws the eye from the inverse model matrix (F-7); a per-point skinned shell would move the raster footprint while the analytic iris and cornea stay at the rest placement. An eye can also never be the edit object (F-8), so no weight gesture reaches it | the drawn matrix is the eye's placement turned by its bone; the pass, the gaze and the lid frame keep working on matrices (§5) | as B |
| **Teeth** | works once non-edit bound objects show the pose (§4.6); weights are set with the tooth as the edit object | works with one field per tooth | B |
| **Lids** | (part of the head mesh in every option: weights) | — | weights on the eye bone (§6) |
| **Same result?** | yes: weight 1.0 gives `A_b·p` = `T⁻¹·S_b·T·p`, i.e. world `S_b·T·p` (F-2) — measured equal to the link on the four teeth to 5.6e-17 [C, §8.1] | `S_b·T·p` | — |
| **Display path** | skin stage per bound object (F-3; a widening of `shown`), the viewport's entry surfaces | the entry's model matrix in `sync_views` (F-5); the eye pass unchanged | both |
| **CPU per pose step** | LBS + table 0.33–0.38 / 0.42–0.44 ms for 4 × 16 tooth points [C] **plus** the viewport's per-point patch ≈ 10.7 µs per point [D: AD-028 §5.4] → ≈ 0.7 ms more [H]; grows with the tooth mesh (a 5,000-point dentition ≈ 55 ms [H]) | 0.06–0.07 / 0.08–0.09 ms for all six objects incl. the bone transforms [C]; independent of mesh size | B's for rigid parts; the head's patch as today |
| **GPU** | unchanged (positions re-uploaded per moved point) | unchanged (one uniform per entry) | — |
| **Undo** | weights through the journal (AD-028); pose no Undo | link / unlink one Undo step each; pose no Undo | both |
| **Topology edits on the part** | weights interpolate (AD-028 §4); refused while posed (S5) | nothing to carry (no point data); refused while posed for a linked edit object (§4.5) | — |
| **Placement** | **locked** while bound (S6, F-2) | free at rest, refused while posed (E3) | — |
| **Duplicate / Copy / mirror copy** | **refused** for a mesh with weights (F-11) — a weighted tooth cannot be duplicated or mirrored | carried (duplicate, paste); mirror copy keeps the link only for a bone on the symmetry plane (§4.4) | — |
| **Apply transform** | allowed, world unchanged (AD-028 §3.2) | allowed, world unchanged (`S_b·I·(T·p)`); eyes: refused as today (F-8) | — |
| **Morph on the part** | morph → skin (AD-028 §5.1) | the mix in object space, then the drawn matrix | — |
| **File format** | none (v7 weights exist) | `"bone"` per object, **v13** | v13 |
| **`src/core`** | none | one additive field (`SceneObject.bone`) + serialization (§9) | as B |
| **Picking (mode `4`)** | the pick must read the skinned surface of the object (a mesh-sized re-projection per pose step on the next click) | the object's camera reads the drawn placement (one transform) | both |

### 3.3 Reading

- **Eyes decide the mechanism.** The eye pass, the gaze, the lid frame and the iris shading are all built on the eye's
  placement matrix (F-7, F-9); per-point skinning cannot drive them. A carrier for rigid parts that is a matrix is
  therefore needed in any case, and once it exists, using it for teeth costs nothing extra.
- **Teeth could go either way** — the points are the same (§8.1). The deciding differences are practical: a weighted tooth
  cannot be duplicated, copied or mirror-copied (F-11) and its placement is locked (S6), while fitting teeth means nudging,
  duplicating and mirroring them; and the link's cost does not grow with the tooth mesh.
- **What weights give that the link does not:** a partial follow (gums that stretch between jaw and head, a tongue), and one
  mechanism for everything. Both stay available in H: a separate deforming object (gums, tongue, clothing) gets weights and
  shows the pose through §4.6.

### 3.4 Recommendation

**H.** Rigid parts link to a bone; deforming parts are weighted; every object shows the pose. Manu's inclination (teeth by
weights, E1 "Gewichte") is not foreclosed: with §4.6 built, a weighted tooth evaluates and draws correctly; it then keeps
the placement lock and the copy refusals of AD-028 / AD-025 §4.4, which the AD states rather than changes.

## 4. The bone link

### 4.1 Data (names `PROVISIONAL`)

- `SceneObject.bone: BoneId | None` — the bone the object follows; `None` = it follows nothing (today's behaviour).
- **Document data:** set and cleared by object commands (one Undo step each), saved with the scene (§9). Not view state:
  "this tooth belongs to the jaw" is a fact about the character, like a weight.
- **Dead link:** an id the rig no longer has (a file from elsewhere, a missed rewrite) follows nothing — valid or dead,
  never wrong (AD-021 §4.5, the dead-key rule of AD-028 §3.3).
- **Linked xor bound:** an object is either linked or bound (has stored weights), not both — linking a bound mesh and
  writing weights on a linked mesh are refused (fail-closed; a gums-with-teeth object is one bound mesh).

### 4.2 Evaluation: the drawn placement

- `drawn(obj) = S_b ∘ T` with `T` the object's placement (similarity, AD-021 §4.3) and `S_b` the bone's world skin
  transform (F-1). A similarity times a similarity is a similarity, so `drawn(obj)` is an ordinary `ObjectTransform`
  with the object's own pivot — checked for all six objects of the test scene [C] — and every consumer that takes a
  placement can take it unchanged (AD-021 §4.3 anticipated this: "a later `parent` … never produces shear").
- **At rest `S_b` is absent** (F-1), so `drawn(obj) = T` bit-exactly: **linking does not move the object, and no offset is
  stored.** The rest frame of the bone *is* the bind, as for weights (AD-028 X-13).
- **Rest edit of the bone** (`edit_bone`, F-13): the object stays bit-identical at rest; in a pose it turns about the new
  head. A stored offset (B-off) would instead have to be rewritten on every rest edit or go stale.
- **Moving the object at rest** (E3 "ja"): `T` changes as today; in a pose the object rides the bone from its new place —
  for a tooth exactly what fitting needs. For an eye see §5.1 (its centre must stay on its bone's head).
- **Morph:** a linked object with a morph weight shows its mix in object space, then the drawn placement.

### 4.3 Consumers: document placement versus drawn placement

The document `transform` stays the rest placement; only consumers of what is *seen* switch to `drawn(obj)` while posed
(70 reads of `.transform` in 20 files of `src/mirai` / `src/gui` [C, grep]; the second opinion checks the split):

| Class | Consumers | Reads |
|---|---|---|
| **View** | the entry matrix in `sync_views` / `_drawn_matrix` (F-5) and the twins (§5.5); object picking `camera_for` (F-6); the orbit focus on a picked object; `frame_eye`; `gaze_frame` / `eye_center` / `rest_forward` (§5.2); the bone chain's pivot snap (refused while posed anyway, AD-028 addendum 2026-11-17) | `drawn(obj)` |
| **Document** | object W/E/R, Clear, Apply, mirror follow and mirror copy, duplicate / paste, the morph view shift, save | `transform` (rest) |

The edit object, if linked: its model matrix is `drawn(edit)` while posed; its component tools are refused while posed
(§4.5), so no tool maps through the pose. (Editing a rigid part *in* the pose is exact in principle — one inverse
matrix, unlike skinning — and can be lifted later on request.)

### 4.4 Commands and rules (`PROVISIONAL`: names, texts, panel rows; no new keys — the hotkey map is full, Manu 2026-11-17)

| Command | What | History |
|---|---|---|
| **Link to bone** (Bone panel, mode `4`) | every selected object (group leaves) → the current bone; refused for a bound mesh, a Reference, while posed, and for an eye whose centre is not at the bone's head (§5.1) | one entry (`ObjectLinkCommand`: before / after per object) |
| **Unlink** (Bone panel) | the selected objects → `None`; refused while posed (the object would jump; Undo of a link still runs) | one entry |
| **Delete bone** (exists) | additionally: every object linked to it is re-linked to the bone's parent (the weights rule of AD-028 §3.4), **except eyes**, which are unlinked (an eye's link is its own eye bone, §5.1); a root's objects are unlinked | the existing `CompositeCommand` gains the link changes |
| **Duplicate / Copy + Paste** | the copy keeps the link (same place, same bone) | as today |
| **Mirror copy** (Shift+M) | the copy keeps the link if the bone lies on the symmetry plane (the AD-028 §8.4 seam rule, e.g. `Kiefer`); else the copy is unlinked with a status note ("needs its mirror bone (not yet)") — the second eye is linked by hand | as today |
| **Apply transform** | allowed, also while posed (world unchanged); eyes refused as today | as today |
| **Clear transform** | at rest as today; refused while posed | as today |

### 4.5 Policies (stage 7, AD-027 §3.5)

- **Posed** (AD-028 §7.1's definition: some bone has a non-identity pose): object W/E/R, Clear transform and a mirror
  partner's follow are refused for a linked object (`"<operation>: <name> follows <bone> - the rig is posed (<rest key> =
  rest pose)"`); a linked edit object refuses position and topology commands with the existing posed text. The placement
  policy (`skeleton.py:1504-1528`) gains "or linked and posed"; the posed policy (`:1486-1503`) gains "or linked".
- **At rest:** a linked object behaves as today (E3). Alternative (E3 "gesperrt"): the S6 lock extended to linked objects.
- Selection, hide, delete, Undo / Redo, the weight and morph commands run as today.

### 4.6 Every object shows the pose (F-16 lifted for display)

- **Linked objects:** `sync_views` draws `drawn(obj)` (§4.2). Re-synced on a pose step (today it runs on a gaze change,
  `objects.py:1405-1409`; a narrower "placements only" update if the reference-PC run asks for it).
- **Bound non-edit objects:** `SkinSurfaceProvider.shown` (F-3) returns every drawn bound object while posed, not only the
  edit object and the morph base. The per-object surfaces, the entry surfaces and their drawing exist; the new parts are
  the wider `shown`, object picking on the posed surface of such an object, and tests. The cost per pose step is that
  object's moved points — in the test scene the head, whose cost is the same as when it is the edit object.
- **Why now:** without it a pose shown while a tooth is the edit object would draw the head at rest and the linked parts
  posed (teeth hanging in the air). If §4.6 is deferred, slice 2 refuses instead (fail-closed): switching the edit object
  away from a bound mesh while posed, and entering a pose while the edit object is not the bound mesh.
- **Morph editing view** (AD-025 §15): the base beside its view is posed (H7-E, unchanged); linked originals at the base
  are posed; the view twins beside the view stay at **rest** (§5.5).

## 5. Eyes: bone pose, gaze and the eye pass (Q2)

### 5.1 The eye's link is its eye bone

- An eye links to **its own eye bone**: a bone whose head lies at the eyeball's centre (the eye object's local origin,
  F-18). Checked when linking (tolerance `PROVISIONAL`: 1e-6 of the eye radius — the bone tool's pivot snap places it to
  1e-12, AD-028 addendum 2026-11-17); otherwise refused: "an eye follows its own eye bone (head at the eyeball's centre:
  Bone panel, snap to the eye)". This separates an eye bone from `Hals` without a new field, and keeps two eyes from
  sharing one bone.
- If an eye and its bone drift apart later (the eye moved at rest, or the bone's head edited), the follow stays
  deterministic (`S_b ∘ T`); the Bone panel names the drift (`PROVISIONAL`). A manual eye-bone rotation then swings the
  eye about the bone's head (F-12) — visible, like a misplaced jaw hinge.
- **Neutral pose** = the eye's own rotation, 3.8° outward included: at rest `S_b` is absent (F-1).

### 5.2 Composition (one rule)

With `b` the eye bone, `P = S_parent(b)` (the head-carried transform; identity at rest) and `T` the eye's placement:

| | Eye drawn | Lid frame (`EyeDraw.rest_matrix`) | Eye bone's pose | Lid points |
|---|---|---|---|---|
| **At rest, gaze `rest`** | `T` | `T` | rest | rest |
| **At rest, gaze on** (E2 "ja") | `G ∘ T` (today's `aimed_transform`) | `T` | rest | rest |
| **Posed, gaze `rest`** | `S_b ∘ T` (the manual eye pose) | `P ∘ T` | the user's channel | follow `S_b` by their weights |
| **Posed, gaze on** | `S_b ∘ T` with the eye bone's channel **from the gaze** | `P ∘ T` | gaze-derived (replaces the manual channel while on) | follow the gaze |

- **Lid frame:** the eye's placement carried by the head, never by the eye's own turn — the AD-033 rule "the lid stays
  with the head while the eye looks around", now also when the head turns. Today the rest matrix is passed only while a
  gaze is on (F-7); it is passed whenever the drawn matrix differs from it (posed or gazing). `rest_rotation` needs no
  change.
- **Gaze-derived channel:** `G` is the shortest rotation about the eye's posed centre `P(c)` from the head-carried rest
  forward `P·f` to the target (Listing's law, as today), clamped to 50° **relative to the head-carried forward**, so a
  camera behind a turned head still never turns the eyes into the skull. The bone channel is
  `L_b = B_b⁻¹ ∘ P⁻¹ ∘ G ∘ P ∘ B_b`, so that `S_b = P ∘ (B_b ∘ L_b ∘ B_b⁻¹) = G ∘ P` (F-1's composition) — a pure
  rotation when the bone's head is the eye's centre (§5.1), and without roll about the bone's own axis (Listing) when the
  bone lies on the eye's gaze axis (bone tool 02's align; true in the test scene, F-18) [H, algebra; for the second
  opinion].
- **The user pose stays the user's:** the gaze-derived channels never enter the SkeletonController's `pose` or
  `last_pose`; the skin stage and the link matrices receive the user pose with the eye bones' channels replaced. So
  `posed()`, the rest ↔ pose toggle and the bone gesture are unchanged; switching the gaze back to `rest` brings the
  manual eye pose back.
- **Gaze pad and mouse plane** (`gaze_frame`) use the head-carried eye placements: "straight ahead" turns with the head.

### 5.3 E2 — does the gaze move the lids while modelling?

- **"ja" (recommended): only in a pose.** At rest the gaze turns the eye objects only (today, AD-033 §12); the rig stays
  unposed, so modelling the bound head with the eyes on the camera keeps working (S5 refuses edits only while posed).
  The lids follow the gaze as soon as any pose is shown (e.g. the jaw open, or one eye bone turned).
- **Alternative: always.** The gaze writes the eye bones also at rest; with lid weights, the lid points then move with every
  gaze step, so a gaze other than `rest` must count as posed, and every move / topology edit of the head is refused until
  the eyes look straight ahead. (A narrower "posed" — only bones with keys in this mesh — would delay this until the lids
  are weighted, not avoid it.)
- **Not offered:** gaze never driving the eye bones (the lids would ignore the gaze), against Manu's "lids must follow the
  eye movement".

### 5.4 What stays

Gaze is view state (no Undo, not saved — or saved in `"view"`, §5.6); eyes are rigid and unmorphed; component editing and
Apply transform of an eye stay refused (F-8); the eye pass, its variants and its uniforms are unchanged apart from
receiving `drawn(obj)` and the lid frame.

### 5.5 View twins (AD-033 §14)

Twins beside a morph target's editing view are drawn at **rest** (`T` shifted, gaze as today): the view shows the target at
rest on an unbound copy (AD-028 §5.2), so the twins must fit that head. The originals at the base follow the pose.

### 5.6 Focus and vergence (kept in mind, no build order)

- **Today [V]:** `GazeState.focus` exists (F-9) — view state, not saved; vergence comes from the one shared target point
  (in `camera` mode from the camera distance). There is no per-eye rest divergence kept while aiming (AD-033 §12 "open"):
  aimed, both eyes look exactly at the point and the 3.8° outward stance disappears.
- **Where a saved value would live:** (1) **now, if wanted:** the scene's `"view"` section (F-14) — gaze mode, focus and a
  fixed target, like the morph sliders: no Core change, no format bump, no Undo; (2) **with animation:** a gaze target
  keyed with the pose channels (`Scene.animation`, AD-028 X-6), i.e. document data in the rig's space. The pose itself
  stays unsaved (S4).
- **Per-eye rest divergence while aiming** (if Manu wants the stance kept): a constant per-eye offset between the eye's
  forward and its aim line (real eyes keep a few degrees between the eyeball's axis and the line of sight — general
  knowledge, not verified). It would be a value on the eye or the link; not designed here.

## 6. Lids: not blocked, and what linear blending cannot do (Q3)

**Setup assumed, not designed:** lid points of the head mesh carry weights split between the head bone and the eye bone
(e.g. upper lid 0.3–0.5 on `Auge_*`), within the ≤ 4 keys (head, jaw, eye, a later lid bone). The eye bone turns about the
eyeball's centre (§5.1).

**What linear blend skinning (AD-028 §5.1) gives for a point with eye weight `w`, turned by `θ` about the centre:**

- **Up / down:** the point follows by about `w·θ` (within 0.12° for `w` = 0.3 at `θ` = 30°, exactly for `w` = 0.5 [H, computed]) — the classic upper-lid follow.
  **Usable.**
- **Sideways:** the same rule turns the lid sideways by `w·θ` like a visor; real lids barely follow horizontal gaze (general knowledge, not verified).
  **Wrong.**
- **Sinking:** a blended point moves on the chord, not the arc; its distance from the turn axis (through the centre)
  shrinks by `1 − |(1−w) + w·e^{iθ}|` — for a lid point straight above the centre and an up/down turn, its distance to the
  centre. For `w` = 0.5: 1.5 % at 20°, 3.4 % at 30°, 9.4 % at the gaze clamp of 50° — at 1.1 eye radii 0.20 / 0.45 /
  1.24 mm on a 12 mm eye [H, computed]. A lid that sits closer than that to the eyeball dips into it.
- **No slide:** the lid margin does not ride over the corneal bulge; no blink (a separate shape, morph or lid bone).

**What that implies later (named, not designed):**

| Need | Remedy that fits this design |
|---|---|
| Up/down only, no sideways swing | an **axis-limited driver**: a lid bone per lid, child of the head bone, its rotation driven by the eye bone's pitch (a pose source in view state, like the gaze of §5.2) |
| No sinking | **dual quaternion skinning** as a per-rig option on the same weights (AD-028 X-4): a blend of rotations about one centre stays on the sphere |
| Slide over the bulge, lid shape per gaze | **correctives**: morph targets dialled by the eye angle (pose-space), on the existing morph layers |
| Blink | morph targets or lid bones; independent of the eye bone |

**Why this design does not block them:** the lids are ordinary weighted head points (WEIGHTS layer, journaled, carried
through topology edits by AD-028 §3.5); the eye bone is a real bone; the gaze reaches the lids through the eye bone's
pose (§5.2); a driven lid bone is another view-state pose source of the same kind; the eye pass's lid shading reads a frame
(§5.2) that a later lid-follow fraction can turn part-way, so the shaded lid edge and the geometric lid can be kept
together. **Known gap:** lid weights cannot be written symmetrically today (off-centre bones, F-16): each side is weighted
on its own until bones can be mirrored.

## 7. The head bone and missing bindings (Q4)

- **Rule:** *what has no binding stays at rest in every pose* — a point without weights (its object share, AD-028 §3.3)
  and an object without a link. Upper teeth, eyes (through their eye bones' parent) and everything else on the skull
  follow **the head bone**; lower teeth follow the jaw.
- **The head bone** is the bone that carries the skull's weights and the eye bones. In the test scene that is `Hals`
  (F-18): a turn of `Hals` turns the whole head about the **neck base**, so the jaw hinge and the eyes travel on a long arc.
  A separate head bone (`Kopf`, child of `Hals`, head at the top of the neck; parent of `Kiefer` and the eye bones) gives a
  turn at the skull base — a rigging choice for Manu (E5), possible today with the chain tool and the panel's re-parent;
  the architecture works either way.
- **In the test scene** 406 points were unbound at `939df8b`, 404 of them in the ears (F-18): a head turn would have left
  the ears behind. Since `4aa4ae9` the ears are weighted; 2 points at the neck base stay unbound, as meant. The four teeth
  and the two eyes follow nothing until they are linked.
- **How the artist sees it** (`PROVISIONAL`, the build's UI choice): (a) a weight-view mode **"unbound"** that shades each
  point's object share `1 − Σw` (the same sink and share cache as the weight view, AD-028 addendum 2026-11-03) — the ears
  light up; (b) in the Bone panel, per selected object "follows: `<bone>`" or "follows no bone", and for the current
  bone the objects linked to it; (c) in a pose, everything unbound visibly stays behind.

## 8. Cost and the reference PC (Q5)

### 8.1 Measured in the container [C]

Scratch probe (not kept; re-runnable): load `Gollum_Head_rigging_test`; pose `Hals` 20° about Y, `Kiefer` 15° about X,
both eye bones −10° about X; median / p95 over 2,000 / 400 / 100 repetitions; alternate between two poses so every step
recomputes. Run on the scene at `939df8b` and again at `4aa4ae9` (ears weighted); p50 / p95 ms.

| What | at `939df8b` | at `4aa4ae9` |
|---|---|---|
| Link route: `skin_transforms` + `S_b ∘ T` for the six objects | **0.059 / 0.080** | **0.065 / 0.091** |
| Every composed placement a valid `ObjectTransform` (similarity) | yes, all six | yes, all six |
| Weight 1.0 (LBS via `SkinSurface`) vs the link, worst world difference on the four teeth | **5.6e-17** | **5.6e-17** |
| Weights route, four teeth × 16 points, one step (LBS + position table, no viewport patch) | 0.33 / 0.42 | 0.38 / 0.44 |
| A skinned eye shell (3,330 points), one step (LBS + table; hypothetical — not possible, §3.2) | 0.48 / 0.66 | 0.53 / 1.78 |
| The head under a `Hals` step: moved points; LBS + table | 1,848 of 2,254; 0.59 / 0.87 | **2,276 of 2,278**; 0.90 / 1.21 |
| A lid-sized region: head points within 1.3 / 1.6 / 2.0 eye radii of the eyeballs, in front of their centres (both eyes) | 466 / 598 / 702 | 466 / 598 / 702 |

### 8.2 Structural cost per option

| | Per pose step | Grows with |
|---|---|---|
| Link | one similarity per linked object (0.06–0.07 ms for six [C]) + the entry's matrix uniform; the existing `sync_views` loop (its own per-call cost unmeasured [H]; it already runs per gaze step) | the number of linked objects |
| Weights on a rigid part | LBS ≈ 0.1–1 µs per point [C: §8.1; D: AD-028 §17.2] **+ the viewport patch ≈ 10.7 µs per moved point in the container, ≈ 21–27 µs on the reference PC** [D: AD-028 §5.4] | the part's point count |
| The head turning (any option) | 2,276 moved points (at `4aa4ae9`) ≈ 17–23 ms in the container, ≈ 45–60 ms on the reference PC [H: AD-028 §17.3's GL rows, 928 points 7.0 / 9.8 ms and 1,093 points 11.2 / 17.2 ms, i.e. 7.5–10 µs per point; 21–27 µs per point on the reference PC, §5.4] — "usable, not fluid" | the bound points — AD-028 P-1; its remedy is the GPU drawing path (its own AD), not this one |
| Gaze driving the eye bones in a pose, lids weighted | the lid points per gaze frame (`camera` / `mouse` move every frame): ≈ 470–700 points → ≈ 5–8 ms container, ≈ 10–19 ms reference PC [H]; plus the pick cache invalidated per frame while hovering (R-11) | the lid region; E2 "ja" keeps it to poses |

### 8.3 What Manu's PC would need to measure (not built here)

One probe run on `Gollum_Head_rigging_test`, in the style of `experiments/drag_cost/probe_morph_gl.py --only-skin`
(200 steps through the real GL chain, render excluded, p50 / p95):
(1) a `Hals` turn step with the six parts linked, and without links (the link's share); (2) a `Kiefer` step with the teeth
linked versus weighted (A against B); (3) orbit frames with gaze `camera` in a pose, the eye bones driven, with a
lid-sized region weighted to them and without. No number in this AD claims the reference PC.

## 9. Format, `src/core` and process (Q6)

### 9.1 The Core change (CORE_V1_FREEZE §7)

1. **Requirement:** rigid parts (eyes, teeth) follow bones and the relation is saved with the scene (Manu, 2026-11-17/18).
2. **Public API?** No. A relation saved with the scene must be in the Core's model — `core.serialization` cannot import
   `src/mirai` (the `MirrorPair` / `ObjectMaterial` / `Rig` precedent, AD-028 §9). The routes without a Core change fail:
   weights cannot carry eyes (§3.2); the `"view"` section (F-14) is view state without Undo, but a link is document data;
   a naming convention is fragile.
3. **Documented:** this AD.
4. **Smallest extension:** `core/scene.py` — `SceneObject.bone: BoneId | None` (a slot, a keyword, a type check; `None`
   by default). `core/serialization.py` — `"bone": <int>` written only when set; **version 13** when any object has a
   link (else as today); versions 2–13 read (`bone = None` below 13); fail-closed: a non-int or negative value, or an id
   at or above the rig's `bone_id_counter` (an id that never existed) or a link without a rig makes the file invalid; an
   id below the counter that the rig lacks loads as a dead link (§4.1). **Not touched:** `Rig`, `Bone`, `Mesh`, the
   weights kind, every operation, `HistoryStack`, `MeshDeltaCommand`, every existing signature. A scene without a link is
   byte-identical (same export, same version).
5. **Contract tests:** round trip (order-sensitive on the JSON text), the version-by-content rule, older versions read,
   invalid values refused with the scene unchanged, no-link equivalence.
6. **Then implement** after Manu's go (E4); the §7.1 entry and the revision line in the same commit.

**Stop-point report (handoff):** the recommended option needs exactly one additive `src/core` field and a format bump —
within the handoff's bound, but a Core change that needs Manu's go. Option A needs none (and cannot carry eyes). No option
contradicts a decided AD; the amendments are named in §12.

### 9.2 What an older build does

An older build refuses a v13 file (unknown version) instead of loading it and saving it back without the links (the
AD-028 §3.6 reasoning).

## 10. Acceptance scenario (test specification; not implemented)

`tests/test_rigid_parts_scenario.py` (`PROVISIONAL`), headless, readable named steps in the AD-027 scenario style (as
`test_jaw_scenario.py`), on `scenes/Gollum_Head_rigging_test.mirai.json`. "Exact" = bit-identical; "≤ ε" = 1e-12 in world
units. The scene file carries no links (Manu, 2026-11-18: the teeth are bound later, by him; the build delivers the
capability), so the test links in its own setup: `UPPER` / `LOWER` is a **test fixture**, not an Artist statement
(`tooth`, `tooth01` → `Hals`; `Zahn_1`, `Zahn_2` → `Kiefer`; `PROVISIONAL`). Setup also weights a left upper-lid region (the points of §8.1's 1.3-radius region above the eye's centre that are fully
on `Hals`) 0.5 to `Auge_Links` through the existing set-weight path (the write rule leaves 0.5 on `Hals`).

| # | Step | Expected |
|---|---|---|
| 0 | Load; weight view "unbound" on | exactly the unbound points shaded (at `4aa4ae9`: the 2 points at the neck base); the panel lists the six parts as "follows no bone" |
| 1 | Link: eyes to `Hals` | refused (head not at the eye centre), nothing changed |
| 2 | Link: each eye to its eye bone; `UPPER` to `Hals`; `LOWER` to `Kiefer` | one Undo step per command; at rest every entry's matrix exact as before; the file round trip keeps the links (v13) |
| 3 | **Head turn:** pose mode, `Hals` current, E about world Y 20° | every linked part drawn `S_Hals ∘ T` (≤ ε, the eyes through their identity eye bones); a head point fully on `Hals` and an upper tooth keep their distance (≤ ε); unbound points exactly at rest (the rule); a mode-`4` click on a tooth's drawn place selects it, a click on its rest place does not; the eye pass's lid frame = `S_Hals ∘ T` |
| 4 | **Jaw opening:** `Kiefer` E about its X 20° | `LOWER` drawn `S_Kiefer ∘ T`, distances to the fully-`Kiefer` head points kept (≤ ε); `UPPER` unchanged from step 3 |
| 5 | **Eye turn, lids follow:** `Auge_Links` E about its X −15° (look up) | the eye drawn `S_eye ∘ T`, its centre at `S_Hals(c)` (≤ ε); lid frame unchanged from step 3 (the lid shading does not turn with the eye); lid points = `evaluate` (≤ ε); a lid point with 0.5 on the eye bone and 0.5 on `Hals`: its distance from the turn axis through the eye's centre is scaled by `cos(7.5°)` (≤ ε; pins the LBS behaviour of §6) |
| 6 | **Gaze in a pose (E2 "ja"):** gaze `target` up-left | the eye bones' channels gaze-derived (clamp relative to the head-carried forward); the lid points follow; the user pose and `last_pose` unchanged; gaze `rest` → the manual pose of step 5 back |
| 7 | **Gaze at rest:** rest toggle, gaze `camera`, orbit | the eyes as today (`aimed_transform`), lid points exactly at rest, `posed()` False, a Move on the head runs |
| 8 | Refusals while posed (back in the pose) | object W/E/R and Clear on a linked tooth refused with the rest-key text, nothing changed; Apply transform on a linked tooth runs, drawn world points unchanged (≤ ε), Undo exact |
| 9 | **Undo / Redo** to before step 2 and back | links gone / back exactly; the pose untouched by Undo (view state) |
| 10 | **Topology edit** at rest: a tooth as edit object, Extrude a face; the head, Loop Insert across the upper lid | the tooth's link unchanged, its new points follow (= `S_b ∘ T · p`, ≤ ε) in the pose; the head's new points get the rule's weights (W1–W4) and = `evaluate` in the pose |
| 11 | **Rest edit:** `Kiefer`'s head 1 % of its length forward (at rest) | every part and the head exact at rest; in the pose `LOWER` turn about the new hinge |
| 12 | **Bone delete** `Kiefer`, then `Auge_Links` | `LOWER` re-linked to `Hals`, the jaw weights to `Hals` (existing rule); the left eye unlinked (at rest in a pose); Undo restores both exactly |
| 13 | **Save / load** | links saved (v13), pose not saved (load at rest); re-pose → the same drawn matrices (≤ ε); a file with a dead link loads (the part follows nothing); an id ≥ counter → invalid file, nothing loaded |
| 14 | **Posed picking** (MODELING_ON_DEFORMED_SURFACES §16), jaw open | a weight click inside the mouth hits the posed surface as today; mode `4` picks the drawn teeth (step 3) |
| 15 | **Every object shows the pose (§4.6):** make a tooth the edit object at rest, pose the jaw | the head (bound, non-edit) drawn posed (= `evaluate`), the edit tooth drawn `S_b ∘ T`, its edits refused |
| 16 | **Morph view:** open a target's editing view while posed | the base beside its view posed; linked originals posed; the twins beside the view at rest |
| 17 | **Equivalence:** the same tooth weighted 1.0 instead of linked (`evaluate`) | the same world points as the link (≤ ε) |

**Mutation checks by hand** (each must fail a step): the link composed on the wrong side (`T ∘ S_b`); the identity
short-circuit bypassed (rest not exact); the lid frame taken from the drawn matrix (the lid turns with the eye); the gaze
written into the user pose (the toggle loses the manual pose); picking with the rest placement; a bone delete leaving
dead links instead of re-linking; the gaze clamp against the document forward under a head turn; v13 not written.

## 11. Decisions for Manu

Only what is his — Intent, Product Truth, Priority, Promotion (DEVCHAT-001 C2). German wording in the Kurzfassung.

| # | Question | Recommendation | Why it is his | Answer (Manu, 2026-11-18) |
|---|---|---|---|---|
| **E1** | Teeth: link or weights 1.0? | link | his stated inclination; workflow (duplicate, mirror, nudge) | **ja** — link |
| **E2** | Does the gaze move the lids also while modelling at rest? | only in a pose | product truth: modelling while the eyes follow the camera | **ja** — only in a pose |
| **E3** | Linked parts movable at rest? | yes; refused while posed | a different rule from S6 (bound placement locked), his to accept | **ja** |
| **E4** | Go for the Core field and format v13 | go | CORE_V1_FREEZE §7 step 6 | **go** |
| **E5** | Test scene facts: which teeth are upper / lower; the ears to `Hals`; a separate head bone or not | — | his model and rig | teeth later (only the capability now); ears weighted (§16) |

Technical defaults stated, not asked: no stored offset (§4.2); eye guard and eye unlink on bone delete (§5.1, §4.4);
mirror copy rule (§4.4); linked xor bound (§4.1); the gaze clamp in the head frame (§5.2); twins at rest (§5.5); the
"unbound" view and "follows" rows (§7).

## 12. Amendments the decision would need

| Document | Amendment |
|---|---|
| AD-028 | §5.3 and F-16: every object shows the pose (§4.6); §7.1: a linked edit object is refused like a bound one; §7.2: the placement rule for linked objects (E3); §3.4 / §8.3: bone delete re-links (eyes unlink); §15: "objects parented to bones and rigid parts" and "per-object evaluated display" leave the not-in-scope list; addendum 2026-11-18's "the eye objects do not follow the bones" points here |
| AD-021 | §4.9 "Rigid parts … a future parent (bone or object) drives. Hierarchy is additive (`parent`)" → answered by `SceneObject.bone`; `parent` stays group-only; object → object parenting stays open |
| AD-033 | §4.3 last bullet and §11 "Not built: an eye parented to a head bone" → answered; §12: the gaze rule in a pose, the clamp and pad in the head frame, the lid frame (§5.2); §14: twins at rest under a pose |
| AD-035 | none (the sclera map is unaffected) |
| CORE_V1_FREEZE | §7.1 entry and the revision line (v13) |
| MODELING_ON_DEFORMED_SURFACES | the status row "Other bound objects (teeth) showing the pose" and R-8 |
| `docs/architecture/README.md`, `docs/ATELIER.md`, ROADMAP "Rigging" | the status lines with the implementation |

**Build outline if decided** (not a roadmap; three slices in fresh sessions, each ends green): (1) Core field + v13 +
contract tests; (2) links: drawn placement, consumers (§4.3), commands and policies, gaze → eye bones, the lid frame,
§4.6, the scenario of §10; (3) the "unbound" view and the panel rows, the probe of §8.3.

## 13. Points for the second opinion

1. **No offset** (§4.2): `S_b` rest-relative and absent at rest (F-1), so the link neither moves the object nor goes stale on a
   rest edit — re-check against `skinning.py:121-158` and `edit_bone`.
2. **Equivalence** weight 1.0 = link (§8.1) — re-run the probe.
3. **The consumer split** (§4.3): every *view* consumer of a placement reads `drawn(obj)` while posed; grep the 70
   `.transform` reads.
4. **Gaze as a pose source** (§5.2): never stored in `pose` / `last_pose`; `posed()` unchanged; the `L_b` algebra; the
   clamp in the head frame.
5. **The lid frame** (§5.2): `P ∘ T`, passed whenever it differs from the drawn matrix.
6. **The eye guard** (§5.1) and the eye-unlink on bone delete — or a better classification.
7. **§4.6** — `shown` widened, picking on a non-edit posed surface; or the fail-closed fallback.
8. **Format v13** rules, dead versus invalid links.
9. **Cost claims** ([C] / [H]) and the reference-PC plan (§8.3).
10. **Nothing foreclosed:** teeth by weights later (§3.4); lid bones, DQS, correctives (§6); a rig transform (AD-028 P-8);
    animation keys (§5.6).

## 14. Risks and guards

| Risk | Guard |
|---|---|
| A view consumer keeps reading the rest placement in a pose (a click misses the drawn tooth) | the consumer table (§4.3), scenario steps 3 and 14 |
| The lid shading turns with the eye | the lid frame rule (§5.2), step 5's check, the mutation check |
| A gaze in camera mode silently blocks modelling | E2 "ja" (gaze drives bones only in a pose), step 7 |
| An eye linked to the wrong bone (the head turns with the gaze) | the eye guard (§5.1), step 1 |
| A deleted bone leaves objects following nothing without notice | re-link to the parent (eyes unlink with a status line), step 12 |
| An older build drops links on save | v13 (§9.2) |
| Head turns are slow on the reference PC | stated (§8.2); P-1's GPU path is its remedy; measured by §8.3 |

## 15. Not in scope

Any feature code; the lid system (lid bones, drivers, correctives, blink, lid geometry); a facial rig system; IK,
constraints, aim rigs in general; a weight brush; tongue and gums (not blocked, §3.3, §4.6); bone mirroring and symmetric
weights of off-centre bones; editing a rigid part in the pose (§4.3); object → object parenting; a rig transform;
animation; a saved gaze (§5.6 says where); the per-eye divergence while aiming; key bindings (`config/keymap.json`
untouched); panel layout; AD-028 S1–S8 beyond the amendments of §12.

## 16. Decision record

**Manu, 2026-11-18 (chat):** "E1 ja, E2 ja, E3 ja, E4 go".

| # | Decided | What follows |
|---|---|---|
| E1 | Teeth follow their bone through the link, not through weights | Option A is not built for teeth; weights on a rigid part stay possible later (§3.4), e.g. with gums |
| E2 | The gaze drives the eye bones only in a pose; at rest it turns the eyeballs only | §5.2's table as written; the "always" alternative of §5.3 is not built |
| E3 | Linked parts stay movable at rest; refused while posed | §4.5 as written; the S6 lock is not extended to linked objects |
| E4 | Go for `SceneObject.bone` and scene format v13 (CORE_V1_FREEZE §7 step 6) | given for the shape of §9.1; if the second opinion changes that shape (the field, its home, the version rules), the change comes back to Manu before the Core slice. The CORE_V1_FREEZE §7.1 entry and its revision line are written with the implementing commit (the AD-028 precedent), not now |
| E5 | answered (Manu, 2026-11-18): "die Zähne müssen noch nicht gebunden werden, das mache ich später, ich brauch nur die Möglichkeit zu binden. Ohren haben mittlerweile Gewichte." | the build delivers Link / Unlink; the scene file stays without links; the scenario of §10 links the teeth in its own setup (a test fixture); the ears are on `Hals` since `4aa4ae9`; no separate head bone requested (`Hals` stays the head bone, §7) |

Unchanged by the answers: every technical default listed under §11; the build outline of §12; the second-opinion points
of §13.

## Prüfung der Vorlage für Manu (Deutsch)

Keine Praxistests, sondern eine Prüfung dieser Vorlage:

1. **Verständlich?** Die Kurzfassung oben — ohne Fachjargon.
2. **Optionen:** §3.2 zeigt pro Möglichkeit, was sie für Zähne, Augen und Lider bedeutet und was sie kostet; §3.3 in
   Worten.
3. **Nur deine Fragen:** E1–E5 (Kurzfassung und §11) — alles andere ist als Standard festgelegt und steht in §11 unten.
4. **Das Szenario am Gollum** (§10) in Worten: Szene laden → sehen, was nicht gebunden ist (die Ohren) → Augen an ihre
   Augenknochen, Oberzähne an den Hals, Unterzähne an den Kiefer hängen → Kopf drehen: alles dreht mit, ungebundene Punkte
   bleiben → Kiefer öffnen: nur die Unterzähne gehen mit → linkes Auge nach oben drehen: der Augapfel dreht sich um seine
   Mitte, das Oberlid geht halb mit, der Lidschatten bleibt beim Kopf → Blick auf ein Ziel: Augen und Lider folgen;
   Blick aus: die vorige Augenstellung ist wieder da → in Ruhe mit Blick in die Kamera modellieren: geht → in der Pose
   Zahn verschieben: abgelehnt mit Hinweis auf die Ruhe-Taste → Undo/Redo, Loop am Lid, Kiefer-Gelenk nachrücken,
   Knochen löschen, Speichern/Laden: alles bleibt richtig. Stimmt das mit deiner Vorstellung überein?

**Nächster Schritt:** E1–E5 sind beantwortet (2026-11-18). Dann die Zweitmeinung im Hauptprojekt (§13) und der Bau in
drei Scheiben (§12).
