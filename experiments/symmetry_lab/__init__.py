"""Symmetry Lab (WP-SYM-LAB-01) — eigenständiges Forschungsfenster.

Einstieg und Steuerung: `README.md` in diesem Ordner. Das Lab importiert
bewusst nichts aus `playground/` (Handoff WP-SYM-LAB-01 Slice 2 §2.6,
abgesichert durch `tests/test_import_boundary.py`).

Dieses Paket-`__init__` bleibt absichtlich leer (keine Imports, kein
sys.path-Eingriff): Der Bootstrap liegt in `_paths.py` und wird von den
Einstiegspunkten explizit aufgerufen.
"""
