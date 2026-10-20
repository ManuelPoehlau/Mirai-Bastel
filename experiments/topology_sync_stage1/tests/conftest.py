import sys
from pathlib import Path

_EXPERIMENTS = Path(__file__).resolve().parents[2]
if str(_EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS))

from topology_sync_stage1._paths import ensure_paths  # noqa: E402

ensure_paths()
