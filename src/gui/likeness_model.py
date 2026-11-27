"""Pure logic of the panel „Kamera“ (AD-042 §8.2): labels, rows, ranges, enabled states - tested headless.

The panel (`likeness_panel`) only draws this and calls `Application`; it holds no state of its own. Lens and photo rows
edit the **active** camera; without a camera only „Neu aus Ansicht“ is enabled. The cameras are saved with the scene
(`view.likeness`, Q-LC-3); no Undo.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mirai.viewport import lens as lens_math

TITLE = "Kamera"
NEW = "Neu aus Ansicht"
LOOK = "Durchschauen"
LEAVE = "Verlassen"
DELETE = "Löschen"
FIX = "Kamera fixieren"
LOAD = "Laden …"
TURN = "90° drehen"
REMOVE = "Entfernen"
SHOW = "Foto ein"
MORE = "Mehr"
FOCAL_BUTTONS = (24, 35, 50, 85, 105, 135, 200)
SENSOR_LABELS = {**{key: label for key, (label, *_rest) in lens_math.SENSORS.items()}, lens_math.CUSTOM: "eigene"}
FIT_LABELS = {"auto": "Auto", "width": "Breite", "height": "Höhe", "diagonal": "Diagonale"}
HINT_FOCAL = "Fotos ab 50 mm KB vergleichen sich am besten"
HINT_SESSION = "Kameras werden mit der Szene gespeichert, Fotos als Kopie in <Szene>_photos/ (kein Rückgängig)"
FIX_HINT = "Navigation verlässt die Kameraansicht und beginnt an der Kamera; die Kamera bleibt (Durchschauen kehrt zurück)"
FRAMING_HINT = "Kameraansicht: die Kamera ist die Rahmung"
EYE_FRAMING_HINT = "erst Kameraansicht verlassen"
MENU_ENTER = "Kameraansicht"
MENU_LEAVE = "Kameraansicht verlassen"
#: The overscan slider („Rand“) and the clip fields' ranges.
OVERSCAN_RANGE = lens_math.OVERSCAN_RANGE
FOCAL_RANGE = lens_math.FOCAL_RANGE_MM


@dataclass(frozen=True)
class CameraRow:
    index: int
    name: str
    active: bool
    viewing: bool
    look_label: str  # „Durchschauen“ or „Verlassen“


@dataclass(frozen=True)
class LensRow:
    focal_mm: float
    sensor: str
    sensor_label: str
    fit: str
    sensor_w_mm: float
    sensor_h_mm: float
    custom: bool
    clip_near: float
    clip_far: float


@dataclass(frozen=True)
class PhotoRow:
    loaded: bool
    line: str  # file name and size, or „kein Foto“
    pending: bool


@dataclass(frozen=True)
class PanelState:
    rows: tuple[CameraRow, ...]
    has_camera: bool
    viewing: bool
    lens: LensRow | None
    photo: PhotoRow | None
    fixed: bool
    distance_line: str
    angles_line: str
    overscan: float
    photo_opacity: float
    photo_shown: bool


def _decimal(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def distance_line(distance: float) -> str:
    """„6,2 Einheiten · ≈ 0,06 m bei 1 Einheit = 1 cm“."""
    return f"{_decimal(distance)} Einheiten · ≈ {_decimal(distance / 100.0, 2)} m bei 1 Einheit = 1 cm"


def angles_line(lens: lens_math.Lens, photo_size: tuple[int, int] | None) -> str:
    """The gate's angles, vertical × horizontal („16,1° × 23,9°“)."""
    h, v = lens_math.gate_angles_degrees(lens, lens_math.frame_aspect(lens, photo_size))
    return f"{_decimal(v)}° × {_decimal(h)}°"


def state(app) -> PanelState:
    session = app.likeness
    view = session.view
    rows = tuple(
        CameraRow(i, cam.name, i == session.active, view is not None and view.index == i,
                  LEAVE if view is not None and view.index == i else LOOK)
        for i, cam in enumerate(session.cameras))
    cam = session.active_camera
    lens = photo = None
    fixed, dist, angles = False, "", ""
    if cam is not None:
        ln = cam.lens
        lens = LensRow(ln.focal_mm, ln.sensor, SENSOR_LABELS.get(ln.sensor, ln.sensor), ln.fit, ln.sensor_w_mm,
                       ln.sensor_h_mm, ln.sensor == lens_math.CUSTOM, cam.clip_near, cam.clip_far)
        pending = session.pending_photo is not None and session.pending_photo[0] == session.active
        if cam.photo is None:
            if pending:
                line = "wird geladen …"
            elif cam.photo_missing is not None:
                line = f"fehlt: {Path(cam.photo_missing[0]).name}"
            else:
                line = "kein Foto"
            photo = PhotoRow(False, line, pending)
        else:
            w, h = cam.photo.size
            line = f"{cam.photo.path.name} · {w} × {h}"
            if cam.photo.source_size != (w, h) and sorted(cam.photo.source_size) != sorted((w, h)):
                line += f" (aus {cam.photo.source_size[0]} × {cam.photo.source_size[1]})"
            photo = PhotoRow(True, line, pending)
        fixed = cam.fixed
        dist = distance_line(cam.distance)
        angles = angles_line(ln, None if cam.photo is None else cam.photo.size)
    return PanelState(rows, cam is not None, view is not None, lens, photo, fixed, dist, angles, session.overscan,
                      session.photo_opacity, session.photo_shown)


def framing_locked(app) -> bool:
    """The LookDev framing buttons and „Auge rahmen“ are disabled in the camera view (AD-042 §5.5)."""
    return app.camera_view_open


def menu_label(app) -> str | None:
    """The SPACE row, shown once a camera exists."""
    session = app.likeness
    if session.view is not None:
        return MENU_LEAVE
    return MENU_ENTER if session.cameras else None


def toggle_row(app, index: int) -> bool:
    """„Durchschauen“ / „Verlassen“ of a row."""
    view = app.likeness.view
    if view is not None and view.index == index:
        return app.leave_camera_view()
    return app.look_through(index)
