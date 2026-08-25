# Mirai-Bastel Research Log

A chronological record of important discoveries and changes in our understanding.

## 2026-08-25 — Initial systematic N-World/Mirai pass

### Major finding: Mirai was deliberately context-driven

A contemporary December 1999 Game Developer review describes Mirai as closer to a **3D operating system** than a conventional UI. Modules behaved like applications while remaining dynamically linked; changes propagated between them. The review also states that LMB/MMB/RMB interaction depended on sequence and context, and that selection strongly affected available options.

**Implication:** the interaction model is likely one of Mirai's defining technologies, not merely a UI skin.

### Major finding: Volume Modeling / Derived Surface

The same 1999 review describes Mirai's subdivision approach as **Volume Modeling**. A low-resolution control volume drives a higher-resolution **Derived Surface**; changes to the control volume update the derived surface. The review notes that the control volume could generate multiple levels of detail and behave like a lattice deformer for poses and morph targets.

**Implication:** SubD should be treated as part of the modeling/deformation architecture, not merely a viewport smoothing switch.

### Major finding: Magnet Move is historically real

The August 1999 Mirai update introduced magnet moves along face normals with falloff. The feature was described as allowing artists to "paint" surface deformations such as cheekbones, brows, clothing and armor. Mirai 1.1 documentation again lists Magnet Move with normal-direction falloff.

**Implication:** our planned Soft Selection / Influence system has a direct historical analogue. It should be a reusable subsystem rather than a one-off tool.

### Major finding: Winged Edge is explicitly identified

Bay Raitt's own professional description identifies Mirai's modeller with a **Winged Edge data structure** and traces its lineage to Symbolics S-Geometry.

**Implication:** topology architecture deserves dedicated research before the final mesh core is chosen. We will compare Winged Edge with Half Edge and modern hybrids rather than blindly copying history.

### Major finding: Modeling was fundamentally polygon/subdivision based

The 1999 review emphasizes Mirai's polygonal roots and says it did not use NURBS/B-splines/H-splines for this modeling approach. Edge alignment, beveling, extrusion, edge loops and subdivision/smoothing were central.

**Implication:** the V1 target of a fast polygon modeler in the Silo/Wings/Mirai family is historically well aligned.

## Research discipline

- Primary sources first.
- Contemporary technical sources second.
- Direct video observations are recorded separately from internal-implementation claims.
- Community reports are leads until independently verified.
- When a later source contradicts an earlier conclusion, preserve the history and mark the conclusion as revised.

## Next

The next major task is a **chapter-by-chapter extraction of the surviving N-World 3.0 online documentation**. Search for concrete terminology, interaction rules, selection semantics, camera behavior, topology/modeling operations, animation, scripting, paint/material systems and data concepts.
