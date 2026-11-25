# Review 001 (ChatGPT) of the Alpha Brush & Stroke plan — archived first pass (2026-11-25)

**What:** an independent review by ChatGPT of the session plan behind
[`ALPHA_BRUSH_STROKE_SYSTEM_PROPOSAL_2026-11-25.md`](ALPHA_BRUSH_STROKE_SYSTEM_PROPOSAL_2026-11-25.md) (the plan
version that proposed "Kreismaske on by default" and the decisions P-18 … P-24).
**Forwarded by:** Manu, 2026-11-25, in the session chat.
**Archived per AGENTS.md §6:** verbatim, first pass, never edited afterwards. The reference to a pasted text file in the
first paragraph is part of the forwarded message; that file did not reach the session.
**How it was used:** its corrections are folded into the proposal (see its status header); its decision table is
recorded there as recommendations for Manu, **not** as decisions.

---

Das ist ein durchdachter und grundsätzlich tragfähiger Vorschlag. Claude hat die richtige Richtung eingeschlagen: Das bestehende Paint-System wird erweitert, nicht neu gebaut. Besonders gut finde ich die klare Trennung zwischen Alpha, Brush, Stroke und Paint Channel. Damit entsteht eine Grundlage, die später auch Roughness- oder Normal-Maps nutzen kann, ohne dass wir diese Kanäle jetzt schon implementieren müssen. Eingefügter Text(20261125-192432).txt


Ich würde den Entwurf allerdings noch nicht völlig ungeprüft zur Umsetzung freigeben. Es gibt einige Stellen, an denen ich gern nachschärfen würde.
Was ich für sehr gut halte
- Bestehende Technik weiterverwenden: PaintSurface, Texel Map, PaintStore, Undo, Seam Padding und Live-Texture-Updates bleiben erhalten.
- Alpha-Projektion auf der echten Oberfläche: Der Ansatz mit einem lokalen Tangentenrahmen ist für unseren Anwendungsfall sinnvoll. Er erlaubt das Malen über UV-Inselgrenzen hinweg und berücksichtigt die tatsächlich angezeigte Oberfläche – auch bei SubD, Morph und Pose.
- Deterministische Zufälligkeit: Ein gespeicherter Zufalls-Seed verhindert, dass Undo oder unterschiedliche Frame-Budgets zu anderen Strichmustern führen.
- World-Space-Spacing: Das ist für Mirai die richtige Richtung. Der Abstand zwischen den Stempeln sollte nicht davon abhängen, wie schnell die Maus über den Bildschirm bewegt wird.
- Referenz-PC bleibt ein echtes Kriterium: Die vorgeschlagenen Performance-Gates verhindern hoffentlich, dass wir ein tolles System bauen, das auf deinem alten Rechner nicht mehr sinnvoll funktioniert.
Was ich vor der Umsetzung noch klären würde
1. Alpha-Projektion und Krümmung

Das ist für mich nach wie vor der kritischste technische Punkt. Eine mittlere Flächennormale über den gesamten Stempelbereich kann auf stark gekrümmten Stellen problematisch werden – zum Beispiel an Nase, Lippen oder Wangen.

Ich würde Claude bitten, ausdrücklich zu testen, ob der lokale Bezugsrahmen bei solchen Übergängen stabil bleibt. Die vorgeschlagene Facing-Fade- und Depth-Window-Begrenzung ist ein guter Ansatz, aber noch keine Garantie gegen Verzerrungen.

2. Kreis-Maske standardmäßig aktiv?

Hier würde ich widersprechen. Bei einer länglichen Ader, Narbe oder einem Kratzer kann eine zusätzliche Kreismaske die Alpha-Form ungewollt beschneiden. Die Alpha selbst sollte zunächst ihre eigene Form bestimmen.

Meine Empfehlung: Kreis-Maske bei importierten Alphas standardmäßig aus. Bei Bedarf kann man sie zuschalten. Beim bisherigen runden Pinsel bleibt das vorhandene Falloff-Verhalten erhalten.

3. Stamp Queue und Loslassen der Maustaste

Die Queue soll pro Frame nur ein begrenztes Zeitbudget verbrauchen. Das ist vernünftig. Aber der Vorschlag sagt auch, dass beim Loslassen alle verbleibenden Stempel abgearbeitet werden.

Das darf nicht dazu führen, dass ein langer Strich beim Loslassen plötzlich mehrere Sekunden einfriert. Hier braucht Claude eine klare Regel: begrenzte Nachverarbeitung, kein unbegrenzter Block im Release-Event.

4. Spray und Scatter

Hier sollten die Begriffe und das Verhalten sehr eindeutig sein:
- Spacing: Abstand der Stempel entlang des Strichs.
- Scatter: Abweichung der Stempel von der Strichlinie.
- Spray: Mehrere kleine Stempel innerhalb eines Bereichs, mit einstellbarer Dichte.
Besonders wichtig: Die Sprühmuster dürfen nicht davon abhängen, wie schnell die Maus bewegt wird oder wie die Frames gerade aufgeteilt werden.

5. Alpha-Import

Die automatische Interpretation von PNGs sollte nicht zu viel voraussetzen. Eine Datei kann sowohl einen Alphakanal als auch Graustufeninformationen enthalten. Nur den Alphakanal zu verwenden, könnte dann die eigentliche Struktur verlieren.

Ich würde beim Import zumindest drei Möglichkeiten vorsehen: Alphakanal, Luminanz und Luminanz × Alphakanal. Die automatische Vorauswahl kann helfen, aber die Vorschau muss eine Korrektur ermöglichen.

Meine Empfehlungen zu den offenen Entscheidungen
Das sind die Punkte P-18 bis P-24 aus dem Vorschlag. Ich würde sie folgendermaßen festlegen:
Entscheidung	Meine Empfehlung
P-18 Spacing	World Arc Length
P-19 Kreis-Maske	Standardmäßig aus bei importierten Alphas
P-20 Pinsel-Presets speichern Größe?	Ja, mit „Größe behalten“-Option
P-21 Ausrichtung	Standardmäßig „Strich folgen“
P-22 Kategorien und Importgröße	Vorgeschlagene Kategorien; zunächst maximal 1024 px
P-23 UI	Vorgeschlagenes kompaktes Layout mit einklappbaren Bereichen
P-24 Reihenfolge	4a → 4b → 4c
Farbe im Preset	Nein

Eine zusätzliche Sache wäre mir wichtig: Der prozedurale Starter-Alpha-Generator sollte zunächst eine Vorschau-Sammlung aller erzeugten Alphas ausgeben. Die Qualität von Poren, Adern, Schmutz, Flecken und Rissen müssen wir visuell beurteilen können, bevor wir diese als Mirai-Bibliothek übernehmen. Technisch korrekte Alphas sind nicht automatisch gute Künstlerwerkzeuge.
Wie ich weitergehen würde
Ich würde die vorgeschlagene Reihenfolge beibehalten:
1. 4a – Alpha-Grundsystem
   
   Alpha-Abdruck auf der Oberfläche, World-Space-Spacing, kontinuierliche Striche und Queue. Erst einmal mit einigen Test-Alphas.
2. 4b – Brush Dynamics
   
   Rotation, Größenvariation, Jitter, Scatter und Spray. Hier entsteht der eigentliche Reichtum an Strichmöglichkeiten.
3. 4c – Bibliothek und Bedienung
   
   Import, Vorschauen, Kategorien, eigene Brushes, Presets und die Starter-Sammlung.
Ein kleiner Zusatz zu 4a: Die visuelle Erprobung sollte nicht bis 4c warten. Wir brauchen schon dort eine einfache Möglichkeit, verschiedene Test-Alphas auszuwählen und auf dem Gollum-Kopf auszuprobieren.

Mein Fazit: Ich würde Claude nicht mit einem neuen Architektur-Audit zurück an den Start schicken. Der Entwurf ist bereits eine gute Grundlage. Ich würde ihm die oben genannten Korrekturen und Entscheidungen geben und anschließend 4a als eng abgegrenzte Implementierung freigeben. Besonders die Alpha-Projektion sollte dabei zuerst auf Nase, Wangen, Lippen, UV-Naht und stark gekrümmten Oberflächen praktisch validiert werden.
