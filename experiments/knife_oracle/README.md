# Knife oracle (regression coverage)

The frozen Knife Face Lab engines (B, D, Q5), golden data and the golden / differential / `split_face` equivalence
tests that hold the Production Knife (`src/mirai/topology/knife*.py`) and `Mesh.split_face` against them. Frozen on
purpose: change an engine only to keep it running, never to follow Production.

Not in the default `pytest` run. Run it once at the end when a change touches the trigger list in
[AGENTS.md §8a](../../AGENTS.md#8a-test-strategy-token--and-runtime-efficient):

```bash
xvfb-run -a pytest experiments/knife_oracle/tests -q    # 351 tests, ≈ 64 s
```

Decision record: [`docs/research/topology/KNIFE_FACE_DECISIONS.md`](../../docs/research/topology/KNIFE_FACE_DECISIONS.md).
