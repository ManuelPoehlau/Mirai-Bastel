# config

`keymap.json` — **Manus Tastenbelegung** (AD-013 Addendum 2026-10-28). Die App (`src/main.py`) und die Labs auf der
App (Morph Lab) laden diese eine Datei beim Start; was hier steht, gilt vor der Standardbelegung im Code.

- Ein Eintrag hier = von Manu gesetzt. Alles, was nur im Code steht, ist ein Engineering-Vorschlag (`PROVISIONAL`).
- Agenten lesen die Datei, schreiben sie nie. Ändern: Manu (später der Hotkey-Editor in der App).
- Format: `docs/architecture/INPUT_COMMAND_TOOL_CONTRACT.md` §8 — `context` (`global`, `knife`, `subd`, `morph`,
  `window`, `topology`), `input` (`kind` `key`/`mouse`/`drag`/`wheel`, `value`, `modifiers`), `command` (Name aus
  `src/mirai/interaction/commands.py` oder `null` = bewusst ungebunden), optional `set` (Datum).
- Ist die Datei kaputt, startet die App trotzdem mit der Standardbelegung und sagt es laut (Konsole, Statuszeile,
  HUD-Zeile „Keymap“). Halte-Werkzeuge (W/E/R, T, G, S, Q, L, N) gehen nur auf Tasten.
- Nicht umbelegbar: Shift/Ctrl/Alt *während* einer Geste (fein, Raster, Kamera, durch das Mesh wählen) — die Liste
  steht beim Start in der Konsole und in der HUD-Zeile „Fixed“.
