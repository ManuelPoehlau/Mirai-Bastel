"""The eye's optics (AD-033 §5): derived geometry and the NumPy references of every function the eye pass's GLSL
computes. GL-free. Promoted from `experiments/lookdev_eye_lab/` (`cornea_optics.py`, `iris_fit.py`,
`limbus_model.py`, Manu's go 2026-11-15, Q-E1); the lab stays frozen as the oracle and its tests compare it with this
module. Nothing here imports `experiments/` (AGENTS.md §8a).

Eye-local units: 1 = the sclera radius (the reference eye: 12 mm); the eye looks down +Z, centred at the origin.

**Geometry** (`EyeGeometry.from_values`): the anterior cornea is a sphere of `cornea_radius` whose rim is the limbus
circle (radius `limbus_radius`, on the unit sphere); the posterior cornea a sphere of 6.6 mm with 0.55 mm central
thickness; the iris a shallow cone `z = a + b r` from the pupil edge (`iris_concavity` behind the root) to its root
`iris_root_z`, its radius just inside the sclera wall; the chamber angle where the posterior sphere meets that cone.
These are the lab's values (P1b), unchanged.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

MM = 1.0 / 12.0
N_AIR = 1.0
N_CORNEA = 1.376
N_AQUEOUS = 1.336
N_EFFECTIVE = 1.3375
POSTERIOR_RADIUS = 6.6 * MM
CENTRAL_THICKNESS = 0.55 * MM
#: The iris root sits this far inside the sclera wall (the lab's gap: a root on the wall poked through as a dark ring).
IRIS_ROOT_GAP = 0.002
MISS, IRIS, PUPIL, LIMBUS = 0, 1, 2, 3
EPS = 1e-6


@dataclass(frozen=True)
class EyeGeometry:
    cornea_radius: float
    limbus_radius: float
    iris_root_z: float
    iris_concavity: float
    pupil_radius: float

    @classmethod
    def from_values(cls, spec) -> "EyeGeometry":
        """From anything with the five anatomy fields (`core.EyeSpec`)."""
        return cls(spec.cornea_radius, spec.limbus_radius, spec.iris_root_z, spec.iris_concavity, spec.pupil_radius)

    @property
    def limbus_z(self) -> float:
        return math.sqrt(1.0 - self.limbus_radius ** 2)

    @property
    def anterior_centre_z(self) -> float:
        return self.limbus_z - math.sqrt(self.cornea_radius ** 2 - self.limbus_radius ** 2)

    @property
    def apex_z(self) -> float:
        return self.anterior_centre_z + self.cornea_radius

    @property
    def posterior_centre_z(self) -> float:
        return self.apex_z - CENTRAL_THICKNESS - POSTERIOR_RADIUS

    @property
    def iris_radius(self) -> float:
        return math.sqrt(1.0 - self.iris_root_z ** 2) - IRIS_ROOT_GAP

    @property
    def iris_b(self) -> float:
        return self.iris_concavity / (self.iris_radius - self.pupil_radius)

    @property
    def iris_a(self) -> float:
        return self.iris_root_z - self.iris_b * self.iris_radius

    def iris_z(self, r):
        return self.iris_a + self.iris_b * np.asarray(r, dtype=np.float64)

    def posterior_z(self, r):
        r = np.asarray(r, dtype=np.float64)
        return self.posterior_centre_z + np.sqrt(np.maximum(POSTERIOR_RADIUS ** 2 - r * r, 0.0))

    def anterior_z(self, r):
        r = np.asarray(r, dtype=np.float64)
        return self.anterior_centre_z + np.sqrt(np.maximum(self.cornea_radius ** 2 - r * r, 0.0))

    @property
    def angle(self) -> tuple[float, float]:
        """(r, z) where the posterior sphere meets the iris cone: the chamber angle (bisection, as the lab)."""
        lo, hi = 0.0, POSTERIOR_RADIUS
        for _ in range(80):
            mid = 0.5 * (lo + hi)
            if float(self.posterior_z(mid)) > float(self.iris_z(mid)):
                lo = mid
            else:
                hi = mid
        return lo, float(self.iris_z(lo))
