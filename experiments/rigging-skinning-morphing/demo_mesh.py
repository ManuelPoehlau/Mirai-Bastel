"""Demo Mesh: Reproducible low-poly test mesh for rigging experiments.

V1: Simple box-based "head" shape with 8 vertices, 12 edges, 6 faces.
Small enough that vertex IDs are traceable, clear bone regions for rigging.

Bone regions (by convention, not enforced by mesh):
  - Skull: top vertices (y > 0)
  - Jaw:  front-bottom vertices (y <= 0, z > 0)
  - Neck: parent bone (virtual, no vertices directly)

The mesh is fully deterministic: same vertices, edges, faces every time.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is in path for src.core imports
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.core.mesh import Mesh
from src.core.ids import VertexId, EdgeId, FaceId


# Vertex positions for a simple "head" box
# Top vertices (y > 0) → skull region
# Bottom vertices (y <= 0) → jaw/neck region
_HEAD_VERTICES = [
    (-1.0, -1.0, -1.0),  # 0: bottom-left-back
    ( 1.0, -1.0, -1.0),  # 1: bottom-right-back
    ( 1.0,  1.0, -1.0),  # 2: top-right-back
    (-1.0,  1.0, -1.0),  # 3: top-left-back
    (-1.0, -1.0,  1.0),  # 4: bottom-left-front
    ( 1.0, -1.0,  1.0),  # 5: bottom-right-front
    ( 1.0,  1.0,  1.0),  # 6: top-right-front
    (-1.0,  1.0,  1.0),  # 7: top-left-front
]

# Face boundaries (counter-clockwise from outside)
_HEAD_FACES = [
    [0, 1, 2, 3],  # back  (z-)
    [5, 4, 7, 6],  # front (z+)
    [4, 0, 3, 7],  # left  (x-)
    [1, 5, 6, 2],  # right (x+)
    [3, 2, 6, 7],  # top   (y+)
    [4, 5, 1, 0],  # bottom(y-)
]


def build_head_mesh() -> Mesh:
    """Build the reproducible low-poly head mesh.
    
    Returns:
        Mesh with 8 vertices, 12 edges, 6 faces.
        Vertex IDs are 0-7 (deterministic).
        Edge/Face IDs depend on Core's allocation order.
    """
    mesh = Mesh()
    
    # Add vertices (IDs 0-7, deterministic)
    for pos in _HEAD_VERTICES:
        mesh.add_vertex(pos)
    
    # Add faces (auto-creates edges)
    for boundary in _HEAD_FACES:
        mesh.add_face(boundary)
    
    return mesh


def get_skull_vertices() -> list[VertexId]:
    """Vertices in the skull region (top, y > 0)."""
    return [VertexId(2), VertexId(3), VertexId(6), VertexId(7)]


def get_jaw_vertices() -> list[VertexId]:
    """Vertices in the jaw region (bottom-front, y <= 0, z > 0)."""
    return [VertexId(4), VertexId(5)]


def get_neck_vertices() -> list[VertexId]:
    """Vertices in the neck region (bottom-back, y <= 0, z <= 0)."""
    return [VertexId(0), VertexId(1)]


def get_vertex_region(vertex_id: VertexId) -> str:
    """Get the named region for a vertex (by convention)."""
    if vertex_id in get_skull_vertices():
        return "skull"
    elif vertex_id in get_jaw_vertices():
        return "jaw"
    elif vertex_id in get_neck_vertices():
        return "neck"
    return "unknown"
