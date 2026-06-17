"""Biblioteka sprawdzonych blokow (sub-obwodow) skladanych jak klocki.

Kazdy blok dokłada do projektu komplet komponentow danego pod-obwodu razem z
dobrymi praktykami (dekapy, bulk, pull-upy, ochrona). Dzieki temu projekt jest
poprawny "z definicji". Builder auto-numeruje referencje (R1, C1, U1...).

Przyklad:
    b = Builder("MojaPlytka")
    b.power_12v_to_5v_to_3v3("VIN", "V5", "3V3", "GND")
    b.esp32(prog_header=True)
    d = b.design
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .library import catalog
from .model import Design, Component


class Builder:
    def __init__(self, name: str):
        self.design = Design(name)
        self._counts: Dict[str, int] = {}
        # rejestr blokow (do raportu/intencji)
        self.blocks: List[str] = []

    def ref(self, prefix: str) -> str:
        self._counts[prefix] = self._counts.get(prefix, 0) + 1
        return f"{prefix}{self._counts[prefix]}"

    def add(self, prefix: str, part: str, value: str, conns: Dict[str, str],
            footprint: Optional[str] = None, label: str = "", role: str = "") -> Component:
        c = Component(self.ref(prefix), part, value,
                      footprint or catalog.default_footprint(part),
                      label=label, role=role)
        for pin, net in conns.items():
            c.connect(str(pin), net)
        return self.design.add(c)

    def relay_driver(self, gpio: str, coil_supply: str, gnd: str, out_com: str,
                     out_no: str, label: str = "") -> Component:
        """Przekaznik 230V + sterownik (tranzystor + dioda gasnaca + rezystor bazy)."""
        coil = f"_COIL_{out_no}"
        k = self.add("K", "Relay_SPDT", "SRD-12V",
                     {"1": coil_supply, "2": coil, "4": out_com, "3": out_no}, label=label, role="relay")
        self.add("Q", "Q_NPN", "BC547", {"1": f"_B_{out_no}", "2": coil, "3": gnd})  # B,C,E
        self.R("1k", gpio, f"_B_{out_no}")
        self.add("D", "D_Rectifier", "1N4148", {"1": coil, "2": coil_supply})  # dioda gasnaca
        return k

    # --- bierne pomocnicze ---
    def R(self, value, a, b):
        return self.add("R", "R", value, {"1": a, "2": b})

    def C(self, value, a, b, bulk=False):
        part = "CP" if bulk else "C"
        fp = "CP_1206" if bulk else "C_0805"
        return self.add("C", part, value, {"1": a, "2": b}, footprint=fp)

    # --- BLOKI ---
    def decoupling(self, power: str, gnd: str, count: int = 1, value="100nF"):
        """N kondensatorow odsprzegajacych 100nF miedzy szyna a masa."""
        for _ in range(count):
            self.C(value, power, gnd)
        self.blocks.append(f"decoupling x{count} {power}/{gnd}")

    def bulk_cap(self, power: str, gnd: str, value="10uF"):
        self.C(value, power, gnd, bulk=True)
        self.blocks.append(f"bulk {value} {power}/{gnd}")

    def ldo(self, vin: str, vout: str, gnd: str, part="AMS1117-3.3", value=None):
        """Regulator LDO + kondensatory wej/wyj (dobre praktyki)."""
        u = self.add("U", part, value or part,
                     {"3": vin, "1": gnd, "2": vout, "4": vout})
        self.bulk_cap(vin, gnd, "10uF")
        self.bulk_cap(vout, gnd, "10uF")
        self.C("100nF", vin, gnd)
        self.C("100nF", vout, gnd)
        self.blocks.append(f"LDO {part}: {vin}->{vout}")
        return u

    def buck_mp1584(self, vin: str, vout: str, gnd: str, r_top="100k", r_bot="20k"):
        """Przetwornica step-down MP1584 z kompletem czesci zewnetrznych."""
        sw, bst, fb = f"_SW_{vout}", f"_BST_{vout}", f"_FB_{vout}"
        u = self.add("U", "MP1584", "MP1584",
                     {"2": vin, "4": gnd, "3": sw, "1": bst, "7": vin, "5": fb})
        self.add("L", "L_power", "10uH", {"1": sw, "2": vout})
        self.add("D", "D_Schottky", "SS34", {"1": gnd, "2": sw})  # dioda zwrotna
        self.C("10nF", bst, sw)                                   # bootstrap
        self.bulk_cap(vin, gnd, "100uF")
        self.bulk_cap(vout, gnd, "47uF")
        self.C("100nF", vin, gnd)                                 # ceramik wejsciowy
        self.C("100nF", vout, gnd)                                # ceramik wyjsciowy
        self.R(r_top, vout, fb)
        self.R(r_bot, fb, gnd)
        self.blocks.append(f"buck MP1584: {vin}->{vout}")
        return u

    def input_protection(self, raw: str, prot: str, gnd: str, fuse="2A"):
        """Bezpiecznik + dioda zabezpieczenia odwrotnego + bulk."""
        mid = f"_FUSED_{prot}"
        self.add("F", "F", fuse, {"1": raw, "2": mid})
        self.add("D", "D_Schottky", "SS34", {"1": mid, "2": prot})
        self.bulk_cap(prot, gnd, "100uF")
        self.blocks.append(f"input protection {raw}->{prot}")

    def esp32(self, p3v3="3V3", gnd="GND", sda="SDA", scl="SCL",
              prog_header=True, decouple=2):
        """Modul ESP32 z obwodem EN/BOOT, dekapami i (opcjonalnie) headerem UART."""
        u = self.add("U", "ESP32-WROOM-32", "ESP32-WROOM-32",
                     {"1": gnd, "2": p3v3, "3": "EN", "15": gnd, "38": gnd,
                      "33": sda, "36": scl, "25": "IO0", "35": "TXD0", "34": "RXD0"})
        self.decoupling(p3v3, gnd, decouple)
        self.R("10k", p3v3, "EN")
        self.C("100nF", "EN", gnd)
        self.R("10k", p3v3, "IO0")
        self.add("SW", "SW_Push", "EN", {"1": "EN", "2": "EN", "3": gnd, "4": gnd})
        self.add("SW", "SW_Push", "BOOT", {"1": "IO0", "2": "IO0", "3": gnd, "4": gnd})
        if prog_header:
            self.add("J", "Header_1x06", "UART",
                     {"1": gnd, "2": p3v3, "3": "EN", "4": "IO0", "5": "TXD0", "6": "RXD0"})
        self.blocks.append("ESP32 (EN/BOOT, dekapy, UART)")
        return u

    def i2c_pullups(self, sda: str, scl: str, vcc: str, value="4.7k"):
        self.R(value, vcc, sda)
        self.R(value, vcc, scl)
        self.blocks.append(f"I2C pull-upy {sda}/{scl}")

    def onewire(self, ow: str, vcc: str, gnd: str, value="4.7k", esd=True):
        """Magistrala 1-wire: pull-up + (opcjonalnie) ochrona ESD."""
        self.R(value, vcc, ow)
        if esd:
            self.add("D", "D_TVS", "ESD", {"1": ow, "2": gnd})
        self.blocks.append(f"1-wire {ow} (pull-up{' + ESD' if esd else ''})")

    def mcp23017(self, p3v3, gnd, sda, scl, rst, intr, buttons: List[str], addr=0):
        """Ekspander I2C MCP23017 (16 IO) + dekap, adres przez A0..A2."""
        conns = {"9": p3v3, "10": gnd, "12": scl, "13": sda, "18": rst, "20": intr}
        # A0..A2 (piny 15,16,17) wg adresu
        for i, pinno in enumerate(("15", "16", "17")):
            conns[pinno] = p3v3 if (addr >> i) & 1 else gnd
        gp = [str(21 + i) for i in range(8)] + [str(1 + i) for i in range(8)]
        for pinno, net in zip(gp, buttons):
            conns[pinno] = net
        u = self.add("U", "MCP23017", "MCP23017", conns)
        self.decoupling(p3v3, gnd, 1)
        self.blocks.append(f"MCP23017 ({len(buttons)} IO)")
        return u

    def rj45_io(self, p3v3, gnd, ow, signals: List[str], label="RJ45", esd_first=True):
        """Gniazdo RJ45 jako zlacze okablowania: 3V3, GND, 1-wire i sygnaly.
        Uklad pinow: 1=3V3, 2..(N+1)=signals, OW, GND, GND. Ekran -> GND."""
        nets = ["3V3" if p3v3 == "3V3" else p3v3]
        nets = [p3v3] + signals + [ow]
        nets += [gnd] * (8 - len(nets))
        nets = nets[:8]
        conns = {str(i + 1): nets[i] for i in range(8)}
        conns["S"] = gnd
        j = self.add("J", "RJ45", label, conns, role="io")
        if esd_first:
            # osobna dioda ESD na kazda linie sygnalowa (zasada: dioda na kazde I/O)
            for net in signals:
                self.add("D", "D_TVS", "ESD", {"1": net, "2": gnd})
        self.blocks.append(f"RJ45 {label} ({len(signals)} przyciskow, ESD/linia)")
        return j

    def board_to_board(self, mapping: Dict[str, str], label="B2B", rows=2, cols=10):
        """Listwa stykowa gora-dol z zadanym mapowaniem pin->siec."""
        part = f"Header_{rows}x{cols}"
        j = self.add("J", part, label, {str(k): v for k, v in mapping.items()})
        self.blocks.append(f"board-to-board {rows}x{cols}")
        return j
