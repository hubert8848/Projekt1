"""HomeController PRO - sterownik domowy 32 wejscia / 16 wyjsc (2 plytki).

GORA (HomeCtrlPro_Top) - logika + wejscia + UI:
  ESP32-C3 + 2x ekspander I2C (32 wejscia), 8x RJ45 (wejscia, TVS/wejscie),
  RS485 + CAN (laczenie sterownikow), zlacze TFT dotykowy. Plytka WEZSZA.
GORA jest wezsza o pasy I/O - dostep do zaciskow dolnej plytki.

DOL (HomeCtrlPro_Bottom) - zasilanie + wyjscia 230V/DC:
  zasilanie 24V (bezpiecznik + dioda + MOV + buck 5V + LDO 3V3),
  ekspander wyjsc, 8x wyjscie przekaznikowe 230V + 8x wyjscie MOSFET DC,
  kazde wyjscie wlasny zacisk srubowy. Przekazniki we wnetrzu (nie przy krawedzi).

ESP32-C3 ma ograniczone GPIO - tu wykorzystane w pelni (USB do programowania,
IO9 dzieli BOOT z CAN-RX). Pod pelna niezaleznosc magistral rozwaz ESP32-S3.

Niezawodnosc 'na 30 lat': TVS na kazdym I/O, bezpiecznik + MOV na zasilaniu,
diody gasnace, pull-down bramek MOSFET, grube sciezki + izolacja 230V, dekapy.

Uruchom:  python -m boards.home_controller_pro
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pcbforge.blocks import Builder
from pcbforge.checks import summarize
from pcbforge.layout import auto_layout_4e
from pcbforge.project import build_project
from pcbforge.spec import dump_design

# listwa miedzyplytkowa: zasilanie + I2C + reset ekspanderow
B2B = {str(i): v for i, v in enumerate(
    ["GND", "GND", "3V3", "3V3", "SDA", "SCL", "EXP_RST", "GND", "3V3", "GND",
     "GND", "3V3", "GND", "3V3", "GND", "3V3", "GND", "3V3", "GND", "GND"], start=1)}


def build_bottom() -> Builder:
    b = Builder("HomeCtrlPro_Bottom")
    b.design.notes = ["Plyta DOLNA: zasilanie 24V + 16 wyjsc (8x 230V przekaznik, 8x MOSFET DC)",
                      "UWAGA 230V! Strefa sieciowa = dolna krawedz. Grube sciezki + izolacja."]
    for _ in range(4):   # otwory montazowe = uziemienie obudowy (PE)
        b.add("H", "MountingHole", "M3", {"1": "PE"}, role="mount", label="M3 / PE")
    b.add("J", "Header_2x10", "B2B", dict(B2B), role="b2b", label="do plyty gornej")

    # zasilanie 24V: zacisk + bezpiecznik + dioda + MOV + buck 5V + LDO 3V3
    b.add("J", "ScrewTerminal_1x02", "24V", {"1": "V24", "2": "GND"}, role="io", label="Zasilanie 24V")
    b.input_protection("V24", "V24P", "GND", fuse="3A")
    b.add("RV", "MOV", "S14K30", {"1": "V24P", "2": "GND"}, label="Ochrona przepiec")
    b.buck_mp1584("V24P", "V5", "GND")
    b.ldo("V5", "3V3", "GND")

    # ekspander WYJSC (adres 0x22)
    outs = [f"OUT{i}" for i in range(16)]
    b.mcp23017("3V3", "GND", "SDA", "SCL", "EXP_RST", "", outs, addr=4)  # 0x24 (wejscia 0x20-0x23)

    # zacisk sieciowy 230V (wejscie L/N/PE) -> gorna krawedz z zasilaniem
    b.add("J", "ScrewTerminal_1x03", "230V", {"1": "L", "2": "N", "3": "PE"},
          role="io", label="Siec 230V L/N/PE")
    # 8 wyjsc przekaznikowych 230V
    for i in range(8):
        b.output_relay(f"OUT{i}", str(i), "V24P", "GND", "L", "N", label=f"Lampa {i+1} 230V")
    # 8 wyjsc MOSFET DC (LED/tasmy 24V)
    for i in range(8, 16):
        b.output_mosfet(f"OUT{i}", str(i), "V24P", "GND", label=f"LED {i-7} DC")

    mains = ["L", "N", "PE"] + [f"LAMP{i}" for i in range(8)]
    b.design.mark_mains(*mains)
    return b


def build_top() -> Builder:
    b = Builder("HomeCtrlPro_Top")
    b.design.notes = ["Plyta GORNA (wezsza): ESP32-C3 + 32 wejscia (RJ45) + RS485/CAN + TFT",
                      "Wejscia na RJ45 (TVS/wejscie). Sklada sie na dolna - otwory i zlacze 1:1."]
    for _ in range(4):
        b.add("H", "MountingHole", "M3", {}, role="mount", label="M3")
    b.add("J", "Header_2x10", "B2B", dict(B2B), role="b2b", label="do plyty dolnej")

    # mozg: ESP32-S3 (duzo GPIO - niezalezne magistrale, dotyk z IRQ, przyciski)
    b.esp32s3({
        "IO8": "SDA", "IO9": "SCL",
        "IO12": "SPI_SCK", "IO11": "SPI_MOSI", "IO13": "SPI_MISO",
        "IO10": "TFT_CS", "IO14": "TFT_DC", "IO21": "TFT_RST",
        "IO47": "TOUCH_CS", "IO48": "TOUCH_IRQ",
        "IO43": "RS485_TXD", "IO44": "RS485_RXD", "IO45": "RS485_DE",
        "IO4": "CAN_TXD", "IO5": "CAN_RXD", "IO17": "EXP_INT",
        "IO6": "BTN_UP", "IO7": "BTN_DOWN", "IO15": "BTN_OK", "IO16": "BTN_BACK",
    }, "3V3", "GND")
    b.i2c_pullups("SDA", "SCL", "3V3")
    b.R("10k", "3V3", "EXP_RST")                 # reset ekspanderow w gore
    b.add("LED", "LED", "PWR", {"1": "_PWRLED", "2": "GND"}); b.R("1k", "3V3", "_PWRLED")

    # przyciski nawigacji TFT (na krawedzi, dostepne palcem)
    for net, lab in [("BTN_UP", "GORA"), ("BTN_DOWN", "DOL"), ("BTN_OK", "OK"), ("BTN_BACK", "WSTECZ")]:
        b.button(net, "3V3", "GND", label=lab)

    # 4 ekspandery WEJSC (adres 0x20..0x23) - 64 wejscia, wspolne przerwanie
    ins = [f"IN{i}" for i in range(64)]
    for e in range(4):
        b.mcp23017("3V3", "GND", "SDA", "SCL", "EXP_RST", "EXP_INT",
                   ins[e * 16:e * 16 + 16], addr=e)

    # 8 PODWOJNYCH gniazd RJ45 (po 8 wejsc) = 16 portow = 64 wejscia, TVS na kazde
    for k in range(8):
        b.input_bank_dual(ins[k * 8:k * 8 + 8], "3V3", "GND", label=f"We {k*8}-{k*8+7}")

    # magistrale laczenia sterownikow (niezalezne piny)
    b.rs485("RS485_TXD", "RS485_RXD", "RS485_DE", "RS485_A", "RS485_B", "3V3", "GND")
    b.can_bus("CAN_TXD", "CAN_RXD", "CAN_H", "CAN_L", "3V3", "GND")

    # ekran TFT dotykowy
    b.tft_connector("3V3", "GND")
    return b


def _emit(b: Builder, base: str):
    d = b.design
    with open(os.path.join(base, "specs", f"{d.name}.json"), "w", encoding="utf-8") as f:
        json.dump(dump_design(d), f, indent=2, ensure_ascii=False)
    res = build_project(d, os.path.join(base, "out", d.name))
    print(f"== {d.name} ==  obrys {tuple(round(v) for v in d.outline)}  "
          f"({len(d.components)} czesci, {len(d.all_net_names())} sieci)")
    print("  ERC:", summarize(res.erc).splitlines()[-1])
    print("  DRC:", summarize(res.drc).splitlines()[-1])
    print("  Reguly:", summarize(res.rules).splitlines()[-1])
    if res.errors:
        for i in res.erc + res.drc + res.rules:
            if i.severity == "error":
                print("   ", i)
    return res.errors


def layout_pair():
    bottom, top = build_bottom(), build_top()
    frame = auto_layout_4e(bottom.design, top.design)
    return bottom, top, frame


def main():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bottom, top, frame = layout_pair()
    errs = _emit(bottom, base) + _emit(top, base)
    print(f"\nRamka {frame.width}x{frame.height} | otwory {[(round(x),round(y)) for x,y in frame.holes]} "
          f"| B2B {tuple(round(v) for v in frame.b2b)}")
    print(f"Razem bledow: {errs}")
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
