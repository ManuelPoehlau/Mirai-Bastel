"""Headless parts of the spike: the 24-bit ID encoding, argument handling, import boundary."""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from array import array

import pytest

from gpu_picking_spike import id_picker
from gpu_picking_spike import probe_gpu_picking as probe
from gpu_picking_spike._paths import EXPERIMENTS_DIR


def _rgba(*indices_or_none) -> bytes:
    words = array("I")
    for index in indices_or_none:
        if index is None:
            words.append(0)
        else:
            r, g, b = id_picker.encode_id(index)
            words.append(r | g << 8 | b << 16 | 255 << 24)
    return words.tobytes()


@pytest.mark.parametrize("index", [0, 1, 254, 255, 256, 65_535, 87_499, id_picker.MAX_ID - 1])
def test_encode_decode_roundtrip(index):
    assert id_picker.decode_ids(_rgba(index)) == {index}


def test_background_is_dropped_and_duplicates_collapse():
    assert id_picker.decode_ids(_rgba(None, 3, None, 3, 70_000)) == {3, 70_000}
    assert id_picker.decode_ids(_rgba(None, None)) == set()


def test_index_beyond_24_bits_is_refused():
    with pytest.raises(ValueError):
        id_picker.encode_id(id_picker.MAX_ID)


def test_probe_defaults_and_bad_arguments(capsys):
    args = probe.parse_args([])
    assert args.assets == list(probe.DEFAULT_ASSETS) and args.cursors == probe.DEFAULT_CURSORS
    for argv in (["--cursors", "0"], ["--repeats", "x"], ["--assets", "no_such_asset"]):
        with pytest.raises(SystemExit) as exc:
            probe.parse_args(argv)
        assert exc.value.code == 2
    assert probe.parse_args(["--assets", probe.GOLLUM]).assets == [probe.GOLLUM]


def test_agreement_classifies_half_pixel_and_real_differences():
    row = probe.Agreement()
    row.add(1, 1, 1, "a")
    row.add(1, 2, 2, "b")  # the CPU at the pixel centre agrees: sampling only
    row.add(1, None, 1, "c")
    row.add(None, 2, None, "d")
    row.add(1, 3, 1, "e")
    assert (row.same, row.half_px, row.gpu_none, row.cpu_none, row.other) == (1, 1, 1, 1, 1)
    assert row.total == 5 and row.real == 3 and len(row.examples) == 3
    assert all(line.isascii() for line in probe.agreement_lines({("vertex", True): row}))


def test_no_pyglet_playground_or_foreign_experiment_imports_at_import_time():
    script = textwrap.dedent(
        f"""
        import json, sys
        sys.path.insert(0, {str(EXPERIMENTS_DIR)!r})
        from gpu_picking_spike._paths import ensure_paths
        ensure_paths()
        import gpu_picking_spike.probe_gpu_picking as probe
        import gpu_picking_spike.id_picker
        probe.parse_args([])
        print(json.dumps(sorted(sys.modules)))
        """
    )
    out = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=True)
    loaded = set(json.loads(out.stdout))
    assert not {m for m in loaded if m == "pyglet" or m.startswith("pyglet.")}
    assert not {m for m in loaded if m.split(".")[0] in {"playground", "drag_cost", "symmetry_lab", "main"}}
