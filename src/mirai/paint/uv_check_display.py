"""The UV check in the viewport (AD-037 Phase 1a): its state while it shows and the face colours it pushes in place of
the region colours (`Application.toggle_uv_check`). View state only - never saved, no History."""

from __future__ import annotations

from dataclasses import dataclass

from core import FaceId, Mesh

from . import uv_health

#: `PROVISIONAL` (agent-set): red = cannot be painted at all, orange = paints in two places, violet = partly off the image.
UV_CHECK_COLOURS = {
    "unmapped": (0.90, 0.12, 0.10),
    "zero_area": (0.90, 0.12, 0.10),
    "overlapping": (1.00, 0.55, 0.05),
    "outside": (0.62, 0.25, 0.85),
}


def uv_check_tints(health: uv_health.UVHealth) -> dict[FaceId, tuple[float, float, float]]:
    return {face: UV_CHECK_COLOURS[kind] for face, kind in health.problem_faces().items()}


@dataclass
class UVCheckState:
    mesh: Mesh
    watch: object
    health: uv_health.UVHealth

    @classmethod
    def of(cls, mesh: Mesh) -> "UVCheckState":
        return cls(mesh, mesh.watch(), uv_health.check(mesh))

    def stale(self) -> bool:
        """True when topology or UVs changed since the check (a position change only moves the density: kept)."""
        change = self.watch.peek()
        if not (change.faces or change.face_uvs):
            if change.vertices:
                self.watch.take()  # positions only: drop the records, they would only pile up
            return False
        return True
