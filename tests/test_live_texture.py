"""AD-037 Phase 1c: `viewport.live_texture.LiveTexture` bookkeeping (headless; the GL path is in test_gl_texture.py)."""

from __future__ import annotations

import numpy as np
import pytest

import tests._bootstrap  # noqa: F401

from viewport.live_texture import LiveTexture


def test_the_first_take_is_a_full_upload_then_only_marked_boxes():
    live = LiveTexture(np.zeros((16, 32, 4), np.uint8))
    assert (live.width, live.height) == (32, 16)
    assert live.take() == (True, [], True)
    assert not live.pending and live.take() == (False, [], False)
    live.mark(-4, 2, 8, 99)  # clipped
    live.mark(5, 5, 5, 9)  # empty
    assert live.take() == (False, [(0, 2, 8, 16)], False)  # "deferred": no mipmaps until finish()
    live.finish()
    assert live.take() == (False, [], True)


def test_the_mip_policies():
    frame = LiveTexture(np.zeros((4, 4, 4), np.uint8), mipmaps="frame")
    frame.take()
    frame.mark(0, 0, 1, 1)
    assert frame.take() == (False, [(0, 0, 1, 1)], True)
    none = LiveTexture(np.zeros((4, 4, 4), np.uint8), mipmaps="none")
    assert none.take() == (True, [], False)
    none.finish()
    none.mark_all()
    assert none.take() == (True, [], False)


@pytest.mark.parametrize("rgba", [np.zeros((4, 4, 3), np.uint8), np.zeros((4, 4, 4), np.float32),
                                  np.zeros((4, 8, 4), np.uint8)[:, ::2]])
def test_only_contiguous_rgba8_is_taken(rgba):
    with pytest.raises(ValueError):
        LiveTexture(rgba)


def test_an_unknown_mip_policy_is_refused():
    with pytest.raises(ValueError):
        LiveTexture(np.zeros((4, 4, 4), np.uint8), mipmaps="always")
