"""AD-021 M0: Scene-Objekte, ObjectId, Edit-Objekt, Selection.objects, Format v2.

Abnahme laut AD-021 §6 Zeile M0: ObjectId nie wiederverwendet, add/remove/
re-add behält die Instanz, ein Mesh-Tausch behält State und Transform,
`clear()`/`is_empty()` unverändert, P-1 als Core-Test (zwei Objekte, ein
Stack), ein v1-Dict lädt.
"""

from __future__ import annotations

import math
import unittest

import tests._bootstrap  # noqa: F401

from core.ids import ObjectId, VertexId
from core.mesh import Mesh, SymmetryDefinition
from core.operation import OperationContext
from core.operations.move import MoveOperation
from core.operations.topology import MeshStateCommand
from core.scene import IDENTITY_TRANSFORM, ObjectState, ObjectTransform, Scene, SceneObject
from core.selection import Selection, SelectionMode
from core.serialization import FORMAT_VERSION, scene_from_dict, scene_from_json, scene_to_dict, scene_to_json
from tests.test_topology_history import full_topology_snapshot


def _quad_mesh(offset: float = 0.0) -> Mesh:
    mesh = Mesh()
    vids = [
        mesh.add_vertex((offset + x, y, 0.0))
        for x, y in ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))
    ]
    mesh.add_face(vids)
    return mesh


def _without_counters(state: dict) -> dict:
    # Die Allocator-Zähler bleiben nach Undo vorwärts (AD-001) - gewollt.
    return {k: v for k, v in state.items() if not k.endswith("_id_counter")}


_ROT_90_Y = ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0), (-1.0, 0.0, 0.0))


class TestDefaultScene(unittest.TestCase):
    def test_new_scene_has_one_empty_normal_edit_object(self) -> None:
        scene = Scene()
        self.assertEqual(len(scene.objects), 1)
        (obj,) = scene.objects.values()
        self.assertEqual(obj.id, scene.edit_object_id)
        self.assertIsInstance(obj.id, ObjectId)
        self.assertIs(scene.edit_object, obj)
        self.assertIs(scene.mesh, obj.mesh)
        self.assertEqual(len(obj.mesh.all_vertex_ids()), 0)
        self.assertIs(obj.state, ObjectState.NORMAL)
        self.assertEqual(obj.transform, IDENTITY_TRANSFORM)
        self.assertEqual(obj.pivot, (0.0, 0.0, 0.0))

    def test_objects_view_is_read_only(self) -> None:
        scene = Scene()
        with self.assertRaises(TypeError):
            scene.objects[ObjectId(5)] = SceneObject(ObjectId(5), Mesh())  # type: ignore[index]

    def test_mesh_getter_fails_loudly_without_edit_object(self) -> None:
        scene = Scene()
        scene._objects.clear()  # nur über Interna erreichbar - der Vertrag sagt "laut"
        with self.assertRaises(LookupError):
            _ = scene.mesh


class TestObjectIds(unittest.TestCase):
    def test_object_id_never_reused_after_remove(self) -> None:
        scene = Scene()
        a = scene.add_object(Mesh())
        b = scene.add_object(Mesh())
        scene.remove_object(b.id)
        c = scene.add_object(Mesh())
        self.assertNotIn(c.id, {scene.edit_object_id, a.id, b.id})
        self.assertGreater(int(c.id), int(b.id))

    def test_object_id_is_its_own_type(self) -> None:
        scene = Scene()
        with self.assertRaises(TypeError):
            scene.edit_object_id = VertexId(int(scene.edit_object_id))  # type: ignore[assignment]
        with self.assertRaises(TypeError):
            SceneObject(VertexId(0), Mesh())  # type: ignore[arg-type]

    def test_add_remove_restore_keeps_instance_id_and_order(self) -> None:
        scene = Scene()
        a = scene.add_object(Mesh(), name="a")
        b = scene.add_object(Mesh(), name="b", state=ObjectState.REFERENCE)
        order = list(scene.objects)

        removed = scene.remove_object(a.id)
        self.assertIs(removed, a)
        self.assertNotIn(a.id, scene.objects)

        scene.restore_object(removed)
        self.assertIs(scene.objects[a.id], a)
        self.assertEqual(list(scene.objects), order)
        self.assertIs(scene.objects[b.id].state, ObjectState.REFERENCE)

    def test_restore_refuses_present_or_never_allocated_id(self) -> None:
        scene = Scene()
        a = scene.add_object(Mesh())
        with self.assertRaises(ValueError):
            scene.restore_object(a)
        with self.assertRaises(ValueError):
            scene.restore_object(SceneObject(ObjectId(scene.object_id_counter), Mesh()))

    def test_edit_object_cannot_be_removed(self) -> None:
        scene = Scene()
        with self.assertRaises(ValueError):
            scene.remove_object(scene.edit_object_id)
        self.assertIn(scene.edit_object_id, scene.objects)


class TestEditObject(unittest.TestCase):
    def test_mesh_accessor_follows_edit_object(self) -> None:
        scene = Scene()
        first = scene.edit_object
        other = scene.add_object(_quad_mesh())
        self.assertIs(scene.mesh, first.mesh)

        scene.edit_object_id = other.id
        self.assertIs(scene.mesh, other.mesh)
        self.assertIs(scene.edit_object, other)

    def test_unknown_edit_object_refused(self) -> None:
        scene = Scene()
        before = scene.edit_object_id
        with self.assertRaises(KeyError):
            scene.edit_object_id = ObjectId(99)
        self.assertEqual(scene.edit_object_id, before)

    def test_mesh_swap_keeps_object_identity_state_and_placement(self) -> None:
        scene = Scene()
        obj = scene.edit_object
        transform = ObjectTransform(translation=(1.0, 2.0, 3.0), rotation=_ROT_90_Y, scale=2.0)
        obj.name = "head"
        obj.transform = transform
        obj.pivot = (0.5, 0.0, 0.0)
        obj.state = ObjectState.REFERENCE
        old_mesh = scene.mesh
        old_mesh.symmetry_definition = SymmetryDefinition(
            plane_point=(0.0, 0.0, 0.0), plane_normal=(1.0, 0.0, 0.0), seam_edges=frozenset()
        )

        new_mesh = _quad_mesh()
        scene.mesh = new_mesh

        self.assertIs(scene.edit_object, obj)
        self.assertIs(obj.mesh, new_mesh)
        self.assertEqual(obj.name, "head")
        self.assertEqual(obj.transform, transform)
        self.assertEqual(obj.pivot, (0.5, 0.0, 0.0))
        self.assertIs(obj.state, ObjectState.REFERENCE)
        self.assertEqual(len(scene.objects), 1)
        # AD-SYM-01: die Definition stirbt mit dem alten Mesh.
        self.assertIsNone(scene.mesh.symmetry_definition)

    def test_mesh_swap_touches_only_the_edit_object(self) -> None:
        scene = Scene()
        other = scene.add_object(_quad_mesh())
        other_mesh = other.mesh
        scene.mesh = Mesh()
        self.assertIs(other.mesh, other_mesh)


class TestObjectTransform(unittest.TestCase):
    def test_default_is_identity(self) -> None:
        t = ObjectTransform()
        self.assertEqual(t.translation, (0.0, 0.0, 0.0))
        self.assertEqual(t.rotation, ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)))
        self.assertEqual(t.scale, 1.0)
        self.assertEqual(t, IDENTITY_TRANSFORM)

    def test_similarity_accepted(self) -> None:
        c, s = math.cos(0.3), math.sin(0.3)
        t = ObjectTransform(translation=[1, 2, 3], rotation=[[c, 0, s], [0, 1, 0], [-s, 0, c]], scale=0.5)
        self.assertEqual(t.translation, (1.0, 2.0, 3.0))
        self.assertIsInstance(t.rotation[0], tuple)

    def test_scale_must_be_positive_and_finite(self) -> None:
        for bad in (0.0, -1.0, math.inf, math.nan):
            with self.assertRaises(ValueError, msg=bad):
                ObjectTransform(scale=bad)

    def test_reflection_shear_and_non_uniform_scale_refused(self) -> None:
        reflection = ((-1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
        shear = ((1.0, 0.5, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
        non_uniform = ((2.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
        for bad in (reflection, shear, non_uniform):
            with self.assertRaises(ValueError, msg=bad):
                ObjectTransform(rotation=bad)

    def test_malformed_values_refused(self) -> None:
        with self.assertRaises(ValueError):
            ObjectTransform(translation=(0.0, 0.0))  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            ObjectTransform(rotation=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)))  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            SceneObject(ObjectId(0), Mesh(), pivot=(0.0, math.nan, 0.0))


class TestSelectionObjects(unittest.TestCase):
    def test_object_mode_writes_objects_only(self) -> None:
        sel = Selection()
        sel.vertices.add(VertexId(1))
        sel.mode = SelectionMode.OBJECT
        sel.set({ObjectId(0)})
        sel.add({ObjectId(1)})
        sel.toggle(ObjectId(2))
        sel.toggle(ObjectId(0))
        sel.remove({ObjectId(1)})
        self.assertEqual(sel.objects, {ObjectId(2)})
        self.assertEqual(sel.vertices, {VertexId(1)})

    def test_component_modes_leave_objects_alone(self) -> None:
        sel = Selection()
        sel.objects.add(ObjectId(3))
        for mode in (SelectionMode.VERTEX, SelectionMode.EDGE, SelectionMode.FACE):
            sel.mode = mode
            sel.set({VertexId(7)})
        self.assertEqual(sel.objects, {ObjectId(3)})

    def test_clear_and_is_empty_stay_component_only(self) -> None:
        """Review R-2: C -> Knife (`is_empty()`) und der Moduswechsel (`clear()`)
        behalten ihre Bedeutung, auch wenn Objekte ausgewählt sind."""
        sel = Selection()
        sel.objects.add(ObjectId(0))
        self.assertTrue(sel.is_empty())

        sel.vertices.add(VertexId(0))
        self.assertFalse(sel.is_empty())
        sel.mode = SelectionMode.OBJECT
        sel.clear()
        self.assertEqual(sel.vertices, set())
        self.assertEqual(sel.objects, {ObjectId(0)})
        self.assertIs(sel.mode, SelectionMode.OBJECT)
        self.assertTrue(sel.is_empty())

        sel.clear_objects()
        self.assertEqual(sel.objects, set())


class TestOneHistoryTwoObjects(unittest.TestCase):
    """Probe P-1 als Core-Test: ein Scene-Stack, Commands auf zwei Objekten."""

    def test_interleaved_undo_redo_across_two_objects(self) -> None:
        scene = Scene()
        scene.mesh = _quad_mesh()
        mesh_a = scene.mesh
        mesh_b = scene.add_object(_quad_mesh(offset=5.0)).mesh
        a0, b0 = mesh_a.export_state(), mesh_b.export_state()

        # Move auf A (das Edit-Objekt).
        moved = next(iter(mesh_a.all_vertex_ids()))
        selection = Selection()
        selection.set({moved})
        op = MoveOperation(OperationContext(target=mesh_a, selection=selection, history=scene.history))
        op.begin()
        op.update(delta=(0.0, 0.0, 1.0))
        op.commit()
        a1 = mesh_a.export_state()

        # Topologie auf B, während scene.mesh weiter A ist.
        self.assertIs(scene.mesh, mesh_a)
        edge = next(iter(mesh_b.all_edge_ids()))
        before = mesh_b.export_state()
        mesh_b.split_edge(edge)
        scene.history.push(MeshStateCommand(mesh=mesh_b, before_state=before, after_state=mesh_b.export_state()))
        b1 = mesh_b.export_state()
        self.assertEqual(len(scene.history), 2)

        scene.history.undo()
        self.assertEqual(_without_counters(mesh_b.export_state()), _without_counters(b0))
        self.assertEqual(mesh_a.export_state(), a1)

        scene.history.undo()
        self.assertEqual(_without_counters(mesh_a.export_state()), _without_counters(a0))
        self.assertEqual(_without_counters(mesh_b.export_state()), _without_counters(b0))

        scene.history.redo()
        self.assertEqual(mesh_a.export_state(), a1)
        self.assertEqual(_without_counters(mesh_b.export_state()), _without_counters(b0))

        scene.history.redo()
        self.assertEqual(mesh_b.export_state(), b1)
        self.assertEqual(mesh_a.export_state(), a1)


class TestSerializationV2(unittest.TestCase):
    def _two_object_scene(self) -> tuple[Scene, SceneObject, SceneObject]:
        scene = Scene()
        scene.mesh = _quad_mesh()
        head = scene.edit_object
        head.name = "head"
        gone = scene.add_object(Mesh())
        scene.remove_object(gone.id)  # verbrauchte ID: der Zähler muss darüber bleiben
        ref = scene.add_object(_quad_mesh(offset=3.0), name="gollum", state=ObjectState.REFERENCE)
        ref.transform = ObjectTransform(translation=(1.0, -2.0, 0.25), rotation=_ROT_90_Y, scale=1.5)
        ref.pivot = (0.0, 1.0, 0.0)
        ref.mesh.symmetry_definition = SymmetryDefinition(
            plane_point=(0.0, 0.0, 0.0), plane_normal=(1.0, 0.0, 0.0), seam_edges=frozenset()
        )
        scene.edit_object_id = ref.id
        return scene, head, ref

    def test_format_is_version_2_with_objects(self) -> None:
        scene, head, ref = self._two_object_scene()
        data = scene_to_dict(scene)
        self.assertEqual(FORMAT_VERSION, 2)
        self.assertEqual(data["version"], 2)
        self.assertNotIn("mesh", data)
        self.assertEqual(data["edit_object"], int(ref.id))
        self.assertEqual(data["object_id_counter"], scene.object_id_counter)
        self.assertEqual([o["id"] for o in data["objects"]], [int(head.id), int(ref.id)])
        self.assertEqual(data["objects"][1]["state"], "reference")
        self.assertEqual(data["objects"][1]["mesh"], ref.mesh.export_state())

    def test_dict_and_json_roundtrip_keep_every_object_field(self) -> None:
        scene, head, ref = self._two_object_scene()
        for restored in (scene_from_dict(scene_to_dict(scene)), scene_from_json(scene_to_json(scene))):
            self.assertEqual(list(restored.objects), [head.id, ref.id])
            self.assertEqual(restored.edit_object_id, ref.id)
            self.assertIsInstance(restored.edit_object_id, ObjectId)
            self.assertEqual(restored.object_id_counter, scene.object_id_counter)
            for original in (head, ref):
                loaded = restored.objects[original.id]
                self.assertIsInstance(loaded.id, ObjectId)
                self.assertIsNot(loaded.mesh, original.mesh)
                self.assertEqual(loaded.name, original.name)
                self.assertIs(loaded.state, original.state)
                self.assertEqual(loaded.transform, original.transform)
                self.assertEqual(loaded.pivot, original.pivot)
                self.assertEqual(full_topology_snapshot(loaded.mesh), full_topology_snapshot(original.mesh))
                self.assertEqual(loaded.mesh.symmetry_definition, original.mesh.symmetry_definition)
            self.assertIs(restored.mesh, restored.objects[ref.id].mesh)

    def test_new_object_after_load_never_reuses_a_dead_id(self) -> None:
        scene, head, ref = self._two_object_scene()
        restored = scene_from_dict(scene_to_dict(scene))
        new = restored.add_object(Mesh())
        self.assertGreater(int(new.id), int(ref.id))
        self.assertEqual(int(new.id), scene.object_id_counter)

    def test_version_1_dict_loads_as_one_normal_edit_object(self) -> None:
        mesh = _quad_mesh()
        v1 = {
            "version": 1,
            "mesh": mesh.export_state(),
            "morph_targets": None,
            "rig": None,
            "animation": None,
        }
        restored = scene_from_dict(v1)
        self.assertEqual(len(restored.objects), 1)
        obj = restored.edit_object
        self.assertIs(obj.state, ObjectState.NORMAL)
        self.assertEqual(obj.transform, IDENTITY_TRANSFORM)
        self.assertEqual(obj.pivot, (0.0, 0.0, 0.0))
        self.assertEqual(restored.mesh.export_state(), mesh.export_state())
        self.assertEqual(scene_to_dict(restored)["version"], 2)

    def test_inconsistent_v2_data_refused(self) -> None:
        scene, head, ref = self._two_object_scene()

        data = scene_to_dict(scene)
        data["edit_object"] = 99
        with self.assertRaises(ValueError):
            scene_from_dict(data)

        data = scene_to_dict(scene)
        data["object_id_counter"] = int(ref.id)
        with self.assertRaises(ValueError):
            scene_from_dict(data)

        data = scene_to_dict(scene)
        data["objects"][1]["id"] = data["objects"][0]["id"]
        with self.assertRaises(ValueError):
            scene_from_dict(data)

        data = scene_to_dict(scene)
        data["objects"][0]["transform"]["scale"] = -1.0
        with self.assertRaises(ValueError):
            scene_from_dict(data)


if __name__ == "__main__":
    unittest.main()
