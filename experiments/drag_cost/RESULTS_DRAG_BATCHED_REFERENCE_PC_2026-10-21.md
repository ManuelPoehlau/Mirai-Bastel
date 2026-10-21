# W drag of large selections after the batched uploads, reference PC, 2026-10-21

Manu's run (Core 2 Quad Q9550, GeForce 9800 GTX, GL 3.3.0, Windows 10, Python 3.14.2), after commit 31c3bf5
(CPU mirrors + merged uploads) and 9ae963c. Command:
`python experiments\drag_cost\probe_navigation_gl.py --scenarios plain_w soft_w --assets examples\meshes\gollum_20k.obj`
(the profile blocks for orbit / zoom / first hover ran as well; first hover after an orbit ~37 ms total for 4 picks
incl. GPU read-back, i.e. ~9 ms per pick).

| Row (gollum_20k) | move p50 | p95 | transform | sync (of which store.update) | draw |
|---|---:|---:|---:|---:|---:|
| plain_w 36 V | 2.31 | 2.69 | 0.18 | 2.13 (0.51) | 2.53 |
| plain_w 112 V | 4.91 | 5.31 | 0.35 | 4.52 (0.96) | 2.79 |
| plain_w 500 V | 14.60 | 16.96 | 1.27 | 13.19 (2.31) | 3.21 |
| soft_w 15 % geodesic, 508 V moving | 15.27 | 17.70 | 1.72 | 13.36 (2.34) | 4.07 |
| soft_w 50 % geodesic, 3 339 V moving | 91.32 | 93.95 | 11.31 | 80.03 (11.33) | 6.73 |

Soft once-per-gesture rows: first move (begin + influence) 86 / 149 ms (15 % / 50 %), commit frame 42 / 63 ms,
selection click 36 / 51 ms, preview recompute 35 / 51 ms, settings change 36 / 53 ms.

Reading (agent): the upload calls are no longer the cost (11 ms of 80 ms sync at 3 339 V); what is left grows with the
number of moved vertices and the faces around them - per-face normals, face-data rows (corner positions + normals for
the Smooth shading) and vertex normals, all in Python, plus the Core transform itself (11 ms). About 2.2x the
container's time for the same rows.

**Manu, 2026-10-21:** „Große Auswahl transformieren fühlt sich noch langsam an. Wir lassen es aber vorerst so.“ Next
(fresh session, his idea): look at how Blender transforms a large selection on 20k without a noticeable delay; probably
relevant for morphing dense meshes too.
