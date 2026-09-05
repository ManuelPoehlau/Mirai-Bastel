"""Mirai-Bastel V1 Core.

Minimaler Architektur-Validierungs-Core gemäß V1_SPEC.md und den
archivierten Architecture Decisions (AD-001 Stable IDs, AD-002 Topology,
AD-003 Interactive Operation Lifecycle).

Dieses Paket ist bewusst klein. Ziel ist der Nachweis, dass die im Draft
festgelegten Architekturgrenzen tatsächlich haltbar sind - nicht eine
vollständige Modeling-Feature-Menge.
"""

from .ids import VertexId, EdgeId, FaceId
from .mesh import Mesh
from .selection import Selection, SelectionMode
from .history import HistoryStack, Command
from .operation import Operation, OperationContext
from .scene import Scene
from .serialization import scene_to_dict, scene_from_dict, scene_to_json, scene_from_json
from .operations.move import MoveOperation, MoveVerticesCommand
from .operations.transform import RotateOperation, ScaleOperation

__all__ = [
    "VertexId",
    "EdgeId",
    "FaceId",
    "Mesh",
    "Selection",
    "SelectionMode",
    "HistoryStack",
    "Command",
    "Operation",
    "OperationContext",
    "Scene",
    "scene_to_dict",
    "scene_from_dict",
    "scene_to_json",
    "scene_from_json",
    "MoveOperation",
    "MoveVerticesCommand",
    "RotateOperation",
    "ScaleOperation",
]
