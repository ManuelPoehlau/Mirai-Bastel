"""Production uses SubD without `experiments/` or `playground/` (2026-10-23).

Fresh subprocess with only the production paths a window start has (`src/`, repo root, `examples/`,
as `src/main.py` puts them), import the SubD package, its GL sink, `Application` and the evaluator,
then build an app and switch the preview on; afterwards no loaded module may live under
`experiments/` or `playground/`.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

_SCRIPT = textwrap.dedent(
    """
    import json, os, sys
    repo = {repo!r}
    sys.path[:0] = [os.path.join(repo, "src"), repo, os.path.join(repo, "examples")]
    import mirai.subdivision, mirai.subdivision.gl_lines, mirai.subdivision.catmull_clark
    from mirai.application import Application
    from mirai.interaction.input import Input
    from loaders.assets import asset_path
    app = Application()
    app.init_scene("obj", obj_path=asset_path("head_basemesh"))
    app.key_press(Input("key", "v"))
    app.viewport.sync()
    assert app.subdivision.provider.surface_mesh is not None
    bad = sorted(
        name for name, module in list(sys.modules.items())
        if any(
            (getattr(module, "__file__", None) or "").startswith(os.path.join(repo, d) + os.sep)
            for d in ("experiments", "playground")
        )
    )
    print(json.dumps(bad))
    """
)


def test_production_subd_imports_nothing_from_experiments_or_playground():
    result = subprocess.run(
        [sys.executable, "-c", _SCRIPT.format(repo=str(REPO))], capture_output=True, text=True, cwd=str(REPO)
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.strip().splitlines()[-1]) == []


def test_no_production_source_names_the_lab_package():
    offenders = [
        str(path.relative_to(REPO))
        for path in (REPO / "src").rglob("*.py")
        if "import subdivision_lab" in path.read_text(encoding="utf-8")
        or "from subdivision_lab" in path.read_text(encoding="utf-8")
        or "from experiments" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []
