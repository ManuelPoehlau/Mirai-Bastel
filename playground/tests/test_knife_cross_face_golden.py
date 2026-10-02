"""WP-KNIFE-01 S4 oracle: cross-face sequences with fixed cameras give exactly the recorded Lab-Q5 results.

Written *before* the planner moved to `src` (commit "spec: S4 …"): the Lab's Q5 replays every stored sequence
identically (the move must not change it, S5 of the S4 handoff); the Production `KnifeTool` reproduces the same
results once it plans across faces (the intended P10 flip) — strict xfail until then (the S4 build removed
the marks). What is recorded and
why ids are not: `knife_cross_face_golden_driver.py` (module docstring). To inspect a difference:
`python playground/tests/knife_cross_face_golden_driver.py --check`.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest  # noqa: E402

from playground._paths import DEFAULT_HEAD_ASSET  # noqa: E402
from playground.tests.knife_cross_face_golden_driver import load, replay  # noqa: E402

GOLDEN = load()
NAMES = list(GOLDEN)


def _entry(name):
    entry = GOLDEN[name]
    if entry["scene"] == "head" and not Path(DEFAULT_HEAD_ASSET).is_file():
        pytest.skip("head asset not found")
    return entry


@pytest.mark.parametrize("name", NAMES)
def test_the_lab_q5_replays_the_golden_sequence(name):
    entry = _entry(name)
    assert replay("q5", entry) == entry["q5"]


@pytest.mark.parametrize("name", NAMES)
def test_production_reproduces_the_golden_sequence(name):
    entry = _entry(name)
    assert replay("production", entry) == entry["q5"]


def test_the_golden_covers_walk_plane_hidden_gaps_closes_orbits_and_the_head():
    planned = [p for entry in GOLDEN.values() for p in entry["q5"]["planned"] if p is not None]
    methods = {p[0] for p in planned}
    assert {"walk", "plane", "direct"} <= methods
    assert any(p[1] > 0 for p in planned)                                       # hidden crossings
    assert any(entry["q5"]["resolution"]["gaps"] > 0 for entry in GOLDEN.values())
    assert any(entry["q5"]["resolution"]["loops_built"] or "close" in name for name, entry in GOLDEN.items())
    assert any(any(isinstance(s, list) and s[0] == "cam" for s in entry["specs"]) for entry in GOLDEN.values())
    assert any(not entry["view"][2] for entry in GOLDEN.values())               # wireframe
    assert sum(1 for entry in GOLDEN.values() if entry["scene"] == "head") >= 10
    assert all(not entry["q5"]["rolled_back"] for entry in GOLDEN.values())
