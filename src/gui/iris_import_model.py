"""The Eye Lab's iris import, pure logic (Eye LookDev phase 5, Manu 2026-11-16; AD-033 §19). No pyglet, no imgui.

An `ImportDraft` is the import dialog's own state while the artist sets it up - the source image, its kind, the two
landmark circles and the options. It is UI state: not saved, no Undo, never part of the document. Only "Importieren"
changes the document, through `Application.import_eye_iris` (one Undo step).

The circles start at `iris_import.estimate`'s suggestion (or a neutral guess when it finds none) and the artist
corrects both: drag a circle's centre handle to move it (both circles together while their centres coincide), its
edge handle or its line to change its radius (`pick_handle`, `drag_handle`), or type the values. For a frontal photo `edge_check` says whether the iris looks radially symmetric.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from mirai import iris_import as ii

KIND_LABELS = {"photo": "Frontales Foto", "flat": "Flach / ungebrochen / gemalt"}
assert tuple(KIND_LABELS) == ii.SOURCES
#: Handles: (circle, part); the edge handle sits on the circle's right.
HANDLES = (("pupil", "centre"), ("pupil", "edge"), ("iris", "centre"), ("iris", "edge"))


@dataclass(frozen=True)
class ImportDraft:
    path: Path
    rgba: np.ndarray
    marks: ii.Landmarks
    kind: str = "photo"
    correct: bool = True
    keep_alpha: bool = False
    hold_outer_color: bool = True
    estimated: str = ""  # "" = the circles are the estimate's; else why there was none
    hint: str = ""  # the symmetry check's hint (frontal photos only)

    @property
    def size(self) -> tuple[int, int]:
        """(width, height) in pixels."""
        return self.rgba.shape[1], self.rgba.shape[0]

    @property
    def has_alpha(self) -> bool:
        return ii.has_alpha(self.rgba)

    @property
    def problem(self) -> str:
        return self.marks.problem()

    @property
    def summary(self) -> str:
        w, h = self.size
        p, i = self.marks.pupil, self.marks.iris
        return (f"{self.path.name}: {w} x {h} px, Pupille r {p.r:.1f}, Iris r {i.r:.1f} px"
                + ("" if not self.estimated else f" (kein Vorschlag: {self.estimated})"))


def _guess(rgba: np.ndarray) -> ii.Landmarks:
    h, w = rgba.shape[:2]
    half = 0.5 * min(w, h)
    return ii.Landmarks(ii.Circle(w / 2, h / 2, 0.25 * half), ii.Circle(w / 2, h / 2, ii.TARGET_SHARE * half))


def open_draft(path: str | Path) -> tuple[ImportDraft | None, str]:
    """Read the image and suggest the circles. (draft, "") or (None, why it cannot be read)."""
    path = Path(str(path).strip().strip('"'))
    if not path.is_file():
        return None, f"{path} nicht gefunden"
    try:
        rgba = ii.read_rgba(path)
    except (OSError, ValueError) as exc:
        return None, f"{path.name}: {exc}"
    marks, why = ii.estimate(rgba)
    draft = ImportDraft(path, rgba, marks or _guess(rgba), estimated=why if marks is None else "")
    return checked(draft), ""


def checked(draft: ImportDraft) -> ImportDraft:
    """The symmetry hint for the draft's current circles (frontal photos only)."""
    if draft.kind != "photo" or draft.problem:
        return replace(draft, hint="")
    return replace(draft, hint=ii.edge_check(draft.rgba, draft.marks)[2])


def with_options(draft: ImportDraft, **changes) -> ImportDraft:
    assert set(changes) <= {"kind", "correct", "keep_alpha", "hold_outer_color"}
    if changes.get("kind", draft.kind) not in ii.SOURCES:
        raise ValueError(changes["kind"])
    return checked(replace(draft, **changes))


def reestimate(draft: ImportDraft) -> ImportDraft:
    marks, why = ii.estimate(draft.rgba)
    return checked(replace(draft, marks=marks or draft.marks, estimated=why if marks is None else ""))


def set_circle(draft: ImportDraft, circle: str, **values) -> ImportDraft:
    """A typed value: `circle` "pupil" / "iris", any of x, y, r (pixels)."""
    assert circle in ("pupil", "iris") and set(values) <= {"x", "y", "r"}
    moved = getattr(draft.marks, circle).moved(**values)
    return checked(replace(draft, marks=replace(draft.marks, **{circle: moved})))


def handle_positions(marks: ii.Landmarks) -> dict[tuple[str, str], tuple[float, float]]:
    """Every handle's image position (pixels)."""
    out = {}
    for name in ("pupil", "iris"):
        c = getattr(marks, name)
        out[(name, "centre")] = (c.x, c.y)
        out[(name, "edge")] = (c.x + c.r, c.y)
    return out


def pick_handle(marks: ii.Landmarks, x: float, y: float, tolerance: float) -> tuple[str, str] | None:
    """The handle nearest to (x, y) within `tolerance` pixels; the pupil's before the iris's when both are as near.
    Without a handle near: the edge of the nearer circle line (so a circle can be grabbed anywhere on its line)."""
    p, i = marks.pupil, marks.iris
    if math.hypot(p.x - i.x, p.y - i.y) < tolerance and math.hypot(x - p.x, y - p.y) < tolerance:
        return ("both", "centre")  # the centres on top of each other: move the whole eye (type a value to split them)
    best, best_d = None, tolerance
    for handle, (hx, hy) in handle_positions(marks).items():
        d = math.hypot(x - hx, y - hy)
        if d < best_d:
            best, best_d = handle, d
    if best is not None:
        return best
    for name in ("pupil", "iris"):
        c = getattr(marks, name)
        if abs(math.hypot(x - c.x, y - c.y) - c.r) < tolerance:
            return (name, "edge")
    return None


def drag_handle(draft: ImportDraft, handle: tuple[str, str], x: float, y: float, check: bool = False) -> ImportDraft:
    """The handle dragged to (x, y): a centre moves its circle, an edge sets its radius (the distance to the centre).
    `check` recomputes the symmetry hint (on release; it samples the image)."""
    name, part = handle
    if name == "both":
        p, i = draft.marks.pupil, draft.marks.iris
        marks = ii.Landmarks(p.moved(x=x, y=y), i.moved(x=i.x + x - p.x, y=i.y + y - p.y))
        out = replace(draft, marks=marks)
        return checked(out) if check else out
    c = getattr(draft.marks, name)
    moved = c.moved(x=x, y=y) if part == "centre" else c.moved(r=math.hypot(x - c.x, y - c.y))
    out = replace(draft, marks=replace(draft.marks, **{name: moved}))
    return checked(out) if check else out


def run_import(app, draft: ImportDraft) -> bool:
    """"Importieren": the document changes here only (`Application.import_eye_iris`, one Undo step)."""
    return app.import_eye_iris(draft.path, draft.marks, draft.kind, correct=draft.correct,
                               keep_alpha=draft.keep_alpha and draft.has_alpha,
                               hold_outer_color=draft.hold_outer_color)
