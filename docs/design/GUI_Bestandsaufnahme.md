# Mirai UX — GUI-Bestandsaufnahme Modellieren, Morph, Rig

Nov 3, 2026 · @Manu

## Kurz gesagt

Fast alles in Mirai ist per Taste erreichbar, aber der Zustand, in dem eine Taste wirkt, ist bei Morph, Rig und Gewichten oft unsichtbar. Die Nähte für eine klickbare GUI sind im Code schon gebaut (AD-027), die GUI selbst nicht. Der erste Schritt ist daher kein neues Panel, sondern eine klarere Statusanzeige plus Rückmeldung direkt im Viewport.

**Basis:** `main` @ `5fed443` (Merge PR #58, AD-028 Slices 3–4). Gelesen: AGENTS.md, CLAUDE.md, Development System, GUI\_STAGE1\_HUD, WORKFLOW, ATELIER, AD-025 §15/§17, AD-027 §3, AD-028 §6–§8/§17, `src/hud.py`, `src/main.py`, `controllers/skeleton.py`, `controllers/morph.py`, Bindings. HUD-Zeilen per Probe im Kiefer-Szenario gezählt.

**Kennzeichnung:** **\[V\]** im Code oder per Probe geprüft · **\[H\]** Hypothese von mir (UX-Chat) · **\[O\]** offen, braucht dich. Kein Satz hier ist ein Artist-Verdikt; alle Vorschläge sind `PROVISIONAL`, bis du sie im Praxistest beurteilst.

**Status und Rolle:** Diese versionierte Bestandsaufnahme ist ein datierter UX-Arbeitsstand, keine Entscheidung und keine GUI-Spezifikation. `[V]` beschreibt den geprüften Bestand, `[H]` sind Vorschläge des UX-Chats, `[O]` sind offene Fragen an Manu. Nichts davon ist ohne dein Urteil Artist Input Truth. Übernommene Entscheidungen gehören anschließend in `GUI_STAGE1_HUD.md` bzw. `UX_RESEARCH.md`; technische Verträge bleiben in den ADs.

## 1. Was heute existiert

Die App hat ein lesendes HUD, drei Menüs am Cursor und Feedback im Viewport; klickbar ist außer den Menüs nichts. Alle Angaben **\[V\]**.

| Element | Was es heute tut | Stand |
| --- | --- | --- |
| HUD (`src/hud.py`) | Zeigt Zustand als Text, zwei Layouts: Leiste unten (A), Panel oben links (B); `H` schaltet A → B → aus | Dein Urteil A gegen B offen (GUI\_STAGE1\_HUD §4 leer) |
| HUD-Zeilen | Start: 13 (Mode, Tool, Axis, Space, Pivot, Sym, Display, View, Soft, SubD, Region, Look, Fixed); mit Morph und Rig: 16 (+ Morph, Targets, Rig). Alle gleich gewichtet, „an“ nur gelb eingefärbt | Probe im Kiefer-Szenario |
| Tastenhinweise | Kommen aus dem `BindingSet`; eine Umbelegung in `keymap.json` erscheint sofort | gut, beibehalten |
| Gesperrte Befehle | `HudState.unavailable` berechnet per `can_run(…, "ui")`, was gerade nicht geht — wird aber nicht angezeigt | Ausgrauen ist laut AD-027 §3.3 die Entscheidung dieses Projekts |
| Menüs am Cursor | `Leertaste` Szenen/OBJ, `Shift+A` Add Mesh, `Shift+M` Mirror; modal, Fenster-Ebene | `PROVISIONAL`; „Menü am Cursor kommt definitiv“ (du, 2026-10-28) |
| Gizmo | Zeigt Achsen, aktive Achse dick, Hover sichtbar; im Pose-Modus am Knochenkopf | **verschwindet während jeder Geste** (`_gizmo_pivot_if_shown`); gesten-/pivotbezogen, nicht die permanente Raumorientierung |
| Raumorientierung | Kein separates, dauerhaft sichtbares XYZ-Orientierungs-Gizmo als eigenes Viewport-Element erfasst | **Grundausstattung fehlt**: Orientierung muss auch ohne aktive Auswahl oder Geste jederzeit ablesbar sein |
| Knochen | Linie Kopf → Spitze mit Kreuz am Kopf; aktueller Knochen orange und dicker; außerhalb des Pose-Modus gedimmt | kein Name, keine Hierarchie sichtbar |
| Gewichte | Wärmefarben über die Soft-Selection-Flächenfärbung | **nur solange `7`/`8` gehalten wird** |
| Morph | Ziel wird daneben bearbeitet (`Tab`); Drahtgitter folgt der Mischung; Gewicht per `N` halten, `+`/`-` | Gewicht nur als Zahl im HUD |
| Namen | Morph-Ziele, Knochen, Gruppen nur über feste Namenslisten (`Smile, Blink…`, `Jaw, Head…`) | **kein Textfeld in der App** |
| Tasten | ≈ 125 Code-Standards + 13 Morph + SubD; 65 Tastenbelegungen mit Ctrl/Shift/Alt (43 mit einem, 20 mit zwei, 2 mit drei Modifiern) | 38 Einträge von dir in `keymap.json` |

**Schon gebaute Nähte für eine klickbare GUI** (AD-027 §3.3–§3.5): `dispatch_command` hat dieselben Sperren wie die Taste; ein Treffertest auf Fenster-Ebene darf vor dem Interaktions-Slot sitzen (Klick aufs Panel → UI, daneben → App, Ziehen und Loslassen folgen dem Druck); `cursor_wrap` ist für Schieberegler vorbereitet; ein `SliderDrag` als Gesten-Art ist vorgesehen. Das HUD selbst kennt seine Rechtecke und die Befehle jeder Zeile (`_HINT_COMMANDS`).

## 2. Was verborgen oder schwer verständlich ist

Die größten Lücken liegen dort, wo eine Taste je nach Zustand etwas anderes tut oder abgelehnt wird, ohne dass man den Zustand sieht. Spalte „Art“ trennt fehlende UI von technischer Grenze und offener UX-Frage.

| # | Lücke | Beleg | Art |
| --- | --- | --- | --- |
| L1 | **Achsen-Sperre während des Tweaks unsichtbar.** Das Gizmo verschwindet, sobald `W`/`E`/`R` gehalten wird; ohne Auswahl (Hover-Tweak) gibt es gar kein Gizmo. Bleibt nur der Text unten im HUD | \[V\] `_gizmo_pivot_if_shown`; dein Ärger 2026-10-28 „HUD-Anzeige unten wird beim Modellieren übersehen“ | fehlende UI |
| L2 | **Pose-Modus fehlt in der Modus-Zeile.** Im Pose-Modus zeigt „Mode“ weiter „Face“, „Tool“ zeigt „Move“; „pose mode“ steht am Ende der Rig-Zeile | \[V\] Probe | fehlende UI |
| L3 | **Ruhe/Pose und „gebunden“.** „posed/rest“ ist Text in der Rig-Zeile; „gebunden“ steht nirgends. Beide Sperren (Modellieren nur in Ruhe, Objekt fest) erfährt man erst durch die Ablehnung | \[V\] AD-028 §7, `status_text` | fehlende UI |
| L4 | **Gewichte im Ruhezustand unsichtbar.** Keine Gewichts-Ansicht zum Einschalten; Prüfen heißt `7`/`8` halten und damit schon schreiben | \[V\] `_show_share` nur in der Geste | fehlende UI |
| L5 | **Knochen-Hierarchie unsichtbar.** Elternknochen = der aktuelle beim Anlegen; man sieht ihn nicht und kann ihn nicht ändern; Wechseln blind per `Alt+J` | \[V\] AD-028 §8.3 | fehlende UI + Funktion (Umhängen fehlt) |
| L6 | **Morph-Liste als Textzeile.** Höchstens 8 von bis zu 64 Zielen sichtbar, Gewicht als Zahl, kein Balken; „Basis“ gegen „Ziel daneben“ nur als Wort | \[V\] `targets_text`, `MAX_TARGETS = 64` | fehlende UI |
| L7 | **Gleiches Gewicht für alles im HUD.** 16 Zeilen; Look, Display, View, Fixed ändern sich selten, stehen aber gleichrangig neben Modus und Achse | \[V\] Probe | UX-Frage |
| L8 | **Gesperrtes wird nicht gezeigt.** `can_run` weiß es pro Befehl, das HUD zeigt es nicht | \[V\] `HudState.unavailable` | fehlende UI |
| L9 | **Kein Umbenennen per Text.** Namenslisten statt Eingabe; bei vielen Zielen oder Knochen nicht tragfähig | \[V\] `RENAME_CYCLE`, `BONE_NAMES` | technische Grenze (kein Textfeld) |
| L10 | **Zwei Heat-Ansichten teilen eine Färbung.** Soft-Zone und Gewichte nutzen dieselbe Flächenfärbung; beide zugleich geht nicht | \[V\] `show_soft_weights` | Gestaltungsgrenze, bei L4 beachten |
| L11 | **Keine permanente Raumorientierung.** Außerhalb einer aktiven Geste fehlt ein eigenständiger, stets sichtbarer Hinweis auf die X-/Y-/Z-Richtung im Weltraum. Das gestenbezogene Gizmo erfüllt diese Aufgabe nicht | \[V\] In der geprüften Viewport-Bestandsaufnahme ist kein separates Orientierungs-Gizmo erfasst | fehlende UI |

Außerhalb der UI, nur notiert: Der Drehring liefert 0°, wenn das Auge genau auf der Drehebene liegt (AD-028 §17.3); der Praxistest umgeht es mit schräger Ansicht. Und eine kleine Doku-Drift: CLAUDE.md sagt noch „Morph is not in `src/`“, ATELIER und AD-025 sagen das Gegenteil.

## 3. Vorgeschlagenes Interaktionsmodell \[H\]

Eine Grammatik für alle Bereiche, keine Mini-App pro Funktion: Modus sagt *woran*, die Halte-Taste sagt *was*, die Maus gibt den *Wert*. Die GUI zeigt diese Grammatik und spiegelt sie, ersetzt sie aber nicht.

**Vier Regeln**

1. **Fünf sichtbare Modi:** Vertex · Edge · Face · Object · **Pose**, in einer Zeile, gleich gewichtet. Technisch bleibt Pose Controller-Zustand (AD-028 §8.2); nur die Anzeige ändert sich. Das „Ziel daneben“ (`Tab`) ist kein sechster Modus, sondern ein Zusatz am Modus: „Face · Ziel *Smile*“.
2. **Halten + Maus = Wert, überall.** Gilt heute schon für `N` (Morph-Gewicht), `7` (Auslauf), `8` (Gewicht), `L` (Licht). Neue Zahlenwerte (Soft-Radius, später Kurven) folgen derselben Regel — passend zu deinem Wunsch, Hand und Finger zu schonen und weniger zu scrollen.
3. **Die GUI zeigt den Wert am Cursor.** Während einer Halte-Geste erscheint neben dem Cursor Name, Zahl und ein kurzer Balken („Jaw · 0,62“). Das Auge bleibt am Mesh, nicht unten im HUD.
4. **Klick wählt, Taste stellt ein.** Im Panel macht ein Klick einen Eintrag aktuell (Ziel, Knochen, Gruppe); verstellt wird mit derselben Halte-Taste wie ohne Panel. Ziehen am Balken geht zusätzlich, ist aber nie der einzige Weg — dauerhaftes Klick-Ziehen empfindest du als belastend (2026-10-28).

**Was der Artist jederzeit wissen muss — und wo er es sieht**

| Frage | Antwort heute | Vorschlag |
| --- | --- | --- |
| Woran arbeite ich? | Mode-Zeile, ohne Pose | Modus-Leiste mit Pose; Edit-Objekt und „Ziel daneben“ als Zusatz |
| Was macht `W`/`E`/`R` jetzt? | Tool-Zeile | dort; im Pose-Modus „Bone · Rotate“ |
| Wie ist der Raum orientiert? | keine permanente XYZ-Anzeige | **Kleines, dauerhaft sichtbares XYZ-Orientierungs-Gizmo** im Viewport; es vermittelt die Weltachsen auch ohne aktive Auswahl oder Geste (L11) |
| Welche Achse gilt gerade beim Bearbeiten? | Axis-Zeile unten | **Achslinie im Viewport während des Tweaks** (L1) |
| Ist das Mesh posiert / gebunden? | Rig-Zeile, Wort „posed“ | Warnmarke dauerhaft sichtbar, mit Taste: „Pose aktiv — Modellieren in Ruhe (`6`)“ |
| Welcher Knochen / welches Ziel ist aktuell? | Rig- / Morph-Zeile | Name am Knochen im Viewport; im Panel hervorgehoben |
| Wie verteilen sich die Gewichte? | nur während `7`/`8` | Gewichts-Ansicht als Anzeige-Umschalter (wie `D`) |

**Übergang Posieren ↔ Gewichte (Rig):** Posieren geschieht im Pose-Modus (`5`), Gewichte korrigieren im Komponenten-Modus (`1`/`2`/`3`) — bei sichtbar bleibender Pose. Der aktuelle Knochen gilt in beiden. Deshalb muss sein Name *auch außerhalb* des Pose-Modus sichtbar sein, sonst schreibt `8` auf einen Knochen, den man nicht sieht.

**Drei Achsen-/Orientierungsanzeigen dürfen nicht verwechselt werden:**

- **Raumorientierung:** ein dauerhaft sichtbares, kleines XYZ-Gizmo. Es zeigt die Richtung der Weltachsen relativ zur aktuellen Kamera und dient der allgemeinen Orientierung im Modellierraum — unabhängig von Werkzeug, Auswahl und Geste.
- **Aktive Werkzeugachse:** temporäres Feedback zur gerade verwendeten Transformations- oder Tweak-Achse, idealerweise als Linie im Viewport und gegebenenfalls mit Wert am Cursor.
- **Working Pivot / lokales Koordinatensystem:** bestimmt den Bezug für eine konkrete Bearbeitung. Seine Position und Orientierung sind kein Ersatz für die allgemeine Weltachsen-Anzeige.

Das Orientierungs-Gizmo sollte beim Drehen der Kamera seine Darstellung entsprechend aktualisieren, selbst aber an einer festen, unaufdringlichen Stelle im Viewport bleiben. Ein klassisches kleines Achsenkreuz in einer Viewport-Ecke ist eine naheliegende Ausgangshypothese; Gestaltung und Platzierung bleiben offen.

**Vergleich mit anderen Programmen** (aus eigener Kenntnis, nicht recherchiert)

| Programm | Lösung | Für Mirai übernehmen | Nicht übernehmen |
| --- | --- | --- | --- |
| Wings 3D / Silo | Infozeile: was LMB/MMB/RMB gerade tun; kaum Panels | kontextuelle Hinweiszeile | — |
| Blender | Pose- und Weight-Paint-Modus im Moduswähler; Shape-Key-Liste mit Wertebalken | Modus sichtbar als Ort; Liste mit Balken | eigener Weight-Paint-Modus mit Pinsel-Panel, Eigenschaftsflut |
| Maya | Shape Editor (Liste, Regler, Edit-Knopf pro Ziel); Paint Skin Weights mit Einflussliste | Edit-Knopf ≈ euer `Tab` daneben | schwebende Fenster, Channel-Box-Dichte |
| Modo | Modus-Knöpfe oben, Werkzeug-Optionen kontextuell | Kontextpanel nur mit Daten | — |

## 4. GUI-Struktur \[H\]

Drei Schichten mit einer Regel: Die Statusleiste zeigt nur, was vom Standard abweicht oder sich beim Arbeiten ändert; Listen erscheinen nur, wenn es Daten gibt; Werte erscheinen dort, wo die Hand gerade arbeitet.

&#91;embedded content: Skizze des Fensters · drei Schichten, nicht maßstäblich\]

Neu für Phase A sind die Gewichtung der Leiste und zusätzliche, klar getrennte Viewport-Hinweise;

| Schicht | Inhalt | Sichtbar |
| --- | --- | --- |
| Statusleiste | Modus-Leiste Vtx · Edge · Face · Obj · Pose; Tool bzw. laufende Geste; Achse, Symmetrie, Soft, Pivot, SubD **nur wenn an**; Warnmarke (Pose aktiv, gebunden, Keymap ungültig); „mehr“ | immer (`H` blendet aus) |
| Zweitebene | Display, View, Look, Space, Region, Fixed | aufgeklappt über „mehr“ bzw. eine Taste |
| Statuszeile | letzte Meldung; Ablehnungen farbig abgesetzt | immer, eine Zeile |
| Kontextpanel | Morph-Ziele mit Balken, Knochen eingerückt nach Eltern, Gruppen | nur, wenn das Edit-Objekt solche Daten hat |
| Viewport | Dauerhaftes XYZ-Orientierungs-Gizmo; zusätzlich Achslinie im Tweak, Wert am Cursor, Name am aktuellen Knochen und Gewichts-Ansicht | Raumorientierung immer; Gesten-Feedback und kontextuelle Hinweise nur solange sie zählen |

**Bewusst nicht:** keine Werkzeugleiste mit Icons, keine Eigenschaftsfenster, kein eigener Weight-Paint-Modus. Werkzeuge bleiben auf Tasten und im künftigen Menü am Cursor.

## 5. Prioritäten \[H\]

Zuerst kommt, was Zustände sichtbar macht und nur liest: Es hilft beim Modellieren *und* bei Morph und Rig, kostet keine neue Architektur und braucht kein neues Framework.

| Wann | Was | Löst | Braucht |
| --- | --- | --- | --- |
| **Jetzt** | Statusleiste neu gewichtet: Modus-Leiste mit Pose, Warnmarke „Pose aktiv / gebunden“, aktueller Knochen und aktuelles Ziel; Seltenes (Look, Display, View, Fixed) in eine einklappbare Zweitebene | L2, L3, L7 | nur `src/hud.py` und lesende Zugriffe |
| **Jetzt** | **Permanentes XYZ-Orientierungs-Gizmo** als allgemeine Raumorientierung; unabhängig von Auswahl, Tool und laufender Geste | L11 | kleines, lesendes Viewport-Overlay; Weltachsen relativ zur Kamera darstellen |
| **Jetzt** | Achslinie im Viewport, solange eine Geste mit Sperre läuft (auch Hover-Tweak ohne Gizmo) | L1 | Overlay im Fenster, Daten aus dem laufenden Tweak |
| **Jetzt** | Wert am Cursor bei Halte-Gesten (`N`, `7`, `8`, `L`, Soft-Radius) | Blick bleibt am Mesh | Overlay im Fenster |
| **Jetzt** | Gewichts-Ansicht zum Einschalten (aktueller Knochen als Wärmefarben), Name am aktuellen Knochen | L4, Teil von L5 | ein Anzeige-Befehl, Taste `PROVISIONAL` |
| **Jetzt** | Gesperrte Hinweise grau statt gleich hell | L8 | Daten existieren schon |
| Danach | Klickpfad: Treffertest auf Fenster-Ebene, Klick löst denselben Befehl aus wie die Taste, mit denselben Sperren | Grundlage fürs Panel | erste Änderung an `Application` für die GUI (AD-027 §3.5) |
| Danach | Kontextpanel: Morph-Ziele mit Gewichtsbalken, Knochenliste mit Einrückung, Gruppen | L5, L6 | Klickpfad |
| Später | Textfeld zum Umbenennen | L9 | Tastatur-Fokus (Tasten gehen ans Feld, nicht an die App) — Input-Architektur |
| Später | Elternknochen umhängen | Rest von L5 | **neuer Rig-Befehl → AD-028-Gebiet, zuerst ins Projekt „Mirai Bastel“** |
| Später | Hotkey-Editor in der App (deine Richtung 2026-10-28), Design des Menüs am Cursor, kleiner Kurveneditor für Soft | Merkbarkeit, Discoverability | Panel-Unterbau und Textfeld |
| Später | Toolkit-Entscheidung (pyglet bleibt oder ImGui/Qt) | — | erst nach dem Panel und einer Messung am Referenz-PC |

## 6. Offene Entscheidungen für dich \[O\]

Nur eine Frage blockiert den Start (E1); alles andere klärt ein Praxistest mit umschaltbaren Varianten oder kommt später.

| # | Frage | Art | Wie es entschieden wird |
| --- | --- | --- | --- |
| E1 | Was zuerst: die sichtbaren Zustände (Phase A) oder gleich die Charakter-Seite mit Panel (Phase B + C)? | Priorität | **deine Antwort** — Empfehlung A, weil sie Modellieren und Rig zugleich hilft und B/C nicht blockiert |
| E2 | Soll sich Pose wie ein fünfter Modus neben `1`–`4` anfühlen? | Product Truth | Praxistest in Phase A, dein KEEP / ITERATE / REJECT |
| E3 | Achslinie im Viewport: wie auffällig? (dünn durch den Pivot, bis zum Rand, farbig nach Achse) | Product Truth | Varianten im Praxistest A |
| E4 | HUD A (Leiste) gegen B (Ecke) | Product Truth | geht in Phase A auf: die neue Leiste wird wieder in beiden Lagen umschaltbar getestet; das alte Urteil kann dann geschlossen werden |
| E5 | Aktive Transformationsachse: einmaliges gegen dauerhaftes Feedback (Praxistest K1–K4 vom 2026-10-28, noch ohne Eintrag) | Product Truth | betrifft nur die aktive Werkzeugachse/Achslinie, **nicht** das permanente XYZ-Orientierungs-Gizmo |
| E6 | Panel fest am Rand oder schwebend über dem Viewport? | Product Truth | Varianten im Praxistest C |
| E7 | Elternknochen umhängen und Knochen frei benennen: wann nötig? | Priorität / Intent | später; Umhängen geht vorher als zweite Meinung ins Projekt „Mirai Bastel“ |
| E8 | Permanente Raumorientierung: Größe, Platzierung und visuelle Form des XYZ-Gizmos | Product Truth | Ausgangshypothese: klein und unaufdringlich in einer Viewport-Ecke; im Praxistest beurteilen |

Grenze dieses Projekts: Alles in Phase A und B bleibt in der UI- und Input-Schicht. Ein neuer Rig-Befehl (E7) oder eine Änderung an AD-027/AD-028 gehört nicht hierher.

## 7. Fahrplan \[H\]

Vier kleine Phasen; A und B hängen nicht voneinander ab, das Panel (C) braucht den Klickpfad (B), Text und Hotkey-Editor (D) bauen auf dem Panel auf.

&#91;embedded content: Fahrplan · 4 Phasen, Abhängigkeiten und Gates\]

Phase A ist ein Discovery-Paket für eine Testsitzung von 20–40 Minuten; die Übergabe an Claude Code steht im Tab „Handoff Phase A“.

**Review-Hinweis (2026-11-03, Vorschlag — noch kein Manu-Verdikt):** Die „Jetzt“-Punkte aus §5 sollten nicht als ein einziger Implementierungsblock behandelt werden. Sinnvoll wäre die Trennung in **A1 Statusklarheit und Raumorientierung** (read-only HUD plus dauerhaftes XYZ-Orientierungs-Gizmo: sichtbarer Arbeitsmodus, relevante Morph-/Rig-Zustände und jederzeitige Orientierung im Weltraum), **A2 Gesten-Feedback** (aktive Achse und Wert direkt am Cursor) und **A3 dauerhafte Gewichtsansicht**. A1 bleibt der kleinste gemeinsame Einstieg. A3 braucht eine eigene technische Klärung: Die heutige Gewichts-/Soft-Färbung teilt sich den Shading-Overlay-Pfad und die Gewichtsanzeige gehört derzeit zur laufenden Geste. Eine dauerhafte Vorschau darf nicht nebenbei die Soft-Selection-Anzeige oder deren Lebensdauer übernehmen.

Zur Übergabe: Handoff Phase A

*Stand 2026-11-03: A1 ist gebaut, Praxistest offen — [GUI_STAGE1_HUD §7 „Stufe 1b“](GUI_STAGE1_HUD.md#7-stufe-1b--phase-a1-statusklarheit-und-raumorientierung).*

| Phase | Fertig, wenn | Modus (M5) |
| --- | --- | --- |
| A | Leiste, permanentes XYZ-Orientierungs-Gizmo, Achslinie, Wert am Cursor und Gewichts-Ansicht gebaut, umschaltbar und getestet; dein Urteil zu E2–E4 und E8 steht in GUI\_STAGE1\_HUD | Discovery |
| B | Klick löst Befehle über `dispatch_command` mit allen Sperren aus; Ziehen folgt dem Druck; die AD-027-Szenario-Tests laufen unverändert | Production (Input-Architektur) |
| C | Panel mit Morph-Zielen, Knochen und Gruppen; Klick = aktuell, Halte-Taste = Wert; zwei Lagen umschaltbar; dein Urteil zu E6 | Discovery |
| D | Umbenennen per Text; Entwurf Hotkey-Editor und Menü am Cursor | zuerst Discovery |
