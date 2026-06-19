"""pcbforge - generator projektow KiCad (schemat + PCB) z autoroutingiem.

Przeplyw A-Z:
  opis ukladu -> Design (model) -> schemat .kicad_sch (bez bledow ERC)
  -> PCB .kicad_pcb z footprintami i rozmieszczeniem -> DSN dla Freerouting
  -> (import .ses w KiCad) -> gotowa plytka.
"""
from .model import Design, Component, Net, DesignRules, PinDef
from .project import build_project, BuildResult
from .knowledge import Knowledge
from . import checks, freerouting

__all__ = [
    "Design", "Component", "Net", "DesignRules", "PinDef",
    "build_project", "BuildResult", "Knowledge", "checks", "freerouting",
]
__version__ = "0.1.0"
