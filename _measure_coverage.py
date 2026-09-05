"""Temporary Gate-3 coverage measurement (stdlib trace, no external deps)."""
import io
import os
import sys
import tokenize
import trace
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tests"))

import tests._bootstrap  # noqa: F401

TEST_MODULES = [
    "tests.test_application",
    "tests.test_camera",
    "tests.test_input_binding",
    "tests.test_picking",
    "tests.test_routing",
    "tests.test_tool_integration",
    "tests.test_tool_lifecycle",
    "tests.test_tool_manager",
    "tests.test_transform_operations",
]


def _collect_and_run():
    import io

    import tests._bootstrap  # noqa: F401

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for name in TEST_MODULES:
        suite.addTests(loader.loadTestsFromName(name))
    devnull = io.StringIO()
    runner = unittest.TextTestRunner(stream=devnull, verbosity=0)
    return runner.run(suite)


tracer = trace.Trace(count=1, trace=0, ignoredirs=[sys.prefix])
result = tracer.runfunc(_collect_and_run)
print(f"tests run: {result.testsRun}, failures={len(result.failures)}, errors={len(result.errors)}")

counts = tracer.results().counts
src_dir = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "src", "mirai")
)

def coverable_lines(path):
    coverable = set()
    with tokenize.open(path) as fh:
        try:
            tokens = tokenize.generate_tokens(fh.readline)
            for tok in tokens:
                if tok.type in (tokenize.ENCODING, tokenize.ENDMARKER):
                    continue
                if tok.type in (tokenize.NEWLINE, tokenize.NL):
                    continue
                if tok.type in (tokenize.INDENT, tokenize.DEDENT):
                    continue
                if tok.type == tokenize.COMMENT:
                    continue
                coverable.add(tok.start[0])
        except tokenize.TokenError:
            pass
    return coverable


total = 0
hit = 0
per_file = []
for root, dirs, files in os.walk(src_dir):
    for f in sorted(files):
        if not f.endswith(".py"):
            continue
        path = os.path.normpath(os.path.join(root, f))
        coverable = coverable_lines(path)
                # trace.Trace().results().counts maps (filename, lineno) -> exec count,
        # so filter by filename (normalized) and collect executed line numbers.
        executed = {
            ln
            for (fname, ln), c in counts.items()
            if os.path.normpath(fname) == path and c > 0
        }
        total += len(coverable)
        hit += len(coverable & executed)
        per_file.append((f, len(coverable), len(coverable & executed)))

for f, t, h in per_file:
    pct = 100.0 * h / t if t else 100.0
    print(f"  {f:28s} {h:4d}/{t:4d}  {pct:5.1f}%")
print(f"\nTOTAL src/mirai: {hit}/{total} lines executed = {100.0*hit/total:.1f}%")