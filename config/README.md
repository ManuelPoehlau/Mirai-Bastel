# config

`keymap.json` — **Manus Tastenbelegung** (AD-013 Addendum 2026-10-28). Die App (`src/main.py`) und die Labs auf der
App (Morph Lab) laden diese eine Datei beim Start; was hier steht, gilt vor der Standardbelegung im Code.

- Ein Eintrag hier = von Manu ausdrücklich freigegebene Belegung; ein Agent darf ihn nach diesem Verdikt festhalten. Alles, was nur im Code steht, ist ein Engineering-Vorschlag (`PROVISIONAL`).
- Agenten lesen die Datei vor Input-Änderungen. Sie legen einen Eintrag an oder ändern ihn nur, wenn Manu genau diese Belegung ausdrücklich freigibt (z. B. „Taste passt“ oder KEEP im Praxistest für diese Taste). Jeder so bestätigte Eintrag erhält `"set": "YYYY-MM-DD"` mit dem Entscheidungsdatum; Manus Wortlaut gehört in die Commit-Nachricht. Ohne ausdrückliche Freigabe fügen Agenten keine Einträge hinzu und verschieben oder ändern sie nicht nach eigenem Ermessen. Später kann der In-App-Hotkey-Editor die Datei in Manus Auftrag bearbeiten.
- Format: `docs/architecture/INPUT_COMMAND_TOOL_CONTRACT.md` §8 — `context` (`global`, `knife`, `subd`, `morph`,
  `window`, `topology`), `input` (`kind` `key`/`mouse`/`drag`/`wheel`, `value`, `modifiers`), `command` (Name aus
  `src/mirai/interaction/commands.py` oder `null` = bewusst ungebunden), optional `set` (Datum).
- Ist die Datei kaputt, startet die App trotzdem mit der Standardbelegung und sagt es laut (Konsole, Statuszeile,
  HUD-Zeile „Keymap“). Halte-Werkzeuge (W/E/R, T, G, S, Q, L, N) gehen nur auf Tasten.
- Nicht umbelegbar: Shift/Ctrl/Alt *während* einer Geste (fein, Raster, Kamera, durch das Mesh wählen) — die Liste
  steht beim Start in der Konsole und in der HUD-Zeile „Fixed“.
