"""Generator pliku schematu .kicad_sch (format KiCad 7, version 20230121).

Strategia polaczen: kazdy uzyty pin dostaje krotki odcinek (wire) i etykiete
globalna z nazwa sieci. Dzieki temu polaczenia sa po nazwie -> netlista jest
jednoznaczna, a ERC czyste (zasilanie domkniete przez PWR_FLAG).
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

from .library import catalog
from .library.symbols import SymbolDef, SymPin, power_flag
from .model import Design, Component, new_uuid
from .sexpr import S, Sym

SCH_VERSION = 20230121


def _dir(angle: int) -> Tuple[float, float]:
    """Wektor kierunku pinu w ukladzie arkusza (Y w dol)."""
    return {0: (1.0, 0.0), 90: (0.0, -1.0), 180: (-1.0, 0.0), 270: (0.0, 1.0)}[angle % 360]


def _pin_sheet_pos(comp: Component, p: SymPin) -> Tuple[float, float]:
    # rotacja 0, bez odbicia: lokalne Y w gore -> arkusz Y w dol
    return (comp.sx + p.cx, comp.sy - p.cy)


def _effects(size=1.27, hide=False, justify=None):
    e = S("effects", S("font", S("size", size, size)))
    if justify:
        e.add(S("justify", Sym(justify)))
    if hide:
        e.add(S("hide", Sym("yes")))
    return e


# ---------------------------------------------------------------------------
# Renderowanie definicji symbolu do sekcji lib_symbols
# ---------------------------------------------------------------------------
def _render_lib_symbol(libid: str, sd: SymbolDef) -> S:
    name = libid.split(":", 1)[-1]
    top = S("symbol", libid)
    top.add(S("pin_names", S("offset", 0.254),
              *([Sym("hide")] if sd.pin_names_hidden else [])))
    if sd.pin_numbers_hidden:
        top.add(S("pin_numbers", Sym("hide")))
    top.add(S("exclude_from_sim", Sym("no")))
    top.add(S("in_bom", Sym("yes")), S("on_board", Sym("yes")))
    if sd.power_symbol:
        top.add(S("power"))
    # property naglowkowe
    top.add(S("property", "Reference", sd.ref_prefix, S("at", 0, 0, 0), _effects()))
    top.add(S("property", "Value", name, S("at", 0, -2.54, 0), _effects()))
    top.add(S("property", "Footprint", "", S("at", 0, 0, 0), _effects(hide=True)))
    top.add(S("property", "Datasheet", "", S("at", 0, 0, 0), _effects(hide=True)))

    # grafika (unit _0_1)
    g = S("symbol", f"{name}_0_1")
    for (x1, y1, x2, y2) in sd.rects:
        g.add(S("rectangle", S("start", x1, y1), S("end", x2, y2),
                S("stroke", S("width", 0.254), S("type", Sym("default"))),
                S("fill", S("type", Sym("none")))))
    for poly in sd.polylines:
        pts = S("pts", *[S("xy", x, y) for (x, y) in poly])
        g.add(S("polyline", pts,
                S("stroke", S("width", 0.254), S("type", Sym("default"))),
                S("fill", S("type", Sym("none")))))
    for (cx, cy, r) in sd.circles:
        g.add(S("circle", S("center", cx, cy), S("radius", r),
               S("stroke", S("width", 0.254), S("type", Sym("default"))),
               S("fill", S("type", Sym("none")))))
    top.add(g)

    # piny (unit _1_1)
    pg = S("symbol", f"{name}_1_1")
    for p in sd.pins:
        pin = S("pin", Sym(p.etype), Sym("line"),
                S("at", p.cx, p.cy, p.angle),
                S("length", p.length),
                S("name", p.name, _effects()),
                S("number", p.number, _effects()))
        pg.add(pin)
    top.add(pg)
    return top


# ---------------------------------------------------------------------------
# Glowny generator
# ---------------------------------------------------------------------------
def build_schematic(design: Design, project_name: str) -> str:
    design.ensure_nets()
    root = S("kicad_sch")
    root.add(S("version", SCH_VERSION))
    root.add(S("generator", Sym("eeschema")))
    root.add(S("uuid", design.uuid))
    root.add(S("paper", "A4"))

    # --- lib_symbols: unikalne symbole uzyte w projekcie + PWR_FLAG/GND ---
    lib = S("lib_symbols")
    used: Dict[str, SymbolDef] = {}
    for c in design.components:
        part = catalog.get_part(c.part)
        sd = part["symbol"]
        used.setdefault(sd.lib_id, sd)
    used["pcbforge:PWR_FLAG"] = _pwr_flag_symbol()
    for libid, sd in used.items():
        lib.add(_render_lib_symbol(libid, sd))
    root.add(lib)

    # --- instancje symboli ---
    auto_grid = _auto_positions(design)
    for c in design.components:
        if c.sx is None or c.sy is None:
            c.sx, c.sy = auto_grid[c.ref]
        part = catalog.get_part(c.part)
        sd: SymbolDef = part["symbol"]
        root.add(_render_instance(c, sd, project_name, design.uuid))
        # etykiety + odcinki na pinach
        for p in sd.pins:
            net = c.connections.get(p.number)
            if not net:
                continue
            root.add(*_pin_label(c, p, net))

    # --- PWR_FLAG na sieciach zasilania/masy (czyste ERC) ---
    flagged = set()
    py = 25.0
    for name, net in sorted(design.nets.items()):
        if (net.is_power or net.is_ground) and name not in flagged:
            root.add(*_pwr_flag_instance(name, 250.0, py, project_name, design.uuid))
            py += 12.0
            flagged.add(name)

    return root.render(indent=2) + "\n"


def _render_instance(c: Component, sd: SymbolDef, project: str, root_uuid: str) -> S:
    inst = S("symbol", S("lib_id", sd.lib_id), S("at", c.sx, c.sy, 0), S("unit", 1))
    inst.add(S("exclude_from_sim", Sym("no")), S("in_bom", Sym("yes")),
             S("on_board", Sym("yes")), S("dnp", Sym("no")))
    inst.add(S("uuid", c.sch_uuid))
    inst.add(S("property", "Reference", c.ref, S("at", c.sx + 2.54, c.sy - 5.0, 0),
              _effects(justify="left")))
    inst.add(S("property", "Value", c.value, S("at", c.sx + 2.54, c.sy + 5.0, 0),
              _effects(justify="left")))
    inst.add(S("property", "Footprint", f"pcbforge:{c.footprint}",
              S("at", c.sx, c.sy, 0), _effects(hide=True)))
    inst.add(S("property", "Datasheet", "", S("at", c.sx, c.sy, 0), _effects(hide=True)))
    for p in sd.pins:
        inst.add(S("pin", p.number, S("uuid", new_uuid())))
    inst.add(S("instances", S("project", project,
              S("path", f"/{root_uuid}", S("reference", c.ref), S("unit", 1)))))
    return inst


def _pin_label(c: Component, p: SymPin, net: str) -> List[S]:
    px, py = _pin_sheet_pos(c, p)
    dx, dy = _dir(p.angle)
    # stub na zewnatrz (przeciwnie do kierunku ciala)
    ex, ey = px - dx * 2.54, py - dy * 2.54
    wire = S("wire", S("pts", S("xy", round(px, 4), round(py, 4)),
                       S("xy", round(ex, 4), round(ey, 4))),
             S("stroke", S("width", 0), S("type", Sym("default"))),
             S("uuid", new_uuid()))
    # kat etykiety: tekst czytany na zewnatrz
    lang = 0
    just = "left"
    if dx < 0:        # cialo po lewej -> stub w prawo
        lang, just = 0, "left"
    elif dx > 0:      # cialo po prawej -> stub w lewo
        lang, just = 180, "right"
    elif dy < 0:      # cialo u gory -> stub w dol
        lang, just = 270, "left"
    else:
        lang, just = 90, "left"
    label = S("global_label", net, S("shape", Sym("bidirectional")),
              S("at", round(ex, 4), round(ey, 4), lang),
              S("fields_autoplaced"),
              _effects(justify=just),
              S("uuid", new_uuid()))
    return [wire, label]


# ---------------------------------------------------------------------------
# PWR_FLAG
# ---------------------------------------------------------------------------
def _pwr_flag_symbol() -> SymbolDef:
    sd = SymbolDef("pcbforge:PWR_FLAG", "#FLG", power_symbol=True,
                   pin_names_hidden=True, pin_numbers_hidden=True)
    sd.pins.append(SymPin("1", "pwr", "power_out", 0, 0, 90, length=0, side="right"))
    sd.polylines.append([(0, 0), (0, 1.27), (-1.016, 1.905), (0, 2.54),
                         (1.016, 1.905), (0, 1.27)])
    return sd


def _pwr_flag_instance(net: str, x: float, y: float, project: str, root_uuid: str) -> List[S]:
    u = new_uuid()
    inst = S("symbol", S("lib_id", "pcbforge:PWR_FLAG"), S("at", x, y, 0), S("unit", 1))
    inst.add(S("exclude_from_sim", Sym("no")), S("in_bom", Sym("no")),
             S("on_board", Sym("yes")), S("dnp", Sym("no")))
    inst.add(S("uuid", u))
    inst.add(S("property", "Reference", "#FLG?", S("at", x, y - 3.0, 0), _effects(hide=True)))
    inst.add(S("property", "Value", "PWR_FLAG", S("at", x, y + 3.0, 0), _effects()))
    inst.add(S("property", "Footprint", "", S("at", x, y, 0), _effects(hide=True)))
    inst.add(S("property", "Datasheet", "", S("at", x, y, 0), _effects(hide=True)))
    inst.add(S("pin", "1", S("uuid", new_uuid())))
    inst.add(S("instances", S("project", project,
              S("path", f"/{root_uuid}", S("reference", "#FLG?"), S("unit", 1)))))
    # etykieta globalna na pinie flagi (pin w gore: koniec na (x, y-0? ) -> at y)
    label = S("global_label", net, S("shape", Sym("bidirectional")),
              S("at", x, y, 0), S("fields_autoplaced"), _effects(),
              S("uuid", new_uuid()))
    return [inst, label]


def _auto_positions(design: Design) -> Dict[str, Tuple[float, float]]:
    """Prosta siatka rozmieszczenia na arkuszu A4 (do czytelnosci)."""
    pos = {}
    x0, y0 = 40.0, 40.0
    dx, dy = 50.0, 45.0
    cols = 4
    i = 0
    for c in design.components:
        col = i % cols
        row = i // cols
        pos[c.ref] = (x0 + col * dx, y0 + row * dy)
        i += 1
    return pos
