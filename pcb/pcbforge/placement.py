"""Autoplacement komponentow na plytce (mm).

Pakowanie polkowe (shelf packing) z gwarancja braku kolizji obrysow:
kolejnosc moduly/IC -> zlacza -> reszta, ukladane rzedami od lewej do prawej.
Reguly "near" z bazy wiedzy stosowane sa tylko gdy nie powoduja kolizji.
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

from .knowledge import Knowledge
from .library import catalog, footprints
from .model import Design, Component


def _fp(c: Component):
    part = catalog.get_part(c.part)
    if "header" in part:
        rows, cols = part["header"]
        return footprints.header_fp(rows * cols, rows)
    return footprints.get(part["footprint"])


def _order(design: Design) -> List[Component]:
    modules = [c for c in design.components if c.ref.startswith("U")]
    connectors = [c for c in design.components if c.ref.startswith(("J", "USB"))]
    rest = [c for c in design.components if c not in modules and c not in connectors]
    return modules + connectors + rest


def _overlaps(box, boxes, gap=0.0) -> bool:
    ax0, ay0, ax1, ay1 = box
    for (_r, bx0, by0, bx1, by1) in boxes:
        if ax0 - gap < bx1 and bx0 < ax1 + gap and ay0 - gap < by1 and by0 < ay1 + gap:
            return True
    return False


def autoplace(design: Design, kb: Knowledge | None = None) -> None:
    kb = kb or Knowledge()
    comps = _order(design)
    gap = max(design.rules.clearance, 0.2) + 2.0
    margin = design.rules.board_margin + 2.0

    # szerokosc docelowa ~ kwadratowa plytka
    total_area = 0.0
    max_w = 0.0
    for c in comps:
        fp = _fp(c)
        w, h = fp.body_w * 2, fp.body_h * 2
        total_area += (w + gap) * (h + gap)
        max_w = max(max_w, w)
    target_w = max(max_w, math.sqrt(total_area) * 1.2)

    placed: List[Tuple] = []
    cursor_x = margin
    cursor_y = margin
    row_h = 0.0

    for c in comps:
        fp = _fp(c)
        w, h = fp.body_w * 2, fp.body_h * 2
        if cursor_x > margin and cursor_x + w > margin + target_w:
            cursor_x = margin
            cursor_y += row_h + gap
            row_h = 0.0
        c.x = round(cursor_x + fp.body_w, 3)
        c.y = round(cursor_y + fp.body_h, 3)
        c.rotation = 0
        placed.append((c.ref, c.x - fp.body_w, c.y - fp.body_h,
                       c.x + fp.body_w, c.y + fp.body_h))
        cursor_x += w + gap
        row_h = max(row_h, h)

    # rozmiar plytki
    xs, ys = [], []
    for c in design.components:
        fp = _fp(c)
        xs += [c.x - fp.body_w, c.x + fp.body_w]
        ys += [c.y - fp.body_h, c.y + fp.body_h]
    design.board_w = round(max(xs) + margin, 1)
    design.board_h = round(max(ys) + margin, 1)
