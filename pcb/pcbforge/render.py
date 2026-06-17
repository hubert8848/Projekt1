"""Podglad graficzny PCB i schematu (SVG/PNG) prosto z modelu - bez KiCada.

render_pcb_svg(design)        -> SVG: obrys plytki, pady, polaczenia, oznaczenia
render_schematic_svg(design)  -> SVG: symbole, piny, etykiety sieci
to_png(svg, path)             -> PNG (jesli dostepne cairosvg/rsvg), inaczej zapis SVG
"""
from __future__ import annotations

import math
import os
from typing import Dict, List, Tuple

from .library import catalog, footprints
from .model import Design, Component

# paleta (ciemne tlo)
BG = "#0f1419"
EDGE = "#d8b24a"
PAD_TOP = "#d6603c"
PAD_BOT = "#3c7fd6"
SILK = "#9fb3c8"
RAT = "#3fae6f"
TXT = "#e6edf3"


def _fp(c: Component):
    part = catalog.get_part(c.part)
    if "header" in part:
        rows, cols = part["header"]
        return footprints.header_fp(rows * cols, rows)
    return footprints.get(part["footprint"])


def _rot(px: float, py: float, deg: float) -> Tuple[float, float]:
    if not deg:
        return px, py
    r = math.radians(deg)
    return px * math.cos(r) - py * math.sin(r), px * math.sin(r) + py * math.cos(r)


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_pcb_svg(design: Design, scale: float = 12.0, show_rats: bool = True) -> str:
    design.ensure_nets()
    w = design.board_w or 80.0
    h = design.board_h or 60.0
    pad = 6.0
    W = (w + 2 * pad) * scale
    H = (h + 2 * pad) * scale

    def X(x): return (x + pad) * scale
    def Y(y): return (y + pad) * scale

    out: List[str] = []
    out.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}" '
               f'viewBox="0 0 {W:.0f} {H:.0f}">')
    out.append(f'<rect width="{W:.0f}" height="{H:.0f}" fill="{BG}"/>')
    # obrys plytki
    out.append(f'<rect x="{X(0):.1f}" y="{Y(0):.1f}" width="{w*scale:.1f}" height="{h*scale:.1f}" '
               f'fill="none" stroke="{EDGE}" stroke-width="2"/>')

    pad_centers: Dict[str, List[Tuple[float, float]]] = {}

    # pady + obrysy + oznaczenia
    for c in design.components:
        if c.x is None or c.y is None:
            continue
        fp = _fp(c)
        col = PAD_TOP if c.side == "top" else PAD_BOT
        # courtyard
        out.append(f'<rect x="{X(c.x-fp.body_w):.1f}" y="{Y(c.y-fp.body_h):.1f}" '
                   f'width="{2*fp.body_w*scale:.1f}" height="{2*fp.body_h*scale:.1f}" '
                   f'fill="none" stroke="{SILK}" stroke-width="0.6" opacity="0.5"/>')
        for p in fp.pads:
            dx, dy = _rot(p.x, p.y, c.rotation)
            ax, ay = c.x + dx, c.y + dy
            net = c.connections.get(p.number, "")
            if net:
                pad_centers.setdefault(net, []).append((ax, ay))
            if p.shape == "circle":
                out.append(f'<circle cx="{X(ax):.1f}" cy="{Y(ay):.1f}" r="{p.w/2*scale:.1f}" fill="{col}"/>')
            else:
                rx = 1.5 if p.shape in ("roundrect", "oval") else 0
                out.append(f'<rect x="{X(ax-p.w/2):.1f}" y="{Y(ay-p.h/2):.1f}" '
                           f'width="{p.w*scale:.1f}" height="{p.h*scale:.1f}" rx="{rx}" fill="{col}"/>')
        out.append(f'<text x="{X(c.x):.1f}" y="{Y(c.y-fp.body_h)-2:.1f}" fill="{TXT}" '
                   f'font-size="{max(8,scale*0.9):.0f}" text-anchor="middle" '
                   f'font-family="monospace">{_esc(c.ref)}</text>')

    # ratsnest (polaczenia) - cienkie linie laczace pady tej samej sieci
    if show_rats:
        for net, pts in pad_centers.items():
            if len(pts) < 2:
                continue
            opacity = 0.25 if net.upper() in ("GND", "GROUND") else 0.5
            for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
                out.append(f'<line x1="{X(x1):.1f}" y1="{Y(y1):.1f}" x2="{X(x2):.1f}" y2="{Y(y2):.1f}" '
                           f'stroke="{RAT}" stroke-width="0.7" opacity="{opacity}"/>')

    out.append(f'<text x="6" y="16" fill="{TXT}" font-size="13" font-family="monospace">'
               f'{_esc(design.name)} — {w:.1f}×{h:.1f} mm — podglad (nie do produkcji)</text>')
    out.append("</svg>")
    return "\n".join(out)


def render_schematic_svg(design: Design, scale: float = 4.0) -> str:
    from .sch_writer import _auto_positions, _dir
    design.ensure_nets()
    grid = _auto_positions(design)
    for c in design.components:
        if c.sx is None:
            c.sx, c.sy = grid[c.ref]
    xs = [c.sx for c in design.components]
    ys = [c.sy for c in design.components]
    minx, maxx = min(xs) - 20, max(xs) + 20
    miny, maxy = min(ys) - 20, max(ys) + 20
    W = (maxx - minx) * scale
    H = (maxy - miny) * scale

    def X(x): return (x - minx) * scale
    def Y(y): return (y - miny) * scale

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}" '
           f'viewBox="0 0 {W:.0f} {H:.0f}">',
           f'<rect width="{W:.0f}" height="{H:.0f}" fill="{BG}"/>']
    for c in design.components:
        sd = catalog.get_part(c.part)["symbol"]
        # symbol: Y lokalne w gore -> arkusz w dol
        for (x1, y1, x2, y2) in sd.rects:
            out.append(f'<rect x="{X(c.sx+min(x1,x2)):.1f}" y="{Y(c.sy-max(y1,y2)):.1f}" '
                       f'width="{abs(x2-x1)*scale:.1f}" height="{abs(y2-y1)*scale:.1f}" '
                       f'fill="none" stroke="{SILK}" stroke-width="1"/>')
        for poly in sd.polylines:
            pts = " ".join(f"{X(c.sx+px):.1f},{Y(c.sy-py):.1f}" for (px, py) in poly)
            out.append(f'<polyline points="{pts}" fill="none" stroke="{SILK}" stroke-width="1"/>')
        for p in sd.pins:
            ex, ey = c.sx + p.cx, c.sy - p.cy
            out.append(f'<circle cx="{X(ex):.1f}" cy="{Y(ey):.1f}" r="1.5" fill="{PAD_TOP}"/>')
            net = c.connections.get(p.number)
            if net:
                dx, dy = _dir(p.angle)
                lx, ly = ex - dx * 2.0, ey - dy * 2.0
                out.append(f'<text x="{X(lx):.1f}" y="{Y(ly):.1f}" fill="{RAT}" '
                           f'font-size="7" font-family="monospace">{_esc(net)}</text>')
        out.append(f'<text x="{X(c.sx):.1f}" y="{Y(c.sy)-8:.1f}" fill="{TXT}" font-size="8" '
                   f'text-anchor="middle" font-family="monospace">{_esc(c.ref)} {_esc(c.value)}</text>')
    out.append("</svg>")
    return "\n".join(out)


def to_png(svg: str, path: str) -> str:
    """Zapisuje PNG (cairosvg lub rsvg-convert); awaryjnie zapisuje SVG obok."""
    svg_path = os.path.splitext(path)[0] + ".svg"
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg)
    try:
        import cairosvg  # type: ignore
        cairosvg.svg2png(bytestring=svg.encode("utf-8"), write_to=path, output_width=1400)
        return path
    except Exception:
        import shutil, subprocess
        if shutil.which("rsvg-convert"):
            subprocess.run(["rsvg-convert", "-w", "1400", "-o", path, svg_path], check=False)
            if os.path.exists(path):
                return path
        return svg_path  # bez konwertera: zwroc SVG
