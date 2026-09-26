# Viewport Shading & Lighting für Formwahrnehmung — Research

**Zielpfad:** `docs/research/viewport/VIEWPORT_SHADING_FORM_PERCEPTION_RESEARCH.md`
**Status:** Research — keine Implementierung, keine Entscheidung
**Datum:** 2026-09-25, überarbeitet 2026-09-26
**Modus:** Discovery (M5)
**Repo-Stand:** `main` @ `f26ee10` (erste Fassung), `b78919f` (Überarbeitung 2026-09-26)
**Gilt für:** Production-Viewport (`GLRenderStore`, AD-018) und künftige Viewport-Labs
**Artist-Verdikt 2026-09-25:** Shadow Map für den Viewport **REJECT** — siehe §2.4
**Artist-Zielsetup 2026-09-25:** Key- + Rim-Light, möglichst ressourcensparend — **am 2026-09-26 von Manu revidiert**, siehe nächste Zeile
**Artist-Zielsetup 2026-09-26:** zunächst **zwei echte Lichter (Key + Fill)**; ob Rim als drittes echtes Licht oder als Shader-Term dazukommt, wird später entschieden — siehe §4.1
**Artist-Aussage 2026-09-26:** MatCap ist raus — siehe §2.4. Blenders Studio-Lösung (gebackenes Licht, A9) ist ein Kandidat für einen späteren Vergleichstest
**Artist-Aussage 2026-09-26:** Hintergrundfarbe soll einstellbar sein, mit Presets für Kontrast und hell/dunkel — siehe §4.1b
**Artist-Entscheidung 2026-09-26 (Priorität):** Die offenen Fragen sind nur noch durch Testen beantwortbar — **das Lab wird gebaut, beginnend mit Slice 1** (§7)

Kennzeichnung wie in `MODELING_WORKFLOW_TOPOLOGY_RESEARCH.md`:
**FAKT** (belegt im Repo oder in Quelle), **EINSCHÄTZUNG** (begründet, aber nicht gemessen), **OFFEN**.

---

## 1. Frage

Welche einfachen, günstigen Darstellungstechniken machen beim Modellieren die **Form** besser lesbar — Krümmung, Wellen, Pinching an Polen, Silhouette, Topologie — und das auf sehr alter Hardware?

Dazu gehören ausdrücklich auch Hover-Hervorhebung und X-Ray, **aber nur als Darstellungstechnik**. Die Frage *wann* etwas als gehovert gilt oder *ob man durch X-Ray hindurch selektieren darf*, ist Interaktions-Semantik und gehört ins Three-Role-UX-System (`docs/design/artist_playground/UX_RESEARCH.md`), nicht hierher.

Das Ziel ist nicht Realismus. Das Ziel ist ein Viewport, der wie eine gute Werkstattlampe funktioniert: Er zeigt Fehler in der Oberfläche, bevor man sie mit der Hand fühlen würde.

**Artist-Aussage (Manu, 2026-09-25):** Viewport/Modelling-Licht ist ein *Worklight*, kein Rendering. Techniken, die in Richtung Rendering gehen, gehören nicht in dieses Thema.

**Artist-Aussage (Manu, 2026-09-25):** Als Licht wird **nur ein Key-Light und ein Rim-Light** gebraucht, **möglichst ressourcensparend**.

**Artist-Aussage (Manu, 2026-09-26), revidiert die vorige:** Key + Rim war eine erste Idee; ein 3-Punkt-Setup ist wohl besser. **Zunächst zwei echte Lichter.** Ob Rim als drittes echtes Licht oder über den Shader dazukommt, wird später überlegt. Gesucht ist ein Setup, bei dem sich Richtung, Farbe/Temperatur, Stärke und Größe/Weichheit anpassen lassen — ohne dass es für eine reine Viewport-Darstellung zu teuer wird.

**Artist-Aussage (Manu, 2026-09-26):** Auch die **Hintergrundfarbe** soll einstellbar sein. Gesucht sind optimale Verhältnisse, also der Kontrast zwischen Hintergrund und Mesh — eventuell als Presets (High Key / Low Key, niedriger / mittlerer / hoher Kontrast). Abzuwägen: optimaler Kontrast für die Formwahrnehmung gegen Augenschonung bei langen Sitzungen. Denkbar ist ein Wechsel je nach Tageszeit, ähnlich wie Light- und Dark-Themes. Vorschlag Manu: als eigener Slice.

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
| Production `src/viewport/gl_render_store.py` | Lambert-Licht **pro Pixel**, ein Licht, Highlight über `highlight_flags` pro Vertex. **FAKT:** Formel `mix(u_base_color * 0.35, u_base_color, ndl)` — der „Ambient" 0.35 ist ein Bodenwert *desselben* Lichts, kein eigenes Licht. `LIGHT_DIR = (0.4, 0.6, 0.7)` ist eine **Python-Konstante**, die bei jedem `draw()` gesetzt wird — kein über `declare_uniform()` geführter, veränderbarer Wert | AD-018, verifiziert |
| `src/mirai/viewport/display.py` | Zustände Shaded / Flat Shaded / Wireframe (+ Overlay) | nur Zustand, keine Darstellung in Production |
| Hintergrund (ergänzt 2026-09-26) | **FAKT:** fest verdrahtete, fast schwarze, leicht bläuliche Clear-Farbe — Playground `window.py` `glClearColor(0.08, 0.08, 0.12)`, Production `src/main.py` `glClearColor(0.05, 0.05, 0.08)`. Mesh-Grundfarbe Production `DEFAULT_BASE_COLOR = (0.72, 0.75, 0.82)`, Highlight-Gelb `(1.0, 0.82, 0.15)`. Kein Regler, kein Verlauf | ein Artist-Verdikt zum Hintergrund ist nicht dokumentiert. Der heutige Zustand ist faktisch ein „Low Key / Dark Mode" |

### 2.3 Beobachtung (nicht bewertet)

- **FAKT:** In **beiden** Shadern (Playground und Production) steht die Lichtrichtung fest in der Welt. Wer beim Orbiten auf die Rückseite schaut, sieht dort nur das Ambient-Licht: Die Form wird dort flach und grau.
- Das steht im Widerspruch zur Raitt/Minter-Empfehlung (mitbewegte Lichter).
- Eine Entscheidung ist das nicht; es ist nur der Ausgangspunkt für F1 in §8.

**Begriffe (ergänzt 2026-09-26), weil sie im Gespräch verwechselbar waren:**
- **Ambient:** eine **richtungslose** Aufhellung. Jede Fläche bekommt denselben Zuschlag, egal wie sie steht. Die Form wird dort flach.
- **Fill:** ein **zweites echtes, gerichtetes** Licht, meist gedimmt und von der Gegenseite. Es hat ein eigenes `N·L` und schattiert die dunkle Seite selbst noch weich — sie wird heller, *ohne* flach zu werden.
- **Rim / Back:** Licht von hinten, das die Silhouette aufhellt. Als echtes Gegenlicht ist es das dritte Licht des klassischen 3-Punkt-Setups (Key + Fill + Back). Als Fresnel-Term (B2) ist es gar kein Licht, sondern eine Funktion des Blickwinkels.
- **EINSCHÄTZUNG:** Das zweite, „untere, auf 50 % gedimmte" Licht bei Raitt/Minter (§2.1) ist funktional ein **Fill**, kein Ambient. Der Artikel selbst benutzt die Wörter „Fill" und „Ambient" an dieser Stelle nicht; die Einordnung ist unsere.
- **FAKT:** Der heutige Code (Playground und Production) hat keins von beidem sauber: Er hat ein Licht mit angehobenem Bodenwert (siehe §2.2).

### 2.4 Verworfen

- **Shadow Map wird für den Viewport nicht verwendet, weil** sie in Richtung Rendering geht und nicht zum Viewport-/Modelling-Worklight gehört (Artist-Verdikt Manu, 2026-09-25: REJECT).
- Das betrifft nur den Viewport. Für ein späteres Rendering-Thema ist damit nichts entschieden.
- `playground/shadow_map.py` bleibt unverändert im Playground liegen (AD-010 Addendum); es ist als Viewport-Ansatz erledigt, nicht als Code gelöscht.

- **MatCap (A5) wird für das Worklight-Setup nicht verwendet** (Artist-Aussage Manu, 2026-09-26: „MatCap ist raus"). Zugrunde liegende Abwägung:
  - MatCap schlägt Farbe auf der Normale **im Blickraum** nach. Es ist damit zwingend kameragebunden und kann nie weltfest sein — es kann F1 also gar nicht beantworten.
  - Es ist ein gebackener *Materiallook*, keine Aussage über das Verhalten eines Arbeitslichts, und braucht eigene gemalte Bilder.
  - Ob das dauerhaft gilt oder nur für dieses Thema, ist nicht gesagt worden (**OFFEN**, nicht abgeleitet).

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
| ~~A5~~ | ~~**MatCap** (Kugelbild: Farbe wird nach Normale relativ zur Kamera nachgeschlagen)~~ | K1 | sehr stark bei sehr wenig Aufwand | **raus** (Artist-Aussage 2026-09-26, §2.4). Per Definition kameraabhängig, kann nicht weltfest sein |
| A6 | **Studio-Setup als echte Einzellichter** (z. B. Key + Fill + Rim, je eine Richtung, folgen der Kamera oder stehen in der Welt) | K0 | stark | Das klassische Film/Foto-3-Punkt-Setup. **Korrektur 2026-09-26:** Blenders „Studio" ist technisch *nicht* so gebaut, siehe A9 |
| A9 | **Gebackenes Studio-Licht** (Blender-Workbench „Studio": Lichtsetup als Spherical-Harmonics-Koeffizienten, eine Formel im Shader) | K1 | stark, sehr weich | **FAKT** (Blender-Quellcode-Historie, Commit `7bb5125`, 2018): Blender wertet das Studio-Licht über wenige Spherical-Harmonics-Koeffizienten aus, nicht als getrennte Einzellichter. Anders als MatCap kann es weltfest sein (Blender-Schalter „World Space Lighting"). **EINSCHÄTZUNG:** Lohnt sich bei komplexen Umgebungen; für 2–3 feste Richtungen kein Vorteil gegenüber A6, braucht aber ein Werkzeug zum Erzeugen der Koeffizienten. **Kandidat für einen späteren Vergleichstest** (Artist-Aussage 2026-09-26) |
| A7 | **Glanzlicht** (Blinn-Phong-Spekular) | K0 | stark für Wellen und Beulen — das Glanzlicht „läuft" über die Krümmung | wirkt wie A2 plus Politur; macht Unruhe in der Oberfläche sichtbar |
| ~~A8~~ | ~~**Schatten** (Shadow Map, wie `playground/shadow_map.py`)~~ | K3 | — | **REJECT für Viewport** (Artist-Verdikt 2026-09-25, §2.4): gehört zum Rendering, nicht zum Worklight. Deckt sich mit Raitt/Minter (Schatten gehören nicht zum Modelling-Licht) |

**Artist-Zielsetup (Manu, 2026-09-25): Key + Rim, möglichst ressourcensparend.** — *am 2026-09-26 revidiert, der folgende Absatz bleibt als Verlauf stehen.*

Was das technisch heißt (EINSCHÄTZUNG):
- **Key-Light:** ein gerichtetes Licht (wie A1, aber nicht zwingend frontal). Eine Lichtrichtung als Uniform, ein Skalarprodukt im Shader. K0.
- **Rim-Light:** zwei günstige Bauweisen, beide K0:
  - **Rim als Fresnel-Term** (B2): hellt Flächen auf, die zur Silhouette hin kippen. Braucht keine eigene Lichtrichtung, nur die Blickrichtung. Die billigste Variante.
  - **Rim als echtes Gegenlicht** (zweites gerichtetes Licht von hinten, wie beim Studio-Setup A6). Eine zweite Lichtrichtung als Uniform.
- Beides läuft im **selben** Shader-Durchgang wie heute: kein zusätzlicher Pass, kein zusätzlicher Buffer, keine Python-Arbeit pro Frame außer Uniforms setzen.
- Die übrigen Grundlicht-Varianten (A2–A7) bleiben als Referenz im Katalog. Sie sind nicht verworfen, aber nicht Zielsetup.
- Beobachtung (nicht bewertet): Raitt/Minter empfehlen zwei *diagonale* Lichter (A2), nicht Key + Rim. Das ist eine andere Aufteilung, kein Widerspruch zum Worklight-Gedanken.

**Artist-Zielsetup (Manu, 2026-09-26): zunächst zwei echte Lichter — Key + Fill.**

- Das entspricht A2 (Raitt/Minter) bzw. den ersten zwei Lichtern von A6.
- Rim ist nicht gestrichen, sondern vertagt: drittes echtes Licht (A6) oder Fresnel-Term (B2) — F7.
- Beide Lichter laufen im selben Shader-Durchgang wie heute: kein zusätzlicher Pass, kein zusätzlicher Buffer.
- Wie das Rig einstellbar wird, beschreibt §4.1a.

**EINSCHÄTZUNG:**
- A2, A4, A6 und A7 lassen sich frei kombinieren. Das ist alles nur Shader-Mathematik.
- Der Unterschied zwischen „Licht folgt Kamera" und „Licht steht in der Welt" ist technisch ein einziger Schalter.
- Er fällt genau in den bestehenden V02-Kamera-Pfad: Lichtrichtung als Uniform, das geht ohne Geometrie-Upload.

### 4.1a Steuerkonzept für das Zwei-Licht-Rig (Vorschlag 2026-09-26, keine Entscheidung)

**Grundidee (EINSCHÄTZUNG):** wenige Regler, die ein Artist aus Foto/Film kennt. Alle landen als Uniforms im Shader. Python rechnet nur dann um, wenn ein Regler bewegt wird — nie pro Frame. Die einzige Ausnahme ist „Licht folgt Kamera"; das läuft im bestehenden Kamera-Dirty-Pfad mit (AD-018), ebenfalls ohne Geometrie-Upload.

*Analogie:* Wie ein Lichtrig im Fotostudio — man stellt Lampe, Softbox und Farbfolie ein. Das Motiv (das Mesh) wird dabei nicht angefasst.

| Regler | Artist-Sicht | Technisch | Kosten |
|---|---|---|---|
| **Richtung Key** | zwei Winkel: *rundherum* (Azimut) und *Höhe* — wie eine Lampe, die man um einen Drehteller führt | Python macht aus den Winkeln einen Vektor → `u_key_dir` | K0 |
| **Bezugsraum** (F1) | „Licht hängt an der Kamera" oder „Licht steht im Raum" | bei „Kamera" dreht Python den Vektor mit der Kamerarotation, im Kamera-Dirty-Pfad | K0 |
| **Richtung Fill** | Standard **gekoppelt**: automatisch diagonal gegenüber und unterhalb vom Key (Raitt/Minter). Kopplung abschaltbar, dann eigene Winkel | aus den Key-Winkeln abgeleitet (Azimut +180°, Höhe gespiegelt) | K0 |
| **Stärke** | Key-Stärke plus **Lichtverhältnis** Key:Fill (Fotografie-Begriff; 2:1 = Fill auf 50 % wie bei Raitt/Minter) | Verhältnis statt zweitem absolutem Regler: die Gesamthelligkeit bleibt stabil, wenn man das Verhältnis ändert | K0 |
| **Farbe / Temperatur** | ein Kelvin-Regler pro Licht (warm ↔ kalt), optional freier Farbton | Python rechnet Kelvin → RGB und multipliziert die Stärke gleich mit ein → ein `vec3` pro Licht. Der Shader sieht nur eine Farbe | K0 |
| **Größe / Weichheit** | „kleine harte Lampe" ↔ „große Softbox" | **Wrap-Lighting:** `(N·L + w) / (1 + w)`. `w = 0` ist die harte Lambert-Grenze wie heute, größeres `w` lässt das Licht weich über die Schattengrenze greifen | K0 — eine Addition, eine Division |
| **Grundhelligkeit** | wie hell eine Stelle bleibt, die keins der beiden Lichter trifft | ersetzt den festen Bodenwert 0.35; mit Fill kann er deutlich niedriger liegen | K0 |

**Warum Weichheit nicht zu teuer ist (EINSCHÄTZUNG):**
- Eine große Lichtquelle macht auf einer matten Fläche zwei Dinge: weiche Schatten *und* einen breiteren, weicheren Übergang an der Schattengrenze.
- Schatten gibt es im Worklight nicht (§2.4). Übrig bleibt nur der weiche Übergang — und genau den bildet Wrap-Lighting nach.
- Echte Flächenlicht-Verfahren braucht es dafür nicht. Weichheit kann also bleiben; man muss sie nicht wegvereinfachen.

**Warum Temperatur mehr ist als Geschmack:**
- **FAKT** (Gooch, Gooch, Shirley, Cohen, SIGGRAPH 1998): Technische Illustratoren zeigen die Flächenausrichtung nicht nur über hell/dunkel, sondern zusätzlich über einen Farbwechsel von warm (zum Licht) nach kalt (vom Licht weg). Das macht Form lesbar, ohne extreme Helligkeitsunterschiede zu brauchen. Die Autoren sagen selbst, dass dieser Farbwechsel die Wahrnehmung der echten Materialfarbe stören kann.
- **EINSCHÄTZUNG:** Ein wärmerer Key und ein kühlerer Fill erzeugen einen ähnlichen Effekt „gratis", allein über die zwei Temperatur-Regler — ohne eigenen Shader-Modus. Für graues Modellier-„Ton" ist die Farbverfälschung egal; bei späteren Materialien nicht. Default deshalb neutral, warm/kalt als Preset zum Ausprobieren (F9).

**Weitere Bausteine (Kandidaten):**
- **Presets:** ein paar benannte Einstellungen, z. B. „Heute" (exakt die jetzige Formel, als Vergleichsbasis), „Raitt 2:1", „Warm/Kalt". Ein Preset ist nur ein Satz Zahlen. So muss Manu nicht selbst tüfteln, um zu vergleichen. Eigene Presets speichern: nicht Teil dieses Vorschlags.
- **Licht ziehen:** Taste halten und im Viewport ziehen → der Key wandert um das Objekt. Das ist die digitale Form von Streiflicht: eine Lampe flach über eine Oberfläche führen, damit Dellen sichtbar werden. **FAKT** (Blender Manual): Blender bietet für weltfeste Studio-Lichter nur eine Drehung um die Z-Achse als Regler. **Abgrenzung:** Welche Taste/Geste das wird, gehört ins Three-Role-UX-System und zur Input-Ownership (AD-013), nicht hierher. Ein Lab nutzt dafür eine vorläufige, lab-lokale Taste.
- **Überbelichtung:** Key + Fill + Grundhelligkeit können zusammen über Weiß hinausgehen; dann verschwindet Form in den hellen Stellen. Einfachste Lösung: Defaults so wählen, dass die Summe ≤ 1 bleibt, sonst begrenzen. Das ist eine Agent-Entscheidung im Lab, keine Artist-Frage.

**Uniform-Budget (EINSCHÄTZUNG):** `u_key_dir`, `u_key_color` (inkl. Stärke), `u_key_wrap`, `u_fill_dir`, `u_fill_color`, `u_fill_wrap`, `u_ambient` — sieben Werte, ein Pass, kein Buffer.

Zur Veranschaulichung, keine Implementierung:

```glsl
float wrap(float ndl, float w) { return max((ndl + w) / (1.0 + w), 0.0); }

vec3 light = u_ambient
           + u_key_color  * wrap(dot(n, u_key_dir),  u_key_wrap)
           + u_fill_color * wrap(dot(n, u_fill_dir), u_fill_wrap);
vec3 shaded = u_base_color * light;
```

**Erweiterbarkeit („Implement little. Assume much."):** Ein späteres Rim als drittes echtes Licht ist dieselbe Zeile ein drittes Mal. Rim als Fresnel ist eine zusätzliche Zeile mit der Blickrichtung. Beides braucht keinen Umbau des Rigs.

### 4.1b Hintergrund und Kontrast (Vorschlag 2026-09-26, keine Entscheidung)

**Kernbeobachtung (EINSCHÄTZUNG):** Ein schattiertes Mesh hat nicht *eine* Helligkeit, sondern eine Spanne — von der dunklen, abgewandten Seite bis zur hellen, beleuchteten. Ein Hintergrund kann nur mit einem Teil dieser Spanne Kontrast haben:
- **Dunkler Hintergrund:** Die beleuchteten Ränder heben sich ab. Die unbeleuchteten Ränder verschwinden im Hintergrund.
- **Heller Hintergrund:** Genau umgekehrt — dunkle Ränder stehen klar, helle Ränder verschwinden.
- **Mittelgrau:** kollidiert mit den Mitteltönen, also meist mit der Zone rund um die Schattengrenze.

„Optimaler Kontrast" ist deshalb keine einzelne Zahl, sondern ein **Verhältnis zwischen Hintergrund und Licht-Rig**. Hintergrund und Licht gehören zusammen eingestellt.

*Analogie:* Im Fotostudio wählt man den Hintergrundkarton passend zur Beleuchtung — dunkler Karton mit Streiflicht, heller Karton mit dunkler Silhouette.

**Verbindung zu Rim (wichtig für die Slice-Reihenfolge):** Rim-Licht und Hintergrundkontrast lösen **dasselbe Problem**: Die Silhouette soll sich vom Hintergrund trennen. Rim hellt die Kante auf, damit sie vor Dunkel steht. Ein passender Hintergrund erreicht das von der anderen Seite. **Wird der Hintergrund zuerst getestet, zeigt sich, ob Rim überhaupt noch gebraucht wird.**

**Zwei Achsen statt einer Liste:**

| Achse | Bedeutung | Bezug zu Manus Begriffen |
|---|---|---|
| **Polarität** | Hintergrund heller oder dunkler als das Mesh | High Key / Low Key, Light / Dark Mode |
| **Kontraststufe** | wie weit Hintergrund und Mesh in der Helligkeit auseinanderliegen | niedrig / mittel / hoch |

Presets wären Kombinationen daraus, z. B. „Dunkel · mittel" (nah am heutigen Zustand, als Vergleichsbasis) oder „Hell · niedrig".

**Kontrast wahrnehmungsgerecht messen (EINSCHÄTZUNG):** Die Kontraststufe sollte über **wahrgenommene Helligkeit** definiert werden, nicht über RGB-Werte — z. B. die Helligkeit L im OKLCH-Farbraum. In RGB wirken gleiche Zahlenabstände je nach Farbe unterschiedlich stark; in OKLCH bedeutet derselbe Abstand in L ungefähr denselben sichtbaren Unterschied. So heißt „mittlerer Kontrast" bei jeder Hintergrundfarbe dasselbe. Die Umrechnung passiert in Python nur beim Umstellen; der Shader sieht weiter nur RGB.

**Günstiger Trick: Verlauf statt Einzelfarbe.**
- **FAKT** (Blender Manual): Blenders Viewport-Hintergrund kann aus dem Theme als Farbverlauf kommen („Gradient Colors").
- **EINSCHÄTZUNG:** Ein senkrechter Verlauf (oben heller, unten dunkler oder umgekehrt) sorgt dafür, dass immer ein Teil der Silhouette vor einem kontrastierenden Ton steht — das entschärft das Spannen-Problem von oben, ohne zusätzliches Licht.
- Kosten: Eine Einzelfarbe ist gratis (`glClearColor`, K0). Ein Verlauf braucht einen zusätzlichen, bildschirmfüllenden Draw mit vier Eckpunkten — kein neuer Mesh-Buffer, kein Render-Target, aber einmal pro Frame das ganze Fenster füllen. Einordnung K1.

**Formwahrnehmung gegen Augenschonung:**
- **FAKT** (Piepenbrock, Mayr, Buchner; Buchner, Mayr, Brandt): In Lese- und Korrekturleseaufgaben schneiden dunkle Inhalte auf hellem Grund besser ab als helle auf dunklem („positive Polarität"). Erklärt wird das über die höhere Bildschirmhelligkeit: Die Pupille wird kleiner, das Netzhautbild schärfer, feine Details sind besser erkennbar.
- **FAKT** (Sensors 2024, und dort zitierte Studien): Bei **wenig Umgebungslicht** wird dunkle Darstellung als Weg diskutiert, Ermüdung zu senken. Die Ergebnisse sind dort ausdrücklich uneinheitlich.
- **EINSCHÄTZUNG:** Beide Befunde stammen aus dem Lesen von Text, nicht aus dem Modellieren. Die Übertragung ist plausibel, aber nicht belegt. Wenn sie gilt, spricht das für Manus Idee: **hell für detailreiche Formprüfung bei Tageslicht, dunkel für lange Sitzungen am Abend** — genau wie Light/Dark-Themes.
- **EINSCHÄTZUNG (gängige Praxis, nicht belegt):** reines Schwarz und reines Weiß meiden; beide Enden sind anstrengender als leicht abgesetzte Töne.

**Was ein Preset mit umschalten muss:**
- Hintergrund (Farbe oder Verlauf).
- Passend dazu Grundhelligkeit und eventuell Stärke des Rigs (§4.1a), weil Kontrast ein Verhältnis ist.
- **Prüfpflicht Highlight:** Das heutige Highlight-Gelb muss auf jedem Preset sichtbar bleiben — auf hellem Hintergrund und hellem Mesh ist Gelb schwach. Ob ein Preset eine eigene Highlight-Farbe braucht, ist eine Darstellungsfrage (hier); *wann* etwas hervorgehoben wird, bleibt beim UX-System.

**Automatischer Wechsel nach Tageszeit oder nach dem Dark Mode des Betriebssystems:** Kandidat für später. Das ist Komfort, keine Formwahrnehmung, und braucht erst Presets, die sich bewährt haben. Nicht Teil eines Slices.

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

**Ergänzung 2026-09-26 zu „Studio + Cavity" (Blender-Standard beim Box-Modelling):**
- Cavity ist **kein Licht**, sondern eine eigene Schicht über dem fertigen Licht-Ergebnis. Sie reagiert darauf, wie sich die Normale zwischen Nachbarn ändert, nicht auf eine Lichtrichtung. Deshalb ist sie in Blender ein eigener Schalter neben „Lighting".
- Blenders Cavity-Einstellung „Both" kombiniert Screen (B3, K0) und World (B4, K2). Wer das 1:1 übernimmt, holt sich den K2-Anteil mit ins Boot — also Python-Arbeit bei jeder Verschiebung. Auf alter Hardware ist das nach §6 die riskanteste Kostenart.
- **EINSCHÄTZUNG:** Screen-Cavity (B3) zuerst, World-Cavity (B4) nur, wenn B3 nicht reicht.

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
  - **FAKT (2026-09-26):** Heute ist die Lichtrichtung dort noch eine Python-Konstante (`LIGHT_DIR`), keine deklarierte Uniform-Ressource. Für ein einstellbares Rig müsste sie zu einer werden — in einem Lab als Fork, nicht in `src/`.
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

Vorbild für die Form des Labs: `experiments/ad018_gl_render_store_verification/` — ein headless `run.py` (Xvfb, Belege + Screenshots) und ein `run_visible.py` (echtes Fenster für Manus PC). Das wird adaptiert, nicht neu erfunden (M1).

*Überarbeitet 2026-09-26 — die frühere Slice-Liste „Key + Rim" ist durch das neue Zielsetup ersetzt.*

1. **Slice 1 — Zwei-Licht-Rig (Key + Fill)** nach §4.1a:
   - Lab-eigener Store unter `experiments/viewport_shading_lab/` als **Unterklasse** von `GLRenderStore` mit eigenem Shader (Korrektur 2026-09-26: Die frühere Formulierung „Kopie, kein Import aus `src/`" war ungenau. Das Vorbild `PlaygroundPygletStore` in AD-010 ist selbst eine Unterklasse des Production-`PygletStore`. Ein Import aus `src/` ist für Experimente erlaubt; verboten ist nur die Gegenrichtung und das Verschieben über die Grenze).
   - Preset „Heute" ist exakt die jetzige Formel — Vergleichsbasis ohne Extra-Aufwand.
   - Schalter „folgt Kamera / weltfest" (F1).
   - Automatische Tests: Ressourcen-IDs bleiben beim Verstellen jedes Reglers gleich (prüft die K0-Einschätzung, statt sie nur zu behaupten); `glGetError() == 0`; Pixel-Unterschied zwischen „Heute" und jeder Variante > 0 (Regler wirkt wirklich).
2. **Slice 2 — Screen-Cavity (B3)** als unabhängig schaltbare Schicht. Getrennt von Slice 1, damit ein Verdikt immer nur eine Veränderung bewertet.
3. **Slice 3 — Hintergrund und Kontrast** nach §4.1b (Vorschlag Manu, 2026-09-26): Einzelfarbe und Verlauf, Presets über Polarität × Kontraststufe, Preset „Heute" als Vergleichsbasis. Automatischer Tageszeit-Wechsel ist nicht Teil davon.
4. **Slice 4 — Rim:** drittes echtes Licht gegen Fresnel-Term (F7). Bewusst *nach* dem Hintergrund, weil Slice 3 zeigen kann, dass Rim gar nicht mehr gebraucht wird (§4.1b).
5. **Später:** Vergleichstest gebackenes Studio-Licht (A9); Formprüfung B1, B6, B7; Topologie, Hover, X-Ray (C2, C4, D2, E1/E3).

Alles andere (B4, B5, D4/D5, E4) erst, wenn die günstigen Varianten nicht reichen. A5 und A8 entfallen (§2.4).

**Priorität (Artist-Entscheidung Manu, 2026-09-26):** Die offenen Fragen F1, F8, F9 sind nicht mehr durch Recherche beantwortbar, nur durch Testen. **Slice 1 wird jetzt gebaut.** Slices 2–4 folgen erst nach den Verdikten aus Slice 1.

---

## 8. Vorbereitete Artist-Fragen (erst im Lab zu beantworten, nicht jetzt)

Jede Frage wird später in einer spielbaren Testsituation gestellt. Antwort: **KEEP / ITERATE / REJECT / UNKNOWN**.

| # | Frage | Technik |
|---|---|---|
| F1 | Soll das Key-Light mit der Kamera mitgehen oder fest in der Welt stehen? | Key, Schalter |
| F7 | Braucht es Rim nach Slice 3 überhaupt noch? Falls ja: drittes echtes Licht oder Shader-Term (Fresnel)? — *Slice 4* | Rim, zwei Varianten |
| F8 | Welche Grundeinstellung für Lichtverhältnis Key:Fill und Weichheit fühlt sich als Worklight richtig an? | §4.1a, Presets |
| F9 | Hilft ein warmer Key / kühler Fill beim Formlesen, oder stört er? | §4.1a, Temperatur |
| F10 | Welche Presets aus Polarität × Kontraststufe tragen — für genaue Formprüfung und für lange Sitzungen? | §4.1b |
| F11 | Einzelfarbe oder Verlauf als Hintergrund? | §4.1b |
| ~~F2~~ | ~~MatCap-Look~~ — **raus** (Artist-Aussage 2026-09-26, §2.4) | A5 |
| ~~F3~~ | ~~Glanzlicht~~ — zurückgestellt, nicht Teil des Zielsetups Key + Rim | A7 |
| F4 | Sind Zebra-Streifen ein nützlicher Prüfmodus (z. B. für Pole)? | B6 |
| F5 | X-Ray: lieber durchsichtige Faces oder nur gedimmte verdeckte Kanten? | E1 vs. E3 |
| F6 | Wie deutlich soll Hover sein — Farbe, Umriss, beides? | D2 (Darstellung), Semantik bleibt im UX-System |

---

## 9. Abgrenzung

- **Nicht hier:** Hover-*Semantik*, X-Ray-*Selektionsverhalten*, Tastenbelegung für Display-Modi. Das gehört ins Three-Role-UX-System.
- **Nicht hier:** Material-/Render-Vorschau, Texturen, Szenenlicht für Präsentation.
- **Nicht hier:** Farbschema der Oberfläche *außerhalb* des Viewports (Panels, HUD, Menüs). Ein späteres Light/Dark-Theme der App berührt den Viewport-Hintergrund, ist aber ein UI-Thema.
- **Nicht hier:** Subdivision Shading (siehe §5).
- **Nicht hier:** Schatten und alles, was Richtung Rendering geht (Artist-Verdikt, §2.4).

---

## 10. Offene Punkte

- **OFFEN:** Historisches Mirai-Viewport-Licht — im Archäologie-Material nicht gefunden.
- **OFFEN:** Hardware-Fähigkeiten auf Manus PC (`gl_PrimitiveID`, `dFdx`, Kosten eines zweiten Passes).
- ~~**OFFEN:** Eigene MatCap-Bilder erzeugen (keine fremden übernehmen).~~ — entfällt, MatCap ist raus (§2.4).
- ~~**OFFEN:** Ob ein Viewport-Lab jetzt Priorität hat — Manus Entscheidung.~~ — **entschieden 2026-09-26:** ja, Slice 1 (§7).
- ~~**OFFEN:** Wie hell die vom Key-Light abgewandte Seite bleibt (heute fester Ambient-Sockel 0.35).~~ — **strukturell beantwortet 2026-09-26:** Diese Aufgabe übernimmt jetzt der Fill; die Grundhelligkeit wird ein Regler (§4.1a). Welcher Default sich richtig anfühlt, ist F8.
- **OFFEN:** Ob „MatCap ist raus" dauerhaft gilt oder nur für dieses Worklight-Thema.
- **Agent-Entscheidung im Lab, keine Artist-Frage:** Umrechnung Kelvin → RGB (Näherungsformel oder kleine Tabelle); Begrenzung gegen Überbelichtung; Umrechnung OKLCH → RGB für Hintergrund-Presets.
- **OFFEN:** Ob die Lese-Befunde zur Polarität (§4.1b) auf das Modellieren übertragbar sind. Nur durch Benutzung prüfbar (F10).
- **OFFEN:** Ob die Worklight-Abgrenzung auch Umgebungsverdeckung (B5, SSAO) oder echte Transparenz-Sortierung (E4) betrifft. Das Verdikt wurde nur für die Shadow Map ausgesprochen; die Ausweitung ist **nicht** abgeleitet.

---

## Quellen

- Repo: `docs/research/MODELING_WORKFLOW_TOPOLOGY_RESEARCH.md` (§4.4, §5.3, §5.4, §7.1, §12), `docs/research/MIRAI_SYSTEMS.md`, `playground/window.py` (`_FACE_VERT`), `playground/shadow_map.py`, `src/viewport/gl_render_store.py`, `src/mirai/viewport/display.py`, `docs/archive/viewport_v02/reviews/VIEWPORT_V02_STATE_REVIEW_CLAUDE_001.md`, `docs/architecture/AD-018-PRODUCTION-DRAW-BINDING.md`
- Blender Manual, Workbench Lighting (Studio-Lichter folgen standardmäßig der Kamera; MatCap): https://docs.blender.org/manual/de/dev/render/workbench/lighting.html
- Blender Manual, Workbench Options (Cavity World/Screen, Ridge/Valley): https://docs.blender.org/manual/en/latest/render/workbench/options.html
- Blender Manual, Viewport Shading (X-Ray, Backface Culling): https://docs.blender.org/manual/ja/2.93/render/workbench/options.html
- Blender Manual, Workbench Lighting (Studio: Lichter folgen standardmäßig der Kamera, „World Space Lighting", Rotation nur um Z): https://docs.blender.org/manual/sl/4.5/render/workbench/lighting.html
- Blender-Quellcode, Commit `7bb5125` „Workbench: Use non-negative lighting evaluation" (2018, Studio-Licht über Spherical Harmonics): https://projects.blender.org/archive/blender-archive/commit/7bb512594cd9502fea290ac6124f2eb5fd3cfce8
- Gooch, Gooch, Shirley, Cohen: *A Non-Photorealistic Lighting Model for Automatic Technical Illustration*, SIGGRAPH 1998 (warm/kalt-Shading für Formlesbarkeit): https://users.cs.northwestern.edu/~ago820/SIG98/abstract.html
- Blender Manual, Viewport Shading (Hintergrund aus Theme als Verlauf, „Gradient Colors"): https://docs.blender.org/manual/zh-hant/dev/editors/3dview/display/shading.html
- Piepenbrock, Mayr, Buchner: *Smaller pupil size and better proofreading performance with positive than with negative polarity displays*, Ergonomics (Positive-Polarity-Vorteil, Helligkeitshypothese); Zusammenfassung u. a. in Mathôt & Ivanov, PeerJ 2019: https://peerj.com/articles/8220.pdf
- *The Effect of Ambient Illumination and Text Color on Visual Fatigue Under Negative Polarity*, Sensors 2024, 24(11), 3516 (dunkle Darstellung bei wenig Umgebungslicht, uneinheitliche Befundlage): https://www.preprints.org/manuscript/202404.1073
- Repo (Überarbeitung 2026-09-26): `playground/window.py` und `src/main.py` (`glClearColor`), `src/viewport/gl_render_store.py` (`FRAGMENT_SRC`, `LIGHT_DIR`), `experiments/ad018_gl_render_store_verification/README.md`, `docs/architecture/AD-010-PLAYGROUND-SUPERSEDES-LAB-BINDING.md`
