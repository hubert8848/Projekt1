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
    holes_override: Optional[List[Tuple[float, float]]] = None  # wspolne otwory (para plyt)
    b2b_override: Optional[Tuple[float, float]] = None          # wspolne B2B

    @property
    def central(self) -> Tuple[float, float, float, float]:
        """Obszar srodkowy (obrys gornej plytki)."""
        return (self.margin, self.io_band, self.width - self.margin, self.height - self.io_band)

    @property
    def holes(self) -> List[Tuple[float, float]]:
        if self.holes_override:
            return self.holes_override
        x0, y0, x1, y1 = self.central
        i = self.hole_inset
        return [(x0 + i, y0 + i), (x1 - i, y0 + i), (x1 - i, y1 - i), (x0 + i, y1 - i)]

    @property
    def b2b(self) -> Tuple[float, float]:
        return self.b2b_override or (self.width / 2, self.height / 2)


def _shelf_height(sizes, width, gap=1.8) -> float:
    """Szacowana wysokosc upakowania polkowego (sortowanie po wysokosci -> ciasno)."""
    x = 0.0
    row_h = 0.0
    total = 0.0
    for w, h in sorted(sizes, key=lambda s: -s[1]):
        if x > 0 and x + w > width:
            total += row_h + gap
            x = 0.0
            row_h = 0.0
        x += w + gap
        row_h = max(row_h, h)
    return total + row_h


def _frame_dims(bottom: "Design", top: "Design", margin=3.0, gap=1.8):
    """Liczy wspolna szerokosc W oraz CIASNE, NIEZALEZNE wysokosci obu plyt."""
    for d in (bottom, top):
        d.ensure_nets()
    hole_inset = 4.5
    io_band = 12.0

    def items(d, *roles):
        return [c for c in d.components if _role(c) in roles]

    def board_w(d):
        t, b = _split_balanced(items(d, "io", "out", "mains"))
        half = max(sum(_fp(c).body_w * 2 + gap for c in t),
                   sum(_fp(c).body_w * 2 + gap for c in b), 40.0)
        return half + 2 * margin + 4 * hole_inset + 6

    W = max(board_w(bottom), board_w(top), 90.0)
    int_w = max(W - 2 * margin - 2.0, 40.0)

    def band_h(cs):
        return (max((_fp(c).body_h * 2 for c in cs), default=0.0) + 2.0) if cs else 0.0

    def packed_h(cs):
        return _shelf_height([(_fp(c).body_w * 2 + gap, _fp(c).body_h * 2 + gap) for c in cs],
                             int_w, gap) if cs else 0.0

    def board_h(d, is_top):
        et, eb = _split_balanced(items(d, "io", "out", "mains"))
        inner = packed_h(items(d, "ic") + items(d, "passive") + items(d, "relay"))
        base = band_h(et) + inner + band_h(eb) + 2 * margin + 4.0
        return base + (2 * io_band if is_top else 0.0)   # gorna plyta wcieta o io_band

    Hb = board_h(bottom, False)
    Ht = board_h(top, True)
    return round(W, 1), round(Hb, 1), round(Ht, 1), io_band, hole_inset, margin


def auto_frame(bottom: "Design", top: "Design", margin: float = 3.0, gap: float = 1.8) -> "Frame":
    """Jedna wspolna ramka (max wysokosc) - dla prostych par o podobnym rozmiarze."""
    W, Hb, Ht, io_band, hole_inset, margin = _frame_dims(bottom, top, margin, gap)
    return Frame(width=W, height=max(Hb, Ht), io_band=io_band,
                 hole_inset=hole_inset, margin=margin)


def auto_layout(bottom: "Design", top: "Design", margin: float = 3.0, gap: float = 1.3) -> "Frame":
    """Rozmieszcza pare plyt z NIEZALEZNYMI wysokosciami (minimalny rozmiar kazdej),
    ale otworami i zlaczem B2B w IDENTYCZNYCH wspolrzednych (skladanie 1:1)."""
    W, Hb, Ht, io_band, hole_inset, margin = _frame_dims(bottom, top, margin, gap)
    hmin = min(Hb, Ht)
    i = hole_inset
    # wspolne otwory w obszarze obecnym na OBU plytach + wspolne B2B
    shared_holes = [(margin + i, io_band + i), (W - margin - i, io_band + i),
                    (W - margin - i, hmin - io_band - i), (margin + i, hmin - io_band - i)]
    shared_b2b = (W / 2, hmin / 2)
    fb = Frame(W, Hb, io_band, hole_inset, margin, shared_holes, shared_b2b)
    ft = Frame(W, Ht, io_band, hole_inset, margin, shared_holes, shared_b2b)
    place_board(bottom, fb, is_top=False)
    place_board(top, ft, is_top=True, bottom_side_passives=6)
    return fb


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


def _split_balanced(items: List[Component]):
    """Dzieli zlacza na dwie krawedzie. Wysokie zlacza (np. podwojne RJ45) trafiaja
    na JEDNA krawedz - zeby nie bylo dwoch wysokich pasow (niska plytka)."""
    if not items:
        return [], []
    hs = sorted(set(round(_fp(c).body_h * 2, 1) for c in items))
    if len(hs) > 1 and hs[-1] >= hs[0] * 1.6:
        thr = (hs[0] + hs[-1]) / 2
        tall = [c for c in items if _fp(c).body_h * 2 >= thr]
        short = [c for c in items if _fp(c).body_h * 2 < thr]
        return tall, short          # wysokie -> gora, niskie -> dol
    # podobne wysokosci: rownowaz szerokosc
    total = sum(_fp(c).body_w * 2 for c in items)
    top, bottom, acc = [], [], 0.0
    for c in items:
        w = _fp(c).body_w * 2
        if acc + w / 2 <= total / 2 or not top:
            top.append(c)
            acc += w
        else:
            bottom.append(c)
    return top, bottom


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
    """Upakowanie polkowe wewnatrz prostokata, omijajac przeszkody.
    Sortowanie po wysokosci malejaco -> wiersze o zblizonej wysokosci (ciasno)."""
    x0, y0, x1, y1 = region
    cx, cy, row_h = x0, y0, 0.0
    for c in sorted(items, key=lambda c: -_fp(c).body_h * 2):
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

    # ZLACZA -> rozlozone na GORNA i DOLNA krawedz (1 rzad przy krawedzi), gesto
    e_top, e_bot = _split_balanced(io + out_terms)
    top_outer = 0.0 if not is_top else frame.io_band
    bot_outer = frame.height if not is_top else (frame.height - frame.io_band)
    ht = _place_edge(e_top, edge_x0, edge_x1, top_outer, "top", rows=1)
    hb = _place_edge(e_bot, edge_x0, edge_x1, bot_outer, "bottom", rows=1)
    _io_obstacles(e_top + e_bot)
    # wnetrze od RZECZYWISTEJ wysokosci zlacz (dol uzywa pelnej plyty, gora - srodka)
    interior_top = (top_outer + ht + 2.0) if e_top else (cy0 if is_top else frame.margin)
    interior_bottom = (bot_outer - hb - 2.0) if e_bot else (cy1 if is_top else frame.height - frame.margin)


    # opcjonalnie czesc pasywnych od spodu (upchac od spodu)
    if bottom_side_passives:
        for c in passives[:bottom_side_passives]:
            c.side = "bottom"

    # IC + pasywne + PRZEKAZNIKI -> jeden ciasny blok wnetrza (sortowany po wysokosci,
    # wiec przekazniki same sie zgrupuja); omija otwory/B2B. Bez luk miedzy strefami.
    interior = ics + passives + relays
    int_x0 = cx0 + 1 if is_top else frame.margin
    int_x1 = cx1 - 1 if is_top else frame.width - frame.margin
    _pack(interior, (int_x0, interior_top + 1, int_x1, interior_bottom - 1), obstacles, gap=1.3)

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
