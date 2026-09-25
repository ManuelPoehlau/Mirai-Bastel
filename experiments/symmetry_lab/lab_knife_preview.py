"""Hover-Vorschau des gespiegelten Knife — Dry-Run ohne Mutation. GL-frei.

Handoff WP-SYM-LAB-01 Slice 7, E28 (Design Brief, Zeile Knife: „Kann der
gespiegelte Pfad nicht eindeutig abgebildet werden, erfährt der Artist das
vor dem Bestätigen"). Für ein Hover-Ziel aus `lab_knife_pick.knife_pick`
bestimmt `knife_hover_preview`, wo der Quellpunkt läge und ob bzw. wohin er
gespiegelt würde — ohne `split_edge`/`connect_vertices` aufzurufen.

Kein zweiter Algorithmus: Die Auflösungsreihenfolge ist die von
`LabKnifeTool` (E17/E18), und wo möglich werden dessen Methoden direkt
benutzt (`partner`, `_seam_vertices`, `_is_seam_edge`, `edge_between`), die
Meldungstexte sind dieselben wie beim echten Klick. `lab_knife.py` bleibt
unverändert. Der Quellpunkt einer Edge wird mit derselben Arithmetik
berechnet wie `Mesh.split_edge` (`p0 * (1 - t) + p1 * t`, `p0` = `edge.v0`);
der Spiegelpunkt wie `LabKnifeTool._split_mirror_edge` über
`mirror_position` (nicht über ein gespiegeltes `t`, Befund P3). Dass beide
bitgleich mit dem Ergebnis des echten Klicks sind, sichert
`tests/test_lab_knife_window.py`.

Abgedeckt ist nur, was E28 verlangt: Auflösbarkeit des Spiegelziels und der
Seam-Sehnen-Fall. Was ein Klick darüber hinaus ablehnen kann (keine gemeinsame
Face, Verbindung existiert bereits, keine Spiegel-Face, gescheiterte
Validierung E19), zeigt die Vorschau nicht — das meldet erst der Klick.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from mirai.symmetry import mirror_position

from .lab_knife import LabKnifeTool, edge_between

Vec3 = tuple[float, float, float]

#: Grund, wenn `LabKnifeTool.hover` das Ziel selbst ablehnt (Edge am Start-Vertex).
REASON_INVALID_TARGET = "Ziel ungültig (Edge am Start-Vertex)"
#: Wortgleich mit `LabKnifeTool._check_vertex_target`/`_check_edge_target`.
REASON_SEAM_CHORD = "Schnitt entlang der Seam nicht unterstützt"


@dataclass(frozen=True)
class KnifeHoverPreview:
    """Was ein Klick auf `target` erzeugen würde (E28), reine Anzeige."""

    #: `knife_pick`-Ergebnis (nur `"vertex"`/`"edge"`).
    target: dict
    #: Vertex-Position bzw. interpolierter Edge-Punkt wie `split_edge`.
    source_position: Vec3
    #: Spiegelpunkt; `None` bei Seam (Quellpunkt ist sein eigener Partner),
    #: bei Symmetrie aus oder wenn nicht auflösbar.
    mirror_position: Optional[Vec3]
    resolvable: bool
    #: Kurztext für die Statuszeile, wenn nicht klickbar.
    reason: Optional[str] = None
    #: `LabKnifeTool.hover(target)["valid"]` (Slice 6, unverändert).
    valid: bool = True

    @property
    def clickable(self) -> bool:
        return self.valid and self.resolvable


def edge_point(mesh, eid, t: float) -> Vec3:
    """Position, die `mesh.split_edge(eid, t)` dem neuen Vertex gäbe."""
    va, vb = mesh.edge_vertices(eid)
    p0 = mesh.vertex_position(va)
    p1 = mesh.vertex_position(vb)
    return tuple(a * (1.0 - t) + b * t for a, b in zip(p0, p1))


def knife_hover_preview(knife: LabKnifeTool, target: Optional[dict]) -> Optional[KnifeHoverPreview]:
    """Dry-Run für ein Hover-Ziel; `None` für `"face"`/`"outside"` (kein Ziel)."""
    kind = target.get("kind") if target else None
    mesh = knife._mesh
    if kind == "vertex":
        vid = target.get("vertex_id")
        if vid is None or not mesh.is_valid_vertex(vid):
            return None
        source = mesh.vertex_position(vid)
    elif kind == "edge":
        eid = target.get("edge_id")
        if eid is None or not mesh.is_valid_edge(eid):
            return None
        source = edge_point(mesh, eid, target.get("t", 0.5))
    else:
        return None

    valid = bool(knife.hover(target)["valid"])
    invalid_reason = None if valid else REASON_INVALID_TARGET

    def preview(mirror: Optional[Vec3], resolvable: bool, reason: Optional[str]):
        return KnifeHoverPreview(
            target=target,
            source_position=source,
            mirror_position=mirror if resolvable else None,
            resolvable=resolvable,
            reason=reason or invalid_reason,
            valid=valid,
        )

    if not knife.mirrored:
        return preview(None, True, None)
    if kind == "vertex":
        return preview(*_resolve_vertex(knife, vid))
    return preview(*_resolve_edge(knife, eid, source))


def _resolve_vertex(knife: LabKnifeTool, vid) -> tuple[Optional[Vec3], bool, Optional[str]]:
    """Wie `_check_vertex_target` (Seam-Sehne) + `_apply_vertex_click` (Partner)."""
    mesh = knife._mesh
    start = knife.start
    if start is not None and vid != start:
        seam = knife._seam_vertices()
        if start in seam and vid in seam:
            return None, False, REASON_SEAM_CHORD
    partner = knife.partner(vid)
    if partner is None:
        return None, False, f"kein Spiegelpartner für v{int(vid)} (INV-5)"
    if partner == vid:
        return None, True, None  # Seam: eigener Partner, kein Spiegelpunkt
    return mesh.vertex_position(partner), True, None


def _resolve_edge(
    knife: LabKnifeTool, eid, source: Vec3
) -> tuple[Optional[Vec3], bool, Optional[str]]:
    """Wie `_check_edge_target` (Seam-Sehne) + `_split` (Partner-Edge)."""
    mesh = knife._mesh
    if knife._is_seam_edge(eid):
        if knife.start is not None and knife.start in knife._seam_vertices():
            return None, False, REASON_SEAM_CHORD
        # Split auf der Seam: selbst-gepaart, Achsenkomponente exakt 0.0.
        return None, True, None
    a, b = mesh.edge_vertices(eid)
    pa, pb = knife.partner(a), knife.partner(b)
    for v, p in ((a, pa), (b, pb)):
        if p is None:
            return None, False, f"kein Spiegelpartner für v{int(v)} (INV-5)"
    mirror_edge = edge_between(mesh, pa, pb)
    if mirror_edge is None:
        return None, False, f"keine Spiegel-Edge zu e{int(eid)}"
    if mirror_edge == eid:
        return None, False, f"e{int(eid)} ist ihr eigenes Spiegelbild, aber keine Seam-Edge"
    definition = mesh.symmetry_definition
    return mirror_position(source, definition.plane_point, definition.plane_normal), True, None
