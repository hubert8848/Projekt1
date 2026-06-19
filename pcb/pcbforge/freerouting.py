"""Integracja z autorouterem Freerouting.

1. export_dsn(design)  -> plik Specctra .dsn (konwencja jak w KiCad: um*10, Y ujemne)
2. run_freerouting()   -> uruchamia freerouting.jar i produkuje .ses
Import .ses do projektu: w KiCad PCB Editor -> File -> Import -> Specctra Session.
(Trzymamy sie tej sciezki, bo SES->tracks robi KiCad niezawodnie jednym klikiem.)
"""
from __future__ import annotations

import os
import shutil
import subprocess
from typing import Dict, List, Tuple

from .library import catalog, footprints
from .library.footprints import Footprint, Pad
from .model import Design, Component

SCALE = 10000  # mm -> jednostki DSN (um*10), jak w KiCad


def _fp(c: Component) -> Footprint:
    part = catalog.get_part(c.part)
    if "header" in part:
        rows, cols = part["header"]
        return footprints.header_fp(rows * cols, rows)
    return footprints.get(part["footprint"])


def _xy(x: float, y: float) -> Tuple[int, int]:
    return int(round(x * SCALE)), int(round(-y * SCALE))


def _padstack_key(pad: Pad) -> str:
    if pad.pad_type == "thru_hole":
        return f"Th_{pad.shape}_{pad.w:.3f}x{pad.h:.3f}_d{pad.drill:.3f}".replace(".", "_")
    return f"Smd_{pad.shape}_{pad.w:.3f}x{pad.h:.3f}".replace(".", "_")


def _pad_shape_lines(pad: Pad, layer: str) -> str:
    w = int(round(pad.w * SCALE)); h = int(round(pad.h * SCALE))
    if pad.shape == "circle":
        return f"(shape (circle {layer} {w}))"
    # rect/roundrect/oval -> prostokat (konserwatywnie)
    return f"(shape (rect {layer} {-w//2} {-h//2} {w//2} {h//2}))"


def export_dsn(design: Design, path: str) -> str:
    design.ensure_nets()
    rules = design.rules
    width = int(rules.track_width * SCALE)
    clear = int(rules.clearance * SCALE)
    via_d = int(rules.via_diameter * SCALE)
    via_dr = int(rules.via_drill * SCALE)
    via_name = f"Via_{via_d}_{via_dr}"

    bw = (design.board_w or 80.0)
    bh = (design.board_h or 60.0)
    bx0, by0 = _xy(0, 0)
    bx1, by1 = _xy(bw, bh)

    out: List[str] = []
    a = out.append
    a(f'(pcb {_q(design.name)}.dsn')
    a('  (parser')
    a('    (string_quote ")')
    a('    (space_in_quoted_tokens on)')
    a('    (host_cad "pcbforge")')
    a('    (host_version "1.0")')
    a('  )')
    a('  (resolution um 10)')
    a('  (unit um)')
    a('  (structure')
    a('    (layer F.Cu (type signal) (property (index 0)))')
    a('    (layer B.Cu (type signal) (property (index 1)))')
    a(f'    (boundary (path pcb 0  {bx0} {by0}  {bx1} {by0}  {bx1} {by1}  {bx0} {by1}  {bx0} {by0}))')
    a(f'    (via "{via_name}")')
    a(f'    (rule (width {width}) (clearance {clear}) (clearance {clear} (type default_smd)) (clearance {clear} (type smd_smd)))')
    a('  )')

    # placement
    a('  (placement')
    by_part: Dict[str, List[Component]] = {}
    for c in design.components:
        by_part.setdefault(_fp(c).name, []).append(c)
    for fpname, comps in by_part.items():
        a(f'    (component {_q(fpname)}')
        for c in comps:
            x, y = _xy(c.x or 0, c.y or 0)
            side = "front" if c.side == "top" else "back"
            a(f'      (place {_q(c.ref)} {x} {y} {side} {int(c.rotation)})')
        a('    )')
    a('  )')

    # library: obrazy + padstacki
    a('  (library')
    padstacks: Dict[str, Pad] = {}
    seen_images = set()
    for c in design.components:
        fp = _fp(c)
        if fp.name in seen_images:
            for pad in fp.pads:
                padstacks.setdefault(_padstack_key(pad), pad)
            continue
        seen_images.add(fp.name)
        a(f'    (image {_q(fp.name)}')
        for pad in fp.pads:
            key = _padstack_key(pad)
            padstacks.setdefault(key, pad)
            px, py = _xy(pad.x, pad.y)
            a(f'      (pin {_q(key)} {_q(pad.number)} {px} {py})')
        a('    )')
    for key, pad in padstacks.items():
        if pad.pad_type == "thru_hole":
            shapes = _pad_shape_lines(pad, "F.Cu") + " " + _pad_shape_lines(pad, "B.Cu")
        else:
            shapes = _pad_shape_lines(pad, "F.Cu")
        a(f'    (padstack {_q(key)} {shapes} (attach off))')
    # padstack przelotki
    a(f'    (padstack "{via_name}" (shape (circle F.Cu {via_d})) (shape (circle B.Cu {via_d})) (attach off))')
    a('  )')

    # network
    a('  (network')
    net_pins: Dict[str, List[str]] = {}
    for c in design.components:
        for pin, net in c.connections.items():
            if net:
                net_pins.setdefault(net, []).append(f"{c.ref}-{pin}")
    for net in sorted(net_pins):
        pins = " ".join(net_pins[net])
        a(f'    (net {_q(net)} (pins {pins}))')
    mains = sorted(n for n in net_pins if n in design.mains_nets)
    normal = sorted(n for n in net_pins if n not in design.mains_nets)
    # klasa domyslna
    if normal:
        a(f'    (class kicad_default "" {" ".join(_q(n) for n in normal)}')
        a(f'      (circuit (use_via "{via_name}"))')
        a(f'      (rule (width {width}) (clearance {clear}))')
        a('    )')
    # klasa 230V: grubsze sciezki + wieksza izolacja (creepage)
    if mains:
        mw = int(rules.mains_track_width * SCALE)
        mc = int(rules.mains_clearance * SCALE)
        a(f'    (class mains "" {" ".join(_q(n) for n in mains)}')
        a(f'      (circuit (use_via "{via_name}"))')
        a(f'      (rule (width {mw}) (clearance {mc}))')
        a('    )')
    a('  )')
    a('  (wiring)')
    a(')')

    text = "\n".join(out) + "\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def _q(s: str) -> str:
    return f'"{s}"'


# ---------------------------------------------------------------------------
# Uruchamianie Freerouting
# ---------------------------------------------------------------------------
def find_jar() -> str | None:
    env = os.environ.get("FREEROUTING_JAR")
    if env and os.path.exists(env):
        return env
    for cand in ("freerouting.jar", "freerouting-executable.jar",
                 os.path.expanduser("~/freerouting.jar")):
        if os.path.exists(cand):
            return cand
    return None


def run_freerouting(dsn_path: str, ses_path: str, passes: int = 10,
                    jar: str | None = None) -> Tuple[bool, str]:
    jar = jar or find_jar()
    if not jar:
        return False, ("Nie znaleziono freerouting.jar. Ustaw FREEROUTING_JAR=/sciezka/freerouting.jar "
                       "lub pobierz z https://github.com/freerouting/freerouting/releases")
    if not shutil.which("java"):
        return False, "Brak java w PATH (Freerouting wymaga Javy)."
    # CLI roznych wersji Freerouting: probujemy nowy i stary zestaw flag
    attempts = [
        ["java", "-jar", jar, "-de", dsn_path, "-do", ses_path, "-mp", str(passes)],
        ["java", "-jar", jar, "-de", dsn_path, "-do", ses_path],
    ]
    last = ""
    for cmd in attempts:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            last = (r.stdout or "") + (r.stderr or "")
            if os.path.exists(ses_path) and os.path.getsize(ses_path) > 0:
                return True, last
        except subprocess.TimeoutExpired:
            last = "Freerouting przekroczyl limit czasu (600 s)."
        except Exception as e:  # pragma: no cover
            last = str(e)
    return os.path.exists(ses_path), last
