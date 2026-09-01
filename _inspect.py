"""Temporär: inspiziert Rohzeichen bestimmter Zeilen."""
lines = open("docs/WP-04_AGENT_VERIFICATION_REPORT.md", encoding="utf-8").read().splitlines()
for i in (132, 134, 135, 136, 159, 195, 200, 299, 310):
    print(i+1, repr(lines[i]))))