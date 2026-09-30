"""Session-State-Persistenz für das Artist Playground.

Session-Komfort (Override-Schicht im Sinne von AD-013 A2) — keine Entscheidung
und keine Promotion einer Variante: Beim Neustart kommt der Artist dort wieder
an, wo er aufgehört hat (fokussierte Family, aktive Variante je Family,
Display-Modus + Wireframe-Overlay), statt sich per Tab/M neu durchzuklicken.

Persistiert wird NUR das, was die Hotkeys ohnehin setzen. Nicht persistiert:
Komponenten-Modus (1/2/3), Selection-Method (Shift+M), Mesh, Selection,
Undo-History, Kamera, Fenster.

Format (eine JSON-Datei, Version 1):

    {"version": 1,
     "focused_family": "knife_face",
     "variants": {"selection": "FaceSelectModifierExperiment", ...},
     "display": {"mode": "WIREFRAME", "wireframe_overlay": false}}

Varianten werden über einen stabilen String identifiziert, nie über den Index
(Registrierungsreihenfolge darf sich ändern). Die Varianten tragen keine eigene
ID (`Experiment.id` ist je Family gleich, `Experiment.variant` ist ein
Anzeige-Label) — als Schlüssel dient deshalb der Klassenname der Variante,
siehe `variant_key()`.

Robustheit: Laden/Anwenden wirft nie. Fehlende/kaputte Datei, andere Version,
unbekannte Family/Variante → betroffene Einträge werden ignoriert (Registry-
Default bleibt), eine Logzeile. Wiederherstellung läuft über dieselben Wege wie
ein manueller Wechsel (`app.activate_variant`, `focused_family`, DisplayState-
Setter) — kein paralleler State-Setter.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from playground._paths import ensure_paths

ensure_paths()

from mirai.viewport.display import DisplayMode  # noqa: E402

_log = logging.getLogger(__name__)

STATE_VERSION = 1

# Neben den übrigen Playground-Dateien; in .gitignore eingetragen (user-lokal).
DEFAULT_STATE_PATH = Path(__file__).resolve().parent / ".session_state.json"

# CLI-Flag am Einstiegspunkt (run.py): Start mit reinen Registry-Defaults.
RESET_FLAG = "--reset-state"


def variant_key(entry) -> str:
    """Stabiler String-Schlüssel einer Variante (`VariantEntry`)."""
    return type(entry.experiment).__name__


# -- Capture / Apply ----------------------------------------------------------

def capture(app) -> dict:
    """Aktuellen persistierbaren Zustand der `PlaygroundApp` als dict."""
    display = app.display_state
    return {
        "version": STATE_VERSION,
        "focused_family": app.focused_family,
        "variants": {fid: variant_key(slot.active) for fid, slot in app.slots.items()},
        "display": {
            "mode": display.mode.name,
            "wireframe_overlay": bool(display.wireframe_overlay),
        },
    }


def apply(app, state: dict) -> list[str]:
    """Zustand auf die App anwenden; gibt die übersprungenen Einträge zurück.

    Reihenfolge ist relevant: Presentation-Varianten setzen Display-Modus und
    Overlay selbst zurück, deshalb kommt der gespeicherte Display-Zustand erst
    NACH den Varianten.
    """
    skipped: list[str] = []

    variants = state.get("variants")
    if isinstance(variants, dict):
        for family_id, key in variants.items():
            slot = app.slots.get(family_id)
            if slot is None:
                skipped.append(f"family '{family_id}'")
                continue
            index = next(
                (i for i, entry in enumerate(slot.variants) if variant_key(entry) == key),
                None,
            )
            if index is None:
                skipped.append(f"variant '{family_id}/{key}'")
                continue
            try:
                app.activate_variant(family_id, index)
            except Exception as exc:  # Variante darf den Start nie verhindern
                skipped.append(f"variant '{family_id}/{key}' ({exc!r})")
    elif variants is not None:
        skipped.append("variants")

    display = state.get("display")
    if isinstance(display, dict):
        mode = display.get("mode")
        if isinstance(mode, str) and mode in DisplayMode.__members__:
            app.display_state.set_mode(DisplayMode[mode])
        elif mode is not None:
            skipped.append(f"display mode '{mode}'")
        overlay = display.get("wireframe_overlay")
        if isinstance(overlay, bool):
            app.display_state.set_wireframe_overlay(overlay)
        elif overlay is not None:
            skipped.append("wireframe_overlay")
    elif display is not None:
        skipped.append("display")

    focused = state.get("focused_family")
    if isinstance(focused, str) and focused in app.slots:
        app.focused_family = focused
    elif focused is not None:
        skipped.append(f"focused_family '{focused}'")

    # Wie nach einem manuellen M in der fokussierten Family: deren aktive
    # Variante ist auch `app.active_experiment` (draw-Hook / HUD). No-op im Slot.
    slot = app.slots.get(app.focused_family)
    if slot is not None:
        app.activate_variant(app.focused_family, slot.active_index)

    return skipped


# -- Datei-I/O ----------------------------------------------------------------

def load(path: Path) -> dict | None:
    """State-Datei lesen. `None` bei fehlender/kaputter Datei oder anderer Version."""
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        _log.warning("[SESSION] no saved state (%s) — using defaults", path)
        return None
    except OSError as exc:
        _log.warning("[SESSION] state file unreadable (%s) — using defaults", exc)
        return None
    try:
        state = json.loads(raw)
    except ValueError as exc:
        _log.warning("[SESSION] state file corrupt (%s) — using defaults", exc)
        return None
    if not isinstance(state, dict) or state.get("version") != STATE_VERSION:
        version = state.get("version") if isinstance(state, dict) else None
        _log.warning(
            "[SESSION] state version %r != %d — using defaults", version, STATE_VERSION
        )
        return None
    return state


def save(path: Path, state: dict) -> bool:
    """State atomar schreiben (Temp-Datei + Replace). Wirft nie; `False` bei Fehler."""
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
        return True
    except OSError as exc:
        _log.warning("[SESSION] could not save state (%s)", exc)
        try:
            tmp.unlink()
        except OSError:
            pass
        return False


def restore(app, path: Path) -> bool:
    """Datei laden und auf die App anwenden. `True`, wenn ein State angewendet wurde."""
    state = load(path)
    if state is None:
        return False
    skipped = apply(app, state)
    if skipped:
        _log.warning("[SESSION] ignored unknown entries: %s", ", ".join(skipped))
    return True


def save_app(app, path: Path) -> bool:
    """Aktuellen Zustand der App in die Datei schreiben."""
    return save(path, capture(app))
