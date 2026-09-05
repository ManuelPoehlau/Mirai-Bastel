"""Mirai-Bastel — Produktions-Application-Layer (Gate 3).

Enthält die Application-Orchestrierung (`mirai.application.Application`)
sowie die Interaktions- (Tools, ToolManager, Input/Bindings) und
Viewport-State-Komponenten (Camera/Picking/Display, window-frei).

Der Core bleibt ein eigenständiges, eingefrorenes top-level Paket
(`src/core/`, Import als `core`) — siehe CORE_V1_FREEZE.md und ADR-001.
Der v0.2-Viewport mit Rendering liegt in Gate 5 (`src/viewport`).
"""

from .application import Application

__all__ = ["Application"]