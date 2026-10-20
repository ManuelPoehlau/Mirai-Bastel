# Multi-target morph blend arithmetic and attribute-layer memory (architecture audit 2026-10-20).
# Read-only discovery probe, pure Python; NumPy rows only if NumPy imports. Measures the blend `out = base + sum(w_i * delta_i)`
# only - no normals, no upload, no draw. Run: python experiments/architecture_audit_probes/probe_morph_blend.py [V]
# Read-only discovery measurement (container, NOT the reference PC). Pure Python vs NumPy.
import time, random, statistics, tracemalloc, array, sys
random.seed(1)
V = int(sys.argv[1]) if len(sys.argv) > 1 else 21875
def med(f, n=5):
    xs=[]
    for _ in range(n):
        a=time.perf_counter(); f(); xs.append((time.perf_counter()-a)*1000)
    return statistics.median(xs)
base=[(random.random(),random.random(),random.random()) for _ in range(V)]
def make_target(frac):
    idx=random.sample(range(V), int(V*frac))
    return {i:(random.random()*.01,random.random()*.01,random.random()*.01) for i in idx}
print(f"V={V}")
# --- pure python: out = base + sum_i w_i * delta_i  (sparse dict deltas, like morph_lab-style per-vertex dicts)
def pure(targets, ws):
    out=list(base)
    for t,w in zip(targets,ws):
        for i,(dx,dy,dz) in t.items():
            x,y,z=out[i]; out[i]=(x+w*dx,y+w*dy,z+w*dz)
    return out
for frac in (0.15,1.0):
    for N in (1,10,50):
        ts=[make_target(frac) for _ in range(N)]; ws=[random.random() for _ in range(N)]
        print(f"pure python  sparse={frac:4.2f}  N_active={N:3d}  {med(lambda:pure(ts,ws),3):9.1f} ms")
try:
    import numpy as np
    print("numpy", np.__version__)
    B=np.array(base,dtype=np.float32)
    for N in (1,10,50,100):
        D=np.random.rand(N,V,3).astype(np.float32)*.01   # dense deltas worst case
        w=np.random.rand(N).astype(np.float32)
        t=med(lambda: B+np.tensordot(w,D,axes=1),5)
        print(f"numpy dense  N_active={N:3d}  {t:9.2f} ms   deltas {D.nbytes/1e6:7.1f} MB")
except ImportError:
    print("numpy not available")
# --- attribute layer memory (per snapshot) ---
def mem(f):
    tracemalloc.start(); x=f(); c,_=tracemalloc.get_traced_memory(); tracemalloc.stop(); return c/1e6,x
m,_=mem(lambda:{i:random.random() for i in range(V)})
print(f"scalar attribute layer as dict[int,float]  : {m:6.2f} MB for V={V}")
m,_=mem(lambda:array.array('f',[0.0])*V)
print(f"scalar attribute layer as array('f')       : {m:6.2f} MB")
m,_=mem(lambda:{i:{j:random.random() for j in range(4)} for i in range(V)})
print(f"skin weights, 4 influences/vertex as dicts : {m:6.2f} MB  (copied into every full snapshot)")
