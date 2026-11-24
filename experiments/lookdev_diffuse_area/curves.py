"""The key's diffuse factor across the terminator, per method (NumPy, GL-free; 2026-11-24; disposable).

    python experiments/lookdev_diffuse_area/curves.py --out <dir>

Writes `curves.png` (needs matplotlib, not a repo dependency: `pip install matplotlib` in the session only) and prints
the error table against the dense reference (max / RMS over n.l in [-1, 1]) plus the brightness a uniformly lit sphere
gains. Small multiples: rows = material wrap 0 / 0.3 (Creature Skin's red channel), columns = key size 0.25 / 0.5 / 1;
x = the angle between normal and the light's centre.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import area_math as am  # noqa: E402

SIZES = (0.25, 0.5, 1.0)
WRAPS = (0.0, 0.3)
#: the reference palette's categorical slots 1-4 (light), fixed order; REF in the secondary text ink
SERIES = (("A  Lambert + Wrap (heute)", "#2a78d6", "-"), ("B  Horizont-Spline", "#eb6834", "-"),
          ("C16  16 Richtungen", "#1baf7a", (0, (4, 2))), ("A'  Wrap + Größe (naiv)", "#eda100", (0, (1, 1.5))))
REF_STYLE = ("Referenz (4096 Richtungen)", "#52514e", (0, (6, 3)))


def table() -> list[str]:
    c = np.linspace(-1.0, 1.0, 4001)
    lines = ["size  sigma   w    | A max/rms     | A' max/rms    | B max/rms     | B2 max/rms    | C8 max/rms    | "
             "C16 max/rms   | sphere gain (B)"]
    for w in WRAPS:
        for size in SIZES:
            s = float(am.size_to_sin(size))
            ref = am.area_reference(c, s, w, 16384)
            cells = []
            for f in (lambda: am.lambert_wrap(c, w), lambda: am.wrap_by_size(c, w, s), lambda: am.area_quad(c, s, w),
                      lambda: am.area_exact(c, s, w), lambda: am.area_samples(c, s, w, 8),
                      lambda: am.area_samples(c, s, w, 16)):
                d = f() - ref
                cells.append(f"{np.abs(d).max():.3f}/{np.sqrt(np.mean(d * d)):.4f}")
            lines.append(f"{size:4.2f}  {float(am.sigma_degrees(size)):4.1f}°  {w:.1f}  | " + " | ".join(
                f"{x:<13}" for x in cells) + f" | +{100 * am.mean_excess(s):.1f} %")
    return lines


def plot(path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    deg = np.linspace(40.0, 150.0, 600)
    c = np.cos(np.radians(deg))
    fig, axes = plt.subplots(len(WRAPS), len(SIZES), figsize=(12, 6.4), sharex=True, sharey=True, dpi=150)
    fig.patch.set_facecolor("#fcfcfb")
    for i, w in enumerate(WRAPS):
        for j, size in enumerate(SIZES):
            ax = axes[i][j]
            ax.set_facecolor("#fcfcfb")
            s = float(am.size_to_sin(size))
            ref = am.area_reference(c, s, w, 8192)
            curves = (am.lambert_wrap(c, w), am.area_quad(c, s, w), am.area_samples(c, s, w, 16),
                      am.wrap_by_size(c, w, s))
            label, colour, style = REF_STYLE
            ax.plot(deg, ref, color=colour, lw=2.0, ls=style, label=label, zorder=1)
            for (label, colour, style), y in zip(SERIES, curves):
                ax.plot(deg, y, color=colour, lw=2.0, ls=style, label=label, zorder=2)
            ax.axvline(90.0, color="#c3c2b7", lw=1.0, zorder=0)
            ax.set_title(f"Key-Größe {size:g} (σ {float(am.sigma_degrees(size)):.0f}°), Wrap {w:g}", fontsize=10,
                         color="#0b0b0b")
            ax.grid(color="#e6e5e0", lw=0.6)
            for spine in ax.spines.values():
                spine.set_color("#c3c2b7")
            ax.tick_params(colors="#52514e", labelsize=8)
            if i == len(WRAPS) - 1:
                ax.set_xlabel("Winkel Normale ↔ Lichtmitte (°); 90° = Terminator", fontsize=9, color="#52514e")
            if j == 0:
                ax.set_ylabel("diffuser Faktor des Key", fontsize=9, color="#52514e")
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=5, frameon=False, fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", default=str(HERE / "out"))
    args = parser.parse_args(argv)
    for line in table():
        print(line)
    try:
        plot(Path(args.out) / "curves.png")
        print(f"wrote {Path(args.out) / 'curves.png'}")
    except ImportError:
        print("matplotlib missing: no curves.png (the table above is the result)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
