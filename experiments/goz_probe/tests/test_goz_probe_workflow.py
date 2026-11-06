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


def test_ticket_paths_survive_a_user_profile(env, tmp_path, monkeypatch):
    """E1 run 2026-11-05: with the repository under the user profile, the redacted ticket pointed at
    `%USERPROFILE%\\...` and the listener reported "hashes NOT ok". Tickets are machine data and stay unredacted."""
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("USERNAME", tmp_path.name)
    lock = probe_listener.acquire_lock(env["inbox"])
    try:
        _send(env, "--mesh", "A", "--dry-run")
        cap = probe_receiver.receive(env["paths"], captures=env["captures"], inbox=env["inbox"], meshes=env["meshes"],
                                     settle=0)
        ticket = json.loads(next(env["inbox"].glob("ticket_*.json")).read_text())
        assert ticket["objects"][0]["copy"].startswith(str(cap))
        assert "%USERPROFILE%" in (cap / "receiver_log.json").read_text()  # the committed log stays redacted
        with open(env["inbox"] / "log.txt", "w", encoding="utf-8") as log:
            assert probe_listener.poll_once(env["inbox"], log)[0]["all_ok"]
    finally:
        probe_listener.release_lock(lock)


def test_check_copy_names_the_problem(tmp_path):
    copy = tmp_path / "x.GoZ"
    copy.write_bytes(b"abc")
    from goz_probe.probe_common import sha256

    assert probe_listener.check_copy(str(copy), sha256(b"abc")) == "ok"
    assert probe_listener.check_copy(str(copy), sha256(b"abd")) == "hash mismatch"
    assert probe_listener.check_copy(str(tmp_path / "gone.GoZ"), "00").startswith("copy not found")
    assert probe_listener.check_copy(None, "00") == "no copy"


def test_recheck_done(env, capsys):
    (env["inbox"] / "done").mkdir(parents=True)
    assert probe_listener.recheck_done(env["inbox"]) == 0
    assert "no tickets" in capsys.readouterr().out


def test_axis_bridge_send_flips_y_and_z_under_its_own_identifier(env):
    """README §11 item 1: `--axis bridge` writes (x, -y, -z) and never reuses the identifier of an unflipped send."""
    run = env["captures"] / "20260101-000000_000_send_A"
    run.mkdir(parents=True)
    (run / "send_log.json").write_text(json.dumps(
        {"mesh": "A", "identifier": str(env["paths"].project_dir() / "E1_A3"), "dry_run": False}))
    assert _send(env, "--mesh", "A", "--axis", "bridge", "--dry-run") == 0
    paths = env["paths"]
    identifier = str(paths.project_dir() / "E1_A_P1")
    assert read_object_list(paths.object_list) == [identifier]
    from goz_probe.goz_probe_format import as_float32, read_goz

    sent = json.loads((env["meshes"] / "A.sent.json").read_text())
    got = read_goz(identifier + ".GoZ").points
    assert got == [tuple(as_float32(s * c) for s, c in zip((1, -1, -1), p)) for p in sent["positions"]]
    cap = probe_receiver.receive(paths, captures=env["captures"], inbox=env["inbox"], meshes=env["meshes"], settle=0.05)
    dump_text = (cap / "dump.txt").read_text()
    assert "matched sent mesh A" in dump_text



def test_groups_bands_send_writes_a_groups_block_and_the_dump_shows_it(env):
    """E2 (P2 polygroups): `--groups bands` sends ids 101-104 under its own identifier."""
    make_meshes.write_meshes(env["meshes"], ids=("C",))
    assert _send(env, "--mesh", "C", "--axis", "bridge", "--groups", "bands", "--dry-run") == 0
    paths = env["paths"]
    identifier = str(paths.project_dir() / "E1_C_P1_G")
    assert read_object_list(paths.object_list) == [identifier]
    from goz_probe.goz_probe_format import read_goz

    goz = read_goz(identifier + ".GoZ")
    assert sorted(set(goz.groups)) == [101, 102, 103, 104] and len(goz.groups) == len(goz.faces)
    cap = probe_receiver.receive(paths, captures=env["captures"], inbox=env["inbox"], meshes=env["meshes"], settle=0.05)
    assert "groups (id: faces): {101:" in (cap / "dump.txt").read_text()


def test_install_import_polygroups_variant(env):
    installer.install(env["paths"], replace=False, python=sys.executable, captures=env["captures"],
                      import_polygroups=True)
    assert b"IMPORT_POLYGROUPS\t= TRUE\r\n" in (env["paths"].app_dir / "GoZ_Info.txt").read_bytes()


# -- E3 (P3: UVs, textures, morph targets) -----------------------------------------------------------------------------


def _receive(env):
    return probe_receiver.receive(env["paths"], captures=env["captures"], inbox=env["inbox"], meshes=env["meshes"],
                                  settle=0.05)


@pytest.mark.parametrize("mode, suffix, reading", [("as-is", "_UV", "'identical': 324"), ("flip-v", "_UVF", "'flip_v': 324")])
def test_uvs_send_a_uv4_block_and_the_receiver_classifies_them(env, mode, suffix, reading):
    make_meshes.write_meshes(env["meshes"], ids=("C",))
    assert _send(env, "--mesh", "C", "--axis", "bridge", "--uvs", mode, "--dry-run") == 0
    identifier = str(env["paths"].project_dir() / f"E1_C_P1{suffix}")
    assert read_object_list(env["paths"].object_list) == [identifier]
    from goz_probe.goz_probe_format import TAG_UV4_LIST, read_goz

    goz = read_goz(identifier + ".GoZ")
    assert goz.uv_tag == TAG_UV4_LIST and len(goz.uvs) == len(goz.faces) == 324
    text = (_receive(env) / "dump.txt").read_text()
    assert "uvs (UV4_LIST): 324 faces" in text and reading in text, text


def test_uvs_need_a_mesh_with_uvs(env):
    assert _send(env, "--mesh", "A", "--uvs", "as-is", "--dry-run") == 2


def test_target_bump_sends_base_and_target_as_two_objects(env):
    make_meshes.write_meshes(env["meshes"], ids=("C",))
    assert _send(env, "--mesh", "C", "--axis", "bridge", "--target", "bump", "--dry-run") == 0
    project = env["paths"].project_dir()
    assert read_object_list(env["paths"].object_list) == [str(project / "E1_C_P1_B"), str(project / "E1_C_P1_T")]
    cap = _receive(env)
    log = json.loads((cap / "receiver_log.json").read_text())
    base, target = (o["analysis"]["target_bump"] for o in log["objects"])
    assert base["weight"] == pytest.approx(0.0, abs=1e-6)  # float32 against the float64 base
    assert target["weight"] == pytest.approx(1.0, abs=1e-6) and target["points_equal_to_target"] == 326
    assert "Morph-Ziel 'bump' (bridge): Gewicht 1.0000" in (cap / "dump.txt").read_text()
    assert (env["meshes"] / "C_bump.obj").is_file()


def test_the_obj_layer_path_reads_with_zbrushs_obj_offset(env):
    """E3 layer route: C.obj imported in ZBrush, C_bump.obj imported into a layer, GoZ: ZBrush's OBJ placement (T2)
    y' = -y + (ymin + ymax), z' = -z + (zmin + zmax); the weight still reads as the layer's strength."""
    make_meshes.write_meshes(env["meshes"], ids=("C",))
    sent = json.loads((env["meshes"] / "C.sent.json").read_text())
    from goz_probe.goz_probe_format import GozFile
    from goz_probe.probe_common import _bbox, analyse

    lo, hi = _bbox(sent["positions"])
    layer = [[p[0] + 0.25 * d[0], -(p[1] + 0.25 * d[1]) + lo[1] + hi[1], -(p[2] + 0.25 * d[2]) + lo[2] + hi[2]]
             for p, d in zip(sent["positions"], sent["target_bump"])]
    goz = GozFile(header_text=b"", points=[tuple(p) for p in layer], faces=[tuple(f) for f in sent["faces"]])
    result = analyse(goz, sent)["target_bump"]
    assert result["axis"] == "obj" and result["weight"] == pytest.approx(0.25, abs=1e-6)


def test_a_half_applied_layer_reads_as_weight_one_half(env):
    """What ZBrush would return with the target in a layer at 50 %: base + 0.5 d."""
    make_meshes.write_meshes(env["meshes"], ids=("C",))
    sent = json.loads((env["meshes"] / "C.sent.json").read_text())
    from goz_probe.probe_common import compare_bump

    half = [[b + 0.5 * dd for b, dd in zip(p, d)] for p, d in zip(sent["positions"], sent["target_bump"])]
    result = compare_bump(sent, half)
    assert result["weight"] == pytest.approx(0.5) and result["max_rest"] < 1e-12
    assert 0 < sum(1 for d in sent["target_bump"] if d[2] > 0) < 326  # a local bump, not the whole head


def test_receiver_copies_a_texture_map_the_file_names(env, tmp_path):
    from goz_probe.goz_probe_format import TAG_TEXTURE_MAP_PATH, _block, _string_payload

    image = tmp_path / "E1_C_TXTR.bmp"
    image.write_bytes(b"BM" + b"\0" * 30)
    data = encode_goz("A", [(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)])
    data = data[:-16] + _block(TAG_TEXTURE_MAP_PATH, 1, _string_payload(str(image))) + data[-16:]
    identifier = str(env["paths"].project_dir() / "E1_TX")
    (env["paths"].project_dir() / "E1_TX.GoZ").write_bytes(data)
    write_goz_text(env["paths"].object_list, [identifier])
    cap = _receive(env)
    log = json.loads((cap / "receiver_log.json").read_text())
    (entry,) = log["objects"][0]["maps"]
    assert entry["block"] == "TEXTURE_MAP_PATH" and entry["bytes"] == 32 and entry["head"].startswith("424d")
    assert (cap / "00map_E1_C_TXTR.bmp").read_bytes() == image.read_bytes()
