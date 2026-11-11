/* Native kernels on packed arrays - measurement prototype for probe_kernels.py (audit 2026-11-10), not product
   code. Built with -O2 -march=core2: only instructions a Core 2 Quad Q9550 has (no SSE4.2 / AVX / FMA).
   Single thread. Every kernel repeats the arithmetic of its production counterpart in the same order. */
#include <math.h>
#include <stdint.h>
#include <string.h>

/* Newell normal of one face (any size), normalised like derived.py (zero below 1e-12). */
static void face_normal(const double *P, const int32_t *cv, int64_t lo, int64_t hi, double *out) {
    double nx = 0, ny = 0, nz = 0;
    for (int64_t c = lo; c < hi; ++c) {
        const double *a = P + 3 * cv[c];
        const double *b = P + 3 * cv[c + 1 < hi ? c + 1 : lo];
        nx += (a[1] - b[1]) * (a[2] + b[2]);
        ny += (a[2] - b[2]) * (a[0] + b[0]);
        nz += (a[0] - b[0]) * (a[1] + b[1]);
    }
    double len = sqrt(nx * nx + ny * ny + nz * nz);
    if (len < 1e-12) { out[0] = out[1] = out[2] = 0.0; }
    else { out[0] = nx / len; out[1] = ny / len; out[2] = nz / len; }
}

static void vertex_normal(const double *FN, const int32_t *vf, int64_t lo, int64_t hi, double *out) {
    double x = 0, y = 0, z = 0;
    for (int64_t k = lo; k < hi; ++k) {
        const double *n = FN + 3 * vf[k];
        x += n[0]; y += n[1]; z += n[2];
    }
    double len = sqrt(x * x + y * y + z * z);
    if (len < 1e-12) { out[0] = out[1] = out[2] = 0.0; }
    else { out[0] = x / len; out[1] = y / len; out[2] = z / len; }
}

void all_normals(const double *P, int64_t V, int64_t F, const int64_t *face_ptr, const int32_t *cv,
                 const int64_t *vf_ptr, const int32_t *vf, double *FN, double *VN) {
    for (int64_t f = 0; f < F; ++f) face_normal(P, cv, face_ptr[f], face_ptr[f + 1], FN + 3 * f);
    for (int64_t v = 0; v < V; ++v) vertex_normal(FN, vf, vf_ptr[v], vf_ptr[v + 1], VN + 3 * v);
}

/* 1-ring patch for `moved` (the RenderMesh._sync_geometry neighbourhood): faces of the moved vertices,
   then the vertices of those faces. `fmark` / `vmark` are caller-owned scratch (F / V bytes, zeroed);
   writes float32 mirrors for the upload and returns the touched slot range in lo_hi. */
int64_t patch_normals(const double *P, int64_t V, int64_t F, const int64_t *face_ptr, const int32_t *cv,
                      const int64_t *vf_ptr, const int32_t *vf, double *FN, double *VN,
                      const int64_t *moved, int64_t n_moved, uint8_t *fmark, uint8_t *vmark,
                      int32_t *fscratch, int32_t *vscratch, float *pos32, float *nrm32, int64_t *lo_hi) {
    int64_t nf = 0, nv = 0, lo = V, hi = 0;
    for (int64_t i = 0; i < n_moved; ++i) {
        int64_t v = moved[i];
        pos32[3 * v] = (float)P[3 * v]; pos32[3 * v + 1] = (float)P[3 * v + 1]; pos32[3 * v + 2] = (float)P[3 * v + 2];
        for (int64_t k = vf_ptr[v]; k < vf_ptr[v + 1]; ++k) {
            int32_t f = vf[k];
            if (!fmark[f]) { fmark[f] = 1; fscratch[nf++] = f; }
        }
    }
    for (int64_t i = 0; i < nf; ++i) {
        int32_t f = fscratch[i];
        face_normal(P, cv, face_ptr[f], face_ptr[f + 1], FN + 3 * f);
        for (int64_t c = face_ptr[f]; c < face_ptr[f + 1]; ++c) {
            int32_t v = cv[c];
            if (!vmark[v]) { vmark[v] = 1; vscratch[nv++] = v; }
        }
        fmark[f] = 0;
    }
    for (int64_t i = 0; i < nv; ++i) {
        int32_t v = vscratch[i];
        vertex_normal(FN, vf, vf_ptr[v], vf_ptr[v + 1], VN + 3 * v);
        nrm32[3 * v] = (float)VN[3 * v]; nrm32[3 * v + 1] = (float)VN[3 * v + 1]; nrm32[3 * v + 2] = (float)VN[3 * v + 2];
        if (v < lo) lo = v;
        if (v + 1 > hi) hi = v + 1;
        vmark[v] = 0;
    }
    lo_hi[0] = lo; lo_hi[1] = hi;
    return nv;
}

/* Linear blend skinning, the production rule: p' = c p + sum w_k (A_k p), c = 1 - sum w_k;
   keys < 0 = no influence. A: per bone 12 doubles (3x4 rows). */
void lbs(const double *rest, const int64_t *rows, int64_t n, const int32_t *keys, const double *wts,
         const double *A, double *out) {
    for (int64_t i = 0; i < n; ++i) {
        const double *p = rest + 3 * rows[i];
        double sx = 0, sy = 0, sz = 0, sum = 0;
        for (int k = 0; k < 4; ++k) {
            int32_t key = keys[4 * i + k];
            if (key < 0) continue;
            const double *a = A + 12 * key;
            double w = wts[4 * i + k];
            sx += w * (a[0] * p[0] + a[1] * p[1] + a[2] * p[2] + a[3]);
            sy += w * (a[4] * p[0] + a[5] * p[1] + a[6] * p[2] + a[7]);
            sz += w * (a[8] * p[0] + a[9] * p[1] + a[10] * p[2] + a[11]);
            sum += w;
        }
        double c = 1.0 - sum;
        double *o = out + 3 * rows[i];
        o[0] = c * p[0] + sx; o[1] = c * p[1] + sy; o[2] = c * p[2] + sz;
    }
}

/* Sparse morph target: shown[rows] = base[rows] + w * offsets. */
void morph(const double *base, const int64_t *rows, int64_t n, const double *offs, double w, double *shown) {
    for (int64_t i = 0; i < n; ++i) {
        const double *b = base + 3 * rows[i];
        double *s = shown + 3 * rows[i];
        s[0] = b[0] + w * offs[3 * i]; s[1] = b[1] + w * offs[3 * i + 1]; s[2] = b[2] + w * offs[3 * i + 2];
    }
}

/* Stencils in CSR form: out[d] = sum w * ctrl[idx]. */
void stencils(const double *ctrl, const int64_t *ptr, const int32_t *idx, const double *w, int64_t n, double *out) {
    for (int64_t d = 0; d < n; ++d) {
        double x = 0, y = 0, z = 0;
        for (int64_t k = ptr[d]; k < ptr[d + 1]; ++k) {
            const double *p = ctrl + 3 * idx[k];
            x += w[k] * p[0]; y += w[k] * p[1]; z += w[k] * p[2];
        }
        out[3 * d] = x; out[3 * d + 1] = y; out[3 * d + 2] = z;
    }
}
