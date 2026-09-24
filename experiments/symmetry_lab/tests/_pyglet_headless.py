"""pyglet für Tests ohne Fenster laden (Headless-Lösung, Handoff Slice 2 §7).

Wie in Slice 1 (`tests/test_pyglet_input.py`): `pyglet.options["headless"] =
True` muss VOR dem ersten `pyglet.window`-Import gesetzt sein, sonst legt
pyglet auf Linux ohne X-Server beim Import ein Shadow-Window an und scheitert
mit `NoSuchDisplayException`.

Abweichung von Slice 1: Die Option wird nur gesetzt, wenn wirklich kein
Display da ist (Linux ohne `DISPLAY`/`WAYLAND_DISPLAY`). pyglets Headless-Zweig
lädt auf *jeder* Plattform EGL (`pyglet/display/__init__.py`, pyglet 2.1);
auf Windows ist EGL üblicherweise nicht vorhanden. Mit Display (Windows,
Desktop-Linux, Xvfb) wird das normale Fenstersystem benutzt. Auf Linux ohne
Display braucht der Headless-Zweig eine EGL-Bibliothek (z. B. Mesa `libegl1`).
"""

from __future__ import annotations

import os
import sys

import pytest


def needs_headless() -> bool:
    if not sys.platform.startswith("linux"):
        return False
    return not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def import_pyglet():
    """Importiert pyglet (Skip, wenn nicht installiert) und setzt ggf. headless."""
    pyglet = pytest.importorskip("pyglet")
    if needs_headless():
        pyglet.options["headless"] = True
    return pyglet
