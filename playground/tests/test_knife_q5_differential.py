"""WP-KNIFE-01 S3 — differential spec: the Production `KnifeTool` does what the Lab's Q5 does inside one face.

Driven by `knife_q5_differential_driver.py` (module docstring: specs, what is compared, why Q5 runs without
a camera). Written before the S3 change to `KnifeTool` (commit "Tests: Q5 vs Production differential
spec …"): 44 of these failed on the S2 tool (no face targets) as strict xfail — S3's acceptance criterion;
the S3 tool flipped all of them and the mark was dropped.

Compared per sequence: which clicks are accepted (and the refusal reasons), `accepts() == click()` on every
click, the path records after every step (kinds, positions, point identity, breaks — undo / redo included),
that the mesh is not touched during the session, the mesh after commit (position-canonical faces, V/E/F),
every count and note of the commit's `KnifeResolution`, rollback, History length and its Undo / Redo, the
residue (selected edges, Edge mode).

Sequences that need a segment across several faces are refused by both (slice S4). Two vertex/edge-only
cases differ on purpose — the S2 rules (S2 KEEP) — and are pinned as such (decision.md, "One Knife S3").
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest  # noqa: E402

from playground._paths import DEFAULT_HEAD_ASSET  # noqa: E402
from playground.tests.knife_cross_face_golden_driver import load as load_cross_face  # noqa: E402
from playground.tests.knife_cross_face_golden_driver import from_json, scene  # noqa: E402
from playground.tests.knife_q5_differential_driver import (  # noqa: E402
    DIFFERENCES,
    MULTI_FACE,
    RANDOM_RUNS,
    RECORDED,
    compare,
    play_both,
    play_production,
    play_q5,
    random_run,
    recorded_specs,
)

@pytest.mark.parametrize("name", list(RECORDED))
def test_recorded_single_face_sequences_match_q5(name):
    scene_name, specs = recorded_specs(name)
    q5, prod = play_both(scene_name, specs)
    assert compare(q5, prod) == []
    expect = RECORDED[name][2]
    if expect is not None:
        assert prod.vef == expect and prod.history == 1


def test_manus_cube_sequences_give_his_counts_in_production():
    """decision.md 2026-09-30: bow-tie `V:13 E:21 F:10` (confirmed), tail join `V:14 E:22 F:10` (his
    hand-made result) — the tail join with the top/front crossing clicked (single-face segments only)."""
    for name, msg_part in (("cube bow-tie (Manu)", "loops_built"), ("cube tail join (Manu), crossing clicked", "joined")):
        scene_name, specs = recorded_specs(name)
        _q5, prod = play_both(scene_name, specs)
        assert prod.vef == RECORDED[name][2], name
        assert prod.resolution[msg_part] >= 1 and prod.resolution["applied"] == prod.resolution["runs"]
        assert prod.history == 1 and prod.undo_restores and prod.redo_restores and prod.mode == "EDGE"


@pytest.mark.parametrize("name", list(MULTI_FACE))
def test_multi_face_sequences_are_refused_by_both(name):
    """A segment over several faces needs the planner (S4): refused, with the S2 reason in Production."""
    scene_name, specs, accepted = MULTI_FACE[name]
    q5, prod = play_both(scene_name, specs)
    assert q5.accepted == accepted
    assert prod.accepted[-1] == "-"
    assert prod.reasons[-1] == "no shared face holds the cut (cross-face: not yet)"


@pytest.mark.parametrize("name", list(MULTI_FACE))
def test_multi_face_sequences_match_q5_up_to_the_refused_click(name):
    scene_name, specs, _accepted = MULTI_FACE[name]
    q5, prod = play_both(scene_name, specs)
    assert compare(q5, prod) == []


def test_documented_difference_retraced_segment():
    """S2-b kept: Production skips the retraced cut (a break), Q5 connects to the earlier point and merges
    the repeat at commit. Same clicks accepted, same mesh, History, residue; only the record differs."""
    q5, prod = play_both(*DIFFERENCES["retraced segment (S2-b)"])
    assert q5.accepted == prod.accepted == "+++++"
    assert (q5.faces, q5.vef, q5.history, q5.residue) == (prod.faces, prod.vef, prod.history, prod.residue)
    assert q5.resolution["repeats"] == 1 and q5.resolution["gaps"] == 0
    assert prod.resolution["repeats"] == 0 and prod.resolution["gaps"] == 1
    assert {line.split(":")[0] for line in compare(q5, prod)} == {"paths", "resolution"}


def test_documented_difference_back_to_the_start_after_one_click():
    """S2-b kept: back on the chain start after one other boundary click — Production accepts (a retrace
    skip), Q5 refuses ("closing needs at least 3 points"). Same mesh, History, residue."""
    q5, prod = play_both(*DIFFERENCES["back to the start after one click (S2-b)"])
    assert q5.accepted == "++-" and prod.accepted == "+++"
    assert q5.reasons == ["closing needs at least 3 points"]
    assert (q5.faces, q5.vef, q5.history, q5.residue) == (prod.faces, prod.vef, prod.history, prod.residue)


@pytest.mark.parametrize("scene_name", list(RANDOM_RUNS))
def test_seeded_random_single_face_sessions_match_q5(scene_name):
    """Seeded sessions of vertex / edge / interior clicks in the faces of the last point (now and then an
    own point, undo / redo, a point anywhere, an interior click too close to an edge), 1-2 sessions per run
    on the mesh the previous one left. Clicks under a documented S2 difference are not played."""
    if scene_name == "head" and not Path(DEFAULT_HEAD_ASSET).is_file():
        pytest.skip("head asset not found")
    sessions = faces = 0
    for seed in range(RANDOM_RUNS[scene_name]):
        for specs, differences, _prod in random_run(scene_name, seed):
            assert differences == [], (scene_name, seed, specs)
            sessions += 1
            faces += sum(1 for sp in specs if sp[0] == "f")
    assert sessions >= RANDOM_RUNS[scene_name] and faces >= sessions  # the sessions really used face points


def test_a_broken_result_is_taken_back_by_both(monkeypatch):
    """The commit check (`knife_resolve.check_commit`) rejects the result: both take the whole session
    back — no History, the session-start mesh, a named problem."""
    from mirai.topology import knife_resolve

    monkeypatch.setattr(knife_resolve, "integrity_problem", lambda mesh, before: "a face would flip (forced)")
    scene_name, specs = recorded_specs("FC2 bent cut, two interior clicks")
    q5, prod = play_both(scene_name, specs)
    assert compare(q5, prod) == []
    assert prod.problem == "a face would flip (forced)" and prod.history == 0 and prod.vef == "25/40/16"


# -- WP-KNIFE-01 S4: cross-face sequences with a camera view (the planner) --------------------------------------

CROSS_FACE = load_cross_face()


CROSS_FACE_PARAMS = [
    pytest.param(name, marks=pytest.mark.xfail(strict=True, reason="WP-KNIFE-01 S4: no cross-face planning yet"))
    if any(p is not None and p[0] != "direct" for p in CROSS_FACE[name]["q5"]["planned"]) else name
    for name in CROSS_FACE
]


@pytest.mark.parametrize("name", CROSS_FACE_PARAMS)
def test_cross_face_sequences_with_a_view_match_q5(name):
    """The S4 golden sequences (`golden/knife_cross_face.json`) through both tools with the same camera: every
    step, every planned crossing (method, hidden count, positions), the mesh, History and residue identical."""
    entry = CROSS_FACE[name]
    if entry["scene"] == "head" and not Path(DEFAULT_HEAD_ASSET).is_file():
        pytest.skip("head asset not found")
    specs = [from_json(s) for s in entry["specs"]]
    view = tuple(entry["view"])
    q5 = play_q5(scene(entry["scene"]), specs, "commit", view)
    prod = play_production(scene(entry["scene"]), specs, "commit", view)
    assert compare(q5, prod) == []
