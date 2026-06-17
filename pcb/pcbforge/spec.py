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
        default_fp = catalog.get_part(part)["footprint"] if "header" not in catalog.get_part(part) \
            else f"Header_{catalog.get_part(part)['header'][0]}x{catalog.get_part(part)['header'][1]:02d}"
        comp = Component(
            ref=cd["ref"],
            part=part,
            value=cd.get("value", part),
            footprint=cd.get("footprint", default_fp),
        )
        for pin, net in cd.get("connections", {}).items():
            comp.connect(str(pin), net)
        d.add(comp)
    return d


def dump_design(design: Design) -> Dict[str, Any]:
    return {
        "name": design.name,
        "rules": {
            "track_width": design.rules.track_width,
            "clearance": design.rules.clearance,
            "via_diameter": design.rules.via_diameter,
            "via_drill": design.rules.via_drill,
        },
        "components": [
            {
                "ref": c.ref,
                "part": c.part,
                "value": c.value,
                "footprint": c.footprint,
                "connections": dict(c.connections),
            }
            for c in design.components
        ],
    }


def load_yaml(path: str) -> Design:
    import yaml  # opcjonalna zaleznosc
    with open(path, "r", encoding="utf-8") as f:
        return load_design(yaml.safe_load(f))


def load_json(path: str) -> Design:
    with open(path, "r", encoding="utf-8") as f:
        return load_design(json.load(f))
