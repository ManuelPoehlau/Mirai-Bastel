"""Datei-Browser-Modell (`gui.file_browser_model`): Ordner, Filter, Suche, Sortierung, Pfadeingabe, Gedächtnis.

Reine Logik; alle Dateien liegen in `tmp_path`.
"""

from __future__ import annotations

import os
from pathlib import Path

import tests._bootstrap  # noqa: F401

from gui.file_browser_model import (
    ALL_FILTER,
    IMAGE_FILTER,
    OBJ_FILTER,
    SCENE_FILTER,
    BrowserModel,
    LastDirs,
    RecentFiles,
    default_places,
    format_size,
    natural_key,
)


def _tree(root: Path) -> Path:
    (root / "Meshes" / "alt").mkdir(parents=True)
    (root / "Texturen").mkdir()
    (root / "Meshes" / "kopf.obj").write_text("v 0 0 0\n")
    (root / "Meshes" / "Hand.OBJ").write_text("v 0 0 0\n")
    (root / "Meshes" / "notiz.txt").write_text("x")
    (root / "Meshes" / "alt" / "zahn.obj").write_text("v 0 0 0\n")
    (root / "Texturen" / "iris.png").write_bytes(b"\x89PNG")
    (root / "Texturen" / "haut.JPG").write_bytes(b"x" * 2048)
    (root / "szene.mirai.json").write_text("{}")
    return root


def _names(model) -> list[str]:
    return [e.name for e in model.visible()]


def test_lists_folders_first_then_only_the_files_of_the_filter(tmp_path):
    root = _tree(tmp_path)
    model = BrowserModel(filters=(OBJ_FILTER, ALL_FILTER), start=root / "Meshes")
    assert model.directory == root / "Meshes"
    assert _names(model) == ["alt", "Hand.OBJ", "kopf.obj"]  # Ordner zuerst, `.OBJ` zählt, `notiz.txt` nicht
    model.filter_index = 1
    assert _names(model) == ["alt", "Hand.OBJ", "kopf.obj", "notiz.txt"]


def test_double_extension_filter_and_images(tmp_path):
    root = _tree(tmp_path)
    scenes = BrowserModel(filters=(SCENE_FILTER,), start=root)
    assert _names(scenes) == ["Meshes", "Texturen", "szene.mirai.json"]
    images = BrowserModel(filters=(IMAGE_FILTER,), start=root / "Texturen")
    assert _names(images) == ["haut.JPG", "iris.png"]


def test_go_up_back_and_forward_walk_the_history(tmp_path):
    root = _tree(tmp_path)
    model = BrowserModel(start=root)
    assert model.go(root / "Meshes") and model.go(root / "Meshes" / "alt")
    assert model.up() and model.directory == root / "Meshes"
    assert model.back() and model.directory == root / "Meshes" / "alt"  # „Zurück“ ist der Weg, den man ging
    assert model.back() and model.directory == root / "Meshes"
    assert model.back() and model.directory == root
    assert not model.can_back() and model.can_forward()
    assert model.forward() and model.directory == root / "Meshes"
    assert model.go(root / "Texturen")  # ein neuer Weg verwirft das „Vor“
    assert not model.can_forward()


def test_a_missing_folder_keeps_the_old_one_and_names_the_reason(tmp_path):
    root = _tree(tmp_path)
    model = BrowserModel(start=root)
    assert not model.go(root / "gibt-es-nicht")
    assert model.directory == root and "nicht gefunden" in model.error
    assert not model.go(root / "szene.mirai.json")
    assert model.directory == root and "kein Ordner" in model.error
    assert model.go(root / "Meshes") and model.error == ""


def test_search_text_narrows_folders_and_files_without_case(tmp_path):
    model = BrowserModel(filters=(ALL_FILTER,), start=_tree(tmp_path) / "Meshes")
    model.query = "ALT"
    assert _names(model) == ["alt"]
    model.query = "o"
    assert _names(model) == ["Hand.OBJ", "kopf.obj", "notiz.txt"]
    model.query = ""
    assert len(model.visible()) == 4


def test_sorting_is_natural_and_by_date_and_size(tmp_path):
    for name, size, mtime in (("a10.obj", 1, 300), ("a2.obj", 30, 100), ("a1.obj", 20, 200)):
        f = tmp_path / name
        f.write_bytes(b"x" * size)
        os.utime(f, (mtime, mtime))
    model = BrowserModel(filters=(OBJ_FILTER,), start=tmp_path)
    assert _names(model) == ["a1.obj", "a2.obj", "a10.obj"]
    model.set_sort("name")  # dieselbe Spalte: umkehren
    assert _names(model) == ["a10.obj", "a2.obj", "a1.obj"]
    model.set_sort("date")  # neue Spalte: das Neueste oben
    assert _names(model) == ["a10.obj", "a1.obj", "a2.obj"]
    model.set_sort("size")  # neue Spalte: aufsteigend, die kleinste zuerst
    assert _names(model) == ["a10.obj", "a1.obj", "a2.obj"]
    assert natural_key("a2") < natural_key("A10")


def test_hidden_files_are_hidden_until_asked_for(tmp_path):
    (tmp_path / ".versteckt.obj").write_text("v")
    (tmp_path / "offen.obj").write_text("v")
    model = BrowserModel(filters=(OBJ_FILTER,), start=tmp_path)
    assert _names(model) == ["offen.obj"]
    model.show_hidden = True
    assert _names(model) == [".versteckt.obj", "offen.obj"]


def test_selecting_and_activating_entries(tmp_path):
    root = _tree(tmp_path)
    model = BrowserModel(filters=(OBJ_FILTER,), start=root / "Meshes")
    folder, hand, kopf = model.visible()
    model.select(kopf)
    assert model.choice() == root / "Meshes" / "kopf.obj"
    model.select(folder)  # ein Ordner ist keine Wahl
    assert model.choice() is None
    assert model.activate(folder) is None and model.directory == root / "Meshes" / "alt"  # Doppelklick: hinein
    assert model.choice() is None
    model.go(root / "Meshes")
    assert model.activate(model.visible()[1]) == root / "Meshes" / "Hand.OBJ"


def test_typed_paths_open_folders_and_pick_files(tmp_path):
    root = _tree(tmp_path)
    model = BrowserModel(filters=(IMAGE_FILTER,), start=root)
    assert model.submit(f'  "{root / "Texturen"}"  ') is None  # Anführungszeichen und Blanks fallen weg
    assert model.directory == root / "Texturen"
    assert model.submit("iris.png") == root / "Texturen" / "iris.png"  # relativ zum Ordner
    assert model.choice() == root / "Texturen" / "iris.png"
    assert model.submit("..") is None and model.directory == root
    assert model.submit(str(root / "Meshes" / "kopf.obj")) == root / "Meshes" / "kopf.obj"  # auch am Filter vorbei
    assert model.submit("nirgends.png") is None and "nicht gefunden" in model.error
    assert model.submit("   ") is None


def test_the_drive_list_is_the_top_on_windows_style_roots(tmp_path):
    model = BrowserModel(start=tmp_path, drives=lambda: [Path("C:\\"), Path("D:\\")])
    assert model.go(None)
    assert model.directory is None and [e.name for e in model.visible()] == ["C:\\", "D:\\"]
    assert all(e.is_dir and e.drive for e in model.visible())
    assert model.back() and model.directory == tmp_path


def test_breadcrumbs_lead_from_the_root_to_the_folder(tmp_path):
    root = _tree(tmp_path)
    model = BrowserModel(start=root / "Meshes" / "alt")
    crumbs = model.breadcrumbs()
    assert [p for _, p in crumbs if p is not None][-3:] == [root, root / "Meshes", root / "Meshes" / "alt"]
    assert crumbs[-1][0] == "alt"


def test_refresh_sees_new_files_and_keeps_the_selection(tmp_path):
    model = BrowserModel(filters=(OBJ_FILTER,), start=tmp_path)
    (tmp_path / "a.obj").write_text("v")
    model.refresh()
    model.select(model.visible()[0])
    (tmp_path / "b.obj").write_text("v")
    assert model.refresh() and _names(model) == ["a.obj", "b.obj"] and model.choice() == tmp_path / "a.obj"


def test_last_dirs_remember_per_purpose_and_survive_a_restart(tmp_path):
    store = tmp_path / "cfg" / "dirs.json"
    folder = tmp_path / "Bilder"
    folder.mkdir()
    dirs = LastDirs(store)
    assert dirs.get("image") is None
    dirs.remember("image", folder)
    assert LastDirs(store).get("image") == folder and LastDirs(store).get("mesh") is None
    assert LastDirs(store).get("mesh", default=tmp_path) == tmp_path  # Standardordner, wenn nichts gemerkt ist
    folder.rmdir()
    assert LastDirs(store).get("image", default=tmp_path) == tmp_path  # der gemerkte Ordner ist weg


def test_last_dirs_without_a_store_or_with_a_broken_one_do_not_fail(tmp_path):
    memory = LastDirs()
    memory.remember("scene", tmp_path)
    assert memory.get("scene") == tmp_path
    broken = tmp_path / "dirs.json"
    broken.write_text("{kaputt")
    assert LastDirs(broken).get("scene") is None
    blocked = LastDirs(tmp_path / "datei" / "dirs.json")
    (tmp_path / "datei").write_text("x")  # der Ordner des Speichers ist eine Datei: Schreiben scheitert still
    blocked.remember("scene", tmp_path)
    assert blocked.get("scene") == tmp_path


def test_default_places_list_only_existing_folders(tmp_path):
    (tmp_path / "Documents").mkdir()
    extra = tmp_path / "scenes"
    extra.mkdir()
    places = default_places(tmp_path, extra=(("Szenen", extra), ("Weg", tmp_path / "weg")))
    assert [p.label for p in places] == ["Home", "Dokumente", "Szenen"]


def test_format_size():
    assert format_size(10) == "10 B" and format_size(2048) == "2.0 KB" and format_size(5 * 1024**2) == "5.0 MB"


def test_recent_files_keep_the_last_ten_newest_first_without_duplicates(tmp_path):
    files = []
    for i in range(12):
        f = tmp_path / f"s{i}.obj"
        f.write_text("v")
        files.append(f)
    recent = RecentFiles()
    for f in files:
        recent.add("mesh", f)
    recent.add("mesh", files[5])  # erneut geöffnet: wieder ganz oben, kein Doppel
    items = recent.items()
    assert len(items) == 10 and items[0] == ("mesh", files[5])
    assert [p.name for _, p in items[1:3]] == ["s11.obj", "s10.obj"]
    assert files[0] not in [p for _, p in items]


def test_recent_files_skip_deleted_files_and_persist(tmp_path):
    store = tmp_path / "cfg" / "recent.json"
    a, b = tmp_path / "a.mirai.json", tmp_path / "b.obj"
    a.write_text("{}")
    b.write_text("v")
    recent = RecentFiles(store)
    recent.add("scene", a)
    recent.add("mesh", b)
    assert RecentFiles(store).items() == [("mesh", b), ("scene", a)]
    b.unlink()
    assert RecentFiles(store).items() == [("scene", a)]  # was es nicht mehr gibt, wird nicht angeboten
    store.write_text("[1, 2")
    assert RecentFiles(store).items() == []  # kaputter Speicher: leer, kein Fehler
