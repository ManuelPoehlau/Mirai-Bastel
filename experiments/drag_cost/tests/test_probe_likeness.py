"""`probe_likeness.py` (AD-042 §10.4): arguments and the generated photo, headless."""

from __future__ import annotations

import pytest

from drag_cost import probe_likeness as probe


def test_defaults_and_refusals(tmp_path):
    args = probe.parse_args([])
    assert tuple(args.size) == (1024, 768) and args.draws == probe.DEFAULT_DRAWS and args.photo is None
    with pytest.raises(SystemExit):
        probe.parse_args(["--draws", "0"])
    with pytest.raises(SystemExit):
        probe.parse_args(["--photo", str(tmp_path / "missing.jpg")])
    photo = tmp_path / "a.jpg"
    photo.write_bytes(b"x")
    assert probe.parse_args(["--photo", str(photo)]).photo == photo


def test_the_generated_photo():
    rgba = probe.test_photo((300, 200))
    assert rgba.shape == (200, 300, 4) and rgba.dtype.name == "uint8" and (rgba[..., 3] == 255).all()
    assert rgba[0, 0, 0] == 0 and rgba[0, -1, 0] == 255 and rgba[-1, 0, 1] == 255
