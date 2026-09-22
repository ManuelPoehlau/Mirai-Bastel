"""DISCOVERY PROBE — per-face Vertex Connect under incremental (persistent) selection.

Evidence for docs/architecture/AD-017_REVIEW_AUTHOR_001.md, question 7.
Applies the Wings-style per-face rule (cyclic boundary order, adjacent pairs skipped) —
the rule connect_per_face.py uses for midpoints — to selected vertices on a hexagon.
Not a tool, not wired anywhere.

Run:  python experiments/topology/vertex_connect_incremental_probe.py
"""
import sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(_ROOT / "src"), str(_ROOT), str(_ROOT / "tests")]
from core import Mesh
from mesh_invariants import assert_mesh_invariants

def per_face_vertex_connect(m, verts):
    """Wings-style per-face vertex connect (cyclic boundary order, skip adjacent) — same rule
    as playground/topology_tools/connect_per_face.py applies to midpoints."""
    sel=set(verts); pairs=[]
    for f in sorted(m.all_face_ids(), key=int):
        on=[v for v in m.face_vertices(f) if v in sel]
        if len(on)==2: pairs.append((on[0],on[1]))
        elif len(on)>2: pairs += [(on[i],on[(i+1)%len(on)]) for i in range(len(on))]
    made=[]
    for a,b in pairs:
        for f in sorted(m.all_face_ids(), key=int):
            vs=m.face_vertices(f)
            if a in vs and b in vs:
                d=(vs.index(a)-vs.index(b))%len(vs)
                if d not in (1,len(vs)-1):
                    e,_,_=m.connect_vertices(f,a,b); made.append(tuple(sorted((int(a),int(b))))); break
    return made

def hexagon():
    m=Mesh(); import math
    v=[m.add_vertex((math.cos(i*math.pi/3), math.sin(i*math.pi/3),0.0)) for i in range(6)]
    m.add_face(v); return m,v

def name(v, names): return names.get(int(v), str(int(v)))

# Case 1: incremental A+B, then +C where C = v5 (chain expected)
for label, cidx in (("C=v5", 5), ("C=v4", 4)):
    m,v=hexagon(); A,B=v[0],v[3]; C=v[cidx]
    names={int(A):"A",int(B):"B",int(C):"C"}
    s1=per_face_vertex_connect(m,[A,B])
    s2=per_face_vertex_connect(m,[A,B,C])
    assert_mesh_invariants(m,context=label)
    fmt=lambda L:[f"{names.get(a,a)}-{names.get(b,b)}" for a,b in L]
    print(f"Inkrementell A+B → {fmt(s1)};  dann A+B+{label} → neue Kanten {fmt(s2)}")

# Case 2: same three vertices selected simultaneously
m,v=hexagon(); A,B,C=v[0],v[3],v[5]; names={int(A):"A",int(B):"B",int(C):"C"}
s=per_face_vertex_connect(m,[A,B,C]); print("Gleichzeitig A+B+C(v5) →",[f"{names[a]}-{names[b]}" for a,b in s])
m,v=hexagon(); A,B,C=v[0],v[2],v[4]; names={int(A):"A",int(B):"B",int(C):"C"}
s=per_face_vertex_connect(m,[A,B,C]); print("Gleichzeitig A+B+C (v0,v2,v4) →",[f"{names[a]}-{names[b]}" for a,b in s])

# Case 3: idempotence — repeat A+B
m,v=hexagon(); per_face_vertex_connect(m,[v[0],v[3]]); n=len(m.all_edge_ids())
again=per_face_vertex_connect(m,[v[0],v[3]]); print("Wiederholung A+B → neue Kanten:",again, "| Kantenzahl gleich:", n==len(m.all_edge_ids()))
