"""Wewnetrzne kontrole spojnosci (ERC/DRC-lite).

Dzialaja bez zainstalowanego KiCada. Gdy KiCad/kicad-cli jest dostepny,
mozna dodatkowo uruchomic prawdziwe ERC/DRC (patrz cli.py --kicad).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .library import catalog, footprints
from .model import Design, Component


@dataclass
class Issue:
    severity: str   # "error" / "warning"
    code: str
    message: str

    def __str__(self) -> str:
        mark = "✗" if self.severity == "error" else "⚠"
        return f"{mark} [{self.code}] {self.message}"


def _footprint_for(c: Component):
    part = catalog.get_part(c.part)
    if "header" in part:
        rows, cols = part["header"]
        return footprints.header_fp(rows * cols, rows)
    return footprints.get(part["footprint"])


def run_erc(design: Design) -> List[Issue]:
    design.ensure_nets()
    issues: List[Issue] = []

    # 1) duplikaty referencji
    seen = {}
    for c in design.components:
        seen.setdefault(c.ref, 0)
        seen[c.ref] += 1
    for ref, n in seen.items():
        if n > 1:
            issues.append(Issue("error", "DUP_REF", f"Powtorzona referencja: {ref} ({n}x)"))

    # 2) piny podlaczone do nieistniejacych padow footprintu
    for c in design.components:
        try:
            fp = _footprint_for(c)
        except KeyError as e:
            issues.append(Issue("error", "NO_FOOTPRINT", f"{c.ref}: {e}"))
            continue
        pad_nums = set(fp.pad_numbers())
        for pin in c.connections:
            if pin not in pad_nums:
                issues.append(Issue("error", "PIN_PAD_MISMATCH",
                                    f"{c.ref}: pin '{pin}' nie ma odpowiednika w footprincie {fp.name}"))

    # 3) sieci z jednym pinem (wiszace)
    net_pads = {}
    for c in design.components:
        for pin, net in c.connections.items():
            if net:
                net_pads.setdefault(net, []).append(f"{c.ref}.{pin}")
    for net, pads in sorted(net_pads.items()):
        if len(pads) < 2:
            issues.append(Issue("warning", "SINGLE_PIN_NET",
                                f"Siec '{net}' ma tylko 1 polaczenie: {pads[0]}"))

    # 4) zasilanie: kazda siec power/ground powinna miec >=2 wezly
    for name, net in design.nets.items():
        if net.is_power or net.is_ground:
            if len(net_pads.get(name, [])) < 2:
                issues.append(Issue("warning", "POWER_NET_THIN",
                                    f"Siec zasilania '{name}' ma <2 polaczen"))

    # 5) komponenty bez polaczen (pomijamy mechaniczne: otwory montazowe H*)
    for c in design.components:
        if c.ref.startswith("H") or c.part == "MountingHole":
            continue
        if not any(c.connections.values()):
            issues.append(Issue("warning", "FLOATING_PART",
                                f"{c.ref} ({c.part}) nie ma podlaczonych pinow"))

    return issues


def run_drc_lite(design: Design) -> List[Issue]:
    """Kontrola rozmieszczenia: kolizje obrysow (courtyard) i pozycje."""
    issues: List[Issue] = []
    boxes = []
    for c in design.components:
        if c.x is None or c.y is None:
            issues.append(Issue("warning", "UNPLACED", f"{c.ref} nie ma pozycji na plytce"))
            continue
        fp = _footprint_for(c)
        bw, bh = (fp.body_h, fp.body_w) if int(getattr(c, "rotation", 0)) % 180 == 90 \
            else (fp.body_w, fp.body_h)
        boxes.append((c.ref, c.x - bw, c.y - bh, c.x + bw, c.y + bh))
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            r1, ax0, ay0, ax1, ay1 = boxes[i]
            r2, bx0, by0, bx1, by1 = boxes[j]
            if ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1:
                issues.append(Issue("error", "COURTYARD_OVERLAP",
                                    f"Nakladanie obrysow: {r1} i {r2}"))
    return issues


def summarize(issues: List[Issue]) -> str:
    errors = sum(1 for i in issues if i.severity == "error")
    warns = sum(1 for i in issues if i.severity == "warning")
    lines = [str(i) for i in issues]
    lines.append(f"\nRazem: {errors} bledow, {warns} ostrzezen.")
    return "\n".join(lines) if issues else "✓ Brak uwag."
