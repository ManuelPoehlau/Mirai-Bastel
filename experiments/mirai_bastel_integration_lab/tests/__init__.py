"""Headless Integration-Boundary-Tests des Integration Labs.

Laufen bewusst ohne pyglet/GL — die Render-Grenze wird gegen den
deterministischen `TraceStore` getestet (exakt das Muster des V0.2-
Experiments). Aufruf vom Repo-Root:  pytest experiments/mirai_bastel_integration_lab/tests
"""