"""Suggest `out/iris_custom.json` for an iris image (2026-11-14): estimates the image's pupil edge and iris edge with the
profile method of `iris_fit` and **prints** them. It writes nothing; the JSON file is yours to write.

Usage (from the repo root):
    python experiments/lookdev_eye_lab/suggest_iris_fit.py                  # out/iris_custom.png
    python experiments/lookdev_eye_lab/suggest_iris_fit.py path/to/iris.png
"""

from __future__ import annotations

import json
import sys
import zlib
from pathlib import Path

_EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
if str(_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS_DIR))

from lookdev_eye_lab._paths import OUT_DIR, ensure_paths  # noqa: E402

ensure_paths()

from lookdev_eye_lab import iris_fit  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    path = Path(argv[0]) if argv else OUT_DIR / "iris_custom.png"
    try:
        pupil, limbus = iris_fit.estimate(iris_fit.read_png_rgb(path))
    except (OSError, ValueError, zlib.error) as exc:
        print(f"{path}: cannot estimate ({exc})")
        return 1
    print(f"{path}: estimated pupil edge {pupil}, iris edge {limbus} (shares of half the image width; "
          f"the lab has the pupil edge at {iris_fit.LAB_PUPIL_SHARE:.3f})")
    if pupil is None or limbus is None:
        print("no suggestion: a threshold was never met (the method expects a dark pupil and a white background)")
        return 1
    print(f"suggestion - check it, then write it yourself to {path.parent / iris_fit.SIDECAR_NAME}:")
    print(json.dumps({"pupil": round(pupil, 3), "limbus": round(limbus, 3)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
