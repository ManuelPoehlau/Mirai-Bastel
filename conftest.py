"""Repo-weites pytest-Verhalten für Tests, die pyglet *und* ein Display brauchen
(Playground, Teile von tests/ und Symmetry Lab; `import pyglet.window` öffnet ein
Shadow-Fenster). Fehlt eines davon, scheitert schon die Collection und bricht den
ganzen Lauf ab. Hier wird genau dieser Fall zu einem sichtbaren Skip (mit Hinweis
auf `xvfb-run -a`); jeder andere Fehler bleibt ein Fehler.
"""

from __future__ import annotations

import pytest

_MARKERS = (
    "No module named 'pyglet",
    "NoSuchDisplayException",
    'Library "EGL" not found',  # pyglet-Fallback ohne Display
)
_HINT = "pyglet/Display fehlt - pip install -r requirements-dev.txt; headless: xvfb-run -a pytest"


@pytest.hookimpl(hookwrapper=True)
def pytest_make_collect_report(collector):
    outcome = yield
    report = outcome.get_result()
    if report.outcome == "failed" and any(m in str(report.longrepr) for m in _MARKERS):
        report.outcome = "skipped"
        report.longrepr = (str(collector.path), 0, f"Skipped: {_HINT}")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    # Tests, die pyglet/Display erst zur Laufzeit (Fixture oder Testkörper) brauchen.
    outcome = yield
    report = outcome.get_result()
    if report.failed and any(m in str(report.longrepr) for m in _MARKERS):
        report.outcome = "skipped"
        report.longrepr = (str(item.path), item.reportinfo()[1] or 0, f"Skipped: {_HINT}")
