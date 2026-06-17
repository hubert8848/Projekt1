"""Smart Switch - JEDNA plytka zbudowana w calosci z blokow (Builder).

Demonstruje "poprawne z definicji": kazdy blok wnosi dobre praktyki, wiec
projekt przechodzi ERC, DRC-lite i silnik regul bez uwag.

Uruchom:  python -m boards.smart_switch
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pcbforge.blocks import Builder
from pcbforge.checks import summarize
from pcbforge.project import build_project
from pcbforge.spec import dump_design
from pcbforge import rules


def build():
    b = Builder("SmartSwitch")
    # wejscie 12V -> bezpiecznik+dioda -> buck 5V -> LDO 3V3
    b.add("J", "ScrewTerminal_1x02", "12V IN", {"1": "VIN", "2": "GND"})
    b.input_protection("VIN", "VIN_P", "GND")
    b.buck_mp1584("VIN_P", "V5", "GND")
    b.ldo("V5", "3V3", "GND")
    # mozg
    esp = b.esp32(prog_header=True)
    esp.connect("26", "OW").connect("6", "EXP_INT")   # IO4=1-wire, IO34=INT
    # magistrale
    b.i2c_pullups("SDA", "SCL", "3V3")
    b.onewire("OW", "3V3", "GND")
    # ekspander 16 przyciskow
    btns = [f"BTN{i}" for i in range(16)]
    b.mcp23017("3V3", "GND", "SDA", "SCL", "EXP_RST", "EXP_INT", btns, addr=0)
    b.R("10k", "3V3", "EXP_RST")
    # 4 gniazda RJ45 (przyciski + 1-wire)
    for i, label in enumerate(["RJ45-A", "RJ45-B", "RJ45-C", "RJ45-D"]):
        b.rj45_io("3V3", "GND", "OW", btns[i * 4:i * 4 + 4], label=label)
    # czujnik temperatury na plytce
    b.add("U", "DS18B20", "DS18B20", {"1": "GND", "2": "OW", "3": "3V3"})
    return b.design, b.blocks


def main():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    d, blocks = build()
    with open(os.path.join(base, "specs", f"{d.name}.json"), "w", encoding="utf-8") as f:
        json.dump(dump_design(d), f, indent=2, ensure_ascii=False)
    res = build_project(d, os.path.join(base, "out", d.name))
    print(f"== {d.name} ==  ({d.board_w}x{d.board_h} mm, {len(d.components)} czesci, "
          f"{len(d.all_net_names())} sieci)")
    print("\nUzyte bloki:")
    for blk in blocks:
        print("  •", blk)
    print("\n-- ERC --\n" + summarize(res.erc))
    print("\n-- DRC-lite --\n" + summarize(res.drc))
    print("\n-- Reguly projektowe --\n" + summarize(res.rules))
    return 0 if res.errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
