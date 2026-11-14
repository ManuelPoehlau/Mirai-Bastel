"""Lookdev P1c - soft limbus lab (2026-11-14). P1b's window plus the limbus levels; P1 and P1b are unchanged.

Usage (from the repo root):
    python experiments/lookdev_eye_lab/run_limbus.py                     # interactive window (starts at P1b V2, L0)
    python experiments/lookdev_eye_lab/run_limbus.py --probe             # measurements + contact sheet
    python experiments/lookdev_eye_lab/run_limbus.py --level L3 --view three_quarter

Keys: every P1 / P1b key (README "Controls", `8` / `9` / `0` = V1 / V2 / V3, `J` ray-class map), plus (lab-local, no
`config/keymap.json` entry):
    Q          level L0 -> L1 -> L2 -> L3 (shift: back)
    O          limbal colour source shader / image (the iris image's outer ring)
    N          shader colour preset (P1b dark / grey-blue / grey-brown)
    A          top / bottom asymmetry on / off (independent of the level)
    MINUS      overlap all round 0 / 0.15 / 0.3 / 0.5 mm (independent of the level and the asymmetry; the '-' key on
               QWERTY and QWERTZ alike - '/' is shift+7 on a German layout, which pyglet reports as '7')
    W          band width +0.25 mm (shift: -0.25)
    D          strength +0.1 (shift: -0.1)
    COMMA      normal blend half width +0.1 mm (shift: -0.1)
    PERIOD     translucency falloff x1.25 (shift: /1.25)
The levels act with V2 / V3 and T-B ... T-D; with V1 or T-A the window shows P1 / P1b as they are.
"""

from __future__ import annotations

import sys
from pathlib import Path

_LAB_DIR = Path(__file__).resolve().parent
if str(_LAB_DIR) not in sys.path:
    sys.path.insert(0, str(_LAB_DIR))

import run  # noqa: E402  (P1's entry point: sets up the paths, LabWindow)
import run_refraction  # noqa: E402

from lookdev_eye_lab import lab_state as ls  # noqa: E402
from lookdev_eye_lab import limbus_model as lm  # noqa: E402
from lookdev_eye_lab._paths import CACHE_DIR, OUT_DIR  # noqa: E402


def _clamp(value, lo, hi):
    return max(lo, min(hi, value))


#: name -> (help, action(state, shift)); mutates the LimbusState in place.
LIMBUS_KEYS = {
    "Q": ("limbus level L0 / L1 / L2 / L3 (shift: back)",
          lambda s, shift: setattr(s, "limbus_level", ls.cycle(lm.LEVELS, s.limbus_level, -1 if shift else 1))),
    "O": ("limbal colour source shader / image",
          lambda s, shift: setattr(s, "colour_source", ls.cycle(lm.COLOUR_SOURCES, s.colour_source))),
    "N": ("shader colour preset", lambda s, shift: setattr(s, "shader_colour", ls.cycle(lm.SHADER_COLOURS,
                                                                                         s.shader_colour))),
    "A": ("top / bottom asymmetry on / off", lambda s, shift: setattr(s, "asym", not s.asym)),
    "MINUS": ("overlap all round 0 / 0.15 / 0.3 / 0.5 mm (shift: back)",
              lambda s, shift: setattr(s, "overlap_mm", ls.cycle(lm.OVERLAP_STEPS, s.overlap_mm, -1 if shift else 1))),
    "W": ("band width +0.25 mm (shift: -0.25)",
          lambda s, shift: setattr(s, "band_mm", round(_clamp(s.band_mm + (-0.25 if shift else 0.25), 0.25, 4.0), 2))),
    "D": ("strength +0.1 (shift: -0.1)",
          lambda s, shift: setattr(s, "strength", round(_clamp(s.strength + (-0.1 if shift else 0.1), 0.0, 1.0), 2))),
    "COMMA": ("normal blend half width +0.1 mm (shift: -0.1)",
              lambda s, shift: setattr(s, "normal_mm", round(_clamp(s.normal_mm + (-0.1 if shift else 0.1), 0.1, 2.0),
                                                             2))),
    "PERIOD": ("translucency falloff x1.25 (shift: /1.25)",
               lambda s, shift: setattr(s, "falloff", round(_clamp(s.falloff / 1.25 if shift else s.falloff * 1.25,
                                                                   0.5, 20.0), 3))),
}


def build_parser():
    p = run_refraction.build_parser()
    p.description = "Lookdev P1c soft limbus lab"
    p.add_argument("--level", choices=lm.LEVELS, default="L0")
    return p


class LimbusWindow(run_refraction.RefractionWindow):
    """P1b's window with the limbus scene (P1b's scene is built by the base class and replaced at once)."""

    def __init__(self, args) -> None:
        super().__init__(args)
        from lookdev_eye_lab import limbus_gl as lg

        self.scene.release()
        self.state = lg.LimbusState(technique=args.technique, cornea=args.cornea, view=args.view,
                                    refraction=args.refraction, limbus_level=args.level)
        width, height = self.window.get_framebuffer_size()
        self.scene = lg.build_scene(self.state, OUT_DIR, CACHE_DIR, width, height)
        self.window.set_caption("Mirai Lookdev P1c - soft limbus (lab)")
        print(self.scene.iris_source.describe(), flush=True)

    def on_key_press(self, symbol, modifiers):
        from pyglet.window import key

        name = run.key_name(symbol)
        if name in LIMBUS_KEYS:
            LIMBUS_KEYS[name][1](self.state, bool(modifiers & key.MOD_SHIFT))
            return True
        return super().on_key_press(symbol, modifiers)

    def draw_hud(self, fw: int, fh: int) -> None:
        from lookdev_eye_lab import limbus_gl as lg

        describe = ls.describe

        def with_limbus(s):
            lines = lg.describe(s, self.scene.renderer)
            if self.help:
                lines += [f"{name:>6}  {text}" for name, (text, _fn) in LIMBUS_KEYS.items()]
            return lines + describe(s)

        ls.describe = with_limbus  # the P1b HUD wraps `ls.describe` again; P1 / P1b stay unchanged
        try:
            super().draw_hud(fw, fh)
        finally:
            ls.describe = describe


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--probe" in argv:
        from lookdev_eye_lab import probe_limbus

        return probe_limbus.main([a for a in argv if a not in ("--probe", "--")])
    args = build_parser().parse_args(argv)
    import pyglet

    LimbusWindow(args)
    pyglet.app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
