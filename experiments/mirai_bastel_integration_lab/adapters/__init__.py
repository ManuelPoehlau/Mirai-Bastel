"""Adapter des Integration Labs.

Die Adapter sind die einzige Brücke zwischen den unabhängigen Bausteinen:

    obj_to_core    OBJ -> ObjMeshData -> src.core.Mesh/Scene
    triangulate    Polygon-Triangulierung (reine Render-Darstellung)
    core_to_render src.core.Mesh -> V0.2 Render-Mesh + Index-Mapping + Sync
    picking        Screen-Space-Vertex-Picking gegen die Lab-Kamera

Siehe README.md im Lab-Ordner für die Architektur.
"""