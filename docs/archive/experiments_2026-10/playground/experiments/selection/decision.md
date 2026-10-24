# Selection Lab — Artist Verdict (WP-AP-03)

**Status:** DECIDED

---

## Varianten

### Replace (Baseline)
`M`-Taste bis `[Replace]` → LMB click

**Fühlt sich an:**

**Verdict:**  REJECT

---

### Modifier (Shift / Ctrl / Alt)
`M`-Taste bis `[Modifier]` → Shift+LMB addiert, Ctrl+LMB entfernt, Alt+LMB togglet

**Fühlt sich an:**

**Verdict:** KEEP
Decided 2026-09-26 (Manu), directly — informs WP-06 Slice B2's Production selection baseline.

---

### Toggle
`M`-Taste bis `[Toggle]` → jeder Click togglet

**Fühlt sich an:**

**Verdict:** REJECT

---

### Box-Select
`M`-Taste bis `[Box]` → LMB ziehen; alle Vertices der Face müssen im Rechteck sein

**Fühlt sich an:**

**Verdict:** KEEP

LMB hold down + drag außerhalb des Meshs aktiviert box select. Shift + LMB hold down + Drag für add box select, ctrl + LMB hold down + drag remove box select
Zusatz: wenn man über die modifier tasten add oder remove  nutzt, kann man auch innerhalb eines Meshes die Box aufziehen (wings 3d style)
---

## Component Mode (1 / 2 / 3)

### Vertex (Taste 1)
**Fühlt sich an:** KEEP

**Verdict:** KEEP

### Edge (Taste 2)
**Fühlt sich an:** KEEP

**Verdict:** KEEP

### Face (Taste 3)
**Fühlt sich an:** KEEP

**Verdict:** KEEP

---

Paint Select

LMB mouse down + drag um auswahl zu malen. Modifier keys Shit für hinzufügen und Strg für Auswahl wegnehmen

**Offener Punkt (Performance):** Paint Select (inkl. Paint Edge) ist für das Basic Selection Toolset fest eingeplant. `pick_face`/`pick_nearest_edge`/`pick_nearest_vertex` in `src/mirai/viewport/picking.py` sind bewusst lineare CPU-Suchen ohne räumlichen Index (siehe Docstring dort: „VIEWPORT_V02-Scope"). Bei Paint-Interaktion wird der Pick pro Mausbewegungs-Event neu ausgeführt — auf schwacher Hardware und/oder dichteren Meshes ist Ruckeln plausibel, zusätzlich zum bekannten Edge-Hover-Problem (dünnes Ziel wird bei schneller Bewegung übersprungen, siehe Selection Lab). Vor oder bei Start der Paint-Select-Implementierung: bewusst practical testen (dichteres Mesh, schnelle Mausbewegung, Referenz-Hardware), nicht stillschweigend annehmen, dass es reicht. Falls nicht: zurück zur VIEWPORT_V02-Scope-Entscheidung (Problem dokumentieren → Alternativen prüfen → Architekturentscheidung aktualisieren), nicht am bestehenden Code vorbeipatchen.

---

Lasso Select

**Entschieden 2026-10-21 (Manu):** kommt in die Production, wie Box und Paint — in der App seit 2026-10-21 (`Q` halten + LMB ziehen, `PROVISIONAL`,
[WP Playground-Werkzeuge, Nachtrag](../../../docs/WP_PLAYGROUND_TOOLS_PROMOTION.md#nachtrag-2026-10-21-lasso-und-gizmo-in-die-app-manu)).

---

## Kandidaten für Production (nach Verdict)

**In der App seit 2026-10-15** (Manus Promotion „die Playground-Werkzeuge in Production einbauen“,
im Chat 2026-10-15): Box-Select und Paint Select, Gesten-Regel von Manu „Startpunkt entscheidet“ —
LMB-Ziehen im leeren Raum = Box, auf dem Mesh = Malen; ohne Taste neu, Shift dazu. Ctrl+Ziehen ist
Tweak („Auswahl weicht“), Entfernen geht nur per Ctrl-Klick. Der Wings-Zusatz oben (Box mit Modifier
auch im Mesh) entfällt damit. Tasten und Optik `PROVISIONAL`, Praxistest steht aus
([WP Playground-Werkzeuge](../../../docs/WP_PLAYGROUND_TOOLS_PROMOTION.md)). Lasso bleibt offen.

[Modifier]` → Shift+LMB addiert, Ctrl+LMB entfernt, Alt+LMB togglet
Component Mode (1 / 2 / 3)
Box-Select (siehe Beschreibung oben)
Paint Select
