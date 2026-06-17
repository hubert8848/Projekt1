"""Generatory symboli schematu.

Symbol = grafika (prostokaty/linie) + piny z dokladnym punktem przylaczenia.
Punkt przylaczenia (cx,cy) sluzy do umieszczania etykiet sieci dokladnie na
koncu pinu, dzieki czemu polaczenia sa po nazwie i ERC jest czyste.
Wspolrzedne w mm, os Y schematu KiCada rosnie w DOL.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class SymPin:
    number: str
    name: str
    etype: str          # passive/power_in/power_out/input/output/bidirectional/no_connect/unspecified
    cx: float           # punkt przylaczenia (koniec pinu) wzgledem srodka symbolu
    cy: float
    angle: int          # kierunek pinu: 0=prawo,90=gora,180=lewo,270=dol
    length: float = 2.54
    side: str = "left"  # po ktorej stronie etykieta ma byc justowana


@dataclass
class SymbolDef:
    lib_id: str                 # np. "pcbforge:R"
    ref_prefix: str
    pins: List[SymPin] = field(default_factory=list)
    rects: List[Tuple[float, float, float, float]] = field(default_factory=list)
    polylines: List[List[Tuple[float, float]]] = field(default_factory=list)
    circles: List[Tuple[float, float, float]] = field(default_factory=list)
    pin_names_hidden: bool = False
    pin_numbers_hidden: bool = False
    power_symbol: bool = False


def two_pin_vertical(lib_id, ref_prefix, p1="~", p2="~",
                     t1="passive", t2="passive", body="rect") -> SymbolDef:
    s = SymbolDef(lib_id, ref_prefix, pin_names_hidden=True)
    s.pins.append(SymPin("1", p1, t1, 0, 3.81, 270, side="right"))
    s.pins.append(SymPin("2", p2, t2, 0, -3.81, 90, side="right"))
    if body == "rect":
        s.rects.append((-1.016, -2.54, 1.016, 2.54))
    elif body == "led":
        # trojkat + kreska (dioda)
        s.polylines.append([(-1.27, -1.27), (-1.27, 1.27), (1.27, 0), (-1.27, -1.27)])
        s.polylines.append([(1.27, -1.27), (1.27, 1.27)])
        # strzalki swiatla
        s.polylines.append([(1.6, -1.8), (2.6, -2.8)])
        s.polylines.append([(2.0, -1.4), (3.0, -2.4)])
    elif body == "diode":
        s.polylines.append([(-1.27, -1.27), (-1.27, 1.27), (1.27, 0), (-1.27, -1.27)])
        s.polylines.append([(1.27, -1.27), (1.27, 1.27)])
    elif body == "cap":
        s.polylines.append([(-1.27, 0.5), (1.27, 0.5)])
        s.polylines.append([(-1.27, -0.5), (1.27, -0.5)])
        s.pins[0].cy = 2.54
        s.pins[1].cy = -2.54
    elif body == "cap_pol":
        s.polylines.append([(-1.27, 0.5), (1.27, 0.5)])
        s.polylines.append([(-1.0, 1.5), (1.0, 1.5)])  # luk uproszczony
        s.pins[0].cy = 2.54
        s.pins[1].cy = -2.54
    return s


def power_flag(name: str, is_gnd: bool = False) -> SymbolDef:
    s = SymbolDef(f"pcbforge:{name}", "#PWR", power_symbol=True,
                  pin_names_hidden=True, pin_numbers_hidden=True)
    etype = "power_in"
    if is_gnd:
        s.pins.append(SymPin("1", name, etype, 0, 0, 90, length=0, side="right"))
        s.polylines.append([(0, 0), (0, -1.27)])
        s.polylines.append([(-1.27, -1.27), (1.27, -1.27)])
        s.polylines.append([(-0.762, -1.778), (0.762, -1.778)])
        s.polylines.append([(-0.254, -2.286), (0.254, -2.286)])
    else:
        s.pins.append(SymPin("1", name, etype, 0, 0, 270, length=0, side="right"))
        s.polylines.append([(0, 0), (0, 1.27)])
        s.polylines.append([(-0.762, 1.27), (0.762, 1.27), (0, 2.032), (-0.762, 1.27)])
    return s


def box(lib_id, ref_prefix, pins, width=None, label_pins=True) -> SymbolDef:
    """Symbol pudelkowy. `pins` to lista krotek (number, name, etype, side)
    gdzie side in {left,right}. Piny rozkladane od gory w dol po obu stronach.
    """
    s = SymbolDef(lib_id, ref_prefix)
    left = [p for p in pins if p[3] == "left"]
    right = [p for p in pins if p[3] == "right"]
    rows = max(len(left), len(right))
    pitch = 2.54
    height = (rows + 1) * pitch
    w = width or 25.4
    top = height / 2
    # prostokat ciala
    s.rects.append((-w / 2, -top, w / 2, top))
    plen = 3.81
    for i, (num, name, etype, _side) in enumerate(left):
        y = top - (i + 1) * pitch
        s.pins.append(SymPin(num, name, etype, -w / 2 - plen, y, 0, plen, side="left"))
    for i, (num, name, etype, _side) in enumerate(right):
        y = top - (i + 1) * pitch
        s.pins.append(SymPin(num, name, etype, w / 2 + plen, y, 180, plen, side="right"))
    return s
