"""Brücke vom Production-Fenster ins Morph Lab (`PROVISIONAL`, Manu 2026-10-17).

Taste `M` in `src/main.py` schickt das ausgewählte Objekt ins Morph Lab: Basis und Ziel stehen
dort sofort (das Lab baut das Paar selbst, `experiments/morph_lab/run.py --von`).

Welches Objekt: in Modus `4` das eine ausgewählte Objekt (mehrere oder keines: Statuszeile,
nichts passiert), sonst das Edit-Objekt. Das Objekt wird als Ein-Objekt-Szenendatei nach
`scenes/morph_lab/von_main/<name>.mirai.json` geschrieben (Format `core.serialization`; die
Platzierung des Objekts geht nicht mit, das Lab setzt die Basis auf die Identität) und das Lab
als eigener Prozess mit eigenem Fenster gestartet. Das Production-Fenster bleibt unverändert,
kein History-Eintrag.

Morph-Ziele (AD-025 Phase 3, `PROVISIONAL`): Production und Lab bestehen nebeneinander. Hat das Mesh
ein Production-Ziel, nimmt die Datei es mit (Punkt-Layer); das Lab baut daraus sein Paar - Basis =
die Ruheform, „Ziel 1“ = Ruheform + Offsets des ersten Ziels, beide ohne Layer
(`lab_scene.build_pair_scene`). Das Lab bleibt eine Einweg-Kopie: nichts kommt zurück. Während das
Ziel daneben bearbeitet wird, geht die Basis (die Ansicht ist flüchtig).

Dieses Modul importiert kein pyglet und kein `experiments/`: es kennt nur den Pfad zu `run.py` und dessen Option `--von` (`main.py` kennt kein Experiment, CLAUDE.md).
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from core.ids import ObjectId
from core.mesh import Mesh
from core.scene import Scene, SceneObject
from core.selection import SelectionMode
from core.serialization import scene_to_json

_ROOT = Path(__file__).resolve().parent.parent
LAB_RUN = _ROOT / "experiments" / "morph_lab" / "run.py"
#: Ordner der gesendeten Objekte, unter dem Lab-Ordner (der das SPACE-Menü nicht listet).
DEFAULT_SEND_DIR = _ROOT / "scenes" / "morph_lab" / "von_main"


def launch_lab(scene_file: Path) -> None:
    """Startet das Morph Lab als eigenen Prozess; er läuft weiter, wenn dieses Fenster schließt."""
    subprocess.Popen(
        [sys.executable, str(LAB_RUN), "--von", str(scene_file)],
        cwd=str(_ROOT),
        start_new_session=True,
    )


def pick_object(app) -> SceneObject | None:
    """Das zu sendende Objekt, oder None mit Grund in der Statuszeile (siehe Modul)."""
    scene = app.scene
    if app.selection.mode is not SelectionMode.OBJECT:
        # AD-025 Phase 3: while a target's editing view is open, the base (the view is transient).
        return getattr(app, "morph_document_object", scene.edit_object)
    chosen = [scene.objects[oid] for oid in sorted(app.selection.objects) if oid in scene.objects]
    if len(chosen) != 1:
        app.set_status("Morph Lab: select exactly one object (mode 4), or leave mode 4 for the edited one")
        return None
    return chosen[0]


def write_object_scene(obj: SceneObject, directory: Path = DEFAULT_SEND_DIR) -> Path:
    """Das Objekt (Mesh-Kopie, gleiche Namen) als Ein-Objekt-Szene; überschreibt gleichnamige."""
    mesh = Mesh.from_state(obj.mesh.export_state())
    one = SceneObject(ObjectId(0), mesh, name=obj.name)
    scene = Scene.from_objects([one], edit_object_id=one.id, object_id_counter=1)
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", obj.name).strip("_") or "objekt"
    path = Path(directory) / f"{stem}.mirai.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(scene_to_json(scene), encoding="utf-8")
    tmp.replace(path)
    return path


def send_to_morph_lab(
    app,
    directory: Path = DEFAULT_SEND_DIR,
    launcher: Callable[[Path], object] = launch_lab,
) -> Path | None:
    """`M`: das ausgewählte Objekt ins Morph Lab. Gibt die geschriebene Datei zurück, None =
    nichts gesendet (Grund in der Statuszeile). Abgelehnt, solange eine Interaktion die Tasten
    hält (wie Strg+S): mitten in W/E/R/T oder dem Knife stünde ein halber Zustand im Mesh."""
    owner = app.interaction_owner
    if owner is not None:
        app.set_status(f"Morph Lab: not while the {owner} interaction runs")
        return None
    obj = pick_object(app)
    if obj is None:
        return None
    try:
        path = write_object_scene(obj, directory)
        launcher(path)
    except Exception as exc:  # disk full, no python, ...: one visible line, the scene stays as is
        app.set_status(f"Morph Lab failed: {exc}")
        return None
    app.set_status(f"Morph Lab: {obj.name!r} sent")
    return path
