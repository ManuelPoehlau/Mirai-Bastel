"""WP-KNIFE-01 S1 safety net: the Knife Face sessions (B, D, Q5) give exactly the recorded results.

Written *before* the resolver moved to `src/mirai/topology/` (commit "Tests: golden regression net …"),
green on the Lab engines as they were; after the move the regenerated file must be byte-identical.
What is compared and why ids are not: `knife_golden_driver.py` (module docstring). To inspect a
difference: `python playground/tests/knife_golden_driver.py --check`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from playground.tests.knife_golden_driver import (  # noqa: E402
    GOLDEN_PATH,
    RECORDED,
    dumps,
    record_all,
    recorded_case,
)


def test_sessions_match_the_golden_file_byte_for_byte():
    assert dumps(record_all()) == GOLDEN_PATH.read_text(encoding="utf-8"), (
        "Knife Face results changed - run `python playground/tests/knife_golden_driver.py --check`"
    )


def test_manus_recorded_cube_sequences_give_the_recorded_counts():
    """decision.md 2026-09-30: the bow-tie (confirmed by Manu, `V:13 E:21 F:10`) and the tail join
    (his hand-made expected result, `V:14 E:22 F:10`)."""
    bow_tie = recorded_case("cube bow-tie (Manu)", "Q5")
    assert bow_tie["vef"] == "13/21/10"
    assert bow_tie["msg"] == "1/1 cut(s) applied; 2 loop(s) closed at a single point — own face, 1 bridge each"
    tail = recorded_case("cube tail join (Manu)", "Q5")
    assert tail["vef"] == "14/22/10"
    assert "1 last point(s) inside a face joined to the nearest corner" in tail["msg"]
    for sig in (bow_tie, tail):
        assert sig["history"] == 1 and sig["undo_redo"] == "True/True"


def test_every_recorded_case_with_an_expectation_meets_it():
    for name, (_scene, variants, _cam, _specs, expect) in RECORDED.items():
        if expect is None:
            continue
        for variant in variants:
            assert recorded_case(name, variant)["vef"] == expect, name


def test_the_golden_file_holds_no_rollback_for_d_or_q5():
    """The resolver itself stays sound: the commit check never has to take a D or Q5 session back
    (B, REJECTed, cuts at click time and is rolled back twice on the cube — recorded, not a goal)."""
    data = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    rolled = [k for k, runs in data["random"].items() if " B " not in k and any("rolled back" in s for s in runs)]
    assert rolled == []
    assert all(s.get("undo_redo", "True/True") == "True/True" for s in data["recorded"].values())
    assert all(" False" not in s.split(" | ")[0] for runs in data["random"].values() for s in runs)
