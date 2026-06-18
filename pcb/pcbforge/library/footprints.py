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


# ---------------------------------------------------------------------------
# Obudowy IC (SMD)
# ---------------------------------------------------------------------------
def soic(pins: int, pitch: float = 1.27, body_w: float = 3.9, span: float = 5.2) -> Footprint:
    """SOIC: pady po dwoch stronach, pin1 gora-lewo, przeciwnie do zegara."""
    fp = Footprint(f"SOIC-{pins}", f"SOIC-{pins} ({pitch}mm)",
                   body_w=body_w / 2 + 0.3, body_h=(pins // 2) * pitch / 2 + 0.6)
    per = pins // 2
    y0 = -(per - 1) * pitch / 2
    pw, ph = 0.6, 1.55
    for i in range(per):  # lewa kolumna 1..per (gora->dol)
        fp.pads.append(Pad(str(i + 1), -span / 2, y0 + i * pitch, pw, ph, "roundrect"))
    for i in range(per):  # prawa kolumna (dol->gora)
        fp.pads.append(Pad(str(pins - i), span / 2, y0 + i * pitch, pw, ph, "roundrect"))
    return fp


def sot23(pins: int = 3) -> Footprint:
    """SOT-23-3 / -5 / -6."""
    fp = Footprint(f"SOT-23-{pins}", f"SOT-23-{pins}", body_w=1.6, body_h=1.6)
    pitch = 0.95
    pw, ph = 0.6, 1.1
    bot = (pins + 1) // 2
    top = pins // 2
    x0 = -(bot - 1) * pitch / 2
    n = 1
    for i in range(bot):  # dolny rzad
        fp.pads.append(Pad(str(n), x0 + i * pitch, 1.0, pw, ph, "roundrect"))
        n += 1
    x0t = -(top - 1) * pitch / 2
    for i in range(top):  # gorny rzad (numeracja od prawej)
        fp.pads.append(Pad(str(pins - i), x0t + i * pitch, -1.0, pw, ph, "roundrect"))
    return fp


def to92() -> Footprint:
    """TO-92 (3 piny THT, raster 2.54, ukladane w linii)."""
    fp = Footprint("TO-92", "TO-92", smd=False, body_w=2.5, body_h=2.5)
    for i, num in enumerate(["1", "2", "3"]):
        fp.pads.append(Pad(num, (i - 1) * 2.54, 0, 1.6, 1.6,
                           "rect" if num == "1" else "circle",
                           pad_type="thru_hole", drill=0.8))
    return fp


# ---------------------------------------------------------------------------
# Diody / cewki / bezpieczniki / kwarce (SMD)
# ---------------------------------------------------------------------------
def diode_2pin(name: str, length: float, width: float, pw: float, ph: float, gap: float) -> Footprint:
    fp = Footprint(name, name, body_w=length / 2 + 0.2, body_h=width / 2 + 0.2)
    fp.pads.append(Pad("1", -gap / 2, 0, pw, ph, "roundrect"))  # 1 = anoda
    fp.pads.append(Pad("2", gap / 2, 0, pw, ph, "roundrect"))   # 2 = katoda
    return fp


def inductor_smd(size: str = "1210") -> Footprint:
    return chip(size if size in _CHIP else "1206", prefix="L")


def power_inductor() -> Footprint:
    """Cewka mocy ~6x6mm (buck)."""
    fp = Footprint("L_6x6", "Cewka mocy 6x6mm", body_w=3.4, body_h=3.4)
    fp.pads.append(Pad("1", -2.6, 0, 1.6, 4.2, "rect"))
    fp.pads.append(Pad("2", 2.6, 0, 1.6, 4.2, "rect"))
    return fp


def fuse_smd(size: str = "1206") -> Footprint:
    return chip(size, prefix="F")


def crystal_smd() -> Footprint:
    """Kwarc 4-pad 3.2x2.5mm (2 aktywne: 1 i 3)."""
    fp = Footprint("Crystal_SMD_3225", "Kwarc 3.2x2.5mm", body_w=1.8, body_h=1.4)
    coords = {"1": (-1.1, 0.85), "2": (1.1, 0.85), "3": (1.1, -0.85), "4": (-1.1, -0.85)}
    for num, (x, y) in coords.items():
        fp.pads.append(Pad(num, x, y, 1.2, 1.0, "roundrect"))
    return fp


# ---------------------------------------------------------------------------
# Zlacza
# ---------------------------------------------------------------------------
def rj45_8p8c() -> Footprint:
    """RJ45 8P8C THT (bez magnetyki). 8 pinow w 2 rzedach + 2 ekrany/kotwy."""
    fp = Footprint("RJ45_8P8C", "Gniazdo RJ45 8P8C THT", smd=False, body_w=8.0, body_h=10.0)
    pitch = 1.016
    # rzad przedni: piny 1,3,5,7 ; tylny: 2,4,6,8 (staggered)
    front = ["1", "3", "5", "7"]
    back = ["2", "4", "6", "8"]
    x0 = -(len(front) - 1) * (pitch * 2) / 2
    for i, num in enumerate(front):
        fp.pads.append(Pad(num, x0 + i * pitch * 2, 1.5, 1.0, 1.0, "circle",
                           pad_type="thru_hole", drill=0.9))
    for i, num in enumerate(back):
        fp.pads.append(Pad(num, x0 + pitch + i * pitch * 2, -1.5, 1.0, 1.0, "circle",
                           pad_type="thru_hole", drill=0.9))
    # ekran/kotwy mechaniczne
    for x in (-6.0, 6.0):
        fp.pads.append(Pad("S", x, 0, 3.2, 3.2, "circle", pad_type="thru_hole", drill=2.4))
    return fp


def screw_terminal(poles: int, pitch: float = 5.08) -> Footprint:
    fp = Footprint(f"ScrewTerminal_1x{poles:02d}_P{pitch:.2f}mm",
                   f"Listwa zaciskowa {poles}x{pitch}mm", smd=False,
                   body_w=poles * pitch / 2 + 0.5, body_h=pitch / 2 + 1.5)
    x0 = -(poles - 1) * pitch / 2
    for i in range(poles):
        fp.pads.append(Pad(str(i + 1), x0 + i * pitch, 0, 2.4, 2.4,
                           "rect" if i == 0 else "circle", pad_type="thru_hole", drill=1.3))
    return fp


def jst_xh(poles: int, pitch: float = 2.5) -> Footprint:
    fp = Footprint(f"JST_XH_1x{poles:02d}", f"JST XH {poles}-pin", smd=False,
                   body_w=poles * pitch / 2 + 1.5, body_h=3.0)
    x0 = -(poles - 1) * pitch / 2
    for i in range(poles):
        fp.pads.append(Pad(str(i + 1), x0 + i * pitch, 0, 1.6, 1.6,
                           "rect" if i == 0 else "circle", pad_type="thru_hole", drill=0.9))
    return fp


def usb_c_power() -> Footprint:
    """USB-C tylko zasilanie: VBUS(A4/B9..) + GND + CC, uproszczone 6 padow + 4 ekrany."""
    fp = Footprint("USB_C_Power", "USB-C (zasilanie)", body_w=4.5, body_h=3.5)
    names = ["VBUS", "GND", "CC1", "CC2", "VBUS2", "GND2"]
    pitch = 0.8
    x0 = -(len(names) - 1) * pitch / 2
    for i, num in enumerate(names):
        fp.pads.append(Pad(num, x0 + i * pitch, 1.8, 0.5, 1.3, "rect"))
    for x in (-4.3, 4.3):
        fp.pads.append(Pad("MP", x, 0, 1.6, 2.0, "rect", pad_type="thru_hole", drill=1.0))
    return fp


def dc_jack() -> Footprint:
    """Gniazdo DC barrel 2.1mm THT (3 piny: +,-,switch)."""
    fp = Footprint("DC_Jack_2.1mm", "Gniazdo DC barrel 2.1mm", smd=False, body_w=4.5, body_h=5.5)
    coords = {"1": (-2.3, 0.0), "2": (2.3, -2.4), "3": (2.3, 2.4)}  # 1=tip(+),2=ring(-),3=sw
    for num, (x, y) in coords.items():
        fp.pads.append(Pad(num, x, y, 2.6, 2.6, "circle", pad_type="thru_hole", drill=1.5))
    return fp


def relay_srd() -> Footprint:
    """Przekaznik PCB SRD (SPDT). Cewka 1,2; kontakty 230V 3=NO,4=COM,5=NC."""
    fp = Footprint("Relay_SPDT_SRD", "Przekaznik SRD SPDT (cewka + kontakty 230V)",
                   smd=False, body_w=9.5, body_h=7.5)
    # cewka (lewa strona, zwykle pady)
    fp.pads.append(Pad("1", -7.5, -3.5, 1.8, 1.8, "circle", pad_type="thru_hole", drill=1.0))
    fp.pads.append(Pad("2", -7.5, 3.5, 1.8, 1.8, "circle", pad_type="thru_hole", drill=1.0))
    # kontakty 230V (prawa strona, SZEROKIE pady)
    fp.pads.append(Pad("3", 7.5, -5.0, 3.2, 3.2, "rect", pad_type="thru_hole", drill=1.5))  # NO
    fp.pads.append(Pad("4", 7.5, 0.0, 3.2, 3.2, "rect", pad_type="thru_hole", drill=1.5))   # COM
    fp.pads.append(Pad("5", 7.5, 5.0, 3.2, 3.2, "rect", pad_type="thru_hole", drill=1.5))   # NC
    return fp


def castellated_module(name: str, left: int, bottom: int, right: int,
                       pitch: float = 1.0, w: float = 13.2, h: float = 13.0,
                       pad_w: float = 0.9, pad_h: float = 1.4) -> Footprint:
    """Generyczny modul kastelowany (np. ESP32-C3-MINI). Pady: lewa 1..L,
    dol L+1.., prawa .. (w gore)."""
    fp = Footprint(name, name, smd=True, body_w=w / 2, body_h=h / 2)
    half_w, half_h = w / 2, h / 2
    y_bottom = half_h - 1.0
    n = 1
    for i in range(left):       # lewa krawedz, gora->dol
        fp.pads.append(Pad(str(n), -half_w, y_bottom - i * pitch, pad_w, pad_h, "roundrect")); n += 1
    span_b = (bottom - 1) * pitch
    for i in range(bottom):     # dol, lewo->prawo
        fp.pads.append(Pad(str(n), -span_b / 2 + i * pitch, half_h, pad_h, pad_w, "roundrect")); n += 1
    for i in range(right):      # prawa krawedz, dol->gora
        fp.pads.append(Pad(str(n), half_w, (y_bottom - (right - 1) * pitch) + i * pitch,
                           pad_w, pad_h, "roundrect")); n += 1
    return fp


def dpak() -> Footprint:
    """TO-252 / DPAK (MOSFET mocy). Pin1=Gate, 2=Drain(tab), 3=Source."""
    fp = Footprint("TO-252", "DPAK / TO-252 (MOSFET mocy)", body_w=3.2, body_h=3.0)
    fp.pads.append(Pad("1", -2.28, 2.3, 0.9, 1.6, "roundrect"))   # Gate
    fp.pads.append(Pad("3", 2.28, 2.3, 0.9, 1.6, "roundrect"))    # Source
    fp.pads.append(Pad("2", 0.0, -1.5, 5.4, 3.0, "rect"))        # Drain (tab)
    return fp


def mov_disc() -> Footprint:
    """Warystor dyskowy (MOV) THT, 2 piny raster 5mm."""
    fp = Footprint("MOV_Disc", "Warystor MOV (ochrona 230V)", smd=False, body_w=4.5, body_h=4.5)
    fp.pads.append(Pad("1", -3.5, 0, 2.0, 2.0, "circle", pad_type="thru_hole", drill=1.0))
    fp.pads.append(Pad("2", 3.5, 0, 2.0, 2.0, "circle", pad_type="thru_hole", drill=1.0))
    return fp


def mounting_hole(diam: float = 3.2, pad: float = 6.0) -> Footprint:
    """Otwor montazowy (np. M3). Pojedynczy pad PTH, bez sieci."""
    fp = Footprint(f"MountingHole_M{int(diam)}", f"Otwor montazowy M{int(diam)}",
                   smd=False, body_w=pad / 2, body_h=pad / 2)
    fp.pads.append(Pad("1", 0, 0, pad, pad, "circle", pad_type="thru_hole", drill=diam))
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
    "L_0805": lambda: inductor_smd("0805"),
    "L_1206": lambda: inductor_smd("1206"),
    "L_6x6": power_inductor,
    "F_1206": lambda: fuse_smd("1206"),
    "SOT-223": sot223,
    "SOT-23-3": lambda: sot23(3),
    "SOT-23-5": lambda: sot23(5),
    "SOT-23-6": lambda: sot23(6),
    "SOIC-8": lambda: soic(8),
    "SOIC-14": lambda: soic(14),
    "SOIC-16": lambda: soic(16),
    "SOIC-28": lambda: soic(28, span=7.5, body_w=7.5),
    "TO-92": to92,
    "D_SMA": lambda: diode_2pin("D_SMA", 4.3, 2.6, 1.6, 1.6, 4.0),
    "D_SOD-123": lambda: diode_2pin("D_SOD-123", 3.7, 1.5, 0.9, 1.2, 3.0),
    "D_SOD-323": lambda: diode_2pin("D_SOD-323", 2.5, 1.25, 0.7, 0.9, 2.2),
    "Crystal_SMD_3225": crystal_smd,
    "RJ45_8P8C": rj45_8p8c,
    "ScrewTerminal_1x02": lambda: screw_terminal(2),
    "ScrewTerminal_1x03": lambda: screw_terminal(3),
    "JST_XH_1x02": lambda: jst_xh(2),
    "JST_XH_1x03": lambda: jst_xh(3),
    "JST_XH_1x04": lambda: jst_xh(4),
    "USB_C_Power": usb_c_power,
    "DC_Jack_2.1mm": dc_jack,
    "USB_Micro-B": micro_usb,
    "ESP32-WROOM-32": esp32_wroom32,
    "SW_Push_6mm": sw_push,
    "Relay_SPDT_SRD": relay_srd,
    "MountingHole_M3": lambda: mounting_hole(3.2),
    "ESP32-C3-MINI-1": lambda: castellated_module("ESP32-C3-MINI-1", 7, 5, 7, w=13.2, h=13.0),
    "TO-252": dpak,
    "MOV_Disc": mov_disc,
}


def get(name: str) -> Footprint:
    if name not in REGISTRY:
        raise KeyError(f"Nieznany footprint: {name}. Dostepne: {sorted(REGISTRY)}")
    return REGISTRY[name]()


def header_fp(pins: int, rows: int = 1, pitch: float = 2.54) -> Footprint:
    return header(pins, rows, pitch)
