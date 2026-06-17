"""Kontroler automatyki domowej - urzadzenie z DWOCH plytek (gora/dol).

DOL (HomeCtrl_Bottom) - zasilanie i mozg:
  wejscie 12V (listwa) -> bezpiecznik + dioda zabezpieczajaca -> buck MP1584 (5V)
  -> LDO AMS1117 (3V3) -> ESP32. I2C/INT/1-wire/zasilanie na listwie board-to-board.

GORA (HomeCtrl_Top) - zlacza i IO:
  listwa board-to-board (od dolu) -> ekspander I2C MCP23017 (16 wejsc przyciskow),
  2x gniazdo RJ45 (przyciski sciennie + 1-wire czujnik temperatury DS18B20),
  ochrona ESD (TVS) i pull-upy.

Listwa 2x10 laczy obie plytki - mapowanie pinow jest wspolne (B2B_MAP).

Uruchom:  python -m boards.home_controller
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pcbforge import Design, Component
from pcbforge.checks import summarize
from pcbforge.project import build_project
from pcbforge.spec import dump_design

# Wspolne mapowanie listwy board-to-board 2x10 (ten sam uklad na obu plytkach)
B2B_MAP = {
    "1": "GND", "2": "GND", "3": "3V3", "4": "3V3", "5": "V5", "6": "V5",
    "7": "SDA", "8": "SCL", "9": "EXP_INT", "10": "EXP_RST",
    "11": "OW", "12": "IO5", "13": "IO18", "14": "IO19", "15": "IO23",
    "16": "IO25", "17": "GND", "18": "3V3", "19": "GND", "20": "GND",
}


def build_bottom() -> Design:
    d = Design("HomeCtrl_Bottom")

    # --- Wejscie 12V ---
    j1 = d.add(Component("J1", "ScrewTerminal_1x02", "12V IN", "ScrewTerminal_1x02"))
    j1.connect("1", "VIN").connect("2", "GND")
    f1 = d.add(Component("F1", "F", "2A", "F_1206"))
    f1.connect("1", "VIN").connect("2", "VIN_F")
    d1 = d.add(Component("D1", "D_Schottky", "SS34", "D_SMA"))  # zabezpieczenie odwrotne
    d1.connect("1", "VIN_F").connect("2", "VIN_P")
    c1 = d.add(Component("C1", "CP", "100uF", "CP_1206"))
    c1.connect("1", "VIN_P").connect("2", "GND")

    # --- Buck MP1584: 12V -> 5V ---
    u1 = d.add(Component("U1", "MP1584", "MP1584", "SOIC-8"))
    u1.connect("2", "VIN_P").connect("4", "GND").connect("3", "SW")
    u1.connect("1", "BST").connect("7", "VIN_P").connect("5", "FB")  # EN=VIN_P
    l1 = d.add(Component("L1", "L_power", "10uH", "L_6x6"))
    l1.connect("1", "SW").connect("2", "V5")
    d2 = d.add(Component("D2", "D_Schottky", "SS34", "D_SMA"))       # dioda zwrotna
    d2.connect("1", "GND").connect("2", "SW")
    cbst = d.add(Component("C2", "C", "10nF", "C_0805"))
    cbst.connect("1", "BST").connect("2", "SW")
    cout = d.add(Component("C3", "CP", "47uF", "CP_1206"))
    cout.connect("1", "V5").connect("2", "GND")
    rf1 = d.add(Component("R1", "R", "100k", "R_0805"))
    rf1.connect("1", "V5").connect("2", "FB")
    rf2 = d.add(Component("R2", "R", "20k", "R_0805"))
    rf2.connect("1", "FB").connect("2", "GND")

    # --- LDO 5V -> 3V3 ---
    u2 = d.add(Component("U2", "AMS1117-3.3", "AMS1117-3.3", "SOT-223"))
    u2.connect("3", "V5").connect("1", "GND").connect("2", "3V3").connect("4", "3V3")
    c4 = d.add(Component("C5", "CP", "10uF", "CP_1206"))
    c4.connect("1", "3V3").connect("2", "GND")
    c5 = d.add(Component("C6", "C", "100nF", "C_0805"))
    c5.connect("1", "3V3").connect("2", "GND")

    # --- ESP32 ---
    u3 = d.add(Component("U3", "ESP32-WROOM-32", "ESP32-WROOM-32", "ESP32-WROOM-32"))
    u3.connect("1", "GND").connect("2", "3V3").connect("3", "EN")
    u3.connect("15", "GND").connect("38", "GND")
    u3.connect("33", "SDA").connect("36", "SCL")   # IO21=SDA, IO22=SCL
    u3.connect("26", "OW").connect("6", "EXP_INT")  # IO4=1-wire, IO34=INT
    u3.connect("25", "IO0").connect("35", "TXD0").connect("34", "RXD0")
    u3.connect("29", "IO5").connect("30", "IO18").connect("31", "IO19")
    u3.connect("37", "IO23").connect("10", "IO25")
    c6 = d.add(Component("C7", "C", "100nF", "C_0805"))
    c6.connect("1", "3V3").connect("2", "GND")
    ren = d.add(Component("R3", "R", "10k", "R_0805"))
    ren.connect("1", "3V3").connect("2", "EN")
    cen = d.add(Component("C8", "C", "100nF", "C_0805"))
    cen.connect("1", "EN").connect("2", "GND")
    rio0 = d.add(Component("R4", "R", "10k", "R_0805"))
    rio0.connect("1", "3V3").connect("2", "IO0")
    rrst = d.add(Component("R5", "R", "10k", "R_0805"))   # reset expandera (aktywny stan wysoki)
    rrst.connect("1", "3V3").connect("2", "EXP_RST")
    sw1 = d.add(Component("SW1", "SW_Push", "EN", "SW_Push_6mm"))
    sw1.connect("1", "EN").connect("2", "EN").connect("3", "GND").connect("4", "GND")
    sw2 = d.add(Component("SW2", "SW_Push", "BOOT", "SW_Push_6mm"))
    sw2.connect("1", "IO0").connect("2", "IO0").connect("3", "GND").connect("4", "GND")

    # --- Header programatora ---
    j2 = d.add(Component("J2", "Header_1x06", "UART", "Header_1x06"))
    for pin, net in zip("123456", ["GND", "3V3", "EN", "IO0", "TXD0", "RXD0"]):
        j2.connect(pin, net)

    # --- Listwa board-to-board do gornej plytki ---
    j3 = d.add(Component("J3", "Header_2x10", "B2B", "Header_2x10"))
    for pin, net in B2B_MAP.items():
        j3.connect(pin, net)

    return d


def build_top() -> Design:
    d = Design("HomeCtrl_Top")

    # --- Listwa board-to-board (od dolnej plytki) ---
    j1 = d.add(Component("J1", "Header_2x10", "B2B", "Header_2x10"))
    for pin, net in B2B_MAP.items():
        j1.connect(pin, net)

    # --- Ekspander I2C MCP23017 (16 wejsc przyciskow) ---
    u1 = d.add(Component("U1", "MCP23017", "MCP23017", "SOIC-28"))
    u1.connect("9", "3V3").connect("10", "GND").connect("12", "SCL").connect("13", "SDA")
    u1.connect("15", "GND").connect("16", "GND").connect("17", "GND")   # A0..A2 -> adres 0x20
    u1.connect("18", "EXP_RST").connect("20", "EXP_INT")
    # GPA0-7 = piny 21..28, GPB0-7 = piny 1..8
    gpa = {str(21 + i): f"BTN{i}" for i in range(8)}
    gpb = {str(1 + i): f"BTN{8 + i}" for i in range(8)}
    for pin, net in {**gpa, **gpb}.items():
        u1.connect(pin, net)
    cd = d.add(Component("C1", "C", "100nF", "C_0805"))
    cd.connect("1", "3V3").connect("2", "GND")

    # --- Pull-upy I2C i 1-wire ---
    rsda = d.add(Component("R1", "R", "4.7k", "R_0805"))
    rsda.connect("1", "3V3").connect("2", "SDA")
    rscl = d.add(Component("R2", "R", "4.7k", "R_0805"))
    rscl.connect("1", "3V3").connect("2", "SCL")
    row = d.add(Component("R3", "R", "4.7k", "R_0805"))
    row.connect("1", "3V3").connect("2", "OW")

    # --- Czujnik temperatury DS18B20 (1-wire, na plytce) ---
    u2 = d.add(Component("U2", "DS18B20", "DS18B20", "TO-92"))
    u2.connect("1", "GND").connect("2", "OW").connect("3", "3V3")

    # --- Gniazda RJ45: przyciski sciennie + 1-wire ---
    # RJ45 #1: 3V3, BTN0..3, OW, GND, GND
    j2 = d.add(Component("J2", "RJ45", "RJ45-A", "RJ45_8P8C"))
    for pin, net in zip("12345678", ["3V3", "BTN0", "BTN1", "BTN2", "BTN3", "OW", "GND", "GND"]):
        j2.connect(pin, net)
    j2.connect("S", "GND")
    # RJ45 #2: 3V3, BTN4..7, OW, GND, GND
    j3 = d.add(Component("J3", "RJ45", "RJ45-B", "RJ45_8P8C"))
    for pin, net in zip("12345678", ["3V3", "BTN4", "BTN5", "BTN6", "BTN7", "OW", "GND", "GND"]):
        j3.connect(pin, net)
    j3.connect("S", "GND")
    # RJ45 #3: 3V3, BTN8..11, OW, GND, GND
    j4 = d.add(Component("J4", "RJ45", "RJ45-C", "RJ45_8P8C"))
    for pin, net in zip("12345678", ["3V3", "BTN8", "BTN9", "BTN10", "BTN11", "OW", "GND", "GND"]):
        j4.connect(pin, net)
    j4.connect("S", "GND")
    # RJ45 #4: 3V3, BTN12..15, OW, GND, GND
    j5 = d.add(Component("J5", "RJ45", "RJ45-D", "RJ45_8P8C"))
    for pin, net in zip("12345678", ["3V3", "BTN12", "BTN13", "BTN14", "BTN15", "OW", "GND", "GND"]):
        j5.connect(pin, net)
    j5.connect("S", "GND")

    # --- Header zapasowy: bezposrednie GPIO z ESP32 (z listwy B2B) ---
    j6 = d.add(Component("J6", "Header_1x06", "GPIO", "Header_1x06"))
    for pin, net in zip("123456", ["GND", "IO5", "IO18", "IO19", "IO23", "IO25"]):
        j6.connect(pin, net)

    # --- Ochrona ESD (TVS) na liniach 1-wire i wybranych przyciskach ---
    tvs_ow = d.add(Component("D1", "D_TVS", "ESD", "D_SOD-323"))
    tvs_ow.connect("1", "OW").connect("2", "GND")
    tvs_b0 = d.add(Component("D2", "D_TVS", "ESD", "D_SOD-323"))
    tvs_b0.connect("1", "BTN0").connect("2", "GND")
    tvs_b4 = d.add(Component("D3", "D_TVS", "ESD", "D_SOD-323"))
    tvs_b4.connect("1", "BTN4").connect("2", "GND")

    return d


def _emit(d: Design, specs_dir: str, out_root: str) -> int:
    os.makedirs(specs_dir, exist_ok=True)
    with open(os.path.join(specs_dir, f"{d.name}.json"), "w", encoding="utf-8") as f:
        json.dump(dump_design(d), f, indent=2, ensure_ascii=False)
    res = build_project(d, os.path.join(out_root, d.name))
    print(f"\n== {d.name} ==  ({d.board_w}x{d.board_h} mm, "
          f"{len(d.components)} czesci, {len(d.all_net_names())} sieci)")
    print("ERC:", summarize(res.erc).splitlines()[-1])
    print("DRC:", summarize(res.drc).splitlines()[-1])
    if res.errors:
        print(summarize(res.erc)); print(summarize(res.drc))
    return res.errors


def main():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    specs = os.path.join(base, "specs")
    out = os.path.join(base, "out")
    errs = 0
    for d in (build_bottom(), build_top()):
        errs += _emit(d, specs, out)
    print(f"\nRazem bledow: {errs}")
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
