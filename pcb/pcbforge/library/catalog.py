"""Katalog czesci: laczy nazwe czesci z symbolem, footprintem i pinami.

`get_part(name)` zwraca slownik: {symbol: SymbolDef, footprint: str, pins: [...]}.
Czesci o zmiennej liczbie pinow (goldpiny) generowane sa dynamicznie:
np. "Header_1x10".
"""
from __future__ import annotations

import re
from typing import Dict

from . import symbols as sym

# Oficjalna tabela pinow ESP32-WROOM-32 (numer, nazwa, typ, strona symbolu)
_ESP32_PINS = [
    (1, "GND", "power_in", "left"),
    (2, "3V3", "power_in", "left"),
    (3, "EN", "input", "left"),
    (4, "SENSOR_VP/IO36", "input", "left"),
    (5, "SENSOR_VN/IO39", "input", "left"),
    (6, "IO34", "input", "left"),
    (7, "IO35", "input", "left"),
    (8, "IO32", "bidirectional", "left"),
    (9, "IO33", "bidirectional", "left"),
    (10, "IO25", "bidirectional", "left"),
    (11, "IO26", "bidirectional", "left"),
    (12, "IO27", "bidirectional", "left"),
    (13, "IO14", "bidirectional", "left"),
    (14, "IO12", "bidirectional", "left"),
    (15, "GND", "power_in", "left"),
    (16, "IO13", "bidirectional", "left"),
    (17, "SD2/IO9", "bidirectional", "left"),
    (18, "SD3/IO10", "bidirectional", "left"),
    (19, "CMD/IO11", "bidirectional", "left"),
    (20, "CLK/IO6", "bidirectional", "right"),
    (21, "SD0/IO7", "bidirectional", "right"),
    (22, "SD1/IO8", "bidirectional", "right"),
    (23, "IO15", "bidirectional", "right"),
    (24, "IO2", "bidirectional", "right"),
    (25, "IO0", "bidirectional", "right"),
    (26, "IO4", "bidirectional", "right"),
    (27, "IO16", "bidirectional", "right"),
    (28, "IO17", "bidirectional", "right"),
    (29, "IO5", "bidirectional", "right"),
    (30, "IO18", "bidirectional", "right"),
    (31, "IO19", "bidirectional", "right"),
    (32, "NC", "no_connect", "right"),
    (33, "IO21", "bidirectional", "right"),
    (34, "RXD0/IO3", "input", "right"),
    (35, "TXD0/IO1", "output", "right"),
    (36, "IO22", "bidirectional", "right"),
    (37, "IO23", "bidirectional", "right"),
    (38, "GND", "power_in", "right"),
]


def _esp32() -> sym.SymbolDef:
    pins = [(str(n), name, et, side) for (n, name, et, side) in _ESP32_PINS]
    return sym.box("pcbforge:ESP32-WROOM-32", "U", pins, width=30.48)


def _ams1117() -> sym.SymbolDef:
    pins = [
        ("1", "GND", "power_in", "left"),
        ("3", "VIN", "power_in", "left"),
        ("2", "VOUT", "power_out", "right"),
        ("4", "VOUT(tab)", "power_out", "right"),
    ]
    return sym.box("pcbforge:AMS1117", "U", pins, width=20.32)


def _usb() -> sym.SymbolDef:
    pins = [
        ("1", "VBUS", "power_out", "left"),
        ("2", "D-", "bidirectional", "left"),
        ("3", "D+", "bidirectional", "left"),
        ("4", "ID", "passive", "left"),
        ("5", "GND", "power_in", "left"),
        ("MP", "SHIELD", "passive", "right"),
    ]
    return sym.box("pcbforge:USB_Micro-B", "J", pins, width=20.32)


def _switch() -> sym.SymbolDef:
    pins = [
        ("1", "A", "passive", "left"),
        ("2", "A", "passive", "left"),
        ("3", "B", "passive", "right"),
        ("4", "B", "passive", "right"),
    ]
    return sym.box("pcbforge:SW_Push", "SW", pins, width=12.7)


def _crystal() -> sym.SymbolDef:
    s = sym.two_pin_vertical("pcbforge:Crystal", "Y", body="crystal")
    s.pins[1].number = "3"   # kwarc 4-pad: aktywne 1 i 3 (2,4 = obudowa)
    return s


def _rj45() -> sym.SymbolDef:
    pins = [(str(i), f"P{i}", "passive", "left" if i <= 4 else "right") for i in range(1, 9)]
    pins.append(("S", "SHIELD", "passive", "right"))
    return sym.box("pcbforge:RJ45_8P8C", "J", pins, width=15.24)


def _rj45_dual() -> sym.SymbolDef:
    pins = [(str(i), f"A{i}", "passive", "left") for i in range(1, 9)]
    pins += [(str(i), f"B{i-8}", "passive", "right") for i in range(9, 17)]
    pins.append(("S", "SHIELD", "passive", "right"))
    return sym.box("pcbforge:RJ45_Dual", "J", pins, width=20.32)


def _screw(poles: int) -> sym.SymbolDef:
    pins = [(str(i), f"{i}", "passive", "left") for i in range(1, poles + 1)]
    return sym.box(f"pcbforge:ScrewTerminal_1x{poles:02d}", "J", pins, width=7.62)


def _jst(poles: int) -> sym.SymbolDef:
    pins = [(str(i), f"{i}", "passive", "left") for i in range(1, poles + 1)]
    return sym.box(f"pcbforge:JST_XH_1x{poles:02d}", "J", pins, width=7.62)


def _usb_c() -> sym.SymbolDef:
    pins = [("VBUS", "VBUS", "power_out", "left"), ("VBUS2", "VBUS", "power_out", "left"),
            ("CC1", "CC1", "passive", "left"), ("CC2", "CC2", "passive", "left"),
            ("GND", "GND", "power_in", "right"), ("GND2", "GND", "power_in", "right"),
            ("MP", "SHIELD", "passive", "right")]
    return sym.box("pcbforge:USB_C_Power", "J", pins, width=17.78)


def _dc_jack() -> sym.SymbolDef:
    pins = [("1", "+", "power_out", "left"), ("2", "-", "power_in", "left"),
            ("3", "SW", "passive", "right")]
    return sym.box("pcbforge:DC_Jack", "J", pins, width=12.7)


def _mcp23017() -> sym.SymbolDef:
    names = ["GPB0", "GPB1", "GPB2", "GPB3", "GPB4", "GPB5", "GPB6", "GPB7",
             "VDD", "VSS", "NC", "SCL", "SDA", "NC2", "A0", "A1", "A2", "RESET",
             "INTB", "INTA", "GPA0", "GPA1", "GPA2", "GPA3", "GPA4", "GPA5", "GPA6", "GPA7"]
    et = {"VDD": "power_in", "VSS": "power_in", "SCL": "input", "SDA": "bidirectional",
          "RESET": "input", "NC": "no_connect", "NC2": "no_connect"}
    pins = []
    for i, nm in enumerate(names, start=1):
        side = "left" if i <= 14 else "right"
        pins.append((str(i), nm, et.get(nm, "bidirectional"), side))
    return sym.box("pcbforge:MCP23017", "U", pins, width=33.0)


def _eeprom() -> sym.SymbolDef:
    pins = [("1", "A0", "input", "left"), ("2", "A1", "input", "left"),
            ("3", "A2", "input", "left"), ("4", "VSS", "power_in", "left"),
            ("5", "SDA", "bidirectional", "right"), ("6", "SCL", "input", "right"),
            ("7", "WP", "input", "right"), ("8", "VCC", "power_in", "right")]
    return sym.box("pcbforge:24LCxx", "U", pins, width=15.24)


def _max485() -> sym.SymbolDef:
    pins = [("1", "RO", "output", "left"), ("2", "RE", "input", "left"),
            ("3", "DE", "input", "left"), ("4", "DI", "input", "left"),
            ("5", "GND", "power_in", "right"), ("6", "A", "bidirectional", "right"),
            ("7", "B", "bidirectional", "right"), ("8", "VCC", "power_in", "right")]
    return sym.box("pcbforge:MAX485", "U", pins, width=15.24)


def _mp1584() -> sym.SymbolDef:
    pins = [("1", "BST", "passive", "left"), ("2", "VIN", "power_in", "left"),
            ("3", "SW", "passive", "left"), ("4", "GND", "power_in", "left"),
            ("5", "FB", "input", "right"), ("6", "COMP", "passive", "right"),
            ("7", "EN", "input", "right"), ("8", "SS", "passive", "right")]
    return sym.box("pcbforge:MP1584", "U", pins, width=17.78)


def _relay() -> sym.SymbolDef:
    pins = [("1", "COIL+", "passive", "left"), ("2", "COIL-", "passive", "left"),
            ("3", "NO", "passive", "right"), ("4", "COM", "passive", "right"),
            ("5", "NC", "passive", "right")]
    return sym.box("pcbforge:Relay_SPDT", "K", pins, width=15.24)


def _mount() -> sym.SymbolDef:
    s = sym.SymbolDef("pcbforge:MountingHole", "H", pin_names_hidden=True,
                      pin_numbers_hidden=True)
    s.circles.append((0, 0, 1.5))
    return s


_ESP32C3_PINS = [
    (1, "GND", "power_in", "left"), (2, "3V3", "power_in", "left"), (3, "EN", "input", "left"),
    (4, "IO0", "bidirectional", "left"), (5, "IO1", "bidirectional", "left"),
    (6, "IO2", "bidirectional", "left"), (7, "IO3", "bidirectional", "left"),
    (8, "IO4", "bidirectional", "left"), (9, "IO5", "bidirectional", "left"),
    (10, "IO6", "bidirectional", "left"), (11, "IO7", "bidirectional", "right"),
    (12, "IO8", "bidirectional", "right"), (13, "IO9", "bidirectional", "right"),
    (14, "IO10", "bidirectional", "right"), (15, "IO18", "bidirectional", "right"),
    (16, "IO19", "bidirectional", "right"), (17, "IO20/RX", "input", "right"),
    (18, "IO21/TX", "output", "right"), (19, "GND", "power_in", "right"),
]


def _esp32c3() -> sym.SymbolDef:
    pins = [(str(n), nm, et, side) for (n, nm, et, side) in _ESP32C3_PINS]
    return sym.box("pcbforge:ESP32-C3-MINI-1", "U", pins, width=25.4)


# ESP32-S3-WROOM-1: 40 pinow (uproszczony, sekwencyjny IO0..IO48)
_ESP32S3_NAMES = (["GND", "3V3", "EN"] +
                  [f"IO{n}" for n in range(0, 22)] +
                  [f"IO{n}" for n in range(35, 49)] + ["GND"])  # 3+22+14+1 = 40


def esp32s3_pin(name: str) -> str:
    """Numer pinu ESP32-S3 dla nazwy GPIO (np. 'IO8' -> '12')."""
    return str(_ESP32S3_NAMES.index(name) + 1)


def _esp32s3() -> sym.SymbolDef:
    pins = []
    for i, nm in enumerate(_ESP32S3_NAMES, start=1):
        et = "power_in" if nm in ("GND", "3V3") else ("input" if nm == "EN" else "bidirectional")
        side = "left" if i <= 20 else "right"
        pins.append((str(i), nm, et, side))
    return sym.box("pcbforge:ESP32-S3-WROOM-1", "U", pins, width=30.48)


def _tja1051() -> sym.SymbolDef:
    pins = [("1", "TXD", "input", "left"), ("2", "GND", "power_in", "left"),
            ("3", "VCC", "power_in", "left"), ("4", "RXD", "output", "left"),
            ("5", "VIO", "power_in", "right"), ("6", "CANL", "bidirectional", "right"),
            ("7", "CANH", "bidirectional", "right"), ("8", "STB", "input", "right")]
    return sym.box("pcbforge:TJA1051", "U", pins, width=15.24)


def _ds18b20() -> sym.SymbolDef:
    pins = [("1", "GND", "power_in", "left"), ("2", "DQ", "bidirectional", "left"),
            ("3", "VDD", "power_in", "right")]
    return sym.box("pcbforge:DS18B20", "U", pins, width=12.7)


_STATIC: Dict[str, dict] = {
    "R": dict(symbol=lambda: sym.two_pin_vertical("pcbforge:R", "R", body="rect"),
              footprint="R_0805"),
    "C": dict(symbol=lambda: sym.two_pin_vertical("pcbforge:C", "C", body="cap"),
              footprint="C_0805"),
    "CP": dict(symbol=lambda: sym.two_pin_vertical("pcbforge:CP", "C", body="cap_pol",
                                                   t1="passive", t2="passive"),
               footprint="CP_1206"),
    "LED": dict(symbol=lambda: sym.two_pin_vertical("pcbforge:LED", "D", body="led"),
                footprint="LED_0805"),
    "D": dict(symbol=lambda: sym.two_pin_vertical("pcbforge:D", "D", body="diode"),
              footprint="D_0805"),
    "L": dict(symbol=lambda: sym.two_pin_vertical("pcbforge:L", "L", body="inductor"),
              footprint="L_0805"),
    "L_power": dict(symbol=lambda: sym.two_pin_vertical("pcbforge:L", "L", body="inductor"),
                    footprint="L_6x6"),
    "FB": dict(symbol=lambda: sym.two_pin_vertical("pcbforge:FB", "FB", body="ferrite"),
               footprint="L_0805"),
    "F": dict(symbol=lambda: sym.two_pin_vertical("pcbforge:F", "F", body="fuse"),
              footprint="F_1206"),
    "Y": dict(symbol=_crystal, footprint="Crystal_SMD_3225"),
    "D_Schottky": dict(symbol=lambda: sym.two_pin_vertical("pcbforge:D_Schottky", "D", body="diode"),
                       footprint="D_SMA"),
    "D_Rectifier": dict(symbol=lambda: sym.two_pin_vertical("pcbforge:D", "D", body="diode"),
                        footprint="D_SMA"),
    "D_TVS": dict(symbol=lambda: sym.two_pin_vertical("pcbforge:D_TVS", "D", body="diode"),
                  footprint="D_SOD-323"),
    "Q_NPN": dict(symbol=lambda: sym.transistor("pcbforge:Q_NPN", "Q", "npn"), footprint="SOT-23-3"),
    "Q_PNP": dict(symbol=lambda: sym.transistor("pcbforge:Q_PNP", "Q", "pnp"), footprint="SOT-23-3"),
    "Q_NMOS": dict(symbol=lambda: sym.transistor("pcbforge:Q_NMOS", "Q", "nmos"), footprint="SOT-23-3"),
    "Q_PMOS": dict(symbol=lambda: sym.transistor("pcbforge:Q_PMOS", "Q", "pmos"), footprint="SOT-23-3"),
    "ESP32-WROOM-32": dict(symbol=_esp32, footprint="ESP32-WROOM-32"),
    "AMS1117-3.3": dict(symbol=_ams1117, footprint="SOT-223"),
    "AMS1117-5.0": dict(symbol=_ams1117, footprint="SOT-223"),
    "MP1584": dict(symbol=_mp1584, footprint="SOIC-8"),
    "MCP23017": dict(symbol=_mcp23017, footprint="SOIC-28"),
    "24LCxx": dict(symbol=_eeprom, footprint="SOIC-8"),
    "MAX485": dict(symbol=_max485, footprint="SOIC-8"),
    "DS18B20": dict(symbol=_ds18b20, footprint="TO-92"),
    "RJ45": dict(symbol=_rj45, footprint="RJ45_8P8C"),
    "RJ45_Dual": dict(symbol=_rj45_dual, footprint="RJ45_Dual"),
    "ScrewTerminal_1x02": dict(symbol=lambda: _screw(2), footprint="ScrewTerminal_1x02"),
    "ScrewTerminal_1x03": dict(symbol=lambda: _screw(3), footprint="ScrewTerminal_1x03"),
    "JST_XH_1x02": dict(symbol=lambda: _jst(2), footprint="JST_XH_1x02"),
    "JST_XH_1x03": dict(symbol=lambda: _jst(3), footprint="JST_XH_1x03"),
    "JST_XH_1x04": dict(symbol=lambda: _jst(4), footprint="JST_XH_1x04"),
    "USB_C_Power": dict(symbol=_usb_c, footprint="USB_C_Power"),
    "DC_Jack": dict(symbol=_dc_jack, footprint="DC_Jack_2.1mm"),
    "USB_Micro-B": dict(symbol=_usb, footprint="USB_Micro-B"),
    "SW_Push": dict(symbol=_switch, footprint="SW_Push_6mm"),
    "Relay_SPDT": dict(symbol=_relay, footprint="Relay_SPDT_SRD"),
    "MountingHole": dict(symbol=_mount, footprint="MountingHole_M3"),
    "ESP32-C3": dict(symbol=_esp32c3, footprint="ESP32-C3-MINI-1"),
    "ESP32-S3": dict(symbol=_esp32s3, footprint="ESP32-S3-WROOM-1"),
    "TJA1051": dict(symbol=_tja1051, footprint="SOIC-8"),
    "MOV": dict(symbol=lambda: sym.two_pin_vertical("pcbforge:MOV", "RV", body="ferrite"),
                footprint="MOV_Disc"),
    "PTC": dict(symbol=lambda: sym.two_pin_vertical("pcbforge:PTC", "F", body="fuse"),
                footprint="PTC_1812"),
    "CMC": dict(symbol=lambda: sym.box("pcbforge:CMC", "L",
                [("1", "A1", "passive", "left"), ("4", "B1", "passive", "left"),
                 ("2", "A2", "passive", "right"), ("3", "B2", "passive", "right")], width=10.16),
                footprint="CMC_4"),
    "Q_NMOS_DPAK": dict(symbol=lambda: sym.transistor("pcbforge:Q_NMOS_DPAK", "Q", "nmos"),
                        footprint="TO-252"),
}


def get_part(name: str) -> dict:
    if name in _STATIC:
        spec = _STATIC[name]
        return {"symbol": spec["symbol"](), "footprint": spec["footprint"], "name": name}
    m = re.fullmatch(r"Header_(\d+)x(\d+)", name)
    if m:
        rows, cols = int(m.group(1)), int(m.group(2))
        n = rows * cols
        pins = []
        for i in range(1, n + 1):
            side = "left" if (i - 1) < n / 2 else "right"
            pins.append((str(i), f"P{i}", "passive", side))
        symbol = sym.box(f"pcbforge:{name}", "J", pins, width=10.16)
        return {"symbol": symbol, "footprint": f"Header_{rows}x{cols:02d}",
                "name": name, "header": (rows, cols)}
    raise KeyError(f"Nieznana czesc: {name}")


def default_footprint(part: str) -> str:
    p = get_part(part)
    if "header" in p:
        rows, cols = p["header"]
        return f"Header_{rows}x{cols:02d}"
    return p["footprint"]


def known_parts():
    return sorted(_STATIC.keys()) + ["Header_RxC (np. Header_1x10)"]
