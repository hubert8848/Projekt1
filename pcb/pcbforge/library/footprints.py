"""Generatory footprintow (proceduralne).

Kazdy footprint to lista padow + kontur (silk/courtyard). Pady maja numery
zgodne z numerami pinow w symbolu, dzieki czemu netlista PCB jest spojna.
Wspolrzedne w mm, srodek footprintu = (0,0).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class Pad:
    number: str
    x: float
    y: float
    w: float
    h: float
    shape: str = "roundrect"        # rect/roundrect/circle/oval
    pad_type: str = "smd"           # smd / thru_hole
    drill: float = 0.0
    rot: float = 0.0

    @property
    def layers(self) -> Tuple[str, ...]:
        if self.pad_type == "thru_hole":
            return ("*.Cu", "*.Mask")
        return ("F.Cu", "F.Paste", "F.Mask")


@dataclass
class Footprint:
    name: str
    description: str
    pads: List[Pad] = field(default_factory=list)
    # kontur silkscreen/courtyard jako prostokat (polowa szerokosci/wysokosci)
    body_w: float = 2.0
    body_h: float = 2.0
    smd: bool = True

    def pad_numbers(self) -> List[str]:
        return [p.number for p in self.pads]


# ---------------------------------------------------------------------------
# Generatory
# ---------------------------------------------------------------------------
_CHIP = {
    # nazwa: (dlugosc, szer, pad_w, pad_h, rozstaw_srodkow)
    "0402": (1.0, 0.5, 0.6, 0.7, 0.9),
    "0603": (1.6, 0.8, 0.9, 1.0, 1.5),
    "0805": (2.0, 1.25, 1.15, 1.4, 1.9),
    "1206": (3.2, 1.6, 1.4, 1.75, 3.0),
}


def chip(size: str = "0805", prefix: str = "R") -> Footprint:
    L, W, pw, ph, gap = _CHIP[size]
    fp = Footprint(f"{prefix}_{size}", f"{prefix} chip {size}", body_w=L / 2 + 0.2, body_h=W / 2 + 0.2)
    fp.pads.append(Pad("1", -gap / 2, 0, pw, ph, "roundrect"))
    fp.pads.append(Pad("2", gap / 2, 0, pw, ph, "roundrect"))
    return fp


def led_chip(size: str = "0805") -> Footprint:
    fp = chip(size, prefix="LED")
    # pin 1 = anoda, 2 = katoda (konwencja); kontur jak chip
    return fp


def diode_chip(size: str = "0805") -> Footprint:
    return chip(size, prefix="D")


def sot223() -> Footprint:
    """SOT-223 (np. AMS1117). Pady 1,2,3 + tab(4)."""
    fp = Footprint("SOT-223", "SOT-223 (regulator LDO)", body_w=3.5, body_h=3.3, smd=True)
    pitch = 2.3
    # trzy pady dolne
    for i, num in enumerate(["1", "2", "3"]):
        fp.pads.append(Pad(num, (i - 1) * pitch, 3.0, 1.2, 2.0, "roundrect"))
    # tab gorny (pad 4 = Vout)
    fp.pads.append(Pad("4", 0, -3.0, 3.8, 2.0, "roundrect"))
    return fp


def header(pins: int, rows: int = 1, pitch: float = 2.54, name: str | None = None) -> Footprint:
    """Goldpiny THT, numeracja 1..N (rzedami)."""
    cols = pins // rows
    name = name or f"PinHeader_{rows}x{cols:02d}_P{pitch:.2f}mm"
    fp = Footprint(name, f"Pin header {rows}x{cols}", smd=False,
                   body_w=cols * pitch / 2 + 0.5, body_h=rows * pitch / 2 + 0.5)
    n = 1
    x0 = -(cols - 1) * pitch / 2
    y0 = -(rows - 1) * pitch / 2
    for r in range(rows):
        for c in range(cols):
            shape = "rect" if n == 1 else "circle"
            pad = Pad(str(n), x0 + c * pitch, y0 + r * pitch, 1.7, 1.7, shape,
                      pad_type="thru_hole", drill=1.0)
            fp.pads.append(pad)
            n += 1
    return fp


def micro_usb() -> Footprint:
    """Uproszczony Micro-USB typ B: 5 padow SMD (1..5) + 2 kotwy THT."""
    fp = Footprint("USB_Micro-B", "Micro USB typ B (uproszczony)", body_w=4.0, body_h=3.0)
    pitch = 0.65
    names = ["1", "2", "3", "4", "5"]  # VBUS D- D+ ID GND
    x0 = -(len(names) - 1) * pitch / 2
    for i, num in enumerate(names):
        fp.pads.append(Pad(num, x0 + i * pitch, 1.8, 0.4, 1.35, "rect"))
    # kotwy mechaniczne (shield) - numer "0" => brak sieci
    for x in (-3.5, 3.5):
        fp.pads.append(Pad("MP", x, 0.0, 1.0, 1.5, "rect"))
    return fp


def esp32_wroom32() -> Footprint:
    """Modul ESP32-WROOM-32: 38 padow kastelowanych.

    Uklad: lewa krawedz 1..15, dolna 16..23, prawa 24..38 (w gore).
    Wymiary ~18 x 25.5 mm, raster 1.27 mm.
    """
    fp = Footprint("ESP32-WROOM-32", "Modul ESP32-WROOM-32 (38 padow)",
                   body_w=9.0, body_h=12.75, smd=True)
    pitch = 1.27
    half_w = 9.0       # +-9 mm => 18 mm szerokosci
    half_h = 12.75     # 25.5 mm wysokosci
    pad_w, pad_h = 0.9, 1.5

    # lewa krawedz: pady 1..15, od dolu do gory (1 na dole)
    n_left = 15
    span = (n_left - 1) * pitch
    y_bottom = half_h - 1.0  # zostaw margines na antene u gory
    for i in range(n_left):
        y = y_bottom - i * pitch
        fp.pads.append(Pad(str(i + 1), -half_w, y, pad_w, pad_h, "roundrect", rot=0))

    # dolna krawedz: pady 16..23 (8), od lewej do prawej
    n_bot = 8
    span_b = (n_bot - 1) * pitch
    x0 = -span_b / 2
    for i in range(n_bot):
        x = x0 + i * pitch
        fp.pads.append(Pad(str(16 + i), x, half_h, pad_h, pad_w, "roundrect"))

    # prawa krawedz: pady 24..38 (15), od dolu do gory
    n_right = 15
    for i in range(n_right):
        y = y_bottom - i * pitch
        fp.pads.append(Pad(str(24 + i), half_w, y, pad_w, pad_h, "roundrect"))

    return fp


def sw_push() -> Footprint:
    """Przycisk tact 6mm THT, 4 piny (pary 1-2 i 3-4 zwarte)."""
    fp = Footprint("SW_Push_6mm", "Tact switch 6mm", smd=False, body_w=3.0, body_h=3.0)
    coords = {"1": (-3.25, -2.25), "2": (-3.25, 2.25),
              "3": (3.25, -2.25), "4": (3.25, 2.25)}
    for num, (x, y) in coords.items():
        fp.pads.append(Pad(num, x, y, 1.6, 1.6, "circle", pad_type="thru_hole", drill=1.0))
    return fp


def cap_polarized(size: str = "1206") -> Footprint:
    fp = chip(size, prefix="CP")
    return fp


# Rejestr footprintow dostepnych po nazwie -> funkcja budujaca
REGISTRY = {
    "R_0402": lambda: chip("0402", "R"),
    "R_0603": lambda: chip("0603", "R"),
    "R_0805": lambda: chip("0805", "R"),
    "R_1206": lambda: chip("1206", "R"),
    "C_0402": lambda: chip("0402", "C"),
    "C_0603": lambda: chip("0603", "C"),
    "C_0805": lambda: chip("0805", "C"),
    "C_1206": lambda: chip("1206", "C"),
    "CP_1206": lambda: cap_polarized("1206"),
    "LED_0805": lambda: led_chip("0805"),
    "D_0805": lambda: diode_chip("0805"),
    "SOT-223": sot223,
    "USB_Micro-B": micro_usb,
    "ESP32-WROOM-32": esp32_wroom32,
    "SW_Push_6mm": sw_push,
}


def get(name: str) -> Footprint:
    if name not in REGISTRY:
        raise KeyError(f"Nieznany footprint: {name}. Dostepne: {sorted(REGISTRY)}")
    return REGISTRY[name]()


def header_fp(pins: int, rows: int = 1, pitch: float = 2.54) -> Footprint:
    return header(pins, rows, pitch)
