"""Artist Playground — Einstiegspunkt.

Verwendung:
    python playground/run.py          # Cube (default)
    python playground/run.py cube     # explizit Cube
    python playground/run.py head     # Head-Basemesh

Oder als Modul vom Repo-Root:
    python -m playground.run
"""

import sys

# sys.path-Bootstrap: sicherstellen, dass Playground-interne Imports
# und Production-Pakete (core/viewport/mirai) gefunden werden.
from playground._paths import ensure_paths

ensure_paths()

import pyglet  # noqa: E402

from playground.app import PlaygroundApp  # noqa: E402
from playground.window import PlaygroundWindow  # noqa: E402


def main() -> None:
    mesh = sys.argv[1] if len(sys.argv) > 1 else "cube"
    app = PlaygroundApp()
    if mesh == "head":
        app.load_head()
    else:
        app.load_cube()
    win = PlaygroundWindow(app)
    pyglet.app.run()


if __name__ == "__main__":
    main()
