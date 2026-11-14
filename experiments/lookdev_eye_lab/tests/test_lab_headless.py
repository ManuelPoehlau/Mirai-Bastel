"""Lab state, keys and boundaries (headless)."""

from __future__ import annotations

import ast
from pathlib import Path

from lookdev_eye_lab import lab_state as ls

LAB = Path(__file__).resolve().parents[1]


def test_every_key_returns_a_new_state_and_cycles():
    state = ls.LabState()
    for name, (_text, action) in ls.KEYS.items():
        for shift in (False, True):
            new = action(state, shift)
            assert isinstance(new, ls.LabState) and new is not state, name
    assert ls.KEYS["1"][1](state, False).technique == "T-A"
    assert ls.KEYS["7"][1](state, False).cornea == "C3"
    assert ls.KEYS["R"][1](ls.KEYS["R"][1](state, False), False).env_size == 64


def test_variants_cover_every_technique_and_treatment():
    assert len(ls.VARIANTS) == 2 + 3 * 3
    assert {t for t, _ in ls.VARIANTS} == set(ls.TECHNIQUES)


def test_env_rotation_turns_the_studio_by_the_yaw():
    import numpy as np

    from lookdev_eye_lab import studio_env as se

    state = ls.LabState(env_yaw=30.0)
    world = se.local_direction(65.0, 0.0)  # a light at az 35 appears at 35 + 30
    assert np.allclose(state.env_rotation() @ world, se.local_direction(35.0, 0.0))


def test_the_lab_does_not_touch_production_files_or_the_keymap():
    """No string in the lab's code (docstrings aside) names a path under `src/`, `tests/` or `config/`, or the
    keymap (D-L9: keys only after the practical test). The lab writes only below its own `out/`."""
    for path in LAB.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = {id(node.body[0].value) for node in ast.walk(tree)
                      if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)) and node.body
                      and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant)}
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
                assert "keymap" not in node.value, (path, node.value)
                assert not node.value.startswith(("src/", "tests/", "config/")), (path, node.value)


def test_run_parser_defaults():
    import sys

    sys.path.insert(0, str(LAB))
    try:
        import run
    finally:
        sys.path.remove(str(LAB))
    args = run.build_parser().parse_args([])
    assert (args.technique, args.cornea, args.view) == ("T-C", "C2", "front")
