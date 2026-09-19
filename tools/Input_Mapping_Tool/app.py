"""Mirai-Bastel — Input Binding Config (Artist Truth).

Standalone, isolated tool. See README.md in this folder for scope and
architectural boundaries.

Run with:
    python app.py

Requires only the Python standard library (tkinter).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional

import storage

# -- Modifier bit masks -----------------------------------------------------
# Tk's event.state bitmask. SHIFT/CONTROL are stable across platforms; ALT
# is not (X11 uses Mod1, Windows commonly reports 0x20000 / "Mod2"-ish bits
# depending on Tcl/Tk build). We check both known bits so this behaves
# correctly on the target machine (Windows). This is best-effort by design —
# it only affects a design tool, not runtime input handling.
_STATE_SHIFT = 0x0001
_STATE_CONTROL = 0x0004
_STATE_ALT_BITS = (0x20000, 0x0008)

_MODIFIER_KEYSYMS = {
    "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R",
    "Meta_L", "Meta_R", "Super_L", "Super_R", "Caps_Lock",
}

_KEY_DISPLAY_OVERRIDES = {
    "space": "Space",
    "Return": "Enter",
    "BackSpace": "Backspace",
    "Delete": "Delete",
    "Tab": "Tab",
    "Up": "Arrow Up",
    "Down": "Arrow Down",
    "Left": "Arrow Left",
    "Right": "Arrow Right",
    "Prior": "Page Up",
    "Next": "Page Down",
    "Home": "Home",
    "End": "End",
    "Insert": "Insert",
}


def _key_display(keysym: str) -> str:
    if keysym in _KEY_DISPLAY_OVERRIDES:
        return _KEY_DISPLAY_OVERRIDES[keysym]
    if len(keysym) == 1:
        return keysym.upper()
    if keysym.startswith("F") and keysym[1:].isdigit():
        return keysym  # F1..F12
    return keysym.capitalize()


def _format_binding(state: int, main: str) -> str:
    parts = []
    if state & _STATE_CONTROL:
        parts.append("Ctrl")
    if any(state & bit for bit in _STATE_ALT_BITS):
        parts.append("Alt")
    if state & _STATE_SHIFT:
        parts.append("Shift")
    parts.append(main)
    return "+".join(parts)


class InputBindingConfigApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Mirai-Bastel — Input Binding Config (Artist Truth)")
        self.root.geometry("780x560")

        self.doc = storage.load_or_seed()
        self.capturing_id: Optional[str] = None
        self._capture_bind_ids: list[tuple[tk.Misc, str, str]] = []

        self._build_ui()
        self._populate_tree()
        self._refresh_conflicts()

    # -- UI construction -----------------------------------------------

    def _build_ui(self) -> None:
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill="x")

        ttk.Label(top, text="Suche:").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._populate_tree())
        search_entry = ttk.Entry(top, textvariable=self.search_var, width=30)
        search_entry.pack(side="left", padx=(4, 12))

        self.capture_btn = ttk.Button(
            top, text="Bindung erfassen", command=self._on_capture_clicked, state="disabled"
        )
        self.capture_btn.pack(side="left")

        self.clear_btn = ttk.Button(
            top, text="Bindung löschen", command=self._on_clear_clicked, state="disabled"
        )
        self.clear_btn.pack(side="left", padx=(6, 0))

        columns = ("binding", "runtime_ref")
        self.tree = ttk.Treeview(self.root, columns=columns, show="tree headings")
        self.tree.heading("#0", text="Funktion")
        self.tree.heading("binding", text="Bindung")
        self.tree.heading("runtime_ref", text="Runtime-Referenz (Info)")
        self.tree.column("#0", width=340)
        self.tree.column("binding", width=180)
        self.tree.column("runtime_ref", width=180)
        self.tree.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        self.tree.tag_configure("category", font=("TkDefaultFont", 9, "bold"))
        self.tree.tag_configure("conflict", foreground="#b45309")

        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Return>", lambda _e: self._on_capture_clicked())

        bottom = ttk.Frame(self.root, padding=(8, 4))
        bottom.pack(fill="x")
        self.status_var = tk.StringVar(value="Bereit.")
        ttk.Label(bottom, textvariable=self.status_var).pack(side="left")

        self.conflict_var = tk.StringVar(value="")
        ttk.Label(bottom, textvariable=self.conflict_var, foreground="#b45309").pack(
            side="left", padx=(16, 0)
        )

    # -- Data helpers -----------------------------------------------------

    def _entries(self) -> list[dict]:
        return self.doc["bindings"]

    def _entry_by_id(self, entry_id: str) -> dict:
        for entry in self._entries():
            if entry["id"] == entry_id:
                return entry
        raise KeyError(entry_id)

    # -- Tree population ----------------------------------------------

    def _populate_tree(self) -> None:
        selected = self._selected_leaf_id()
        for item in self.tree.get_children():
            self.tree.delete(item)

        query = self.search_var.get().strip().lower()
        conflicts = storage.find_conflicts(self._entries())

        by_category: dict[str, list[dict]] = {}
        for entry in self._entries():
            by_category.setdefault(entry["category"], []).append(entry)

        categories = sorted(by_category.keys(), key=storage.category_sort_key)

        for category in categories:
            entries = by_category[category]
            if query:
                entries = [
                    e for e in entries
                    if query in e["label"].lower() or query in e["id"].lower()
                ]
                if not entries:
                    continue
            cat_iid = f"cat::{category}"
            self.tree.insert("", "end", iid=cat_iid, text=category, open=True, tags=("category",))
            for entry in entries:
                tags = ("conflict",) if entry["id"] in _flatten_conflict_ids(conflicts) else ()
                self.tree.insert(
                    cat_iid,
                    "end",
                    iid=entry["id"],
                    text="    " + entry["label"],
                    values=(entry.get("binding", ""), entry.get("runtime_ref") or "—"),
                    tags=tags,
                )

        if selected and self.tree.exists(selected):
            self.tree.selection_set(selected)

    def _selected_leaf_id(self) -> Optional[str]:
        sel = self.tree.selection()
        if not sel:
            return None
        iid = sel[0]
        if iid.startswith("cat::"):
            return None
        return iid

    # -- Selection / capture wiring ----------------------------------------

    def _on_select(self, _event=None) -> None:
        leaf = self._selected_leaf_id()
        state = "normal" if leaf else "disabled"
        self.capture_btn.config(state=state)
        self.clear_btn.config(state=state)

    def _on_double_click(self, _event=None) -> None:
        leaf = self._selected_leaf_id()
        if leaf:
            self._start_capture(leaf)

    def _on_capture_clicked(self) -> None:
        leaf = self._selected_leaf_id()
        if leaf:
            self._start_capture(leaf)

    def _on_clear_clicked(self) -> None:
        leaf = self._selected_leaf_id()
        if not leaf:
            return
        self._entry_by_id(leaf)["binding"] = ""
        storage.save(self.doc)
        self._populate_tree()
        self._refresh_conflicts()
        self.status_var.set(f"Bindung für '{leaf}' gelöscht.")

    # -- Capture mode -------------------------------------------------

    def _start_capture(self, entry_id: str) -> None:
        if self.capturing_id is not None:
            return
        self.capturing_id = entry_id
        label = self._entry_by_id(entry_id)["label"]
        self.status_var.set(f"Warte auf Eingabe für '{label}' … (Esc zum Abbrechen)")

        self._bind_capture(self.root, "<KeyPress>", self._on_capture_key)
        for button, name in (("1", "LMB"), ("2", "MMB"), ("3", "RMB")):
            self._bind_capture(self.root, f"<ButtonPress-{button}>", self._make_button_handler(name))
        self._bind_capture(self.root, "<MouseWheel>", self._on_capture_wheel)

    def _bind_capture(self, widget: tk.Misc, sequence: str, handler) -> None:
        widget.bind_all(sequence, handler, add=False)
        self._capture_bind_ids.append((widget, sequence, ""))

    def _end_capture(self) -> None:
        for widget, sequence, _ in self._capture_bind_ids:
            widget.unbind_all(sequence)
        self._capture_bind_ids.clear()
        self.capturing_id = None
        self.status_var.set("Bereit.")

    def _make_button_handler(self, name: str):
        def handler(event):
            self._finalize_capture(_format_binding(event.state, name))
        return handler

    def _on_capture_key(self, event) -> None:
        if event.keysym == "Escape":
            self._end_capture()
            return
        if event.keysym in _MODIFIER_KEYSYMS:
            return  # keep listening — this was only a modifier going down
        self._finalize_capture(_format_binding(event.state, _key_display(event.keysym)))

    def _on_capture_wheel(self, event) -> None:
        direction = "Wheel Up" if event.delta > 0 else "Wheel Down"
        self._finalize_capture(_format_binding(event.state, direction))

    def _finalize_capture(self, binding_str: str) -> None:
        entry_id = self.capturing_id
        if entry_id is None:
            return
        self._entry_by_id(entry_id)["binding"] = binding_str
        self._end_capture()
        storage.save(self.doc)
        self._populate_tree()
        self._refresh_conflicts()
        self.status_var.set(f"'{entry_id}' → {binding_str} gespeichert.")

    # -- Conflicts ------------------------------------------------------

    def _refresh_conflicts(self) -> None:
        conflicts = storage.find_conflicts(self._entries())
        if not conflicts:
            self.conflict_var.set("")
            return
        parts = []
        for _normalized, ids in sorted(conflicts.items()):
            # Display the binding as the artist actually typed/captured it
            # (find_conflicts groups case-insensitively, but the label
            # should show real casing, e.g. "W" not "w").
            display_binding = self._entry_by_id(ids[0]).get("binding", "")
            parts.append(f"{display_binding} → {', '.join(sorted(ids))}")
        self.conflict_var.set("Konflikte: " + " | ".join(parts))


def _flatten_conflict_ids(conflicts: dict[str, list[str]]) -> set[str]:
    result: set[str] = set()
    for ids in conflicts.values():
        result.update(ids)
    return result


def main() -> None:
    root = tk.Tk()
    InputBindingConfigApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
