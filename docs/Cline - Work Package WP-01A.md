CLI Reading Confirmation
✅ AGENTS.md (Root) — gelesen. ✅ docs/Mirai-Bastel — Work Package WP-01A.md — gelesen. Beide auf main vorhanden, Inhalte identisch mit dem bereitgestellten Stand.

Phase 1 — Repository-Analyse (Ist-Zustand auf main)
1.1 Git-Zustand
Branch main, Worktree sauber, einzige untracked Datei: das WP-01A-Dokument selbst.
Letzte Commits: Architekturvertrag Input→Command→Tool→Operation + ROADMAP V1.0 + Topology-aware Connect Edges. Die Infrastruktur-Vorgaben für WP-01A sind also frisch dokumentiert und „accepted" für dieses WP.
1.2 Produktion (src/)
NUR src/core/ — eingefroren (CORE_V1_FREEZE.md). Repo-Tests importieren core.* (nicht mirai_bastel_core.*).
Core-API, die WP-01A nutzen kann, ohne sie zu ändern: Scene (mesh/selection/history), SelectionMode (VERTEX/EDGE/FACE/OBJECT), Selection (toggle/set/add/remove/clear/hovered), MoveOperation/OperationContext (interaktiver Lifecycle begin→update→commit/cancel), Mesh-Queries, Topology-Primitives.
Test-Baseline verifiziert: python -m tests.run_core_suite → 29/29 unittest + Architekturverträge = Gesamt: PASS.
Python 3.12.10, pyglet 2.1.16 installiert.
1.3 Experiment (maßgebliche Viewport-Referenz)
experiments/mirai_bastel_viewport_V1/ ist laut README das aktive interaktive Praxistestfeld. Aktueller Verhaltensstand (aus dem Code, nicht aus Annahmen):

Bereich	aktueller Stand im Code
Kamera (camera.py)	OrbitCamera: Orbit ±85°, Dolly/Zoom, screen_to_ray, project_to_screen, screen_delta_to_world. Kein Pan, kein Frame/Focus. Reine Mathe-Klasse, ohne pyglet testbar.
Picking (picking.py)	Vertex (Pixel-Distanz), Edge (Segment-Distanz), Face (Ray→Möller-Trumbore), ohne GPU testbar.
Selection	V/E/F-Modi (Toggle-Multi-Selection, Klick ins Leere = clear, Hover-Feedback), aufgebaut auf Core-Selection.
Rendering	Solid-Faces + Wireframe + Punkte, ein Farbshader, kein Flat/Shaded-Unterschied, kein Wireframe-Mode/Overlay.
Keys	hart kodiert in app.py (key.V/_1, E/_2, F/_3, Ctrl+Z/Y, Esc) und topology_app.py (S Split, K Collapse, C Connect, Shift+C ConnectEdges, L Loop, R Ring). Es existiert keine Mapping-Schicht.
Mouse	LMB → Select + Move-Drag, RMB → Orbit, Wheel → Zoom. Nicht konfigurierbar.
Tools	topology_tools.py ist bereits sauber Key-frei (nur Domain-Logik + History-Snapshots). Der Move-Drag ist ein impliziter Fensterzustand (_drag_mode), der die Core-MoveOperation nutzt.
1.4 Abweichungen der WP-Annahmen vom tatsächlichen Repository-Stand
Nach Regel „Repo-Stand hat Vorrang" dokumentiere ich zwei Anpassungen:

Implementierungsort. SOURCE_ARCHITECTURE.md §2/§5 legt explizit fest: genaue Aufteilung von viewport/, tools/ und die Event-/Command-Architektur sind bewusst noch nicht entschieden; es werden keine Top-Level-Ordner unter src/ vorsorglich angelegt. src/README.md und CORE_V1_FREEZE.md §5 sagen: „Produktionsstruktur außerhalb des Core wird erst aus den gewachsenen Experimenten und echten Anforderungen abgeleitet." → Die Implementierung gehört daher in experiments/mirai_bastel_viewport_V1/ als structurally sauber getrennter, automatisch testbarer Block. Die Ableitung der src/-Produktionsstruktur ist danach eine explizite Folge-Architekturentscheidung. WP-01A liefert dafür genau die nötige Evidenz.
„Soweit der aktuelle Code es erlaubt". Orbit/Zoom existieren und bleiben erhalten; Pan existiert nicht → wird minimal ergänzt. Shaded/Flat Shaded/Wireframe existieren nicht → minimaler Display-State + einfache Normalen-Beleuchtung, ohne Renderer-/Material-Stack. Das Vertrags-Beispiel W → ToggleWireframe übersetze ich in praktisch passende Defaults (siehe unten), ohne Hotkeys zu erfinden.
1.5 Test- und Lauf-Konventionen
Experiment-Tests: eigene tests/-Mappe, plain-run_all-Stil mit sys.path-Adjustierung, laufen gegen mirai_bastel_core_V1 (gefrorene Referenzkopie). Es gibt IDE-Run-Konfigurationen run, run_topology, Test_pyglet.
Repo-Tests (tests/) laufen gegen src/core und dürfen nicht brechen.
Phase 2 — Implementierungsplan (intern konsistent, noch nichts umgesetzt)
2.1 Architekturziel für WP-01A (im Experiment)

pyglet-Event (Key/Mouse/Wheel)
      ↓  Adapter (nur in app.py, pyglet-abhängig)
Input (kind, value, modifiers)                    ← input_binding.py, pyglet-frei
      ↓
Context ("global" | "topology")
      ↓
BindingSet.command_for(input, context)            ← default + optional keymap.json-Overlay
      ↓
Command (benannte String-Konstante)
      ↓
Dispatcher im Window: Tool-/Action-Handler         ← z.B. Move-Drag (impliziter Tool-State) → MoveOperation (Core)
      ↓
History/Core  (unverändert, Core-Freeze)
2.2 Neue/geänderte Dateien unter experiments/mirai_bastel_viewport_V1/
Neu: viewport/commands.py Benannte Command-Konstanten (Strings): SET_VERTEX_MODE, SET_EDGE_MODE, SET_FACE_MODE, UNDO, REDO, CANCEL, ORBIT, PAN, ZOOM, SELECT (inkl. Move-Drag auf bestehender Selektion), CYCLE_DISPLAY_MODE, TOGGLE_WIREFRAME_OVERLAY, SET_SHADED, SET_FLAT_SHADED, SET_WIREFRAME sowie Topology-Lab-Commands SPLIT_EDGE, COLLAPSE, CONNECT_VERTICES, CONNECT_EDGES, EDGE_LOOP, EDGE_RING.

Neu: viewport/input_binding.py (pure, ohne pyglet, testbar)

Input (frozen dataclass): kind = "key" | "mouse" | "wheel", value (z.B. "V", "LMB", "MMB", "RMB", "wheel"), modifiers (frozen set, z.B. {"ctrl"}).
GLOBAL_CONTEXT + BindingSet mit zwei Ebenen: Defaults + User-Overlay.
API: bind/unbind/command_for, to_dict()/from_dict() für die Konfigurationsdatei, set_user_overrides(...).
Context-Auflösung minimal: command_for(input, context) prüft zuerst context, dann Fallback auf GLOBAL_CONTEXT — genau der reale Bedarf „Topology-Lab-Keys vs. globale Keys", kein Framework-Overkill.
Neu: viewport/display_state.py (pure, testbar)

DisplayMode = SHADED | FLAT_SHADED | WIREFRAME; DisplayState.mode + wireframe_overlay: bool.
API: set_mode(), toggle_wireframe_overlay(), cycle() (Reihenfolge Shaded→Flat→Wireframe→Shaded), gültige Übergänge, Property-Helfer show_faces/show_edges für die 5 Kombis (Shaded, Shaded+Wire, Flat, Flat+Wire, Wireframe). Ungültige Modi → ValueError.
Neu: viewport/default_bindings.py Abgeleitete, minimal erfundene Defaults:

Keys global: V/1, E/2, F/3 → Selektion-Modi; Ctrl+Z→UNDO, Ctrl+Y→REDO, Esc→CANCEL; O→CYCLE_DISPLAY_MODE, W→TOGGLE_WIREFRAME_OVERLAY (O/W frei, kollisionsfrei, zwei Tasten statt Hotkey-Flut).
Keys Context "topology": S, K, C, Shift+C, L, R (wie bisher im Lab, jetzt übers Mapping).
Mouse: LMB→SELECT, RMB(Drag)→ORBIT, MMB(Drag)→PAN (neu), wheel→ZOOM. Damit bleibt das bestehende V1-Verhalten vollständig erhalten; Pan ist die einzige neue Maus-Konvention (modellierer-üblich).
Geändert: viewport/camera.py — nur additive Ergänzung:

pan(dx_px, dy_px, width, height): verschiebt target entlang Kamera-right/up, skaliert mit 2·distance·tan(fov/2)/height (natürliches Pan-Tempo). Reine Mathe, bestehende Orbit/Dolly unverändert, new tests.
Geändert: viewport/app.py

__init__: display_state, bindings = build_default_bindings() + optional keymap.json-Overlay aus dem Experiment-Root.
Event-Adapter (pyglet-spezifisch, einzige Stelle mit pyglet.window.key/mouse): _key_input(symbol, modifiers), _mouse_input(button, modifiers), _wheel_input(...).
on_key_press: kein key.*-Vergleich mehr — nur command_for + _exec_command(cmd).
on_mouse_press/drag/scroll: Mouse-Commands über BindingSet; Drag-Modi orbit/pan/move aus dem aufgelösten Command.
Rendering über DisplayState: Faces nur bei show_faces, Edges gemäß show_edges, Overlay als Edge-Gl-Linien darüber; minimaler Lambert-Shader mit Face-/Vertex-Normalen (Flat = Face-Normalen, Shaded = gemittelte Vertex-Normalen) — ein Shader, kein Material-Stack.
Selection-/Move-Verhalten bleibt unverändert (dokumentierte Ausnahme: Move ist bewusst weiterhin impliziter Drag-ToolState, der formale Tool-Framework bleibt WP-02).
Geändert: viewport/topology_app.py

_run_topology_tool(symbol, modifiers) → _run_topology_command(command); Keys kommen nur noch aus dem Mapping (Context "topology").
Neu: keymap.json-Schema (optional, z.B. Werte):


{"context":"global","bindings":[{"input":{"kind":"key","value":"G","modifiers":[]},"command":"MOVE"}]}
2.3 Tests
Neu tests/test_input_binding.py: Default-Binding; geändertes Binding; mehrere Bindings auf ein Command; command_for-Auflösung; Context-Vorrang + Global-Fallback; unbind; Dict-Roundtrip; statischer Guard „der Tool-/Fenster-Dispatch enthält keine pyglet.key-Konstanten mehr" (Quelltextprüfung von app.py/topology_app.py).
Neu tests/test_display_state.py: Shaded/Flat/Wireframe, Overlay ON/OFF, die 5 nutzbaren Kombinationen, Cycle-Reihenfolge, gültige/ungültige Übergänge, Normalisierung (Overlay im Wireframe-Mode → keine Faces).
Erweitert tests/test_camera_picking.py: pan bewegt target auf der Bildebene, Distanz/Orbit unangetastet.
Regression experimentell: test_camera_picking, test_constraints, test_loop_ring, test_connect_edges weiter grün.
Regression Produktion: python -m tests.run_core_suite bleibt unverändert PASS (Core-Freeze: src/core/ wird nicht berührt).
2.4 Praktischer Viewport-Test (Phase 5)
python run.py (Cube) und python run_topology.py (Grid), exakt nach WP-Checkliste: Orbit → Zoom → Pan; V/E/F; Toggle/Multi; Leerklick; Shaded/Flat/Wireframe/Overlay ON/OFF; Hotkey; Binding ändern (keymap.json); Command über neuen Hotkey; Mouse-Binding ändern; gleiche Aktion über neue Maustaste. Prüfziele zusätzlich: keine Selection-Verluste, keine History-Einträge durch reine Viewport-Aktionen (Historie unverändert leer), keine schwarzen Zustände. (Achtung Hinweis: Start auf diesem Rechner öffnet das reale Fenster; die UI-Interaktion führe ich an, sofern das Display verfügbar ist, sonst dokumentiere ich den Freigabepunkt.)

2.5 Dokumentation (Phase 7)
docs/architecture/ROADMAP.md: WP-01A-Status im Abschnitt „Current development direction" + Verweis unter WP-01.
docs/architecture/INPUT_COMMAND_TOOL_CONTRACT.md: Statusvermerk „in Viewport-V1-Experiment implementiert/validiert".
experiments/mirai_bastel_viewport_V1/README.md: neue Steuerung, Display-Modes, keymap.json.
docs/design/WORKFLOW.md: neue Pan-Konvention festhalten. Keine redundanten Docs.
2.6 Commit (Phase 8)
Ein sauberer Commit: Implement basic viewport and input foundation.

2.7 Definition-of-Done-Abgleich
Alle 17 DoD-Punkte sind über 2.2–2.6 abgedeckt; insbesondere: Bindings konfigurierbar (Keymap), Commands Input-frei, Tool/Operation-Grenze (impliziter Drag-State → MoveOperation), keine Viewport-History, Core unangetastet.