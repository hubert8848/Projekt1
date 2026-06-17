"""Silnik regul projektowych - wymusza dobre praktyki i Twoje preferencje.

Rozni sie od checks.py (ERC): tam sprawdzamy spojnosc elektryczna, tu - czy
projekt spelnia zasady dobrej praktyki, ktore chcesz zawsze stosowac:
  - kazdy IC ma kondensator odsprzegajacy do masy,
  - kazda szyna z regulatora ma kondensator bulk,
  - I2C ma pull-upy, 1-wire ma pull-up,
  - kazdy pin zasilania jest podlaczony.
Poziom (error/warning/off) mozna nadpisac w bazie wiedzy (kb.design_rules).
"""
from __future__ import annotations

from typing import Dict, List, Set

from .checks import Issue
from .knowledge import Knowledge
from .library import catalog
from .model import Design

# domyslny poziom waznosci dla regul
_DEFAULT_SEVERITY = {
    "DECOUPLING": "warning",
    "BULK_CAP": "warning",
    "I2C_PULLUP": "warning",
    "ONEWIRE_PULLUP": "warning",
    "POWER_PIN_OPEN": "error",
}


def _pin_types(part: str) -> Dict[str, str]:
    try:
        sd = catalog.get_part(part)["symbol"]
    except KeyError:
        return {}
    return {p.number: p.etype for p in sd.pins}


def _ground_nets(design: Design) -> Set[str]:
    design.ensure_nets()
    return {n for n, net in design.nets.items() if net.is_ground}


def _caps_between(design: Design, net: str, gnds: Set[str], parts=("C",)) -> bool:
    for c in design.components:
        if c.part not in parts:
            continue
        vals = set(c.connections.values())
        if net in vals and vals & gnds:
            return True
    return False


def _res_from(design: Design, net: str, power_nets: Set[str]) -> bool:
    for c in design.components:
        if c.part != "R":
            continue
        vals = set(c.connections.values())
        if net in vals and vals & power_nets:
            return True
    return False


def run_rules(design: Design, kb: Knowledge | None = None) -> List[Issue]:
    kb = kb or Knowledge()
    design.ensure_nets()
    sev = dict(_DEFAULT_SEVERITY)
    sev.update(getattr(kb, "design_rules", {}) or {})
    issues: List[Issue] = []
    gnds = _ground_nets(design)
    power_nets = {n for n, net in design.nets.items() if net.is_power and not net.is_ground}

    def emit(code, msg):
        s = sev.get(code, "warning")
        if s != "off":
            issues.append(Issue(s, code, msg))

    # zbierz info o IC
    ic_power_in: Dict[str, Set[str]] = {}   # ref -> sieci power_in (bez masy)
    reg_outputs: Set[str] = set()           # sieci bedace wyjsciem regulatora
    for c in design.components:
        types = _pin_types(c.part)
        if not types:
            continue
        is_ic = c.ref.startswith("U")
        for pin, et in types.items():
            net = c.connections.get(pin)
            if not net:
                # niepodlaczony pin zasilania
                if et in ("power_in", "power_out") and is_ic:
                    emit("POWER_PIN_OPEN", f"{c.ref}: pin {pin} ({et}) niepodlaczony")
                continue
            if et == "power_in" and net not in gnds and is_ic:
                ic_power_in.setdefault(c.ref, set()).add(net)
            if et == "power_out" and net not in gnds:
                reg_outputs.add(net)

    # 1) dekapy przy kazdym IC
    for ref, nets in ic_power_in.items():
        for net in nets:
            if not _caps_between(design, net, gnds, parts=("C",)):
                emit("DECOUPLING", f"{ref}: brak kondensatora odsprzegajacego na {net} (zalecane 100nF do masy)")

    # 2) bulk na wyjsciach regulatorow
    for net in sorted(reg_outputs):
        if not _caps_between(design, net, gnds, parts=("CP",)):
            emit("BULK_CAP", f"Szyna {net}: brak kondensatora bulk (CP) do masy")

    # 3) pull-upy I2C
    for c in design.components:
        for pin, net in c.connections.items():
            up = net.upper()
            if up in ("SDA", "SCL") and not _res_from(design, net, power_nets):
                emit("I2C_PULLUP", f"Siec I2C {net}: brak pull-upu do zasilania")
    # 4) pull-up 1-wire
    onewire = {n for n in design.all_net_names() if n.upper() in ("OW", "ONEWIRE", "1WIRE", "DQ") or n.upper().startswith("OW")}
    for net in sorted(onewire):
        if not _res_from(design, net, power_nets):
            emit("ONEWIRE_PULLUP", f"1-wire {net}: brak pull-upu (zalecane 4.7k do zasilania)")

    # deduplikacja
    seen = set()
    uniq = []
    for i in issues:
        k = (i.code, i.message)
        if k not in seen:
            seen.add(k)
            uniq.append(i)
    return uniq
