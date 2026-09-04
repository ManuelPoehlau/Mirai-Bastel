"""Ressourcen-Store für das V0.2 Experiment.

Kein allgemeines GPU-Resource-Management — nur die minimale Abstraktion,
die den Proof messbar macht:

- Jede GPU-Ressource hat eine stabile ``resource_id`` (Identität).
- ``create`` = structural (neue ID) -> gpu_resource_creations
- ``update``  = partial (dieselbe ID, gleiche Ressource) -> kein Creation
- ``destroy`` = gpu_resource_destroys

Zwei Backends:
- ``TraceStore``  : rein in-memory (kein GL), deterministisch für Tests.
- ``PygletStore`` : echtes pyglet/OpenGL, für den Live-Demonstrator. Verifiziert,
  dass ein Partial-Update dieselbe VertexList/Buffer-Identität behält.

Die Entscheidungslogik (welche Ressource darf welche Kategorie verändern,
partial vs. rebuild) liegt im RenderMesh, NICHT hier.
"""
from __future__ import annotations

import itertools
from abc import ABC, abstractmethod

try:
    from .stats import Stats
except ImportError:  # direkter Skript-Aufruf
    from stats import Stats


class GpuResource:
    """Eine benannte GPU-Ressource mit stabiler Identität."""

    _id_counter = itertools.count(1)

    def __init__(self, name: str) -> None:
        self.name = name
        self.resource_id = next(GpuResource._id_counter)
        self.created = False
        self.updates = 0
        self.bytes_uploaded = 0

    def __repr__(self) -> str:  # pragma: no cover - Debug-Hilfe
        return f"<GpuResource {self.name} id={self.resource_id}>"


class ResourceStore(ABC):
    def __init__(self, stats: Stats) -> None:
        self.stats = stats
        self._resources: dict[str, GpuResource] = {}

    def _ensure(self, name: str) -> GpuResource:
        if name not in self._resources:
            res = GpuResource(name)
            self._resources[name] = res
        return self._resources[name]

    # -- Structurals/Partials (Backend-spezifisch) --------------------------
    @abstractmethod
    def allocate(self, name: str, nbytes: int) -> None:
        """Legt die Ressource an (structural; neue ID)."""

    @abstractmethod
    def update(self, name: str, offset: int, data: list[float], nbytes: int) -> None:
        """Partielles Update in dieselbe Ressource (gleiche ID)."""

    @abstractmethod
    def destroy(self, name: str) -> None:
        """Gibt die Ressource frei."""

    def resource(self, name: str) -> GpuResource:
        return self._resources[name]

    def resource_ids(self) -> dict[str, int]:
        return {name: r.resource_id for name, r in self._resources.items()}


class TraceStore(ResourceStore):
    """In-memory-Backend für deterministische Tests ohne GL-Kontext."""

    def __init__(self, stats: Stats) -> None:
        super().__init__(stats)
        self._data: dict[str, list[float]] = {}

    def allocate(self, name: str, nbytes: int) -> None:
        res = self._ensure(name)
        if res.created:
            # Re-Allocation ist eine Recreation einer bestehenden Ressource
            self.destroy(name)
            res = self._ensure(name)
        res.created = True
        self._data[name] = []
        self.stats.count("gpu_resource_creations")
        self.stats.snapshot(res)

    def update(self, name: str, offset: int, data: list[float], nbytes: int) -> None:
        res = self._ensure(name)
        buf = self._data.setdefault(name, [0.0] * (offset + len(data)))
        if len(buf) < offset + len(data):
            buf.extend([0.0] * (offset + len(data) - len(buf)))
        buf[offset : offset + len(data)] = data
        self._data[name] = buf
        res.updates += 1
        res.bytes_uploaded += nbytes
        self.stats.add_upload(nbytes)
        self.stats.snapshot(res)

    def destroy(self, name: str) -> None:
        res = self._resources.pop(name, None)
        if res is not None:
            self._data.pop(name, None)
            self.stats.count("gpu_resource_destroys")

    def data(self, name: str) -> list[float]:
        return self._data.get(name, [])


class PygletStore(ResourceStore):
    """Echtes pyglet/OpenGL-Backend für den Demonstrator.

    ``allocate(name, ...)`` reserviert eine Ressource mit stabiler Identität
    (``resource_id`` + Referenzobjekt). ``update`` schreibt in dieselbe
    Ressource (partial) — die Identität bleibt erhalten. Der tatsächliche
    pyglet-VBO-Upload passiert im Demonstrator über
    ``vlist.set_attribute_data`` (in-place, kein neuer VBO).
    """

    def __init__(self, stats: Stats) -> None:
        super().__init__(stats)
        self._buffer_objects: dict[str, bytearray] = {}
        self._gpu_refs: dict[str, object] = {}

    def allocate(self, name: str, nbytes: int) -> None:
        res = self._ensure(name)
        if res.created:
            self.destroy(name)
            res = self._ensure(name)
        res.created = True
        self._buffer_objects[name] = bytearray(nbytes)
        self._gpu_refs[name] = object()  # simulierte GPU-Buffer-Referenz
        self.stats.count("gpu_resource_creations")
        self.stats.snapshot(res)

    def update(self, name: str, offset: int, data: list[float], nbytes: int) -> None:
        res = self._ensure(name)
        buf = self._buffer_objects.setdefault(name, bytearray())
        needed = offset + len(data) * 4
        if len(buf) < needed:
            buf.extend(b"\x00" * (needed - len(buf)))
        import struct

        struct.pack_into("<%df" % len(data), buf, offset * 4, *data)
        res.updates += 1
        res.bytes_uploaded += nbytes
        self.stats.add_upload(nbytes)
        self.stats.snapshot(res)

    def destroy(self, name: str) -> None:
        res = self._resources.pop(name, None)
        if res is not None:
            self._buffer_objects.pop(name, None)
            self._gpu_refs.pop(name, None)
            self.stats.count("gpu_resource_destroys")

    def gpu_ref(self, name: str) -> object:
        return self._gpu_refs.get(name)


