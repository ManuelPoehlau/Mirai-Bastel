"""Lookdev P1b - Corneal Refraction Lab (2026-11-14). The P1 window plus the refraction variants; P1 is unchanged.

Usage (from the repo root):
    python experiments/lookdev_eye_lab/run_refraction.py                  # interactive window
    python experiments/lookdev_eye_lab/run_refraction.py --probe          # measurements + contact sheets
    python experiments/lookdev_eye_lab/run_refraction.py --refraction V3 --view three_quarter

Keys: every P1 key (README "Controls"), plus `8` / `9` / `0` = V1 / V2 / V3 and `J` for the ray-class map (red iris,
green pupil, blue limbal tissue). V2 / V3 need T-B, T-C or T-D (T-A is the production Worklight and has no
refraction).
"""

from __future__ import annotations

import sys
from pathlib import Path

_LAB_DIR = Path(__file__).resolve().parent
if str(_LAB_DIR) not in sys.path:
    sys.path.insert(0, str(_LAB_DIR))

import run  # noqa: E402  (P1's entry point: sets up the paths, LabWindow)

from lookdev_eye_lab import lab_state as ls  # noqa: E402
from lookdev_eye_lab._paths import CACHE_DIR, OUT_DIR  # noqa: E402

REFRACTION_KEYS = {"8": "V1", "9": "V2", "0": "V3"}


def build_parser():
    p = run.build_parser()
    p.description = "Lookdev P1b corneal refraction lab"
    p.add_argument("--refraction", choices=("V1", "V2", "V3"), default="V2")
    return p


class RefractionWindow(run.LabWindow):
    """P1's window with the refraction scene: P1's scene is built by the base class and replaced at once."""

    def __init__(self, args) -> None:
        super().__init__(args)
        from lookdev_eye_lab import refraction_gl as rg

        self.scene.release()
        self.state = rg.RefractionState(technique=args.technique, cornea=args.cornea, view=args.view,
                                        refraction=args.refraction)
        width, height = self.window.get_framebuffer_size()
        self.scene = rg.build_scene(self.state, OUT_DIR, CACHE_DIR, width, height)
        print(self.scene.iris_source.describe(), flush=True)

    def on_key_press(self, symbol, modifiers):
        name = run.key_name(symbol)
        if name in REFRACTION_KEYS:
            self.state.refraction = REFRACTION_KEYS[name]
            return True
        if name == "J":
            self.scene.renderer.debug_kind = not self.scene.renderer.debug_kind
            return True
        return super().on_key_press(symbol, modifiers)

    def draw_hud(self, fw: int, fh: int) -> None:
        describe = ls.describe

        def with_refraction(s):
            note = "" if s.refraction_active or s.refraction == "V1" else " (inactive with T-A)"
            mode = {"V1": "V1 no refraction (P1)", "V2": "V2 one surface, n 1.3375",
                    "V3": "V3 air 1.0 -> cornea 1.376 -> aqueous 1.336"}[s.refraction]
            extra = "   ray-class map (J)" if self.scene.renderer.debug_kind else ""
            return [f"refraction {mode}{note}   keys 8 / 9 / 0{extra}"] + describe(s)

        ls.describe = with_refraction  # P1's HUD reads `ls.describe`; swapped for this one call, P1 stays unchanged
        try:
            super().draw_hud(fw, fh)
        finally:
            ls.describe = describe


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--probe" in argv:
        from lookdev_eye_lab import probe_refraction

        return probe_refraction.main([a for a in argv if a not in ("--probe", "--")])
    args = build_parser().parse_args(argv)
    import pyglet

    RefractionWindow(args)
    pyglet.app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
