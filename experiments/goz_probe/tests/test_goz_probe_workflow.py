"""Install / receive / listen / send on a fake GoZ root (README §5, §6): no program is ever started."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

import pytest

from goz_probe import install_probe_app as installer
from goz_probe import make_meshes, probe_listener, probe_receiver, probe_send
from goz_probe._paths import EXPERIMENT_DIR
from goz_probe.goz_probe_format import encode_goz
from goz_probe.probe_common import APP_MARKER, GozPaths, ProbeError, read_object_list, redact, write_goz_text


@pytest.fixture
def env(tmp_path):
    root = tmp_path / "Pixologic"
    (root / "GoZBrush").mkdir(parents=True)
    (root / "GoZProjects" / "Default").mkdir(parents=True)
    zbrush = tmp_path / "ZBrush 2022" / "ZBrush.exe"
    (zbrush.parent / "ZStartup" / "ExportTamplates").mkdir(parents=True)
    (zbrush.parent / "ZStartup" / "ExportTamplates" / "GoZ Complete Binary.GoZ").write_bytes(b"")
    (root / "GoZBrush" / "GoZ_Config.txt").write_text(f'PATH = "{zbrush}"\r\nIMPORT_AS_SUBTOOL = TRUE\r\n')
    meshes = tmp_path / "meshes"
    make_meshes.write_meshes(meshes, ids=("A",))
    return {"root": root, "paths": GozPaths(root), "captures": tmp_path / "captures", "inbox": tmp_path / "inbox",
            "meshes": meshes}


def _tree(folder):
    return sorted((str(p.relative_to(folder)), p.stat().st_size if p.is_file() else -1) for p in folder.rglob("*"))


def test_install_replace_uninstall(env):
    paths = env["paths"]
    written = installer.install(paths, replace=False, python="C:/Python/python.exe", captures=env["captures"])
    assert {p.name for p in written} == {"Locate.bat", "Init.bat", "Edit.bat", "GoZ_Info.txt", APP_MARKER}
    edit = (paths.app_dir / "Edit.bat").read_bytes().decode()
    assert '"C:/Python/python.exe" -I ' in edit and str(env["root"]) in edit
    assert not re.search(r"@[A-Z_]+@", edit)
    assert b"\r\n" in (paths.app_dir / "Edit.bat").read_bytes()
    assert (paths.app_dir / "GoZ_Info.txt").read_text().count('EDIT_COMMAND\t= "Edit.bat"') == 1
    with pytest.raises(ProbeError, match="already installed"):
        installer.install(paths, replace=False, python="p", captures=env["captures"])
    installer.install(paths, replace=True, python="p", captures=env["captures"])
    assert installer.uninstall(paths) and not paths.app_dir.exists()
    assert not installer.uninstall(paths)


def test_foreign_app_folder_is_never_touched(env):
    paths = env["paths"]
    paths.app_dir.mkdir(parents=True)
    (paths.app_dir / "theirs.txt").write_text("x")
    with pytest.raises(ProbeError, match="not ours"):
        installer.install(paths, replace=True, python="p", captures=env["captures"])
    with pytest.raises(ProbeError, match="not ours"):
        installer.uninstall(paths)
    assert (paths.app_dir / "theirs.txt").read_text() == "x"


def test_install_needs_gozbrush(tmp_path):
    with pytest.raises(ProbeError, match="GoZ installed"):
        installer.install(GozPaths(tmp_path / "none"), replace=False, python="p", captures=tmp_path)


def test_inventory_is_read_only(env):
    before = _tree(env["root"])
    report = installer.inventory(env["root"])
    assert _tree(env["root"]) == before
    assert "'GoZ Complete Binary.GoZ': FOUND" in report and "GoZ_Config.txt" in report


def _send(env, *extra):
    argv = ["--root", str(env["root"]), "--meshes", str(env["meshes"]), "--captures", str(env["captures"]), *extra]
    return probe_send.main(argv)


def test_dry_run_send_then_receive_round_trip(env):
    assert _send(env, "--mesh", "A", "--dry-run") == 0
    paths = env["paths"]
    identifier = str(paths.project_dir() / "E1_A")
    assert read_object_list(paths.object_list) == [identifier]
    assert paths.object_list.read_bytes().endswith(b"\r\n")
    assert paths.application_file.read_text() == "MiraiProbe"
    cap = probe_receiver.receive(paths, captures=env["captures"], inbox=env["inbox"], meshes=env["meshes"], settle=0.05)
    log = json.loads((cap / "receiver_log.json").read_text())
    obj = log["objects"][0]
    assert obj["complete_at_start"] and obj["changed_after_settle"] is False
    assert obj["matched_sent"]["id"] == "A" and obj["analysis"]["positions"]["changed"] == 0
    assert (cap / "GoZ_ObjectList.txt").is_file() and "Rundreise unverändert" in (cap / "dump.txt").read_text()
    assert log["listener"]["alive"] is False


def test_truncated_file_is_reported_not_parsed(env):
    paths = env["paths"]
    identifier = str(paths.project_dir() / "broken")
    data = encode_goz("broken", [(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)])
    (paths.project_dir() / "broken.GoZ").write_bytes(data[:-20])
    write_goz_text(paths.object_list, [identifier, str(paths.project_dir() / "missing")])
    cap = probe_receiver.receive(paths, captures=env["captures"], inbox=env["inbox"], meshes=env["meshes"], settle=0)
    objects = json.loads((cap / "receiver_log.json").read_text())["objects"]
    assert objects[0]["complete_at_start"] is False and "format_error" in objects[0]
    assert objects[1]["stat_at_start"] == {"exists": False} and objects[1]["complete_at_start"] is False


def test_ticket_to_a_running_listener(env):
    lock = probe_listener.acquire_lock(env["inbox"])
    try:
        with pytest.raises(ProbeError, match="another listener"):
            probe_listener.acquire_lock(env["inbox"])
        _send(env, "--mesh", "A", "--dry-run")
        cap = probe_receiver.receive(env["paths"], captures=env["captures"], inbox=env["inbox"], meshes=env["meshes"],
                                     settle=0)
        assert json.loads((cap / "receiver_log.json").read_text())["listener"]["alive"] is True
        tickets = list(env["inbox"].glob("ticket_*.json"))
        assert len(tickets) == 1 and not list(env["inbox"].glob("*.tmp"))
        with open(env["inbox"] / "log.txt", "w", encoding="utf-8") as log:
            handled = probe_listener.poll_once(env["inbox"], log)
        assert handled[0]["all_ok"] and handled[0]["objects"] == 1
        assert not list(env["inbox"].glob("ticket_*.json")) and len(list((env["inbox"] / "done").iterdir())) == 1
    finally:
        probe_listener.release_lock(lock)
    assert not lock.exists()


def test_stale_lock_is_replaced(env):
    env["inbox"].mkdir()
    (env["inbox"] / probe_receiver.LOCK_NAME).write_text(json.dumps({"pid": 2 ** 22 + 12345}))
    lock = probe_listener.acquire_lock(env["inbox"])
    assert json.loads(lock.read_text())["pid"] == os.getpid()
    probe_listener.release_lock(lock)


def test_identifier_is_reused_for_the_same_mesh(env):
    run = env["captures"] / "20260101-000000_000_send_A"
    run.mkdir(parents=True)
    identifier = str(env["paths"].project_dir() / "E1_A3")
    (run / "send_log.json").write_text(json.dumps({"mesh": "A", "identifier": identifier, "dry_run": False}))
    assert _send(env, "--mesh", "A", "--dry-run") == 0
    assert read_object_list(env["paths"].object_list) == [identifier]
    assert (env["paths"].project_dir() / "E1_A3.GoZ").is_file()


def test_resend_refuses_a_newer_zbrush_file(env):
    _send(env, "--mesh", "A", "--dry-run")
    paths = env["paths"]
    cap = probe_receiver.receive(paths, captures=env["captures"], inbox=env["inbox"], meshes=env["meshes"], settle=0)
    assert _send(env, "--resend", "last", "--dry-run") == 0  # identical bytes: not rewritten
    target = paths.project_dir() / "E1_A.GoZ"
    target.write_bytes(encode_goz("newer", [(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)]))
    assert _send(env, "--resend", str(cap), "--dry-run") == 2
    assert _send(env, "--resend", str(cap), "--dry-run", "--force") == 0
    assert target.read_bytes() == next(cap.glob("00_*.GoZ")).read_bytes()


def test_redact_keeps_keys_and_words(monkeypatch):
    monkeypatch.setenv("USERPROFILE", r"C:\Users\Manuel")
    monkeypatch.setenv("USERNAME", "Manuel")
    value = {"root": r"C:\Users\Manuel\repo", "word": "Manuelle", "p": r"D:\data\Manuel\x",
             "other": r"C:\Users\Manuel2\x", "cmd": r'cwd=[C:\Users\Manuel] "C:\Users\Manuel\py.exe"'}
    assert redact(value) == {
        "root": r"%USERPROFILE%\repo", "word": "Manuelle", "p": r"D:\data\%USERNAME%\x",
        "other": r"C:\Users\Manuel2\x", "cmd": r'cwd=[%USERPROFILE%] "%USERPROFILE%\py.exe"',
    }
    monkeypatch.delenv("USERPROFILE")
    monkeypatch.delenv("USERNAME")
    assert redact({"x": "/tmp/a/root"}) == {"x": "/tmp/a/root"}


@pytest.mark.parametrize(
    "script", ["make_meshes.py", "install_probe_app.py", "probe_receiver.py", "probe_listener.py", "probe_send.py"]
)
def test_scripts_run_isolated_without_pyglet(script):
    probe = (
        "import runpy, sys; sys.argv = [%r, '--help']\n"
        "try:\n    runpy.run_path(%r, run_name='__main__')\nexcept SystemExit as e:\n    assert e.code == 0\n"
        "assert 'pyglet' not in sys.modules, 'pyglet imported'\n"
    ) % (script, str(EXPERIMENT_DIR / script))
    result = subprocess.run([sys.executable, "-I", "-c", probe], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
