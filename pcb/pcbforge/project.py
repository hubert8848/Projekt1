"""Zapis kompletnego projektu KiCad oraz orkiestracja calego przeplywu."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import List

from . import checks, freerouting, kicad, pcb_writer, rules, sch_writer
from .knowledge import Knowledge
from .model import Design
from .placement import autoplace


def _kicad_pro(name: str) -> str:
    data = {
        "board": {"design_settings": {"defaults": {}}, "layer_presets": [], "viewports": []},
        "boards": [],
        "meta": {"filename": f"{name}.kicad_pro", "version": 1},
        "net_settings": {"classes": [{"name": "Default", "clearance": 0.2,
                                      "track_width": 0.25, "via_diameter": 0.8,
                                      "via_drill": 0.4}]},
        "pcbnew": {"page_layout_descr_file": ""},
        "schematic": {"legacy_lib_dir": "", "legacy_lib_list": []},
        "sheets": [],
        "text_variables": {},
    }
    return json.dumps(data, indent=2)


@dataclass
class BuildResult:
    outdir: str
    files: List[str] = field(default_factory=list)
    erc: list = field(default_factory=list)
    drc: list = field(default_factory=list)
    rules: list = field(default_factory=list)

    @property
    def errors(self) -> int:
        return sum(1 for i in (self.erc + self.drc + self.rules) if i.severity == "error")


def build_project(design: Design, outdir: str, kb: Knowledge | None = None,
                  do_place: bool = True, do_dsn: bool = True) -> BuildResult:
    os.makedirs(outdir, exist_ok=True)
    kb = kb or Knowledge.load()

    # zastosuj uczone preferencje footprintow
    for c in design.components:
        c.footprint = kb.footprint_for(c.part, c.footprint)

    # nie ruszaj gotowego rozmieszczenia (np. uklad par plytek z layout.py)
    already_placed = design.components and all(c.x is not None for c in design.components)
    if do_place and not already_placed:
        autoplace(design, kb)

    name = design.name
    paths = []

    pro = os.path.join(outdir, f"{name}.kicad_pro")
    with open(pro, "w", encoding="utf-8") as f:
        f.write(_kicad_pro(name))
    paths.append(pro)

    sch = os.path.join(outdir, f"{name}.kicad_sch")
    with open(sch, "w", encoding="utf-8") as f:
        f.write(sch_writer.build_schematic(design, name))
    paths.append(sch)

    pcb = os.path.join(outdir, f"{name}.kicad_pcb")
    with open(pcb, "w", encoding="utf-8") as f:
        f.write(pcb_writer.build_pcb(design))
    paths.append(pcb)

    if do_dsn:
        dsn = os.path.join(outdir, f"{name}.dsn")
        freerouting.export_dsn(design, dsn)
        paths.append(dsn)

    res = BuildResult(outdir=outdir, files=paths)
    res.erc = checks.run_erc(design)
    res.drc = checks.run_drc_lite(design)
    res.rules = rules.run_rules(design, kb)
    return res


def fabricate(design: Design, outdir: str, kb: Knowledge | None = None,
              gerbers=True, step=True, kicad_checks=True) -> dict:
    """Pelny pakiet produkcyjny przez prawdziwy KiCad (jesli dostepny):
    Gerbery + wiercenia, model 3D STEP oraz ERC/DRC (KiCad >=8)."""
    res = build_project(design, outdir, kb=kb)
    report = {"build": res, "kicad": kicad.version(), "outputs": {}}
    if not kicad.available():
        report["note"] = "kicad-cli niedostepny - tylko pliki + kontrole wbudowane"
        return report

    sch = os.path.join(outdir, f"{design.name}.kicad_sch")
    pcb = os.path.join(outdir, f"{design.name}.kicad_pcb")
    if kicad_checks:
        report["outputs"]["erc"] = kicad.run_erc(sch)
        report["outputs"]["drc"] = kicad.run_drc(pcb)
    if gerbers:
        report["outputs"]["gerbers"] = kicad.export_gerbers(pcb, os.path.join(outdir, "gerbers"))
    if step:
        report["outputs"]["step"] = kicad.export_step(pcb, os.path.join(outdir, f"{design.name}.step"))
    report["outputs"]["svg"] = kicad.export_svg(pcb, os.path.join(outdir, f"{design.name}_kicad.svg"))
    return report
