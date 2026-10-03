"""`Application.set_status` (WP-SYM-LAB-03 H4, AD-013 H2 addendum § Decision).

The public status setter for a host's own messages: same `status_message` /
`status_serial` as `Application`'s internal `_set_status`, which stays.
Headless; deliberately not named `test_application_*` (that set is re-run by
the T-R5c pass-through run).
"""

from __future__ import annotations

import tests._bootstrap  # noqa: F401

from mirai.application import Application


def test_set_status_posts_message_and_counts():
    app = Application()
    serial = app.status_serial
    app.set_status("Symmetrie: X")
    assert app.status_message == "Symmetrie: X"
    assert app.status_serial == serial + 1


def test_repeated_identical_message_counts_twice():
    app = Application()
    serial = app.status_serial
    app.set_status("same")
    app.set_status("same")
    assert app.status_serial == serial + 2


def test_shares_the_serial_with_the_internal_setter():
    app = Application()
    app.init_scene("cube")
    serial = app.status_serial
    app._set_status("internal")
    app.set_status("public")
    assert app.status_serial == serial + 2
    assert app.status_message == "public"
