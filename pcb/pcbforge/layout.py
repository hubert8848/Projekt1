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


def _shelf_height(sizes, width, gap=1.8) -> float:
    """Szacowana wysokosc upakowania polkowego listy (w,h) w danej szerokosci."""
    x = 0.0
    row_h = 0.0
    total = 0.0
    for w, h in sizes:
        if x > 0 and x + w > width:
            total += row_h + gap
            x = 0.0
            row_h = 0.0
        x += w + gap
        row_h = max(row_h, h)
    return total + row_h


def auto_frame(bottom: "Design", top: "Design", margin: float = 3.0, gap: float = 1.8) -> "Frame":
    """Dobiera CIASNA wspolna ramke do zawartosci obu plyt (bez pustego miejsca).
    Szerokosc z najszerszego rzedu krawedziowego; wysokosc z upakowania dolnej."""
    for d in (bottom, top):
        d.ensure_nets()

    def items(d, *roles):
        return [c for c in d.components if _role(c) in roles]

    hole_inset = 4.5
    rows = 2

    def edge_w(cs):
        """Szerokosc krawedzi: najszerszy z `rows` rzedow (zmienne szerokosci)."""
        if not cs:
            return 0.0
        groups = [cs[r::rows] for r in range(rows)]
        rw = max(sum(_fp(c).body_w * 2 + gap for c in g) for g in groups)
        return rw + 2 * margin + 4 * hole_inset + 6

    edge_items = items(bottom, "io", "out", "mains") + items(top, "io", "out", "mains")
    tallest = max((_fp(c).body_h * 2 for c in edge_items), default=8.0)
    io_band = rows * (tallest + gap) + 4.0     # pas na 2 rzedy zlacz

    # szerokosc z LICZBY zlacz (najszersza krawedz, 2 rzedy)
    W = max(edge_w(items(bottom, "io")), edge_w(items(bottom, "out", "mains")),
            edge_w(items(top, "io")), edge_w(items(top, "out", "mains")), 90.0)

    # wysokosc: upakowanie wnetrza dolnej plyty (najgestsza) + strefy
    inter = items(bottom, "ic") + items(bottom, "passive")
    sizes = [(_fp(c).body_w * 2 + gap, _fp(c).body_h * 2 + gap) for c in inter]
    int_w = max(W - 2 * margin - 4 * hole_inset, 40.0)
    int_h = _shelf_height(sizes, int_w, gap)
    relays = items(bottom, "relay")
    rsizes = [(_fp(c).body_w * 2 + gap, _fp(c).body_h * 2 + gap) for c in relays]
    relay_h = _shelf_height(rsizes, int_w, gap) if relays else 0.0
    out_band = io_band if items(bottom, "out", "mains") else 0.0
    # dol: pas I/O (gora) + wnetrze + strefa przekaznikow + pas wyjsc (dol)
    H_bottom = io_band + int_h + relay_h + out_band + 2 * margin + 12.0
    # gora: pas I/O (gora) + wnetrze + wolny pas (dolna krawedz wcieta)
    tinter = items(top, "ic") + items(top, "passive")
    tsizes = [(_fp(c).body_w * 2 + gap, _fp(c).body_h * 2 + gap) for c in tinter]
    tint_h = _shelf_height(tsizes, int_w, gap)
    H_top = 2 * io_band + tint_h + 2 * margin + 10.0
    H = max(H_bottom, H_top)
    return Frame(width=round(W, 1), height=round(H, 1), io_band=round(io_band, 1),
                 hole_inset=hole_inset, margin=margin)


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


def _place_edge(items: List[Component], x0: float, x1: float, outer_y: float,
                side: str, rows: int = 2, gap: float = 2.0, edge_inset: float = 1.5) -> float:
    """Zlacza wzdluz krawedzi w `rows` rzedach (podwojne w pionie) - szerokosc
    wynika z liczby zlacz. Zwraca wysokosc zajetego pasa."""
    if not items:
        return 0.0
    groups = [items[r::rows] for r in range(rows)]   # rownomierny podzial na rzedy
    rpitch = max(_fp(c).body_h * 2 for c in items) + gap
    for r, group in enumerate(groups):
        row_w = sum(_fp(c).body_w * 2 + gap for c in group)
        x = max(x0, (x0 + x1) / 2 - row_w / 2)       # wysrodkuj rzad
        for c in group:
            fp = _fp(c)
            c.x = round(x + fp.body_w, 2)
            if side == "top":
                c.y = round(outer_y + edge_inset + fp.body_h + r * rpitch, 2)
                c.rotation = 0
            else:
                c.y = round(outer_y - edge_inset - fp.body_h - r * rpitch, 2)
                c.rotation = 180
            c.pinned = True
            x += fp.body_w * 2 + gap
    return rows * rpitch + edge_inset


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
    out_terms = [c for c in comps if _role(c) in ("out", "mains")]  # wyjscia -> dolna krawedz
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
    interior_top = cy0
    edge_x0 = frame.margin + 2 * frame.hole_inset + 3   # omin otwory narozne
    edge_x1 = frame.width - frame.margin - 2 * frame.hole_inset - 3

    def _io_obstacles(items):
        for c in items:
            fp = _fp(c)
            obstacles.append((c.x - fp.body_w, c.y - fp.body_h, c.x + fp.body_w, c.y + fp.body_h))

    # WEJSCIA/zasilanie/magistrale -> GORNA krawedz, 2 rzedy (podwojne w pionie)
    io_outer = 0.0 if not is_top else frame.io_band
    io_h = _place_edge(io, edge_x0, edge_x1, io_outer, "top", rows=2)
    _io_obstacles(io)
    if io:
        interior_top = io_outer + io_h + 2.0

    # WYJSCIA (zaciski) -> DOLNA krawedz, 2 rzedy
    out_outer = frame.height if not is_top else (frame.height - frame.io_band)
    out_h = _place_edge(out_terms, edge_x0, edge_x1, out_outer, "bottom", rows=2)
    _io_obstacles(out_terms)
    if out_terms:
        interior_bottom = min(interior_bottom, out_outer - out_h - 2.0)

    # PRZEKAZNIKI -> STREFA 230V WEWNATRZ (kilka rzedow), nad wyjsciami, omija otwory
    if relays:
        hc = 2 * frame.hole_inset + 6
        rsizes = [(_fp(c).body_w * 2 + 1.5, _fp(c).body_h * 2 + 1.5) for c in relays]
        rband_h = _shelf_height(rsizes, (cx1 - cx0) - 2 * hc, 1.5)
        rtop = interior_bottom - rband_h - 1.5
        _pack(relays, (cx0 + hc, rtop, cx1 - hc, interior_bottom), obstacles, gap=1.5)
        interior_bottom = rtop - 2.0

    # opcjonalnie czesc pasywnych od spodu (upchac od spodu)
    if bottom_side_passives:
        for c in passives[:bottom_side_passives]:
            c.side = "bottom"

    # IC + pasywne -> srodek (pod rzedem I/O, nad strefa przekaznikow, omijajac otwory/B2B)
    interior = ics + passives
    _pack(interior, (cx0 + 1, interior_top + 1, cx1 - 1, interior_bottom - 1), obstacles, gap=1.5)

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
