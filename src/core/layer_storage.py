"""Packed storage of point-layer values (AD-025 §4.2, Phase 4; CORE_V1_FREEZE §7.1 2026-10-27).

Core-internal, behind the unchanged `Mesh` point-layer API. A layer's values were one `dict[VertexId,
tuple]` (≈ 190 bytes per stored value: a hash entry, a tuple and three float objects); 50 dense targets at
20k points took ≈ 204 MiB against the 50 MB budget of audit §G. Now each layer is a `PackedValues`: three
float64 per slot in one `array('d')` plus one presence byte (25 bytes per slot), and every layer of a mesh
shares one `LayerSlots` map from `VertexId` to slot.

- **Slots, not IDs as indices** (AD-001: an ID is never an array index): `LayerSlots` hands out a slot the
  first time a vertex gets a value in any layer. It is **append-only** — a slot is never freed or reused, so
  a value array kept in a journal record or a history delta keeps meaning the same vertices for good, and
  the map needs no journal of its own (it changes no observable state). A mesh that grows by editing grows
  the map; `Mesh.from_state` starts a fresh one.
- **Mapping semantics:** `PackedValues` is a `MutableMapping[VertexId, tuple[float, float, float]]` with the
  operations the Core used on the dicts (`get`, item access, `in`, `pop`, `len`, iteration, `items`,
  `copy`, `==` — also against a plain dict). Values come back as new tuples of the stored floats (float64:
  bit-exact). Iteration is in slot order, which is not semantic (AD-025 §4.2 exactness point 4: every
  reader is order-free or sorts).
- **Copy-on-write** stays the Mesh's rule (`_layer_shared`); `copy()` is two buffer copies.

`PackedWeights` (AD-028 §3.6, CORE_V1_FREEZE §7.1 2026-11-02) is the same mapping for the WEIGHTS kind
over the same `LayerSlots`: per slot four keys (`array('i')`, 32-bit), four float64 weights and a count
byte (0 = absent) - 49 bytes per slot. Values are the canonical tuples `((key, w), ...)` the Mesh
validated (W1-W4, `core.mesh`); this class stores and returns them bit-exactly and checks nothing.
"""

from __future__ import annotations

import math
from array import array
from collections.abc import Iterator, Mapping, MutableMapping
from itertools import compress

from .ids import VertexId

_ZEROS = (0.0, 0.0, 0.0)


class LayerSlots:
    """VertexId -> slot of one mesh's packed layer arrays; append-only (module docstring)."""

    __slots__ = ("index", "vertices")

    def __init__(self) -> None:
        self.index: dict[VertexId, int] = {}
        self.vertices: list[VertexId] = []

    def slot(self, vid: VertexId) -> int:
        s = self.index.get(vid)
        if s is None:
            s = self.index[vid] = len(self.vertices)
            self.vertices.append(vid)
        return s

    def __len__(self) -> int:
        return len(self.vertices)


class PackedValues(MutableMapping):
    """One vector layer's stored values over a shared `LayerSlots` (module docstring)."""

    __slots__ = ("slots", "_index", "_data", "_present", "_count")
    #: the kind's default value (never stored, L2)
    default = _ZEROS

    def __init__(self, slots: LayerSlots, values: Mapping | None = None) -> None:
        self.slots = slots
        self._index = slots.index
        self._data = array("d")
        self._present = bytearray()
        self._count = 0
        if values:
            self._fill(values.items())

    def _fill(self, items) -> None:
        """Bulk insert into an empty layer (load, packing a dict): slots first, then one pass."""
        items = list(items)
        slot = self.slots.slot
        where = [slot(vid) for vid, _ in items]
        self._grow(max(where, default=-1))
        d, present = self._data, self._present
        for s, (x, y, z) in zip(where, (value for _, value in items)):
            i = 3 * s
            d[i] = x
            d[i + 1] = y
            d[i + 2] = z
            present[s] = 1
        self._count = present.count(1)

    # -- reading ------------------------------------------------------------------------------------

    def _slot_of(self, vid) -> int | None:
        s = self._index.get(vid)
        if s is None or s >= len(self._present) or not self._present[s]:
            return None
        return s

    def get(self, vid, default=None):
        s = self._index.get(vid)
        if s is None:
            return default
        try:
            if not self._present[s]:
                return default
        except IndexError:
            return default
        d = self._data
        i = 3 * s
        return (d[i], d[i + 1], d[i + 2])

    def __getitem__(self, vid):
        s = self._slot_of(vid)
        if s is None:
            raise KeyError(vid)
        i = 3 * s
        d = self._data
        return (d[i], d[i + 1], d[i + 2])

    def __contains__(self, vid) -> bool:
        return self._slot_of(vid) is not None

    def __len__(self) -> int:
        return self._count

    def __bool__(self) -> bool:
        return self._count > 0

    def _live_slots(self):
        return compress(range(len(self._present)), self._present)

    def __iter__(self) -> Iterator[VertexId]:
        return iter(self.keys())

    def keys(self):
        return list(compress(self.slots.vertices, self._present))

    def _triples(self):
        d = self._data
        return zip(d[0::3], d[1::3], d[2::3])

    def items(self):
        # C-level iterators throughout: no Python loop per stored value
        return list(compress(zip(self.slots.vertices, self._triples()), self._present))

    def values(self):
        return list(compress(self._triples(), self._present))

    # -- writing ------------------------------------------------------------------------------------

    def _grow(self, s: int) -> None:
        n = max(s + 1, len(self.slots))
        extra = n - len(self._present)
        if extra > 0:
            self._present.extend(bytes(extra))
            self._data.frombytes(bytes(24 * extra))

    def __setitem__(self, vid, value) -> None:
        s = self._index.get(vid)
        if s is None:
            s = self.slots.slot(vid)
        present = self._present
        if s >= len(present):
            self._grow(s)
        d = self._data
        i = 3 * s
        d[i] = value[0]
        d[i + 1] = value[1]
        d[i + 2] = value[2]
        if not present[s]:
            present[s] = 1
            self._count += 1

    def __delitem__(self, vid) -> None:
        s = self._slot_of(vid)
        if s is None:
            raise KeyError(vid)
        i = 3 * s
        d = self._data
        d[i] = d[i + 1] = d[i + 2] = 0.0  # absent slots hold +0.0 (equality below relies on it)
        self._present[s] = 0
        self._count -= 1

    def copy(self) -> "PackedValues":
        out = PackedValues.__new__(PackedValues)
        out.slots = self.slots
        out._index = self._index
        out._data = array("d", self._data)
        out._present = bytearray(self._present)
        out._count = self._count
        return out

    def mapped(self, m) -> "PackedValues":
        """A new layer with every value v -> M·v (AD-025 §4.3, `Mesh.map_vector_layers`), the same
        arithmetic per component as before (`a·x + b·y + c·z`); a value mapped to (0, 0, 0) is dropped
        (L2). Raises ValueError when a result is not finite."""
        (a, b, c), (e, f, g), (h, k, l) = m
        d = self._data
        xs, ys, zs = d[0::3], d[1::3], d[2::3]
        nx = array("d", [a * x + b * y + c * z for x, y, z in zip(xs, ys, zs)])
        ny = array("d", [e * x + f * y + g * z for x, y, z in zip(xs, ys, zs)])
        nz = array("d", [h * x + k * y + l * z for x, y, z in zip(xs, ys, zs)])
        out = PackedValues.__new__(PackedValues)
        out.slots = self.slots
        out._index = self._index
        data = array("d", bytes(len(d) * 8))
        data[0::3], data[1::3], data[2::3] = nx, ny, nz
        if not all(map(math.isfinite, data)):
            raise ValueError("mapped value not finite")
        present = bytearray(self._present)
        for s in compress(range(len(present)), present):
            if nx[s] == 0.0 and ny[s] == 0.0 and nz[s] == 0.0:
                present[s] = 0
                data[3 * s] = data[3 * s + 1] = data[3 * s + 2] = 0.0
        out._data = data
        out._present = present
        out._count = present.count(1)
        return out

    # -- comparison ---------------------------------------------------------------------------------

    def __eq__(self, other) -> bool:
        if isinstance(other, PackedValues) and other.slots is self.slots:
            if self._count != other._count:
                return False
            a, b = (self, other) if len(self._present) <= len(other._present) else (other, self)
            n = len(a._present)
            if a._present != b._present[:n] or any(b._present[n:]):
                return False
            if a._data.tobytes() == b._data[: 3 * n].tobytes():
                return True
            return a._data == b._data[: 3 * n]  # -0.0 == 0.0, as the dicts compared
        if isinstance(other, Mapping):
            return len(other) == self._count and dict(self.items()) == dict(other.items())
        return NotImplemented

    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        return f"PackedValues({dict(sorted(self.items()))!r})"

    # -- measurement --------------------------------------------------------------------------------

    def nbytes(self) -> int:
        """Bytes of the value buffers (without the shared slot map)."""
        return self._data.buffer_info()[1] * self._data.itemsize + len(self._present)


#: Influences per point of a weights layer (AD-028 §3.3 W1).
WEIGHTS_WIDTH = 4
#: Keys are stored as 32-bit signed ints (`array('i')`); the Mesh refuses larger ones.
WEIGHTS_KEY_LIMIT = 2**31


class PackedWeights(MutableMapping):
    """One weights layer's stored values over a shared `LayerSlots` (module docstring): a
    `MutableMapping[VertexId, tuple[tuple[int, float], ...]]` with the semantics of `PackedValues`.
    Unused entries of a slot (beyond its count, or an absent slot) hold key 0 and weight +0.0, so
    two layers compare by their buffers (stored weights are > 0: no -0.0)."""

    __slots__ = ("slots", "_index", "_keys", "_weights", "_n", "_count")
    default = ()

    def __init__(self, slots: LayerSlots, values: Mapping | None = None) -> None:
        if array("i").itemsize != 4:  # pragma: no cover - every supported platform has a 32-bit int
            raise RuntimeError("PackedWeights needs a 32-bit array('i')")
        self.slots = slots
        self._index = slots.index
        self._keys = array("i")
        self._weights = array("d")
        self._n = bytearray()
        self._count = 0
        if values:
            for vid, value in values.items():
                self[vid] = value

    # -- reading ------------------------------------------------------------------------------------

    def get(self, vid, default=None):
        s = self._index.get(vid)
        if s is None:
            return default
        try:
            n = self._n[s]
        except IndexError:
            return default
        if not n:
            return default
        i = WEIGHTS_WIDTH * s
        k, w = self._keys, self._weights
        if n == 1:
            return ((k[i], w[i]),)
        return tuple(zip(k[i:i + n], w[i:i + n]))

    def __getitem__(self, vid):
        value = self.get(vid)
        if value is None:
            raise KeyError(vid)
        return value

    def __contains__(self, vid) -> bool:
        s = self._index.get(vid)
        return s is not None and s < len(self._n) and self._n[s] != 0

    def __len__(self) -> int:
        return self._count

    def __bool__(self) -> bool:
        return self._count > 0

    def __iter__(self) -> Iterator[VertexId]:
        return iter(self.keys())

    def keys(self):
        return list(compress(self.slots.vertices, self._n))

    def items(self):
        get = self.get
        return [(vid, get(vid)) for vid in compress(self.slots.vertices, self._n)]

    def values(self):
        return [value for _, value in self.items()]

    # -- writing ------------------------------------------------------------------------------------

    def _grow(self, s: int) -> None:
        n = max(s + 1, len(self.slots))
        extra = n - len(self._n)
        if extra > 0:
            self._n.extend(bytes(extra))
            self._keys.frombytes(bytes(4 * WEIGHTS_WIDTH * extra))
            self._weights.frombytes(bytes(8 * WEIGHTS_WIDTH * extra))

    def __setitem__(self, vid, value) -> None:
        n = len(value)
        if not 0 < n <= WEIGHTS_WIDTH:
            raise ValueError(f"a weights value holds 1-{WEIGHTS_WIDTH} pairs: {value!r}")
        s = self._index.get(vid)
        if s is None:
            s = self.slots.slot(vid)
        if s >= len(self._n):
            self._grow(s)
        i = WEIGHTS_WIDTH * s
        k, w = self._keys, self._weights
        for j in range(WEIGHTS_WIDTH):
            if j < n:
                k[i + j], w[i + j] = value[j]
            else:
                k[i + j] = 0
                w[i + j] = 0.0
        if not self._n[s]:
            self._count += 1
        self._n[s] = n

    def __delitem__(self, vid) -> None:
        s = self._index.get(vid)
        if s is None or s >= len(self._n) or not self._n[s]:
            raise KeyError(vid)
        i = WEIGHTS_WIDTH * s
        for j in range(WEIGHTS_WIDTH):
            self._keys[i + j] = 0
            self._weights[i + j] = 0.0
        self._n[s] = 0
        self._count -= 1

    def copy(self) -> "PackedWeights":
        out = PackedWeights.__new__(PackedWeights)
        out.slots = self.slots
        out._index = self._index
        out._keys = array("i", self._keys)
        out._weights = array("d", self._weights)
        out._n = bytearray(self._n)
        out._count = self._count
        return out

    # -- comparison ---------------------------------------------------------------------------------

    def __eq__(self, other) -> bool:
        if isinstance(other, PackedWeights) and other.slots is self.slots:
            if self._count != other._count:
                return False
            a, b = (self, other) if len(self._n) <= len(other._n) else (other, self)
            n = len(a._n)
            if a._n != b._n[:n] or any(b._n[n:]):
                return False
            m = WEIGHTS_WIDTH * n
            return a._keys == b._keys[:m] and a._weights.tobytes() == b._weights[:m].tobytes()
        if isinstance(other, Mapping):
            return len(other) == self._count and dict(self.items()) == dict(other.items())
        return NotImplemented

    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        return f"PackedWeights({dict(sorted(self.items()))!r})"

    # -- measurement --------------------------------------------------------------------------------

    def nbytes(self) -> int:
        """Bytes of the value buffers (without the shared slot map): 49 per slot."""
        return (
            self._keys.buffer_info()[1] * self._keys.itemsize
            + self._weights.buffer_info()[1] * self._weights.itemsize
            + len(self._n)
        )
