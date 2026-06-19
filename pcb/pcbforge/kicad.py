"""Integracja z prawdziwym KiCad (kicad-cli), jesli dostepny w srodowisku.

Gdy kicad-cli jest zainstalowany, mozemy uruchomic PRAWDZIWE ERC/DRC, wygenerowac
Gerbery + wiercenia, eksport SVG/PNG i model STEP 3D. Bez KiCada toolkit dziala
dalej na wbudowanych kontrolach (checks.py) - degradacja jest lagodna.

Instalacja w sesji web: hook .claude/hooks/session_start (instaluje kicad).
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import List, Optional


def cli() -> Optional[str]:
    return shutil.which("kicad-cli")


def available() -> bool:
    return cli() is not None


def version() -> str:
    if not available():
        return ""
    try:
        r = subprocess.run([cli(), "version"], capture_output=True, text=True, timeout=30)
        return (r.stdout or r.stderr).strip()
    except Exception:
        return ""


def major() -> int:
    v = version()
    try:
        return int(v.split(".")[0])
    except Exception:
        return 0


def supports_erc_drc() -> bool:
    """ERC/DRC z linii polecen dodano w KiCad 8."""
    return major() >= 8


def _run(args: List[str], timeout=300) -> subprocess.CompletedProcess:
    return subprocess.run([cli()] + args, capture_output=True, text=True, timeout=timeout)


@dataclass
class KiCadResult:
    ok: bool
    log: str = ""
    artifacts: List[str] = field(default_factory=list)


def run_erc(sch_path: str, out_json: Optional[str] = None) -> KiCadResult:
    if not available():
        return KiCadResult(False, "kicad-cli niedostepny")
    if not supports_erc_drc():
        return KiCadResult(False, f"ERC z CLI wymaga KiCad 8 (masz {version()}) - uzyto kontroli wbudowanych")
    out_json = out_json or os.path.splitext(sch_path)[0] + "_erc.json"
    r = _run(["sch", "erc", "--format", "json", "--output", out_json,
              "--exit-code-violations", sch_path])
    log = (r.stdout or "") + (r.stderr or "")
    return KiCadResult(r.returncode == 0, log, [out_json] if os.path.exists(out_json) else [])


def run_drc(pcb_path: str, out_json: Optional[str] = None) -> KiCadResult:
    if not available():
        return KiCadResult(False, "kicad-cli niedostepny")
    if not supports_erc_drc():
        return KiCadResult(False, f"DRC z CLI wymaga KiCad 8 (masz {version()}) - uzyto kontroli wbudowanych")
    out_json = out_json or os.path.splitext(pcb_path)[0] + "_drc.json"
    r = _run(["pcb", "drc", "--format", "json", "--output", out_json,
              "--exit-code-violations", pcb_path])
    log = (r.stdout or "") + (r.stderr or "")
    return KiCadResult(r.returncode == 0, log, [out_json] if os.path.exists(out_json) else [])


def export_gerbers(pcb_path: str, outdir: str) -> KiCadResult:
    if not available():
        return KiCadResult(False, "kicad-cli niedostepny")
    os.makedirs(outdir, exist_ok=True)
    r1 = _run(["pcb", "export", "gerbers", "--output", outdir, pcb_path])
    r2 = _run(["pcb", "export", "drill", "--output", outdir, pcb_path])
    log = "".join([r1.stdout or "", r1.stderr or "", r2.stdout or "", r2.stderr or ""])
    arts = [os.path.join(outdir, f) for f in os.listdir(outdir)] if os.path.isdir(outdir) else []
    return KiCadResult(r1.returncode == 0, log, arts)


def export_svg(pcb_path: str, out_svg: str, layers="F.Cu,B.Cu,Edge.Cuts,F.SilkS") -> KiCadResult:
    if not available():
        return KiCadResult(False, "kicad-cli niedostepny")
    r = _run(["pcb", "export", "svg", "--output", out_svg, "--layers", layers, pcb_path])
    return KiCadResult(os.path.exists(out_svg), (r.stdout or "") + (r.stderr or ""),
                       [out_svg] if os.path.exists(out_svg) else [])


def export_step(pcb_path: str, out_step: str) -> KiCadResult:
    if not available():
        return KiCadResult(False, "kicad-cli niedostepny")
    r = _run(["pcb", "export", "step", "--output", out_step, pcb_path])
    return KiCadResult(os.path.exists(out_step), (r.stdout or "") + (r.stderr or ""),
                       [out_step] if os.path.exists(out_step) else [])


def summarize_violations(json_path: str) -> str:
    """Czytelne podsumowanie raportu ERC/DRC z JSON kicad-cli."""
    import json
    if not os.path.exists(json_path):
        return "(brak raportu)"
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    viols = data.get("violations", [])
    if not viols:
        return "✓ Brak naruszen."
    lines = []
    for v in viols[:50]:
        lines.append(f"  [{v.get('severity','?')}] {v.get('type','?')}: {v.get('description','')}")
    return f"{len(viols)} naruszen:\n" + "\n".join(lines)
