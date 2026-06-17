"""SmartHome230 - flagowe urzadzenie z DWOCH plytek wg zasad uzytkownika.

Zasady wdrozone:
  1. I/O (zasilanie, RJ45) na GORNEJ krawedzi dolnej plytki (dostep srubokretem).
  4/5. Otwory montazowe i zlacze board-to-board w IDENTYCZNYCH wspolrzednych.
  6. Osobna dioda ESD na kazda linie I/O (przyciski, 1-wire).
  7/8. Przekazniki + zaciski 230V w osobnej STREFIE 230V (dolna krawedz),
       sieci L/N/PE/LAMP oznaczone jako 230V -> grubsze sciezki + izolacja.
  9. Opisy po polsku na silkscreenie.
  + Gorna plytka WEZSZA o pasy I/O (gora/dol) - srubokret dochodzi do zaciskow.

Uruchom:  python -m boards.smart_home_230
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pcbforge.blocks import Builder
from pcbforge.checks import summarize
from pcbforge.layout import Frame, place_pair
from pcbforge.project import build_project
from pcbforge.spec import dump_design
from pcbforge import rules

# wspolne mapowanie listwy board-to-board 2x10 (te same piny na obu plytkach)
B2B = {
    "1": "GND", "2": "GND", "3": "3V3", "4": "3V3", "5": "SDA", "6": "SCL",
    "7": "EXP_INT", "8": "EXP_RST", "9": "OW", "10": "BTN0", "11": "BTN1",
    "12": "BTN2", "13": "BTN3", "14": "BTN4", "15": "BTN5", "16": "BTN6",
    "17": "BTN7", "18": "GND", "19": "3V3", "20": "GND",
}
BTNS = [f"BTN{i}" for i in range(8)]

# wspolna ramka wspolrzednych obu plytek (otwory + B2B identyczne)
FRAME = Frame(width=130.0, height=115.0, io_band=18.0)


def build_bottom() -> Builder:
    b = Builder("SmartHome230_Bottom")
    b.design.notes = ["Plyta glowna: zasilanie + ESP32 + przekazniki 230V",
                      "UWAGA 230V! Strefa sieciowa = dolna krawedz. Grube sciezki."]
    # otwory + listwa miedzyplytkowa (pozycje ustawi layout - wspolne z gora)
    for _ in range(4):
        b.add("H", "MountingHole", "M3", {}, role="mount", label="otwor M3")
    b.add("J", "Header_2x10", "B2B", {k: v for k, v in B2B.items()},
          role="b2b", label="do plyty gornej")

    # I/O niskonapieciowe (gorna krawedz)
    b.add("J", "ScrewTerminal_1x02", "12V", {"1": "VIN", "2": "GND"},
          role="io", label="Zasilanie 12V")
    b.add("J", "RJ45", "Przyciski A", {"1": "3V3", "2": "BTN0", "3": "BTN1",
          "4": "BTN2", "5": "BTN3", "6": "OW", "7": "GND", "8": "GND", "S": "GND"},
          role="io", label="Przyciski scienne A")
    b.add("J", "RJ45", "Przyciski B", {"1": "3V3", "2": "BTN4", "3": "BTN5",
          "4": "BTN6", "5": "BTN7", "6": "OW", "7": "GND", "8": "GND", "S": "GND"},
          role="io", label="Przyciski scienne B")

    # zasilanie 12V -> 5V (buck) -> 3V3 (LDO)
    b.input_protection("VIN", "V12", "GND")
    b.buck_mp1584("V12", "V5", "GND")
    b.ldo("V5", "3V3", "GND")

    # mozg
    esp = b.esp32(prog_header=True)
    esp.connect("13", "OW").connect("6", "EXP_INT")           # 1-wire, INT z expandera
    esp.connect("26", "RELAY1").connect("29", "RELAY2")       # sterowanie przekaznikami
    b.R("10k", "3V3", "EXP_RST")                              # reset expandera w gore
    b.i2c_pullups("SDA", "SCL", "3V3")

    # osobna dioda ESD na kazda linie I/O (przyciski + 1-wire)
    for net in BTNS + ["OW"]:
        b.add("D", "D_TVS", "ESD", {"1": net, "2": "GND"})

    # strefa 230V: zacisk sieciowy + przekazniki + wyjscia
    b.add("J", "ScrewTerminal_1x03", "230V IN", {"1": "L", "2": "N", "3": "PE"},
          role="mains", label="Siec 230V L/N/PE")
    b.relay_driver("RELAY1", "V12", "GND", out_com="L", out_no="LAMP1",
                   label="Przekaznik 1 - oswietlenie")
    b.relay_driver("RELAY2", "V12", "GND", out_com="L", out_no="LAMP2",
                   label="Przekaznik 2 - gniazdo")
    b.add("J", "ScrewTerminal_1x03", "Wyj.1", {"1": "LAMP1", "2": "N", "3": "PE"},
          role="mains", label="Wyjscie 1 230V")
    b.add("J", "ScrewTerminal_1x03", "Wyj.2", {"1": "LAMP2", "2": "N", "3": "PE"},
          role="mains", label="Wyjscie 2 230V")

    # oznacz sieci 230V -> grubsze sciezki + izolacja
    b.design.mark_mains("L", "N", "PE", "LAMP1", "LAMP2")
    return b


def build_top() -> Builder:
    b = Builder("SmartHome230_Top")
    b.design.notes = ["Plyta gorna (wezsza): ekspander I/O + ochrona",
                      "Skladana na plyte glowna - otwory i zlacze pasuja 1:1"]
    for _ in range(4):
        b.add("H", "MountingHole", "M3", {}, role="mount", label="otwor M3")
    b.add("J", "Header_2x10", "B2B", {k: v for k, v in B2B.items()},
          role="b2b", label="do plyty glownej")

    # ekspander I2C - 8 przyciskow (BTN0..7)
    conns = {"9": "3V3", "10": "GND", "12": "SCL", "13": "SDA",
             "15": "GND", "16": "GND", "17": "GND", "18": "EXP_RST", "20": "EXP_INT"}
    gp = [str(21 + i) for i in range(8)]                      # GPA0..7
    for pinno, net in zip(gp, BTNS):
        conns[pinno] = net
    b.add("U", "MCP23017", "MCP23017", conns, label="Ekspander przyciskow")
    b.C("100nF", "3V3", "GND")                                # dekap
    b.i2c_pullups("SDA", "SCL", "3V3")
    b.onewire("OW", "3V3", "GND")                             # pull-up + ESD
    b.add("U", "DS18B20", "DS18B20", {"1": "GND", "2": "OW", "3": "3V3"},
          label="Czujnik temperatury")
    return b


def _emit(b: Builder, base: str):
    d = b.design
    with open(os.path.join(base, "specs", f"{d.name}.json"), "w", encoding="utf-8") as f:
        json.dump(dump_design(d), f, indent=2, ensure_ascii=False)
    res = build_project(d, os.path.join(base, "out", d.name))
    rule_iss = res.rules
    print(f"== {d.name} ==  obrys {d.outline}  ({len(d.components)} czesci, {len(d.all_net_names())} sieci)")
    print("  ERC:", summarize(res.erc).splitlines()[-1])
    print("  DRC:", summarize(res.drc).splitlines()[-1])
    print("  Reguly:", summarize(rule_iss).splitlines()[-1])
    if res.errors:
        for i in res.erc + res.drc + rule_iss:
            if i.severity == "error":
                print("   ", i)
    return res.errors


def main():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    frame = FRAME
    bottom, top = build_bottom(), build_top()
    place_pair(bottom.design, top.design, frame)
    errs = _emit(bottom, base) + _emit(top, base)
    print(f"\nRamka wspolna: {frame.width}x{frame.height} mm | "
          f"otwory @ {[(round(x),round(y)) for x,y in frame.holes]} | B2B @ {tuple(round(v) for v in frame.b2b)}")
    print(f"Gorna plytka obrys (wezsza): {top.design.outline}")
    print(f"Razem bledow: {errs}")
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
