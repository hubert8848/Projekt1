"""Deklaratywny opis plytki (dict / YAML / JSON) <-> Design.

Pozwala definiowac plytki bez kodu - np. z formularza web albo pliku YAML.
Format:
  name: Moja_Plytka
  rules: {track_width: 0.25, clearance: 0.2}
  components:
    - ref: U1
      part: ESP32-WROOM-32
      value: ESP32-WROOM-32
      footprint: ESP32-WROOM-32   # opcjonalne; domyslny z katalogu
      connections: {"1": GND, "2": 3V3}
"""
from __future__ import annotations

import json
from typing import Any, Dict

from .library import catalog
from .model import Design, Component


def load_design(data: Dict[str, Any]) -> Design:
    d = Design(data["name"])
    r = data.get("rules", {})
    for k, v in r.items():
        if hasattr(d.rules, k):
            setattr(d.rules, k, float(v))
    for cd in data.get("components", []):
        part = cd["part"]
        comp = Component(
            ref=cd["ref"],
            part=part,
            value=cd.get("value", part),
            footprint=cd.get("footprint", catalog.default_footprint(part)),
            label=cd.get("label", ""),
            x=cd.get("x"), y=cd.get("y"),
            rotation=cd.get("rotation", 0.0),
            side=cd.get("side", "top"),
            pinned=cd.get("pinned", False),
            role=cd.get("role", ""),
        )
        for pin, net in cd.get("connections", {}).items():
            comp.connect(str(pin), net)
        d.add(comp)
    if data.get("outline"):
        d.outline = tuple(data["outline"])
    d.board_w = data.get("board_w")
    d.board_h = data.get("board_h")
    d.mains_nets = set(data.get("mains_nets", []))
    d.notes = data.get("notes", [])
    return d


def dump_design(design: Design) -> Dict[str, Any]:
    def comp(c):
        d = {"ref": c.ref, "part": c.part, "value": c.value,
             "footprint": c.footprint, "connections": dict(c.connections)}
        if c.label:
            d["label"] = c.label
        if c.x is not None:
            d.update(x=c.x, y=c.y, rotation=c.rotation, side=c.side,
                     pinned=c.pinned, role=c.role)
        return d

    out = {
        "name": design.name,
        "rules": {
            "track_width": design.rules.track_width,
            "clearance": design.rules.clearance,
            "via_diameter": design.rules.via_diameter,
            "via_drill": design.rules.via_drill,
            "mains_track_width": design.rules.mains_track_width,
            "mains_clearance": design.rules.mains_clearance,
        },
        "components": [comp(c) for c in design.components],
    }
    if design.outline:
        out["outline"] = list(design.outline)
    if design.board_w:
        out["board_w"], out["board_h"] = design.board_w, design.board_h
    if design.mains_nets:
        out["mains_nets"] = sorted(design.mains_nets)
    if design.notes:
        out["notes"] = design.notes
    return out


def load_yaml(path: str) -> Design:
    import yaml  # opcjonalna zaleznosc
    with open(path, "r", encoding="utf-8") as f:
        return load_design(yaml.safe_load(f))


def load_json(path: str) -> Design:
    with open(path, "r", encoding="utf-8") as f:
        return load_design(json.load(f))
