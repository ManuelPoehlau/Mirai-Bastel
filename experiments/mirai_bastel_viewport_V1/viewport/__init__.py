"""Viewport V1 Experiment Package.

This directory contains the interactive viewport experiment modules
(cube scene, topology lab, transform tools, etc.) used by the
run.py / run_topology.py / run_cylinder.py / run_all_tools.py
entry points.

Adding this __init__.py makes viewport a regular package instead of
a PEP 420 namespace package.  This prevents the experiment viewport/
directory from being silently merged with any other viewport/ directory
that may appear earlier on sys.path (e.g. the stray top-level viewport/
at the repository root).  Without this marker the namespace package
resolution can pick up the wrong directory and fail to find modules
such as topology_app.
"""
