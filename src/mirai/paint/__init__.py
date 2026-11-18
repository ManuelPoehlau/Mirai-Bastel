"""Texture painting in UV space (AD-037; audit `docs/research/TEXTURE_PAINT_ROOM_ARCHITECTURE_AUDIT_2026-11-18.md`).

Phase 1 (foundations, no room and no brush yet):
- `uv_health` - the read-only UV check (unmapped, zero-area, overlapping, outside 0-1, texel density);
- `texel_map` - the derived texel -> (triangle, barycentric) map with journal patching;
- `store` - the CPU-authoritative pixels of each painted object (layers, tiles, composite, flatten);
- `commands` - `PaintStrokeCommand` (the before/after tiles of one stroke) and the layer-property step;
- `files` - PNG persistence of the layers beside the scene and the flattened image.

The document value is the Core's `SceneObject.paint` (`core.scene.PaintStack`); everything here is `src/mirai`.
"""
