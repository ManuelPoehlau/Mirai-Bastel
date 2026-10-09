# Future Ideas – Modeling

Ideen und Beobachtungen rund um Modeling, die bewusst noch nicht umgesetzt werden.

> Im Hinterkopf behalten und später erneut bewerten.
>
 Generate Mesh from/around bones
-- Quick way to build a mannequin like mesh, which is poseable and editable
--example: Create a humanoid bone skeletal structure and auto generate a simple Mesh around those bones.
-- ability to choose from: turn to mesh only or turn to rigged/skinned mesh
-- Similar to the idea of Zbrush Zspheres
> 

 Knife Cut Through — optional mode to also cut hidden faces (Blender "Cut Through"); Artist, 2026-09-29: maybe later as an extra option. See [KNIFE_CROSS_FACE_DISCOVERY.md §1.1](../research/topology/KNIFE_CROSS_FACE_DISCOVERY.md).

 Knife: Start im leeren Raum — Manu, 2026-10-09 (zu [Knife Discovery §6 F6](../research/symmetry/SYMMETRY_KNIFE_DISCOVERY.md)), wörtlich: „offen lassen (die Idee ist, später bei Start im leeren Raum ein Slice zu starten, ist jetzt aber erstmal irrelevant)“. Nicht ausgelegt; F6 bleibt offen.

 Knife angle constraint — left out of WP-KNIFE-01 UX2 (Artist, 2026-10-02), revisit later. Reference (Blender 2.79 `knife_snap_angle`, `editmesh_knife.c`, `[SRC]`): `C` toggles it; while a chain is being drawn the cursor is snapped, **in screen space**, to 45° steps of the direction from the previous point, measured against the screen's vertical axis; a guide line is drawn. Blender 3.0+ `[DOC]`: `R` cycles reference edges. Open design questions for later: screen space vs. face plane; which key (Blender's `C` is Cut Through in 3.0+); interaction with the 14 px snap and the midpoint snap (`Shift`+click, UX2). Record: `playground/experiments/knife_face/decision.md`, "WP-KNIFE-01 UX2".
