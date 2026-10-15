"""The soft scenario of the drag-cost probe (WP-SOFT-01 S2b): variants, arguments and report
format - headless (no pyglet, no window) - plus one end-to-end smoke run that is skipped
when no GL context is available (use `xvfb-run -a` in a container)."""

from __future__ import annotations

import pytest

from drag_cost import probe_drag_gl as probe


def test_soft_variants_are_radius_times_metric_with_the_handoff_defaults():
    assert probe.SOFT_RADIUS_PERCENTS == (5, 15, 30, 50)
    variants = probe.SCENARIOS["soft_w"].variants("head_basemesh", None, None)
    assert variants == [
        (5, "euclidean"), (15, "euclidean"), (30, "euclidean"), (50, "euclidean"),
        (5, "geodesic"), (15, "geodesic"), (30, "geodesic"), (50, "geodesic"),
    ]


def test_soft_variants_honour_sizes_and_metrics():
    variants = probe.SCENARIOS["soft_w"].variants("man_with_shoes_basemesh", [15, 30], ["geodesic"])
    assert variants == [(15, "geodesic"), (30, "geodesic")]


def test_every_default_radius_is_a_real_radius_step():
    steps, metrics = probe.soft_choices()
    assert set(probe.SOFT_RADIUS_PERCENTS) <= set(steps)
    assert set(metrics) == {"euclidean", "geodesic"}


def test_plain_w_variants_are_still_the_selection_sizes():
    plain = probe.SCENARIOS["plain_w"]
    assert plain.variants("head_basemesh", None, None) == [9, 36, 68]
    assert plain.variants("head_basemesh", [5], None) == [5]


def test_valid_soft_arguments_parse():
    args = probe.parse_args(["--scenarios", "soft_w", "--sizes", "5", "50", "--metrics", "geodesic"])
    assert args.sizes == [5, 50] and args.metrics == ["geodesic"]


def _fake_result(scenario="soft_w", extras=()):
    sample = probe.MoveSample(transform=0.1, sync=0.4, update=0.1, draw=0.9, updates=30)
    return probe.ScenarioResult(
        scenario=scenario, asset="head_basemesh", vertex_count=326, selected=5, moves=1,
        samples=(sample,), label="r  5 % euclidean", influenced=9, extras=extras,
    )


def test_report_prints_soft_rows_and_once_per_row_timings():
    extra = (("first move (begin + influence)", probe.Stats.of([0.9])),)
    lines = probe.report_lines([_fake_result(extras=extra)], ("GL 3.3", "test"), 1)
    text = "\n".join(lines)
    assert "[soft_w] head_basemesh: 326 vertices" in text
    assert "r  5 % euclidean: seeds   5 V, moving    9 V" in text
    assert "once: first move (begin + influence)" in text
    assert text.isascii()


def test_plain_report_is_unchanged_in_shape():
    lines = probe.report_lines([_fake_result("plain_w")], ("GL 3.3", "test"), 1)
    assert any(l.startswith("  selection ") for l in lines)
    assert not any("once:" in l for l in lines)


def test_soft_scenario_runs_end_to_end_with_the_window_chain():
    pytest.importorskip("pyglet")
    import importlib

    try:
        src_main = importlib.import_module("main")
        results, _ = probe.run_probe(
            ["head_basemesh"], [5], moves=4, warmup=1, scenarios=["soft_w"], src_main=src_main,
            metrics=["euclidean"],
        )
    except Exception as exc:  # no display / GL context in this environment
        if type(exc).__name__ in {"NoSuchDisplayException", "ImportError"} or "display" in str(exc).lower():
            pytest.skip(f"no GL context available: {exc}")
        raise
    (result,) = results
    names = [name for name, _ in result.extras]
    assert names[0].startswith("first move") and names[1].startswith("commit frame")
    assert any(n.startswith("preview recompute") for n in names)
    assert any(n.startswith("settings change") for n in names)
    assert len(result.samples) == 4 and result.influenced >= result.selected


# -- soft_w_sym (AD-SYM-04 SS3, D-4) ----------------------------------------------------------


def test_symmetric_soft_variants_are_the_soft_variants():
    sym = probe.SCENARIOS["soft_w_sym"]
    assert sym.variants("head_basemesh", None, None) == probe.SCENARIOS["soft_w"].variants(
        "head_basemesh", None, None
    )
    assert probe.SOFT_SCENARIOS == ("soft_w", "soft_w_sym")
    args = probe.parse_args(["--scenarios", "soft_w_sym", "--sizes", "15", "--metrics", "geodesic"])
    assert args.scenarios == ["soft_w_sym"] and args.sizes == [15]
    assert probe.parse_args([]).scenarios == ["plain_w", "soft_w"]  # default unchanged


@pytest.mark.parametrize("bad", [["--sizes", "7"], ["--metrics", "manhattan"]])
def test_symmetric_soft_arguments_are_checked_like_soft_w(bad):
    with pytest.raises(SystemExit):
        probe.parse_args(["--scenarios", "soft_w_sym", *bad])


@pytest.mark.parametrize("asset", ["head_basemesh", "man_with_shoes_basemesh"])
def test_symmetric_seeds_are_paired_on_plus_x_next_to_the_seam(asset):
    from loaders.assets import asset_path
    from mirai.scene_factory import build_core_scene_from_obj
    from mirai.symmetry import CorrespondenceState, vertex_correspondence
    from mirai.symmetry_axis import set_symmetry_axis

    mesh = build_core_scene_from_obj(asset_path(asset)).mesh
    set_symmetry_axis(mesh, "X")
    corr = vertex_correspondence(mesh)
    seed, seeds = probe.seed_off_plane_with_ring(mesh)
    assert seed in seeds and len(seeds) >= 2
    for vid in seeds:
        assert corr[vid].state is CorrespondenceState.PAIRED and mesh.vertex_position(vid)[0] > 0.0
    neighbours = {o for e in mesh.vertex_edges(seed) for o in mesh.edge_vertices(e)}
    assert any(corr[o].state is CorrespondenceState.SEAM for o in neighbours)


def test_report_prints_symmetric_soft_rows():
    result = _fake_result(scenario="soft_w_sym")
    text = "\n".join(probe.report_lines([result], ("GL 3.3", "test"), 1))
    assert "[soft_w_sym] head_basemesh: 326 vertices" in text
    assert "r  5 % euclidean: seeds   5 V, moving    9 V" in text


def test_symmetric_soft_scenario_runs_end_to_end_with_the_window_chain():
    pytest.importorskip("pyglet")
    import importlib

    try:
        src_main = importlib.import_module("main")
        results, _ = probe.run_probe(
            ["head_basemesh"], [15], moves=4, warmup=1, scenarios=["soft_w_sym"],
            src_main=src_main, metrics=["geodesic"],
        )
    except Exception as exc:  # no display / GL context in this environment
        if type(exc).__name__ in {"NoSuchDisplayException", "ImportError"} or "display" in str(exc).lower():
            pytest.skip(f"no GL context available: {exc}")
        raise
    (result,) = results
    names = [name for name, _ in result.extras]
    assert names[0].startswith("first move") and names[1].startswith("commit frame")
    assert "preview recompute (sym field + bands)" in names
    assert "symmetry report (per geometry change)" in names
    assert " X, seam " in result.label and not result.label.endswith("seam  0 V")
    assert len(result.samples) == 4 and result.influenced > result.selected
