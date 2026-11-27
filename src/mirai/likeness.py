"""Likeness camera records (AD-042 §4.1, §5.1, §18): the cameras, their photo and its fit, the saved free view.

Saved with the scene in `view.likeness` (`mirai.likeness_files`, Q-LC-3 / LC-D2 C); no Undo. The pose is
stored in orbit form (target, distance, yaw, pitch), so writing it into the one interactive camera and back is
lossless and every navigation of the free view works on it; M3 maps it to an object transform (LC-D2).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .exif import ExifInfo
from .viewport.lens import Lens
from .viewport.photo_fit import PhotoFit
from .viewport.vecmath import Vec3


@dataclass
class LikenessPhoto:
    path: Path  # where it was read (panel line; after a save: its copy in `<stem>_photos/`)
    rgba: np.ndarray  # (h, w, 4) uint8, top row first, capped (AD-042 §8.1)
    source_size: tuple[int, int]  # (w, h) before the cap (panel line)
    serial: int  # new on every load and quarter turn: the viewport uploads once per serial
    turns: int = 0  # clockwise quarter turns applied to the file's pixels („90° drehen“; saved with the scene)
    exif: ExifInfo = ExifInfo()  # AD-042 §18.4: the file's orientation and focal length (a suggestion only)
    oriented: bool = True  # the EXIF orientation was applied before the turns (False: a file saved by M1)

    @property
    def size(self) -> tuple[int, int]:
        """(w, h) as shown (after the cap and any quarter turn)."""
        return int(self.rgba.shape[1]), int(self.rgba.shape[0])


@dataclass
class LikenessCamera:
    name: str  # „Kamera 1“, „Kamera 2“, ...; renamed in the panel
    target: Vec3  # the pose in orbit form: target, distance, yaw, pitch
    distance: float
    yaw: float
    pitch: float
    lens: Lens
    clip_near: float
    clip_far: float
    photo: LikenessPhoto | None = None
    fixed: bool = False  # LC-D3 „Kamera fixieren“
    photo_fit: PhotoFit = PhotoFit()  # AD-042 §18.3: rotation (LC-D4), offset, crop scale, mirror of the photo
    #: a saved photo that was not found on load: (absolute path, turns), written again on the next save (Q-LC-3)
    photo_missing: tuple[str, int] | None = None
    photo_missing_oriented: bool = True  # that photo's `oriented` flag, written again with it


@dataclass(frozen=True)
class FreeView:
    """The free view saved on entering the camera view, restored bit for bit on leaving (AD-042 §5.1 step 4)."""

    target: Vec3
    distance: float
    yaw: float
    pitch: float
    fov_degrees: float
    ortho: bool
    near: float
    far: float
    clip_follows_distance: bool
    view_name: str | None
    ortho_auto: bool

    @classmethod
    def of(cls, camera, view_name: str | None, ortho_auto: bool) -> "FreeView":
        return cls(tuple(camera.target), camera.distance, camera.yaw, camera.pitch, camera.fov_degrees,
                   bool(camera.ortho), camera.near, camera.far, bool(camera.clip_follows_distance), view_name,
                   bool(ortho_auto))

    def write(self, camera) -> None:
        """The eight camera fields and the clip flag exactly as saved, one revision bump (never the saved number)."""
        camera.target = self.target
        camera.distance = self.distance
        camera.yaw = self.yaw
        camera.pitch = self.pitch
        camera.fov_degrees = self.fov_degrees
        camera.ortho = self.ortho
        camera.near = self.near
        camera.far = self.far
        camera.clip_follows_distance = self.clip_follows_distance
        camera.camera_revision += 1


def default_clip(distance: float) -> tuple[float, float]:
    """Clip of a new likeness camera (AD-042 E3): room for an 8x dolly out and a 100x dolly in."""
    return min(1.0, max(0.05, distance / 100.0)), max(1000.0, 8.0 * distance)
