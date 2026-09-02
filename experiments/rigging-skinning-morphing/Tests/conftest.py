"""pytest-Kontext für Tests/ dieses Experiments.

Zwei Aufgaben:

1. Pfad-Bootstrap (Projekt-Root für src.core-Fallbacks, Experiment-Ordner
   für bone/deformation/rig_controller/loaders/viewport_adapter).

2. Workaround für pytest 9.x: Der Experiment-Ordner heißt
   `rigging-skinning-morphing` — Bindestriche sind kein gültiger
   Python-Identifier, pytest kann den Ordner daher nicht als Package
   importieren und versucht stattdessen, `__init__.py` als Top-Level-Modul
   `__init__` zu laden. Die relativen Imports in `__init__.py`
   (from .bone import ...) brechen dann mit "attempted relative import with
   no known parent package" — das betrifft ALLE Tests unter Tests/,
   auch die bestehenden. Der Workaround lädt das Experiment-Package
   bewusst über importlib unter einem gültigen Namen und registriert es
   zusätzlich unter dem Namen `__init__`, damit der pytest-Import-Zugriff
   auf einen bereits geladenen, korrekt initialisierten Modulkontext trifft.
   Keine Änderung an bestehenden Experiment-/Core-Dateien.
"""

import importlib.util
import sys
from pathlib import Path

_EXPERIMENT_DIR = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _EXPERIMENT_DIR.parent.parent

for _path in (str(_PROJECT_ROOT), str(_EXPERIMENT_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

_PACKAGE_NAME = "rigging_skinning_morphing_testpkg"

if _PACKAGE_NAME not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        _PACKAGE_NAME,
        _EXPERIMENT_DIR / "__init__.py",
        submodule_search_locations=[str(_EXPERIMENT_DIR)],
    )
    assert _spec is not None and _spec.loader is not None  # Datei existiert
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[_PACKAGE_NAME] = _module
    _spec.loader.exec_module(_module)
    # pytest-Workaround (siehe Modul-Docstring Punkt 2): pytest 9.x
    # importiert das Package-__init__ hyphen-behafteter Ordner als
    # Top-Level-Modul '__init__'. Eintrag hier abfangen:
    sys.modules.setdefault("__init__", _module)
