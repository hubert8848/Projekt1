"""Rozmieszczenie wg zasad uzytkownika (urzadzenie z dwoch plytek).

Zasady:
  1. I/O (zlacza) na GORNEJ i DOLNEJ krawedzi plytki (dostep srubokretem).
  2. R/C/diody upakowane w srodku (lub od spodu) - "z rekami i nogami".
  4. Otwory montazowe w IDENTYCZNYCH wspolrzednych na obu plytkach.
  5. Zlacze board-to-board w IDENTYCZNYM miejscu (idealnie sie skladaja).
  7/8. Przekazniki + zaciski 230V w osobnej STREFIE 230V (dolna krawedz).
  Gorna plytka jest WEZSZA o pasy I/O (gora/dol), zeby srubokret dochodzil
  do zaciskow dolnej plytki - ale otwory i B2B zostaja na miejscu.

Obie plytki uzywaja WSPOLNEJ ramki wspolrzednych (Frame).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .library import catalog, footprints
from .model import Design, Component


@dataclass
class Frame:
    width: float
    height: float           # pelna wysokosc (dolna plytka)
    io_band: float = 16.0   # pas I/O na gorze i dole
    hole_inset: float = 4.5
    margin: float = 3.0

    @property
    def central(self) -> Tuple[float, float, float, float]:
        """Obszar srodkowy (obrys gornej plytki)."""
        return (self.margin, self.io_band, self.width - self.margin, self.height - self.io_band)

    @property
    def holes(self) -> List[Tuple[float, float]]:
        x0, y0, x1, y1 = self.central
        i = self.hole_inset
        return [(x0 + i, y0 + i), (x1 - i, y0 + i), (x1 - i, y1 - i), (x0 + i, y1 - i)]

    @property
    def b2b(self) -> Tuple[float, float]:
        return (self.width / 2, self.height / 2)


def _fp(c: Component):
    part = catalog.get_part(c.part)
    if "header" in part:
        rows, cols = part["header"]
        return footprints.header_fp(rows * cols, rows)
    return footprints.get(part["footprint"])


def _role(c: Component) -> str:
    if c.role:
        return c.role
    if c.ref.startswith("H") or c.part == "MountingHole":
        return "mount"
    if c.part == "Relay_SPDT":
        return "relay"
    if c.ref.startswith(("J", "USB")):
        return "io"
    if c.ref.startswith("U"):
        return "ic"
    return "passive"


def _overlaps(box, boxes, gap=0.5) -> bool:
    ax0, ay0, ax1, ay1 = box
    for (bx0, by0, bx1, by1) in boxes:
        if ax0 - gap < bx1 and bx0 < ax1 + gap and ay0 - gap < by1 and by0 < ay1 + gap:
            return True
    return False


def _place_row(items: List[Component], x0: float, x1: float, *,
               outer_y: float, side: str, edge_inset: float = 1.5):
    """Rozklada zlacza wzdluz krawedzi, ZLICOWANE zewnetrzna krawedzia do brzegu
    (bez zygzakow) i obrocone wejsciem do krawedzi.

    side="top": zewnetrzna (gorna) krawedz ciala na linii outer_y; rotacja 0.
    side="bottom": zewnetrzna (dolna) krawedz na linii outer_y; rotacja 180.
    """
    if not items:
        return
    widths = [_fp(c).body_w * 2 for c in items]
    total = sum(widths)
    n = len(items)
    gap = max((x1 - x0 - total) / (n + 1), 2.0)
    x = x0 + gap
    for c, w in zip(items, widths):
        fp = _fp(c)
        c.x = round(x + w / 2, 2)
        if side == "top":
            c.y = round(outer_y + edge_inset + fp.body_h, 2)   # gorna krawedz ciala zlicowana
            c.rotation = 0
        else:
            c.y = round(outer_y - edge_inset - fp.body_h, 2)   # dolna krawedz ciala zlicowana
            c.rotation = 180
        c.pinned = True
        x += w + gap


def _place_centered_row(items: List[Component], x0: float, x1: float, center_y: float):
    """Rzad komponentow wysrodkowany na wysokosci center_y (NIE przy krawedzi)."""
    if not items:
        return
    widths = [_fp(c).body_w * 2 for c in items]
    gap = max((x1 - x0 - sum(widths)) / (len(items) + 1), 2.0)
    x = x0 + gap
    for c, w in zip(items, widths):
        c.x = round(x + w / 2, 2)
        c.y = round(center_y, 2)
        c.rotation = 0
        c.pinned = True
        x += w + gap


def _pack(items: List[Component], region, obstacles, gap=2.0):
    """Upakowanie polkowe wewnatrz prostokata, omijajac przeszkody."""
    x0, y0, x1, y1 = region
    cx, cy, row_h = x0, y0, 0.0
    for c in items:
        fp = _fp(c)
        w, h = fp.body_w * 2, fp.body_h * 2
        placed = False
        while not placed:
            if cx + w > x1:
                cx = x0
                cy += row_h + gap
                row_h = 0.0
            box = (cx, cy, cx + w, cy + h)
            if cy + h > y1:
                # brak miejsca - i tak postaw (rozszerzy obszar)
                placed = True
            elif _overlaps(box, obstacles, gap):
                cx += w + gap        # przeskocz przeszkode
                continue
            else:
                placed = True
            c.x = round(cx + fp.body_w, 2)
            c.y = round(cy + fp.body_h, 2)
            c.rotation = 0
            obstacles.append((cx, cy, cx + w, cy + h))
            cx += w + gap
            row_h = max(row_h, h)


def place_board(design: Design, frame: Frame, is_top: bool, bottom_side_passives: int = 0):
    design.ensure_nets()
    comps = design.components
    holes = [c for c in comps if _role(c) == "mount"]
    b2b = [c for c in comps if _role(c) == "b2b" or (c.role == "" and c.part.startswith("Header_2x"))]
    io = [c for c in comps if _role(c) == "io" and c not in b2b]
    mains_terms = [c for c in comps if _role(c) == "mains"]   # zaciski 230V -> krawedz
    relays = [c for c in comps if _role(c) == "relay"]        # przekazniki -> wnetrze
    ics = [c for c in comps if _role(c) == "ic"]
    passives = [c for c in comps if _role(c) == "passive"]

    obstacles: List[Tuple] = []

    # otwory montazowe -> wspolne wspolrzedne
    for c, (hx, hy) in zip(holes, frame.holes):
        c.x, c.y, c.pinned, c.rotation = hx, hy, True, 0
        fp = _fp(c)
        obstacles.append((hx - fp.body_w, hy - fp.body_h, hx + fp.body_w, hy + fp.body_h))

    # zlacze board-to-board -> wspolny srodek
    for c in b2b:
        bx, by = frame.b2b
        c.x, c.y, c.pinned, c.rotation = bx, by, True, 0
        fp = _fp(c)
        obstacles.append((bx - fp.body_w, by - fp.body_h, bx + fp.body_w, by + fp.body_h))

    cx0, cy0, cx1, cy1 = frame.central
    interior_bottom = cy1  # gorna granica strefy przekaznikow

    if not is_top:
        # I/O niskonapieciowe -> GORNA krawedz (zlicowane, wejsciem do krawedzi)
        _place_row(io, frame.margin, frame.width - frame.margin,
                   outer_y=0.0, side="top")
        # zaciski 230V -> DOLNA krawedz (dostep kablem), zlicowane
        _place_row(mains_terms, frame.margin, frame.width - frame.margin,
                   outer_y=frame.height, side="bottom")
        # PRZEKAZNIKI -> pas 230V WEWNATRZ, tuz nad zaciskami, NIE przy krawedzi
        if relays:
            rh = max(_fp(c).body_h for c in relays)
            relay_cy = cy1 - rh - 2.0
            _place_centered_row(relays, cx0 + 14, cx1 - 14, relay_cy)
            for c in relays:
                fp = _fp(c)
                obstacles.append((c.x - fp.body_w, c.y - fp.body_h, c.x + fp.body_w, c.y + fp.body_h))
            interior_bottom = relay_cy - rh - 2.0   # logika nad strefa przekaznikow
        for c in io + mains_terms:
            fp = _fp(c)
            obstacles.append((c.x - fp.body_w, c.y - fp.body_h, c.x + fp.body_w, c.y + fp.body_h))

    # opcjonalnie czesc pasywnych od spodu (upchac od spodu)
    if bottom_side_passives:
        for c in passives[:bottom_side_passives]:
            c.side = "bottom"

    # IC + pasywne -> srodek (omijajac otwory, B2B i strefe przekaznikow)
    interior = ics + passives
    _pack(interior, (cx0 + 1, cy0 + 1, cx1 - 1, interior_bottom - 1), obstacles, gap=2.0)

    # wymiary i obrys
    design.board_w = frame.width
    design.board_h = frame.height
    if is_top:
        design.outline = frame.central     # gorna plytka: tylko srodek (wezsza)
    else:
        design.outline = (0.0, 0.0, frame.width, frame.height)


def place_pair(bottom: Design, top: Design, frame: Frame):
    """Rozmieszcza obie plytki we wspolnej ramce: otwory i B2B identyczne,
    gorna wezsza o pasy I/O."""
    place_board(bottom, frame, is_top=False)
    place_board(top, frame, is_top=True, bottom_side_passives=4)
