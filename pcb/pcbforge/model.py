"""Model dziedzinowy: komponenty, piny, sieci, projekt.

Reprezentacja niezalezna od KiCada. Writery (sch_writer/pcb_writer)
tlumacza ten model na pliki KiCad.
"""
from __future__ import annotations

import uuid as _uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional


def new_uuid() -> str:
    return str(_uuid.uuid4())


@dataclass
class PinDef:
    """Definicja pinu w symbolu/footprincie."""
    number: str
    name: str
    etype: str = "passive"  # passive/power_in/power_out/input/output/bidirectional/no_connect


@dataclass
class Component:
    """Instancja komponentu na schemacie i plytce."""
    ref: str                      # np. "U1", "R3"
    part: str                     # klucz w katalogu, np. "ESP32-WROOM-32"
    value: str                    # widoczna wartosc, np. "10k", "3.3V"
    footprint: str                # nazwa footprintu z biblioteki, np. "R_0805"
    # pin -> nazwa sieci
    connections: Dict[str, str] = field(default_factory=dict)
    # rozmieszczenie na plytce (mm) i obrot (deg); None = autoplacement
    x: Optional[float] = None
    y: Optional[float] = None
    rotation: float = 0.0
    side: str = "top"            # top/bottom
    # rozmieszczenie na schemacie (mm w siatce arkusza)
    sx: Optional[float] = None
    sy: Optional[float] = None
    uuid: str = field(default_factory=new_uuid)
    sch_uuid: str = field(default_factory=new_uuid)

    def connect(self, pin: str, net: str) -> "Component":
        self.connections[pin] = net
        return self


@dataclass
class Net:
    name: str
    is_power: bool = False
    is_ground: bool = False


@dataclass
class DesignRules:
    """Reguly DRC/trasowania (mm)."""
    track_width: float = 0.25
    clearance: float = 0.2
    via_diameter: float = 0.8
    via_drill: float = 0.4
    power_track_width: float = 0.5
    board_margin: float = 2.0


@dataclass
class Design:
    name: str
    components: List[Component] = field(default_factory=list)
    nets: Dict[str, Net] = field(default_factory=dict)
    rules: DesignRules = field(default_factory=DesignRules)
    # wymiary plytki (mm); None = autorozmiar po rozmieszczeniu
    board_w: Optional[float] = None
    board_h: Optional[float] = None
    uuid: str = field(default_factory=new_uuid)

    def add(self, comp: Component) -> Component:
        if any(c.ref == comp.ref for c in self.components):
            raise ValueError(f"Duplikat referencji: {comp.ref}")
        self.components.append(comp)
        return comp

    def net(self, name: str, power: bool = False, ground: bool = False) -> Net:
        if name not in self.nets:
            self.nets[name] = Net(name, is_power=power, is_ground=ground)
        return self.nets[name]

    def all_net_names(self) -> List[str]:
        names = set()
        for c in self.components:
            for n in c.connections.values():
                if n:
                    names.add(n)
        # zachowaj porzadek deterministyczny
        return sorted(names)

    def ensure_nets(self) -> None:
        """Tworzy obiekty Net dla sieci wykrytych w polaczeniach."""
        for name in self.all_net_names():
            if name not in self.nets:
                lname = name.upper()
                is_gnd = lname in ("GND", "GROUND", "VSS", "AGND", "DGND")
                is_pwr = is_gnd or lname.startswith(("VCC", "VDD", "+", "3V3", "5V", "VBUS", "VIN", "VBAT"))
                self.nets[name] = Net(name, is_power=is_pwr, is_ground=is_gnd)
