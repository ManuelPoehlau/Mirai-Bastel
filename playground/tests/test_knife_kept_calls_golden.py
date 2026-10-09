"""AD-SYM-03 slice 6a / AD-017 §13 item 5: the Knife resolver's kept-call report replayed verbatim rebuilds the
resolved mesh in **every session of the golden net**.

The golden net is what `test_knife_resolver_golden.py` and `test_knife_cross_face_golden.py` run: the recorded
and the seeded random sessions of the Lab variants D and Q5 (`knife_golden_driver.record_all`) and the
cross-face sequences through the Lab's Q5 and the Production `KnifeTool` (`knife_cross_face_golden_driver`).
Here the three call sites of the resolver (`engine.resolve_collected`, `engine_q5.resolve_cross_face`,
`mirai.topology.knife.resolve_cross_face`) are wrapped to keep, per session: the mesh state right before the
resolver runs, the resolution and the mesh state right after it. The wrapper changes nothing, which the
first test proves by comparing the whole net with the golden file byte for byte.

The replay itself (`tests/knife_kept_replay.py`) is shared with `tests/test_knife_kept_calls.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest  # noqa: E402

from playground.tests import knife_cross_face_golden_driver as cross_face  # noqa: E402  (puts src/ on sys.path)
from playground.tests import knife_golden_driver as net  # noqa: E402
from playground.experiments.knife_face import engine as lab_d  # noqa: E402
from playground.experiments.knife_face import engine_q5 as lab_q5  # noqa: E402
from mirai.topology import knife as production_knife  # noqa: E402
from mirai.topology.knife_resolve import mesh_content  # noqa: E402
from tests.knife_kept_replay import assert_report_replays  # noqa: E402


@pytest.fixture(scope="module")
def captured():
    """{call site: [(state before the resolver, resolution, state after the resolver, session-start state
    handed to it)]} over the whole golden net, and the net's own recording."""
    sessions: dict[str, list] = {"lab D": [], "lab Q5": [], "production": []}

    def wrap(site: str, real):
        def wrapped(mesh, path, before_state):
            start = mesh.export_state()
            res = real(mesh, path, before_state)
            sessions[site].append((start, res, mesh.export_state(), before_state))
            return res
        return wrapped

    saved = (lab_d.resolve_collected, lab_q5.resolve_cross_face, production_knife.resolve_cross_face)
    lab_d.resolve_collected = wrap("lab D", saved[0])
    lab_q5.resolve_cross_face = wrap("lab Q5", saved[1])
    production_knife.resolve_cross_face = wrap("production", saved[2])
    try:
        recorded = net.record_all()
        golden = cross_face.load()
        for entry in golden.values():
            if entry["scene"] == "head" and not Path(net.DEFAULT_HEAD_ASSET).is_file():
                continue
            cross_face.replay("q5", entry)
            cross_face.replay("production", entry)
    finally:
        lab_d.resolve_collected, lab_q5.resolve_cross_face, production_knife.resolve_cross_face = saved
    return sessions, recorded


def test_wrapping_the_resolver_calls_changes_nothing(captured):
    """The net recorded through the wrappers is the golden file, byte for byte."""
    _sessions, recorded = captured
    assert net.dumps(recorded) == net.GOLDEN_PATH.read_text(encoding="utf-8")


def test_the_net_reaches_all_three_resolver_call_sites_many_times(captured):
    sessions, _ = captured
    assert {site: len(s) >= 40 for site, s in sessions.items()} == {"lab D": True, "lab Q5": True, "production": True}
    assert sum(len(res.kept_calls) for s in sessions.values() for _a, res, _b, _c in s) >= 400
    ops = {c.op for s in sessions.values() for _a, res, _b, _c in s for c in res.kept_calls}
    assert ops == {"split_edge", "split_face"}


@pytest.fixture(scope="module")
def replayed(captured):
    """{call site: number of sessions in which a rollback burned ids} — after replaying every session's report
    on its start state (`assert_report_replays` raises on the first session that does not rebuild)."""
    sessions, _ = captured
    out = {}
    for site, rows in sessions.items():
        burned = 0
        for i, (start, res, after, before_state) in enumerate(rows):
            assert mesh_content(start) == mesh_content(before_state), f"{site} #{i}: the resolver started on a changed mesh"
            burned += assert_report_replays(start, res.kept_calls, after, context=f"[{site} #{i}]")
        out[site] = burned
    return out


@pytest.mark.parametrize("site", ["lab D", "lab Q5", "production"])
def test_the_report_replayed_verbatim_rebuilds_the_resolved_mesh_in_every_golden_session(captured, replayed, site):
    assert len(captured[0][site]) >= 40 and site in replayed


def test_the_net_includes_sessions_that_took_calls_back_and_sessions_that_cut_nothing(captured, replayed):
    """The rollback paths are in the net, not only the straight ones (the Lab D sessions drop runs)."""
    assert sum(replayed.values()) > 0
    sessions, _ = captured
    assert any(not res.kept_calls for rows in sessions.values() for _a, res, _b, _c in rows)
