"""Plyta deweloperska ESP32-WROOM-32 - przyklad end-to-end.

Zasilanie: USB Micro-B (5V/VBUS) -> LDO AMS1117-3.3 -> 3V3.
Programowanie: header 1x06 pod zewnetrzny konwerter USB-UART (GND,3V3,EN,IO0,TX,RX).
Reset/Boot: przyciski EN i BOOT. LED statusu na IO2. Breakout GPIO 1x10.

Uruchom:  python -m boards.esp32_devboard
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pcbforge import Design, Component
from pcbforge.checks import summarize
from pcbforge.project import build_project


def build() -> Design:
    d = Design("ESP32_DevBoard")
    d.rules.track_width = 0.25
    d.rules.power_track_width = 0.5

    # --- Modul ESP32 ---
    u1 = d.add(Component("U1", "ESP32-WROOM-32", "ESP32-WROOM-32", "ESP32-WROOM-32"))
    u1.connect("1", "GND").connect("2", "3V3").connect("3", "EN")
    u1.connect("15", "GND").connect("38", "GND")
    u1.connect("25", "IO0").connect("24", "IO2")
    u1.connect("35", "TXD0").connect("34", "RXD0")
    # breakout GPIO
    gpio = {"26": "IO4", "29": "IO5", "14": "IO12", "16": "IO13", "13": "IO14",
            "23": "IO15", "27": "IO16", "28": "IO17", "30": "IO18", "31": "IO19"}
    for pin, net in gpio.items():
        u1.connect(pin, net)

    # --- Regulator AMS1117-3.3 ---
    u2 = d.add(Component("U2", "AMS1117-3.3", "AMS1117-3.3", "SOT-223"))
    u2.connect("3", "VBUS").connect("1", "GND").connect("2", "3V3").connect("4", "3V3")

    # --- USB Micro-B (tylko zasilanie + linie danych na header) ---
    # USB sluzy tu jako zasilanie 5V (D+/D- nieuzywane - ESP32-WROOM nie ma USB)
    j1 = d.add(Component("J1", "USB_Micro-B", "USB_Micro-B", "USB_Micro-B"))
    j1.connect("1", "VBUS").connect("5", "GND").connect("MP", "GND")

    # --- Kondensatory ---
    c1 = d.add(Component("C1", "CP", "10uF", "CP_1206"))   # wejscie LDO
    c1.connect("1", "VBUS").connect("2", "GND")
    c2 = d.add(Component("C2", "CP", "10uF", "CP_1206"))   # wyjscie LDO
    c2.connect("1", "3V3").connect("2", "GND")
    c3 = d.add(Component("C3", "C", "100nF", "C_0805"))    # odsprzeganie U1
    c3.connect("1", "3V3").connect("2", "GND")
    c4 = d.add(Component("C4", "C", "100nF", "C_0805"))    # opoznienie EN
    c4.connect("1", "EN").connect("2", "GND")

    # --- Rezystory ---
    r1 = d.add(Component("R1", "R", "10k", "R_0805"))      # pull-up EN
    r1.connect("1", "3V3").connect("2", "EN")
    r2 = d.add(Component("R2", "R", "10k", "R_0805"))      # pull-up IO0
    r2.connect("1", "3V3").connect("2", "IO0")
    r3 = d.add(Component("R3", "R", "330", "R_0805"))      # szereg LED
    r3.connect("1", "IO2").connect("2", "LED_A")

    # --- LED statusu ---
    led = d.add(Component("LED1", "LED", "GREEN", "LED_0805"))
    led.connect("1", "LED_A").connect("2", "GND")

    # --- Przyciski EN i BOOT ---
    sw1 = d.add(Component("SW1", "SW_Push", "EN", "SW_Push_6mm"))
    sw1.connect("1", "EN").connect("2", "EN").connect("3", "GND").connect("4", "GND")
    sw2 = d.add(Component("SW2", "SW_Push", "BOOT", "SW_Push_6mm"))
    sw2.connect("1", "IO0").connect("2", "IO0").connect("3", "GND").connect("4", "GND")

    # --- Header programatora 1x06: GND,3V3,EN,IO0,TX,RX ---
    j2 = d.add(Component("J2", "Header_1x06", "UART", "Header_1x06"))
    for pin, net in zip("123456", ["GND", "3V3", "EN", "IO0", "TXD0", "RXD0"]):
        j2.connect(pin, net)

    # --- Header breakout GPIO 1x10 ---
    j3 = d.add(Component("J3", "Header_1x10", "GPIO", "Header_1x10"))
    breakout = ["IO4", "IO5", "IO12", "IO13", "IO14", "IO15", "IO16", "IO17", "IO18", "IO19"]
    for i, net in enumerate(breakout, start=1):
        j3.connect(str(i), net)

    return d


def main():
    d = build()
    outdir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out", d.name)
    res = build_project(d, outdir)
    print(f"== {d.name} ==")
    print("Pliki:")
    for p in res.files:
        print("  ", p)
    print("\n-- ERC --")
    print(summarize(res.erc))
    print("\n-- DRC-lite (rozmieszczenie) --")
    print(summarize(res.drc))
    print(f"\nPlytka: {d.board_w} x {d.board_h} mm | sieci: {len(d.all_net_names())} | "
          f"komponenty: {len(d.components)}")
    return 0 if res.errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
