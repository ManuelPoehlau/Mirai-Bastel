"""Ressourcen-Store: minimale GPU-Ressourcen-Abstraktion für den Viewport v0.2.

Portiert und für Produktion gehärtet aus dem verifizierten Proof-of-
Architecture-Experiment (`experiments/mirai_bastel_viewport_V02/renderer.py`).

Kein allgemeines GPU-Resource-Management (das ist explizit ein Non-Goal,
siehe VIEWPORT_V02_ARCHITECTURE.md §1) — nur die minimale Abstraktion, die
GPU Resource Persistence (§7) messbar und testbar macht:

- Jede benannte Ressource hat eine stabile `resource_id` (Identität).
- `allocate()`  = structural (neue ID, sofern die Ressource neu ist oder
  explizit neu angelegt wird) -> zählt `gpu_resource_creations`.
- `update()`    = partial (dieselbe Ressource, dieselbe ID) -> kein Creation.
- `destroy()`   = zählt `gpu_resource_destroys`.

Zwei Backends:

- `TraceStore`  — rein in-memory (kein GL-Kontext nötig), deterministisch,
  Basis für die komplette Test-Suite (headless, CI-tauglich).
- `PygletStore` — echtes pyglet/OpenGL-Backend über
  `pyglet.graphics.get_default_shader().vertex_list()` (pyglet >= 2.0 API;
  in pyglet 1.x lag diese Funktion noch direkt auf `pyglet.graphics`).
  Ein `update()` patcht die bestehende `VertexList` in-place
  (`vlist.<attribut>[offset:...] = data`) statt eine neue anzulegen — das
  ist der eigentliche Nachweis von GPU Resource Persistence mit echtem
  GL-Backend. Benötigt einen aktiven GL-Kontext (Fenster) und wird deshalb
  nicht in der headless-Testsuite ausgeführt, sondern per Xvfb-Live-Check
  verifiziert (siehe Gate 5 Completion Report, Abschnitt
  "GL-Live-Verifikation": Objektidentität + `resource_id` bleiben über
  mehrere `update()`-Aufrufe hinweg stabil, `gpu_resource_creations` bleibt
  konstant).

Die Entscheidungslogik (welche Update-Kategorie welche Ressource verändern
darf, partial vs. rebuild) liegt in `RenderMesh`, NICHT hier.
"""

from __future__ import annotations

import itertools
from abc import ABC, abstractmethod

from .benchmark import BenchmarkCounters


class GpuResource:
    """Eine benannte GPU-Ressource mit stabiler Identität (`resource_id`)."""

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
    """Backend-unabhängiges Interface für benannte GPU-Ressourcen."""

    def __init__(self, stats: BenchmarkCounters) -> None:
        self.stats = stats
        self._resources: dict[str, GpuResource] = {}

    def _ensure(self, name: str) -> GpuResource:
        if name not in self._resources:
            self._resources[name] = GpuResource(name)
        return self._resources[name]

    @abstractmethod
    def allocate(self, name: str, nbytes: int) -> None:
        """Legt die Ressource an (structural; ggf. neue Identität)."""

    @abstractmethod
    def update(self, name: str, offset: int, data: list[float], nbytes: int) -> None:
        """Partielles Update in dieselbe Ressource (gleiche Identität)."""

    @abstractmethod
    def destroy(self, name: str) -> None:
        """Gibt die Ressource frei."""

    def has(self, name: str) -> bool:
        return name in self._resources

    def resource(self, name: str) -> GpuResource:
        return self._resources[name]

    def resource_ids(self) -> dict[str, int]:
        """Snapshot aller aktuell aktiven Ressourcen-IDs (für Persistence-Checks)."""
        return {name: r.resource_id for name, r in self._resources.items()}


class TraceStore(ResourceStore):
    """In-memory-Backend für deterministische, headless-taugliche Tests."""

    def __init__(self, stats: BenchmarkCounters) -> None:
        super().__init__(stats)
        self._data: dict[str, list[float]] = {}

    def allocate(self, name: str, nbytes: int) -> None:
        res = self._ensure(name)
        if res.created:
            # Re-Allocation einer bestehenden Ressource ist eine Recreation.
            self.destroy(name)
            res = self._ensure(name)
        res.created = True
        self._data[name] = []
        self.stats.count("gpu_resource_creations")
        self.stats.snapshot_resource(res)

    def update(self, name: str, offset: int, data: list[float], nbytes: int) -> None:
        res = self._ensure(name)
        buf = self._data.setdefault(name, [])
        needed = offset + len(data)
        if len(buf) < needed:
            buf.extend([0.0] * (needed - len(buf)))
        buf[offset:offset + len(data)] = data
        res.updates += 1
        res.bytes_uploaded += nbytes
        self.stats.add_upload(nbytes)
        self.stats.snapshot_resource(res)

    def destroy(self, name: str) -> None:
        res = self._resources.pop(name, None)
        if res is not None:
            self._data.pop(name, None)
            self.stats.count("gpu_resource_destroys")

    def data(self, name: str) -> list[float]:
        return self._data.get(name, [])


class PygletStore(ResourceStore):
    """Echtes pyglet/OpenGL-Backend (benötigt aktiven GL-Kontext).

    `allocate()` legt eine `VertexList` über
    `pyglet.graphics.get_default_shader().vertex_list()` an (pyglet >= 2.0
    API - siehe Modul-Docstring) mit stabiler Python-Objektidentität.
    `update()` schreibt per Slice-Assignment in dieselbe VertexList
    (`vlist.<attr>[offset:offset+n] = data`) — pyglet patcht dabei intern
    denselben zugrunde liegenden Vertex-Buffer, es wird KEIN neuer Buffer
    angelegt. Das ist der GL-seitige Nachweis von GPU Resource Persistence
    (VIEWPORT_V02_ARCHITECTURE.md §7), live verifiziert unter Xvfb (siehe
    Gate 5 Completion Report).

    `attribute_name` (z. B. `"position"`) legt fest, unter welchem
    VertexList-Attribut die Daten liegen. Format-Strings für pyglet >= 2.0
    sind reine GL-Typ-Buchstaben (`"f"` = float) - die Komponentenzahl pro
    Vertex (z. B. 3 für vec3) wird separat über `components` verwaltet.

    Scope-Grenze (bewusst, siehe VIEWPORT_V02_ARCHITECTURE.md §1 Non-Goals
    "kein eigener GPU Resource Manager"): `pyglet.graphics.get_default_shader()`
    kennt nur drei fest verdrahtete Attribute (`position` vec3, `colors`
    vec4, `tex_coords` vec3). Um alle vier RenderMesh-Ressourcen
    (`positions`/`normals`/`indices`/`highlight_flags`) GLEICHZEITIG über
    echtes GL darzustellen, wäre ein eigenes Shader-Programm mit passenden
    Attribut-Deklarationen nötig - das ist expliziter Non-Goal-Scope für
    Gate 5 (kein Shader-/Renderpipeline-System). Der Live-Beweis für GPU
    Resource Persistence (Gate 5 Completion Report, "GL-Live-Verifikation")
    beschränkt sich deshalb bewusst auf EINE Ressource über das `position`-
    Attribut - das genügt, um die Kern-Invariante (VertexList-Objektidentität
    + `resource_id` bleiben über `update()` hinweg stabil) mit echtem
    GL-Backend nachzuweisen. Ein vollständiger Multi-Attribut-Renderer ist
    Aufgabe eines künftigen Entry-Point-/Renderer-Gates, nicht dieses Stores.
    """

    def __init__(self, stats: BenchmarkCounters) -> None:
        super().__init__(stats)
        self._vertex_lists: dict[str, object] = {}
        self._attribute_specs: dict[str, tuple[str, int]] = {}

    def register_attribute_spec(
        self, name: str, attribute_name: str, components: int
    ) -> None:
        """Legt fest, welches VertexList-Attribut/welche Komponentenzahl
        (z. B. 3 für vec3) eine logische Ressource beim nächsten `allocate()`
        verwendet."""
        self._attribute_specs[name] = (attribute_name, components)

    def allocate(self, name: str, nbytes: int) -> None:
        import pyglet  # lokal importiert: GL-Backend ist optional

        attribute_name, components = self._attribute_specs.get(
            name, ("position", 3)
        )
        count = max(1, nbytes // (4 * components))

        res = self._ensure(name)
        if res.created:
            self.destroy(name)
            res = self._ensure(name)
        res.created = True

        # pyglet >= 2.0: vertex_list() lebt auf dem (Default-)ShaderProgram,
        # nicht mehr als freie Funktion in `pyglet.graphics` (API-Bruch ggü.
        # pyglet 1.x, siehe Gate 5 Completion Report). Format-String ist nur
        # der GL-Typ-Buchstabe ("f" = float) - die Komponentenzahl (z. B. 3
        # für vec3) ist durch das Attribut selbst festgelegt, kein "3f".
        shader = pyglet.graphics.get_default_shader()
        vlist = shader.vertex_list(
            count, pyglet.gl.GL_POINTS,
            **{attribute_name: ("f", (0.0,) * (count * components))},
        )
        self._vertex_lists[name] = vlist
        self.stats.count("gpu_resource_creations")
        self.stats.snapshot_resource(res)

    def update(self, name: str, offset: int, data: list[float], nbytes: int) -> None:
        res = self._ensure(name)
        vlist = self._vertex_lists[name]
        attribute_name, _components = self._attribute_specs.get(
            name, ("position", 3)
        )
        attr_array = getattr(vlist, attribute_name)
        attr_array[offset:offset + len(data)] = data
        res.updates += 1
        res.bytes_uploaded += nbytes
        self.stats.add_upload(nbytes)
        self.stats.snapshot_resource(res)

    def destroy(self, name: str) -> None:
        res = self._resources.pop(name, None)
        if res is not None:
            vlist = self._vertex_lists.pop(name, None)
            if vlist is not None:
                vlist.delete()
            self.stats.count("gpu_resource_destroys")

    def vertex_list(self, name: str):
        """Zugriff auf die zugrunde liegende pyglet-VertexList (für Draw-Calls)."""
        return self._vertex_lists.get(name)
