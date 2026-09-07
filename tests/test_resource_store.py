"""ResourceStore (TraceStore): Ressourcen-Identität, Persistence, Bytes.

Gate 5 (Viewport Production). Headless (kein GL-Kontext nötig).
"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401

from viewport.benchmark import BenchmarkCounters
from viewport.resource_store import TraceStore


class TraceStoreTests(unittest.TestCase):
    def setUp(self):
        self.stats = BenchmarkCounters()
        self.store = TraceStore(self.stats)

    def test_allocate_creates_resource_with_stable_id(self):
        self.store.allocate("positions", 12)
        rid = self.store.resource("positions").resource_id
        self.assertIsNotNone(rid)
        self.assertTrue(self.store.has("positions"))

    def test_allocate_counts_gpu_resource_creation(self):
        self.store.allocate("positions", 12)
        self.assertEqual(self.stats.get("gpu_resource_creations"), 1)

    def test_update_does_not_change_resource_id(self):
        self.store.allocate("positions", 12)
        rid_before = self.store.resource("positions").resource_id
        self.store.update("positions", 0, [1.0, 2.0, 3.0], 12)
        rid_after = self.store.resource("positions").resource_id
        self.assertEqual(rid_before, rid_after)

    def test_update_does_not_count_as_creation(self):
        self.store.allocate("positions", 12)
        self.store.update("positions", 0, [1.0, 2.0, 3.0], 12)
        self.assertEqual(self.stats.get("gpu_resource_creations"), 1)

    def test_update_writes_data_at_offset(self):
        self.store.allocate("positions", 24)
        self.store.update("positions", 0, [1.0, 2.0, 3.0], 12)
        self.store.update("positions", 3, [9.0, 9.0, 9.0], 12)
        self.assertEqual(self.store.data("positions"), [1.0, 2.0, 3.0, 9.0, 9.0, 9.0])

    def test_update_tracks_uploaded_bytes(self):
        self.store.allocate("positions", 12)
        self.store.update("positions", 0, [1.0, 2.0, 3.0], 12)
        self.assertEqual(self.stats.uploaded_bytes, 12)

    def test_reallocate_existing_resource_is_recreation(self):
        self.store.allocate("positions", 12)
        rid_before = self.store.resource("positions").resource_id
        self.store.allocate("positions", 12)
        rid_after = self.store.resource("positions").resource_id
        self.assertNotEqual(rid_before, rid_after)
        self.assertEqual(self.stats.get("gpu_resource_creations"), 2)

    def test_destroy_removes_resource_and_counts(self):
        self.store.allocate("positions", 12)
        self.store.destroy("positions")
        self.assertFalse(self.store.has("positions"))
        self.assertEqual(self.stats.get("gpu_resource_destroys"), 1)

    def test_resource_ids_snapshot_multiple_resources(self):
        self.store.allocate("positions", 12)
        self.store.allocate("normals", 12)
        ids = self.store.resource_ids()
        self.assertEqual(set(ids.keys()), {"positions", "normals"})
        self.assertNotEqual(ids["positions"], ids["normals"])

    def test_resource_ids_stable_across_updates(self):
        self.store.allocate("positions", 12)
        self.store.allocate("normals", 12)
        before = self.store.resource_ids()
        for _ in range(50):
            self.store.update("positions", 0, [1.0, 2.0, 3.0], 12)
            self.store.update("normals", 0, [0.0, 1.0, 0.0], 12)
        after = self.store.resource_ids()
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
