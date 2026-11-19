"""The LookDev studio presets (AD-038 §6, proposal §8.2) as data - values `PROVISIONAL`, tuned in the M1 practical test.

A preset is a `viewport.lookdev_optics.LookdevState`: the studio's content (dome + soft rectangles, linear radiance), the
key / fill / rim (relative intensity, direction in the studio frame, Kelvin, size), environment intensity, exposure
(EV), tone curve and the background (display values, shown as picked - LD-D9). The studio is fixed to the world
(LD-D5); "Licht folgt Kamera" is the state's `follow_camera`. Portrait is the default.
"""

from __future__ import annotations

from viewport.lookdev_optics import LookdevState, Softbox, Studio, StudioLight

PORTRAIT = "Portrait"
DEFAULT_PRESET = PORTRAIT

PRESETS: dict[str, LookdevState] = {
    "Neutral Inspection": LookdevState(
        preset="Neutral Inspection",
        studio=Studio((0.32, 0.32, 0.32), (0.26, 0.26, 0.26), (0.16, 0.16, 0.16),
                      (Softbox(0.0, 55.0, 40.0, 25.0, (0.8, 0.8, 0.8)),)),
        key=StudioLight(True, 1.1, 15.0, 50.0, 6000.0, 0.25),
        fill=StudioLight(True, 0.6, -40.0, 10.0, 6500.0, 0.35),
        rim=StudioLight(False, 0.5, 180.0, 30.0, 6500.0, 0.1),
        env_intensity=1.0, exposure=0.0,
        background=((0.30, 0.30, 0.31), (0.30, 0.30, 0.31)), background_gradient=False),
    PORTRAIT: LookdevState(
        preset=PORTRAIT,
        studio=Studio((0.06, 0.06, 0.065), (0.04, 0.04, 0.045), (0.015, 0.015, 0.015),
                      (Softbox(45.0, 30.0, 30.0, 22.0, (1.2, 1.15, 1.1)),
                       Softbox(-150.0, 20.0, 6.0, 35.0, (1.0, 1.0, 1.05)))),
        key=StudioLight(True, 1.6, 45.0, 30.0, 5600.0, 0.10),
        fill=StudioLight(True, 0.55, -60.0, 5.0, 6500.0, 0.25),
        rim=StudioLight(True, 1.4, -150.0, 25.0, 7500.0, 0.05),
        env_intensity=1.0, exposure=0.0,
        background=((0.04, 0.04, 0.045), (0.16, 0.16, 0.17)), background_gradient=True),
    "Soft Studio": LookdevState(
        preset="Soft Studio",
        studio=Studio((0.45, 0.45, 0.46), (0.30, 0.30, 0.30), (0.12, 0.12, 0.12),
                      (Softbox(35.0, 25.0, 35.0, 28.0, (1.6, 1.6, 1.55)),
                       Softbox(-55.0, 15.0, 30.0, 25.0, (0.9, 0.9, 0.95)))),
        key=StudioLight(True, 1.2, 35.0, 25.0, 6000.0, 0.35),
        fill=StudioLight(True, 0.6, -55.0, 10.0, 6500.0, 0.4),
        rim=StudioLight(True, 0.4, -160.0, 20.0, 7000.0, 0.15),
        env_intensity=1.0, exposure=0.0,
        background=((0.62, 0.62, 0.63), (0.62, 0.62, 0.63)), background_gradient=False),
    "Dramatic": LookdevState(
        preset="Dramatic",
        studio=Studio((0.01, 0.01, 0.012), (0.006, 0.006, 0.007), (0.002, 0.002, 0.002),
                      (Softbox(-140.0, 15.0, 5.0, 30.0, (1.5, 1.5, 1.6)),)),
        key=StudioLight(True, 2.2, 70.0, 20.0, 4800.0, 0.03),
        fill=StudioLight(True, 0.25, -70.0, 0.0, 6500.0, 0.3),
        rim=StudioLight(True, 2.0, -140.0, 25.0, 8000.0, 0.03),
        env_intensity=1.0, exposure=0.0,
        background=((0.01, 0.01, 0.012), (0.03, 0.03, 0.035)), background_gradient=True),
}
PRESET_NAMES = tuple(PRESETS)


def preset(name: str) -> LookdevState:
    try:
        return PRESETS[name]
    except KeyError:
        raise ValueError(f"LookDev studio: no preset {name!r} ({', '.join(PRESET_NAMES)})") from None
