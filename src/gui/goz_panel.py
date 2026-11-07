"""Das GoZ-Panel (AD-030 §12, Manu 2026-11-07): ZBrush-Brücke als eigenes Panel statt Zeilen im SPACE-Menü.

Die Logik bleibt in `src/zbrush_bridge.py`; das Panel zeigt dieselben Zeilen (`ZBrushBridge.entries`, höchstens
vier Mal pro Sekunde neu gelesen, weil es den Ordner prüft) und führt sie über `activate` aus. Die Sende-Optionen
(was alles zu ZBrush geht: nur Mesh, auch Morphs, ...) kommen später hierher; heute gibt es nur „Senden“.
"""

from __future__ import annotations

import time

from zbrush_bridge import APPLY_PREFIX, DROP_PREFIX, INSTALL_LABEL, NEW_OBJECT_PREFIX, RESET_NAMES_LABEL, SEND_LABEL

_REFRESH_SECONDS = 0.25


class GozPanel:
    def __init__(self, imgui, bridge) -> None:
        self.imgui, self.bridge = imgui, bridge
        self._rows: tuple[str, ...] = ()
        self._read_at = float("-inf")

    def rows(self) -> tuple[str, ...]:
        now = time.monotonic()
        if now - self._read_at >= _REFRESH_SECONDS:
            self._rows, self._read_at = self.bridge.entries(), now
        return self._rows

    def draw(self) -> None:
        imgui, bridge = self.imgui, self.bridge
        rows = self.rows()
        if imgui.button("An ZBrush senden"):
            bridge.activate(SEND_LABEL)
        waiting = [r for r in rows if r.startswith((APPLY_PREFIX, NEW_OBJECT_PREFIX, DROP_PREFIX))]
        imgui.separator()
        if waiting:
            imgui.text_disabled("Rückgaben aus ZBrush")
            for label in waiting:
                if imgui.small_button(label):
                    bridge.activate(label)
                    self._read_at = float("-inf")
        else:
            imgui.text_disabled("Keine Rückgabe offen")
        if INSTALL_LABEL in rows:
            imgui.separator()
            if imgui.button("Mirai bei GoZ eintragen"):
                bridge.activate(INSTALL_LABEL)
                self._read_at = float("-inf")
        imgui.separator()
        if RESET_NAMES_LABEL in rows:
            if imgui.small_button("GoZ-Namen zurücksetzen"):
                bridge.activate(RESET_NAMES_LABEL)
                self._read_at = float("-inf")
        imgui.text_disabled("Sende-Optionen folgen")
