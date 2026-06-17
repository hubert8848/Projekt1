"""Generator pliku plytki .kicad_pcb (format KiCad 7, version 20221018).

Netlista jest jawna: kazdy pad odwoluje sie do indeksu sieci, a tabela
(net N "nazwa") jest na poczatku pliku. Footprinty generowane z biblioteki
proceduralnej (pcbforge.library.footprints).
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from .library import catalog, footprints
from .library.footprints import Footprint, Pad
from .model import Design, Component, new_uuid
from .sexpr import S, Sym

PCB_VERSION = 20221018

_LAYERS = [
    (0, "F.Cu", "signal", None), (31, "B.Cu", "signal", None),
    (32, "B.Adhes", "user", "B.Adhesive"), (33, "F.Adhes", "user", "F.Adhesive"),
    (34, "B.Paste", "user", None), (35, "F.Paste", "user", None),
    (36, "B.SilkS", "user", "B.Silkscreen"), (37, "F.SilkS", "user", "F.Silkscreen"),
    (38, "B.Mask", "user", None), (39, "F.Mask", "user", None),
    (40, "Dwgs.User", "user", "User.Drawings"), (41, "Cmts.User", "user", "User.Comments"),
    (42, "Eco1.User", "user", "User.Eco1"), (43, "Eco2.User", "user", "User.Eco2"),
    (44, "Edge.Cuts", "user", None), (45, "Margin", "user", None),
    (46, "B.CrtYd", "user", "B.Courtyard"), (47, "F.CrtYd", "user", "F.Courtyard"),
    (48, "B.Fab", "user", None), (49, "F.Fab", "user", None),
]


def _get_footprint(c: Component) -> Footprint:
    part = catalog.get_part(c.part)
    if "header" in part:
        rows, cols = part["header"]
        return footprints.header_fp(rows * cols, rows)
    return footprints.get(part["footprint"])


def build_pcb(design: Design) -> str:
    design.ensure_nets()
    # mapa sieci -> indeks (0 zarezerwowane dla braku sieci)
    net_index: Dict[str, int] = {"": 0}
    for i, name in enumerate(design.all_net_names(), start=1):
        net_index[name] = i

    root = S("kicad_pcb")
    root.add(S("version", PCB_VERSION))
    root.add(S("generator", Sym("pcbnew")))
    root.add(S("general", S("thickness", 1.6)))
    root.add(S("paper", "A4"))

    layers = S("layers")
    for (idx, name, ltype, alias) in _LAYERS:
        if alias:
            layers.add(S(str(idx), name, Sym(ltype), alias))
        else:
            layers.add(S(str(idx), name, Sym(ltype)))
    root.add(layers)

    root.add(S("setup", S("pad_to_mask_clearance", 0)))

    # tabela sieci
    for name, idx in sorted(net_index.items(), key=lambda kv: kv[1]):
        root.add(S("net", idx, name))

    # footprinty
    for c in design.components:
        fp = _get_footprint(c)
        root.add(_render_footprint(c, fp, net_index, design.name))

    # obrys plytki
    w, h = _board_size(design)
    root.add(*_board_outline(w, h, design.rules.board_margin))

    return root.render(indent=2) + "\n"


def _render_footprint(c: Component, fp: Footprint, net_index: Dict[str, int], project: str) -> S:
    x = c.x if c.x is not None else 0.0
    y = c.y if c.y is not None else 0.0
    layer = "F.Cu" if c.side == "top" else "B.Cu"
    f = S("footprint", f"pcbforge:{fp.name}", S("layer", layer))
    f.add(S("tstamp", c.uuid))
    if c.rotation:
        f.add(S("at", x, y, c.rotation))
    else:
        f.add(S("at", x, y))
    f.add(S("descr", fp.description))
    f.add(S("attr", Sym("smd") if fp.smd else Sym("through_hole")))

    # teksty
    f.add(S("fp_text", Sym("reference"), c.ref,
            S("at", 0, -(fp.body_h + 0.8), 0), S("layer", "F.SilkS"),
            S("tstamp", new_uuid()),
            S("effects", S("font", S("size", 1, 1), S("thickness", 0.15)))))
    f.add(S("fp_text", Sym("value"), c.value,
            S("at", 0, fp.body_h + 0.8, 0), S("layer", "F.Fab"),
            S("tstamp", new_uuid()),
            S("effects", S("font", S("size", 1, 1), S("thickness", 0.15)))))

    # kontur silk + courtyard
    bw, bh = fp.body_w, fp.body_h
    for layer_name, width in (("F.SilkS", 0.12), ("F.CrtYd", 0.05)):
        corners = [(-bw, -bh), (bw, -bh), (bw, bh), (-bw, bh), (-bw, -bh)]
        for (x1, y1), (x2, y2) in zip(corners, corners[1:]):
            f.add(S("fp_line", S("start", x1, y1), S("end", x2, y2),
                    S("stroke", S("width", width), S("type", Sym("solid"))),
                    S("layer", layer_name), S("tstamp", new_uuid())))

    # pady
    for pad in fp.pads:
        net_name = c.connections.get(pad.number, "")
        f.add(_render_pad(pad, net_index.get(net_name, 0), net_name))
    return f


def _render_pad(pad: Pad, net_idx: int, net_name: str) -> S:
    ptype = Sym("smd") if pad.pad_type == "smd" else Sym("thru_hole")
    shape_map = {"roundrect": "roundrect", "rect": "rect", "circle": "circle", "oval": "oval"}
    shape = Sym(shape_map.get(pad.shape, "roundrect"))
    p = S("pad", pad.number, ptype, shape)
    if pad.rot:
        p.add(S("at", pad.x, pad.y, pad.rot))
    else:
        p.add(S("at", pad.x, pad.y))
    p.add(S("size", pad.w, pad.h))
    if pad.pad_type == "thru_hole":
        p.add(S("drill", pad.drill))
    p.add(S("layers", *[name for name in pad.layers]))
    if pad.shape == "roundrect":
        p.add(S("roundrect_rratio", 0.25))
    if net_idx > 0 and net_name:
        p.add(S("net", net_idx, net_name))
    p.add(S("tstamp", new_uuid()))
    return p


def _board_size(design: Design) -> Tuple[float, float]:
    if design.board_w and design.board_h:
        return design.board_w, design.board_h
    xs, ys = [], []
    for c in design.components:
        if c.x is None or c.y is None:
            continue
        fp = _get_footprint(c)
        xs += [c.x - fp.body_w, c.x + fp.body_w]
        ys += [c.y - fp.body_h, c.y + fp.body_h]
    if not xs:
        return 80.0, 60.0
    return (max(xs) - min(xs)) + 10, (max(ys) - min(ys)) + 10


def _board_outline(w: float, h: float, margin: float) -> List[S]:
    # obrys wokol (0,0)..(w,h) z marginesem; komponenty rozmieszczane wewnatrz
    x0, y0 = 0.0, 0.0
    x1, y1 = w, h
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
    out = []
    for (ax, ay), (bx, by) in zip(corners, corners[1:]):
        out.append(S("gr_line", S("start", ax, ay), S("end", bx, by),
                     S("stroke", S("width", 0.1), S("type", Sym("default"))),
                     S("layer", "Edge.Cuts"), S("tstamp", new_uuid())))
    return out
