"""AD-027 §6 E1: the golden interaction corpus must replay exactly after every restructuring step.

`tests/interaction_trace.py` drives `Application` through its public entry points only and digests one
observation per event; the fixtures in `tests/fixtures/interaction_traces/` were recorded on the
baseline commit `dfd6e5d`. A divergence is a bug of the step that caused it - the corpus is never
re-recorded to make a step pass (only a driver bug justifies that, from a baseline worktree).

Lifecycle (AD-027 C1): the random corpus is a migration oracle and goes at M8 with its generator; the
scripted sequences (V1-V7, the test-point scenarios) then become readable regression tests.
"""

from __future__ import annotations

import json

import pytest

import tests._bootstrap  # noqa: F401
from tests import interaction_trace as trace

_RANDOM = sorted(trace.FIXTURES.glob("random_*.json"))
_SCRIPTED = json.loads((trace.FIXTURES / "scripted.json").read_text(encoding="utf-8"))


def _check_driver(recorded: str) -> None:
    assert recorded == trace.driver_hash(), (
        "tests/interaction_trace.py changed since the corpus was recorded: re-record only for a driver bug, "
        "from a worktree of the baseline commit (AD-027 §6)"
    )


def test_corpus_covers_every_scene() -> None:
    assert {path.stem.removeprefix("random_") for path in _RANDOM} == set(trace.CORPUS)
    assert set(_SCRIPTED["sequences"]) == set(trace.SCRIPTED)


@pytest.mark.parametrize("path", _RANDOM, ids=lambda p: p.stem)
def test_random_corpus_replays(path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    _check_driver(data["driver"])
    scene = data["scene"]
    for sequence in data["sequences"]:
        expected = trace.split_digests(sequence["digests"])
        driver = trace.run_random(scene, sequence["seed"], sequence["events"])
        for index, (want, got) in enumerate(zip(expected, driver.digests)):
            if want != got:
                pytest.fail(
                    f"{scene} seed {sequence['seed']}: first divergence at event {index} ({driver.events[index]!r}); "
                    f"previous events: {driver.events[max(0, index - 5):index]}. Observation: "
                    f"python tests/interaction_trace.py observe {scene} {sequence['seed']} {sequence['events']} {index}"
                )
        assert len(driver.digests) == len(expected)


@pytest.mark.parametrize("name", sorted(trace.SCRIPTED))
def test_scripted_sequence_replays(name) -> None:
    _check_driver(_SCRIPTED["driver"])
    expected = _SCRIPTED["sequences"][name]
    driver = trace.run_scripted(name)
    got = [json.loads(json.dumps(obs)) for obs in driver.observations]
    assert [step["event"] for step in expected] == driver.events
    for index, (step, observation) in enumerate(zip(expected, got)):
        want = step["observation"]
        if want != observation:
            keys = sorted(k for k in want if want.get(k) != observation.get(k))
            details = {k: (want.get(k), observation.get(k)) for k in keys}
            pytest.fail(f"{name}: step {index} ({step['event']!r}) differs in {keys}: {details}")
