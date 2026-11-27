"""LikenessSession (AD-042 §4.2): the session's likeness cameras and the camera view - pure state.

No GL, no `Application` import (the `LookdevRoom` pattern) and **no interaction session**: the camera view changes
no gesture (LC-D1, like LookDev). `Application` drives it (`look_through`, `leave_camera_view`, the setters).

- `cameras`, `active` (the camera the SPACE row looks through: the last one created or looked through);
- `view`: while looking through, the camera's index and the saved free view;
- the session view values `overscan`, `photo_opacity`, `photo_shown`, `passepartout`;
- `pending_photo`: the two-step load (the status line is drawn before a long decode, AD-042 §8.1);
- a serial counter for photos.

The session survives a scene load (it is not document data, Q-LC-3); the camera view does not (§5.5).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..likeness import FreeView, LikenessCamera
from ..viewport.lens import OVERSCAN_DEFAULT

NAME_LIMIT = 40
PASSEPARTOUT_DEFAULT = 0.5


@dataclass
class CameraView:
    index: int
    saved: FreeView


class LikenessSession:
    def __init__(self) -> None:
        self.cameras: list[LikenessCamera] = []
        self.active: int | None = None
        self.view: CameraView | None = None
        self.overscan = OVERSCAN_DEFAULT
        self.photo_opacity = 1.0
        self.photo_shown = True
        self.passepartout = PASSEPARTOUT_DEFAULT
        self.pending_photo: tuple[int, Path] | None = None
        self.pending_frames = 0  # ticks left before the pending photo decodes
        self._serial = 0

    def reset(self) -> None:
        """A scene replacement (Q-LC-3: the cameras belong to the scene): no camera, the view values at their defaults;
        the serial counter keeps counting (a viewport never sees a serial twice). The caller left the camera view."""
        serial = self._serial
        self.__init__()
        self._serial = serial

    @property
    def viewing(self) -> LikenessCamera | None:
        """The camera looked through, None = the free view."""
        return None if self.view is None else self.cameras[self.view.index]

    @property
    def active_camera(self) -> LikenessCamera | None:
        return None if self.active is None else self.cameras[self.active]

    def next_serial(self) -> int:
        self._serial += 1
        return self._serial

    def next_name(self) -> str:
        """„Kamera n“ with the lowest unused n."""
        used = {cam.name for cam in self.cameras}
        n = 1
        while f"Kamera {n}" in used:
            n += 1
        return f"Kamera {n}"

    def add(self, camera: LikenessCamera) -> int:
        self.cameras.append(camera)
        self.active = len(self.cameras) - 1
        return self.active

    def remove(self, index: int) -> LikenessCamera:
        """Drop a camera (the caller has left its camera view); the indices after it shift down."""
        camera = self.cameras.pop(index)
        if self.view is not None and self.view.index > index:
            self.view.index -= 1
        if self.pending_photo is not None:
            pending = self.pending_photo[0]
            self.pending_photo = None if pending == index else (
                (pending - 1, self.pending_photo[1]) if pending > index else self.pending_photo)
        if self.active is not None:
            if self.active == index:
                self.active = (min(index, len(self.cameras) - 1)) if self.cameras else None
            elif self.active > index:
                self.active -= 1
        return camera
