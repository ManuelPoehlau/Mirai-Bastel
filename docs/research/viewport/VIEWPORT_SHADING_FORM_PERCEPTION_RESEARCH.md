# Viewport Shading & Lighting für Formwahrnehmung — Research

**Zielpfad:** `docs/research/viewport/VIEWPORT_SHADING_FORM_PERCEPTION_RESEARCH.md`
**Status:** Research — keine Implementierung, keine Entscheidung
**Datum:** 2026-09-25
**Modus:** Discovery (M5)
**Repo-Stand:** `main` @ `f26ee10`
**Gilt für:** Production-Viewport (`GLRenderStore`, AD-018) und künftige Viewport-Labs
**Artist-Verdikt 2026-09-25:** Shadow Map für den Viewport **REJECT** — siehe §2.4
**Artist-Zielsetup 2026-09-25:** Key- + Rim-Light, möglichst ressourcensparend — siehe §4.1

Kennzeichnung wie in `MODELING_WORKFLOW_TOPOLOGY_RESEARCH.md`:
**FAKT** (belegt im Repo oder in Quelle), **EINSCHÄTZUNG** (begründet, aber nicht gemessen), **OFFEN**.

---

## 1. Frage

Welche einfachen, günstigen Darstellungstechniken machen beim Modellieren die **Form** besser lesbar — Krümmung, Wellen, Pinching an Polen, Silhouette, Topologie — und das auf sehr alter Hardware?

Dazu gehören ausdrücklich auch Hover-Hervorhebung und X-Ray, **aber nur als Darstellungstechnik**. Die Frage *wann* etwas als gehovert gilt oder *ob man durch X-Ray hindurch selektieren darf*, ist Interaktions-Semantik und gehört ins Three-Role-UX-System (`docs/design/artist_playground/UX_RESEARCH.md`), nicht hierher.

Das Ziel ist nicht Realismus. Das Ziel ist ein Viewport, der wie eine gute Werkstattlampe funktioniert: Er zeigt Fehler in der Oberfläche, bevor man sie mit der Hand fühlen würde.

**Artist-Aussage (Manu, 2026-09-25):** Viewport/Modelling-Licht ist ein *Worklight*, kein Rendering. Techniken, die in Richtung Rendering gehen, gehören nicht in dieses Thema.

**Artist-Aussage (Manu, 2026-09-25):** Als Licht wird **nur ein Key-Light und ein Rim-Light** gebraucht, **möglichst ressourcensparend**.

---

## 2. Was bereits existiert (M1)

### 2.1 Bereits vorhandene Erkenntnisse

- **FAKT** (`MODELING_WORKFLOW_TOPOLOGY_RESEARCH.md` §5.4, Raitt/Minter): Ein kamerafestes Einzellicht („Stirnlampe") verdeckt die Kontur. Empfohlen sind **zwei mitbewegte, diagonal gegeneinander gerichtete Lichter, das untere auf 50 % gedimmt**. Echtzeit-Renderer machen Shading, keine Schatten.
- **FAKT** (dort §4.4 und §7.1): An Polen (Valenz ≠ 4) ist die Grenzfläche nur C¹-stetig. Ein Teil der sichtbaren „Topologiefehler" ist eigentlich ein Normalenfeld-Problem.
- **FAKT** (dort §12, Frage Q6): „Wie viel des wahrgenommenen Topologieproblems ist in Wahrheit Shading/Darstellung?" ist dort als *technisch prüfbar* offen. Dieses Dokument liefert Werkzeuge für genau diese Prüfung.
- **FAKT** (`docs/research/MIRAI_SYSTEMS.md`): Hover-Highlighting ist als historisches Mirai-Merkmal genannt. Wie Mirai selbst beleuchtet hat, ist im Repo **nicht** dokumentiert (**OFFEN**).

### 2.2 Bereits vorhandener Code

| Ort | Was es tut | Status |
|---|---|---|
| Playground (`playground/window.py`, `_FACE_VERT`) | Lambert-Licht **pro Vertex** (Gouraud), Ambient 0.35, Smooth/Flat umschaltbar über ein zusätzliches `flat_normal`-Attribut in expandierten Buffern | Presentation Lab AP-02.5 „done"; ein Artist-Verdikt zum *Lichtsetup* ist nicht dokumentiert |
| Playground Hover | eigene Overlay-Geometrie mit halbtransparenter Gelbfarbe | in Benutzung |
| `playground/shadow_map.py` | Self-Shadowing per Shadow Map (Depth-Pass, PCF) | **UNVERIFIED** laut eigenem Docstring, **nicht** in `window.py` eingebunden. **Für den Viewport verworfen** (Artist-Verdikt, §2.4) |
| Production `src/viewport/gl_render_store.py` | Lambert-Licht **pro Pixel**, Ambient 0.35, ein Licht, Highlight über `highlight_flags` pro Vertex | AD-018, verifiziert |
| `src/mirai/viewport/display.py` | Zustände Shaded / Flat Shaded / Wireframe (+ Overlay) | nur Zustand, keine Darstellung in Production |

### 2.3 Beobachtung (nicht bewertet)

- **FAKT:** In **beiden** Shadern (Playground und Production) steht die Lichtrichtung fest in der Welt. Wer beim Orbiten auf die Rückseite schaut, sieht dort nur das Ambient-Licht: Die Form wird dort flach und grau.
- Das steht im Widerspruch zur Raitt/Minter-Empfehlung (mitbewegte Lichter).
- Eine Entscheidung ist das nicht; es ist nur der Ausgangspunkt für F1 in §8.

### 2.4 Verworfen

- **Shadow Map wird für den Viewport nicht verwendet, weil** sie in Richtung Rendering geht und nicht zum Viewport-/Modelling-Worklight gehört (Artist-Verdikt Manu, 2026-09-25: REJECT).
- Das betrifft nur den Viewport. Für ein späteres Rendering-Thema ist damit nichts entschieden.
- `playground/shadow_map.py` bleibt unverändert im Playground liegen (AD-010 Addendum); es ist als Viewport-Ansatz erledigt, nicht als Code gelöscht.

---

## 3. Bewertungskriterien

1. **Formlesbarkeit** — nach Raitt/Minter: Silhouette (2D-Umriss), Kontur (wie Licht über die Form läuft). „Bewegung" ist hier nicht relevant.
2. **GPU-Kosten** — siehe Kostenklassen unten.
3. **CPU-Kosten im Python-Pfad.** **EINSCHÄTZUNG:** Auf Manus altem PC ist der Engpass sehr wahrscheinlich die Python-Seite (Buffer vorbereiten, Daten umrechnen), nicht die GPU. Tricks, die ganz im Shader leben, sind deshalb fast immer günstiger als Tricks, die Python-Vorberechnung brauchen.
4. **V02-Verträglichkeit** — erfüllt die Technik die Invarianten „Kamera ändert keine Geometrie" und „Selection/Hover ändert nicht das Basis-Mesh"? Im besten Fall entsteht bei Kamera oder Hover **null** Buffer-Upload.
5. **Buffer-Layout-Bedarf** — braucht die Technik neue Daten (Kanten, expandierte Dreiecke, Krümmung)? Das berührt die offenen Fragen Q2–Q4 aus dem State Review.
6. **Artist-Steuerbarkeit** — gibt es einen sinnvollen Regler (Stärke, an/aus)?

**Kostenklassen (EINSCHÄTZUNG, nicht gemessen):**

| Klasse | Bedeutung | Analogie |
|---|---|---|
| **K0** | nur zusätzliche Shader-Mathematik | ein Regler mehr am Material |
| **K1** | zusätzliche Uniforms oder ein Textur-Lookup | eine zusätzliche Textur im Material |
| **K2** | zusätzliche Buffer-Daten oder CPU-Vorberechnung | eine zusätzliche Map, die man backen und bei Änderung neu backen muss |
| **K3** | zusätzlicher Render-Pass oder Render-Target | ein zweiter Render-Layer im Compositing |

---

## 4. Technikkatalog

### 4.1 A — Grundlicht (wie fällt Licht auf die Form?)

| # | Technik | Kosten | Formwirkung | Anmerkung |
|---|---|---|---|---|
| A1 | **Stirnlampe** (ein Licht, kamerafest) | K0 | schwach — Flächen frontal zur Kamera sind alle gleich hell | laut Raitt/Minter verdeckt es die Kontur |
| A2 | **Zwei mitbewegte Diagonallichter** (Raitt/Minter), unteres gedimmt | K0 | stark — Kontur liest sich aus jedem Winkel | historisch belegte Modeller-Empfehlung |
| A3 | **Hemisphere-Licht** (Himmel-/Bodenfarbe nach Normalenrichtung) | K0 | mittel — gibt Oben/Unten, keine harten Schatten | sehr weich, kein schwarzer Bereich |
| A4 | **Wrap / Half-Lambert** (Licht „wickelt" über die Schattengrenze) | K0 | mittel — keine tote schwarze Rückseite | ersetzt den harten Ambient-Sockel 0.35 durch einen weichen Verlauf |
| A5 | **MatCap** (Kugelbild: Farbe wird nach Normale relativ zur Kamera nachgeschlagen) | K1 | sehr stark bei sehr wenig Aufwand | per Definition kameraabhängig; „backt" einen Look ein. Eigene MatCap-Bilder nötig, keine fremden kopieren |
| A6 | **Studio-Setup** (mehrere Lichter, z. B. Key vorne + Rim hinten, folgen der Kamera) | K0 | stark | Blender-Workbench-Standard; dort umschaltbar auf weltfest |
| A7 | **Glanzlicht** (Blinn-Phong-Spekular) | K0 | stark für Wellen und Beulen — das Glanzlicht „läuft" über die Krümmung | wirkt wie A2 plus Politur; macht Unruhe in der Oberfläche sichtbar |
| ~~A8~~ | ~~**Schatten** (Shadow Map, wie `playground/shadow_map.py`)~~ | K3 | — | **REJECT für Viewport** (Artist-Verdikt 2026-09-25, §2.4): gehört zum Rendering, nicht zum Worklight. Deckt sich mit Raitt/Minter (Schatten gehören nicht zum Modelling-Licht) |

**Artist-Zielsetup (Manu, 2026-09-25): Key + Rim, möglichst ressourcensparend.**

Was das technisch heißt (EINSCHÄTZUNG):
- **Key-Light:** ein gerichtetes Licht (wie A1, aber nicht zwingend frontal). Eine Lichtrichtung als Uniform, ein Skalarprodukt im Shader. K0.
- **Rim-Light:** zwei günstige Bauweisen, beide K0:
  - **Rim als Fresnel-Term** (B2): hellt Flächen auf, die zur Silhouette hin kippen. Braucht keine eigene Lichtrichtung, nur die Blickrichtung. Die billigste Variante.
  - **Rim als echtes Gegenlicht** (zweites gerichtetes Licht von hinten, wie beim Studio-Setup A6). Eine zweite Lichtrichtung als Uniform.
- Beides läuft im **selben** Shader-Durchgang wie heute: kein zusätzlicher Pass, kein zusätzlicher Buffer, keine Python-Arbeit pro Frame außer Uniforms setzen.
- Die übrigen Grundlicht-Varianten (A2–A7) bleiben als Referenz im Katalog. Sie sind nicht verworfen, aber nicht Zielsetup.
- Beobachtung (nicht bewertet): Raitt/Minter empfehlen zwei *diagonale* Lichter (A2), nicht Key + Rim. Das ist eine andere Aufteilung, kein Widerspruch zum Worklight-Gedanken.

**EINSCHÄTZUNG:**
- A2, A4, A6 und A7 lassen sich frei kombinieren. Das ist alles nur Shader-Mathematik.
- Der Unterschied zwischen „Licht folgt Kamera" und „Licht steht in der Welt" ist technisch ein einziger Schalter.
- Er fällt genau in den bestehenden V02-Kamera-Pfad: Lichtrichtung als Uniform, das geht ohne Geometrie-Upload.

### 4.2 B — Formprüfung (wo ist die Oberfläche unruhig?)

| # | Technik | Kosten | Formwirkung | Anmerkung |
|---|---|---|---|---|
| B1 | **Flat Shading im Shader** (Flächennormale aus Bildschirm-Ableitungen `dFdx`/`dFdy`) | K0 | zeigt jede einzelne Facette | **FAKT:** OpenGL 3.3 unterstützt diese Ableitungen im Fragment-Shader. Braucht **keine** expandierten Buffer und kein zweites Normalen-Attribut. Bezug zu Q2, siehe §5 |
| B2 | **Rim / Fresnel** (Kanten zur Silhouette hin aufhellen) | K0 | stärkt die Silhouette | sehr günstig, lässt die Form vom Hintergrund abheben |
| B3 | **Kavität im Bildraum** (Änderung der Normale über Pixel) | K0 | Grate und Täler betont | Blender beschreibt die Screen-Variante als schnell, aber ohne Rücksicht auf die Größe der Grate und Täler |
| B4 | **Kavität aus Mesh-Krümmung** (pro Vertex vorberechnet) | K2 | präziser | müsste in `DerivedGeometry` wie die Normalen **inkrementell** nachgeführt werden; Python-Kosten bei jeder Verschiebung |
| B5 | **Umgebungsverdeckung** (SSAO) | K3 | Tiefe in Spalten | teuer (Extra-Pass, Render-Target); auf altem PC fraglich |
| B6 | **Zebra-Streifen / Reflexionslinien** | K0 | **sehr stark** für Stetigkeit: Knicke und Wellen brechen die Streifen sichtbar | Standard im CAD für Flächenqualität. **Direkter Bezug** zu den C¹-Polen aus der Modeling-Research: Pinching wird als Streifenknick sichtbar. Beantwortet Q6 dort technisch |
| B7 | **Rückseiten-Farbe** (`gl_FrontFacing`) | K0 | zeigt geflippte Normalen, Löcher, Innenseiten | fast gratis, rein diagnostisch |
| B8 | **Normalen als Linien** | K2 | diagnostisch | braucht eigene Liniengeometrie; eher Debug als Artist-Werkzeug |

### 4.3 C — Topologie sichtbar machen

| # | Technik | Kosten | Wirkung | Anmerkung |
|---|---|---|---|---|
| C1 | **Wireframe über Polygon-Modus „Linie"** | K0 (Extra-Draw) | zeigt Dreiecke | **FAKT:** Zeigt die internen Diagonalen der Quads mit. Für Quad-Modelling daher **falsch**: Es zeigt eine Topologie, die der Artist nie gebaut hat |
| C2 | **Kanten-Index-Buffer aus echten Mesh-Kanten** (Linien, leicht nach vorne versetzt) | K2 | korrekte Quad-Kanten | braucht Kantendaten, die RenderMesh heute nicht hat; kann aber den **bestehenden** Positions-Buffer mitbenutzen. Bezug zu Q3 |
| C3 | **Wireframe im Shader** (baryzentrische Koordinaten + Kantenmaske) | K2 | sehr sauber, weich | braucht expandierte Dreiecke plus die Info, welche Dreieckskante eine Quad-Diagonale ist |
| C4 | **Vertex-Punkte** über denselben Positions-Buffer | K1 | Vertices sichtbar | keine eigenen Positionsdaten nötig |
| C5 | **Pol-Markierung** (Vertices mit Valenz ≠ 4 einfärben) | K2 | Pole auf einen Blick | ein Flag pro Vertex, ändert sich nur bei Topologie-Änderung; Bezug zur Topologie-Research |

### 4.4 D — Hover und Hervorhebung (nur Darstellung)

| # | Technik | Kosten | Wirkung | Anmerkung |
|---|---|---|---|---|
| D1 | **Flag-Buffer pro Vertex** (Production heute: `highlight_flags`) | K2 | Vertex-Highlight gut; Face-Highlight „blutet" auf Nachbarflächen | für Hover schlecht: jede Mausbewegung wäre ein Buffer-Upload |
| D2 | **Hover per Uniform-ID** (`u_hover_face`, Abgleich über Primitiv-ID → Face) | K1 | exakte Face-Hervorhebung | **Hover kostet null Buffer-Uploads**, nur einen Uniform-Wert. **FAKT:** `gl_PrimitiveID` gibt es im Fragment-Shader ab OpenGL 3.2 core. Die Zuordnung Dreieck → Face ändert sich nur bei Topologie-Änderung, genau wie heute die Indizes. Passt ideal zur V02-Invariante |
| D3 | **Eigene Overlay-Geometrie** (Playground heute) | K2 | flexibel | zusätzliche Buffer, die bei Hover-Wechsel neu gebaut werden |
| D4 | **Umriss per Stencil** (zweiter Pass) | K3 | klarer Rand um das Objekt/Element | eher für Objekt-Auswahl als für einzelne Komponenten |
| D5 | **Umriss per „inverted hull"** (leicht aufgeblasene Rückseiten) | K3 | Comic-artiger Umriss | Artefakte an scharfen Kanten |

**EINSCHÄTZUNG:**
- Hover und Selection sind darstellerisch *dieselbe Mechanik mit anderen Farben*.
- D2 könnte deshalb später beide abdecken. Das wäre auch eine mögliche Antwort auf Q4 (Overlay-Darstellung).
- Kanten-Hover braucht zusätzlich C2.

### 4.5 E — X-Ray (nur Darstellung)

| # | Technik | Kosten | Wirkung | Anmerkung |
|---|---|---|---|---|
| E1 | **Faces halbtransparent**, ohne Tiefen-Schreiben | K1 | man sieht durch das Mesh | leichte Sortier-Artefakte; bei einem einzelnen Mesh meist tolerierbar. Blender bietet X-Ray als Transparenz-Regler |
| E2 | **E1 plus Kanten/Vertices ohne Tiefentest obendrauf** | K1–K2 | verdeckte Vertices sichtbar | braucht C2/C4 |
| E3 | **Verdeckte Kanten gedimmt** (Kanten zweimal zeichnen: sichtbar normal, verdeckt schwach) | K2 | „Hidden Line" wie auf technischen Zeichnungen | Mesh bleibt undurchsichtig und lesbar, die Rückseitentopologie ist trotzdem erkennbar |
| E4 | **Echte Transparenz-Sortierung** (Depth Peeling, OIT) | K3 | korrekt | Overkill für ein Modelling-Werkzeug |

---

## 5. Querbezüge zur Architektur (Beobachtungen, keine Entscheidungen)

- **Q2 (Flat Shading / Buffer-Layout):**
  - B1 zeigt, dass Flat Shading **ohne** Layout-Änderung möglich ist, also ohne expandierte Buffer und ohne zweites Normalen-Attribut.
  - Das würde eine der offenen Architekturfragen möglicherweise sehr klein machen.
  - **OFFEN**, bis es gemessen und von Manu angeschaut ist.
- **Q3 (Kanten/Punkte):**
  - C1 ist für Quad-Modelling ungeeignet. Ein Wireframe braucht also echte Kantendaten (C2 oder C3).
  - C4 und E2 profitieren davon, dass der Positions-Buffer mitbenutzt werden kann.
- **Q4 (Overlay-Darstellung):** D2 würde Hover *und* Selection über Uniforms plus eine Dreieck→Face-Zuordnung lösen, ohne Upload pro Mausbewegung.
- **Q5 (Normalen unter Symmetrie):** B6 (Zebra) würde asymmetrische Normalen sofort sichtbar machen. Das Symmetry Lab hat dieses Problem bereits gefunden.
- **AD-018-Vertrag:**
  - Licht, Hover-ID, X-Ray-Stärke und Modus-Schalter sind alles **Uniforms**.
  - Der Vertrag kennt Uniforms bereits (`declare_uniform`).
  - Lichtrichtung „folgt Kamera" wäre Teil des Kamera-Dirty-Pfads, ohne Geometrie-Upload.
- **`DerivedGeometry`:** B4 und C5 wären inkrementelle Erweiterungen im selben Muster wie die Normalen. Das ist die einzige Stelle, an der Python-Kosten entstehen.
- **Subdivision Shading** (Normalen mitunterteilen, Modeling-Research §4.4) ist bewusst nicht Teil dieses Dokuments. Es gehört zur späteren Subdivision.

---

## 6. Low-End-Hardware — Einschätzung

**EINSCHÄTZUNG, nicht gemessen:**
- K0- und K1-Techniken kosten bei Meshes im Bereich des Referenzkopfes (326 Vertices) auf der GPU praktisch nichts.
- Relevant werden auf altem PC: K3-Pässe (Füllrate bei voller Fenstergröße) und alles, was Python pro Event rechnet (K2 bei häufiger Änderung, D1/D3 bei Hover).
- Die Reihenfolge der Vorsicht ist deshalb: Python-Arbeit pro Event > Extra-Pässe > Shader-Mathematik.
- Offen und nur durch Messung zu klären (**OFFEN**):
  - ob Manus GPU/Treiber `gl_PrimitiveID` und Fragment-Ableitungen zuverlässig liefert;
  - wie viel ein zweiter Pass dort tatsächlich kostet.

---

## 7. Kandidaten für ein späteres Lab (Empfehlung, keine Entscheidung)

Falls aus dieser Research ein Lab wird, bietet sich ein kleines, isoliertes Viewport-Lab unter `experiments/` an:
- auf Basis des Production-`GLRenderStore`-Shaders als Fork;
- nicht im Playground (AD-010 Addendum);
- jede Variante mit der aktuellen Beleuchtung als Vergleichsbasis.

1. **Grundlicht = Key + Rim** (Zielsetup, §4.1):
   - Rim als Fresnel-Term gegen Rim als echtes Gegenlicht.
   - Key mit Schalter „folgt Kamera / weltfest".
   - Vergleichsbasis: die heutige Beleuchtung.
2. **Formprüfung:** B1, B2, B6, B7, B3 (Bildraum).
3. **Topologie, Hover, X-Ray:** C2, C4, D2, E1/E3.

Alles andere (B4, B5, D4/D5, E4) erst, wenn die günstigen Varianten nicht reichen. A8 entfällt (§2.4).

---

## 8. Vorbereitete Artist-Fragen (erst im Lab zu beantworten, nicht jetzt)

Jede Frage wird später in einer spielbaren Testsituation gestellt. Antwort: **KEEP / ITERATE / REJECT / UNKNOWN**.

| # | Frage | Technik |
|---|---|---|
| F1 | Soll das Key-Light mit der Kamera mitgehen oder fest in der Welt stehen? | Key, Schalter |
| F7 | Rim als Fresnel (Silhouetten-Aufhellung) oder als echtes Gegenlicht? | Rim, zwei Varianten |
| ~~F2~~ | ~~MatCap-Look~~ — zurückgestellt, nicht Teil des Zielsetups Key + Rim | A5 |
| ~~F3~~ | ~~Glanzlicht~~ — zurückgestellt, nicht Teil des Zielsetups Key + Rim | A7 |
| F4 | Sind Zebra-Streifen ein nützlicher Prüfmodus (z. B. für Pole)? | B6 |
| F5 | X-Ray: lieber durchsichtige Faces oder nur gedimmte verdeckte Kanten? | E1 vs. E3 |
| F6 | Wie deutlich soll Hover sein — Farbe, Umriss, beides? | D2 (Darstellung), Semantik bleibt im UX-System |

---

## 9. Abgrenzung

- **Nicht hier:** Hover-*Semantik*, X-Ray-*Selektionsverhalten*, Tastenbelegung für Display-Modi. Das gehört ins Three-Role-UX-System.
- **Nicht hier:** Material-/Render-Vorschau, Texturen, Szenenlicht für Präsentation.
- **Nicht hier:** Subdivision Shading (siehe §5).
- **Nicht hier:** Schatten und alles, was Richtung Rendering geht (Artist-Verdikt, §2.4).

---

## 10. Offene Punkte

- **OFFEN:** Historisches Mirai-Viewport-Licht — im Archäologie-Material nicht gefunden.
- **OFFEN:** Hardware-Fähigkeiten auf Manus PC (`gl_PrimitiveID`, `dFdx`, Kosten eines zweiten Passes).
- **OFFEN:** Eigene MatCap-Bilder erzeugen (keine fremden übernehmen).
- **OFFEN:** Ob ein Viewport-Lab jetzt Priorität hat — Manus Entscheidung.
- **OFFEN:** Wie hell die vom Key-Light abgewandte Seite bleibt (heute fester Ambient-Sockel 0.35). Das ist ein Detail innerhalb von Key + Rim, keine neue Lichtquelle.
- **OFFEN:** Ob die Worklight-Abgrenzung auch Umgebungsverdeckung (B5, SSAO) oder echte Transparenz-Sortierung (E4) betrifft. Das Verdikt wurde nur für die Shadow Map ausgesprochen; die Ausweitung ist **nicht** abgeleitet.

---

## Quellen

- Repo: `docs/research/MODELING_WORKFLOW_TOPOLOGY_RESEARCH.md` (§4.4, §5.3, §5.4, §7.1, §12), `docs/research/MIRAI_SYSTEMS.md`, `playground/window.py` (`_FACE_VERT`), `playground/shadow_map.py`, `src/viewport/gl_render_store.py`, `src/mirai/viewport/display.py`, `docs/archive/viewport_v02/reviews/VIEWPORT_V02_STATE_REVIEW_CLAUDE_001.md`, `docs/architecture/AD-018-PRODUCTION-DRAW-BINDING.md`
- Blender Manual, Workbench Lighting (Studio-Lichter folgen standardmäßig der Kamera; MatCap): https://docs.blender.org/manual/de/dev/render/workbench/lighting.html
- Blender Manual, Workbench Options (Cavity World/Screen, Ridge/Valley): https://docs.blender.org/manual/en/latest/render/workbench/options.html
- Blender Manual, Viewport Shading (X-Ray, Backface Culling): https://docs.blender.org/manual/ja/2.93/render/workbench/options.html
