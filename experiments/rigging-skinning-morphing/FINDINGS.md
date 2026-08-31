# Experiment Findings — Phase 2c

**Status:** In Progress  
**Last Updated:** [Tests being run]  
**Experiment:** Rigging/Skinning/Morphing - RigController Foundation  

---

## Overview

This document captures actual experimental findings from Phase 2c tests.
It starts **empty** (no hypotheses pre-filled) and is filled with results as tests run.

**Methodology:**
1. Unit Tests verify RigController components
2. Integration Tests verify topology snapshot/change detection
3. Research Tests investigate topology operations with actual Core API
4. Findings documented here (observations only, no speculation)

---

## Research Questions

### Q1: Can we identify parent edge after split()?

**Question:** After split_edge() creates a new vertex, can we determine which edge was split?

**Method:** Geometric heuristic — new vertex position ≈ midpoint of some edge

**Status:** [PENDING TEST RESULTS]

**Finding:** [To be filled by test_split_edge_parent_inference]

---

### Q2: Which vertex survives in collapse_edge()?

**Question:** From CORE_API_AUDIT: "survivor = v0 (first endpoint)". Can we verify this?

**Method:** Call edge_vertices(edge_id) before collapse, then check which is still valid after

**Status:** [PENDING TEST RESULTS]

**Finding:** [To be filled by test_collapse_edge_survivor_determination]

---

### Q3: How many vertices are created in loop_insert()?

**Question:** When loop_insert() is called, how many vertices are added? (Not in V1 Core API audit yet)

**Status:** [NOT YET IMPLEMENTED IN TESTS]

**Finding:** [Depends on loop_insert() API]

---

### Q4: What edges/faces change in connect_vertices()?

**Question:** After connecting two face vertices, which faces are created? Can we identify them?

**Method:** Capture before/after state, trace new edges/faces

**Status:** [PENDING TEST RESULTS]

**Finding:** [To be filled by test_connect_vertices_topology_change]

---

## Unit Test Results

### Bone Management

[PENDING: Run test_rig_controller.py::TestBoneManagement]

- add_bone()
- get_bone()
- bone hierarchy
- get_chain_to_root()

### Skinning Weights

[PENDING: Run test_rig_controller.py::TestSkinningWeights]

- set_vertex_weight()
- multiple weights per vertex
- inherit_weights() for split scenario
- clear_weights()

### Morph Targets

[PENDING: Run test_rig_controller.py::TestMorphTargets]

- add_morph_target()
- set_morph_offset()
- morph blending
- activate/deactivate

### Topology Snapshots

[PENDING: Run test_rig_controller.py::TestTopologySnapshots]

- Snapshot capture
- Change detection (before/after)

### Topology Queries

[PENDING: Run test_rig_controller.py::TestTopologyQueries]

- query_vertex_topology()
- query_edge_topology()
- Use of Core APIs verified

### Topology Event Handling

[PENDING: Run test_rig_controller.py::TestTopologyEventHandling]

- handle_vertex_deletion()
- handle_new_vertex() with parent
- Weight/morph inheritance

### Deformation

[PENDING: Run test_rig_controller.py::TestDeformation]

- Skinning + morphs combined
- On-demand deformation computation

---

## Topology Operation Research

### split_edge() Research

**Test:** test_split_edge_return_values

Status: [PENDING]

Finding: [Captured by test output / print statements]

---

**Test:** test_split_edge_position_midpoint

Status: [PENDING]

Finding: [To verify position = midpoint calculation]

---

**Test:** test_split_edge_parent_inference

Status: [PENDING]

Finding: [Geometric heuristic: can we find parent edge?]

---

### collapse_edge() Research

**Test:** test_collapse_edge_survivor_determination

Status: [PENDING]

Finding: [Verify v0 always survives]

---

**Test:** test_collapse_edge_weight_merging

Status: [PENDING]

Finding: [Design decision: how to merge weights]

---

### connect_vertices() Research

**Test:** test_connect_vertices_topology_change

Status: [PENDING]

Finding: [Edge/face creation tracing]

---

## Core API Verification

**From CORE_API_AUDIT.md:**

- [VERIFY] all_vertex_ids() returns live vertices only
- [VERIFY] all_edge_ids() returns live edges only
- [VERIFY] all_face_ids() returns live faces only
- [VERIFY] edge_vertices() returns (v0, v1) consistently
- [VERIFY] edge_faces() returns all faces touching edge
- [VERIFY] vertex_edges() scans all edges (O(n) per call)
- [VERIFY] No automatic edge cleanup after remove_face()

---

## Limitations Identified

[PENDING: Tests will surface limitations]

Examples to verify:
- No parent tracking for split() (geometric heuristic required)
- No operation-context logging (must infer from snapshots)
- No automatic edge cleanup
- No vertex lineage metadata

---

## RigController Robustness

[PENDING: Tests will identify edge cases]

---

## Next Phase (Phase 3)

[PENDING: Phase 2c completion]

Findings from this experiment will guide Phase 3 decisions:
- Which Core APIs are sufficient for RigController?
- Which gaps require Core extensions?
- Should we implement automatic sync (requires Core changes)?

---

## Test Execution Instructions

Run all tests:
```bash
pytest test_rig_controller.py -v
pytest test_topology_operations.py -v -s
```

Individual test classes:
```bash
pytest test_rig_controller.py::TestBoneManagement -v
pytest test_topology_operations.py::TestSplitEdge -v -s
```

---

**Date Created:** August 2026  
**Status:** ✓ Template Ready, ⏳ Waiting for Test Results
