"""Baza wiedzy: uczone preferencje footprintow i reguly rozmieszczania.

Web-owy interfejs pozwala "uczyc" toolkit: gdy poprawisz footprint lub
regule rozmieszczenia, zapisuje sie tutaj i wplywa na przyszle generacje.
Persystencja: knowledge/kb.json
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

_DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "..", "knowledge", "kb.json")


@dataclass
class Knowledge:
    # part -> domyslny footprint (nadpisuje katalog)
    footprint_prefs: Dict[str, str] = field(default_factory=dict)
    # reguly rozmieszczania: {"part": "C", "rule": "near", "target_ref": "U1", "dist": 3.0}
    placement_rules: List[dict] = field(default_factory=list)
    # poziom regul projektowych: kod -> "error"/"warning"/"off"
    design_rules: Dict[str, str] = field(default_factory=dict)
    # notatki edukacyjne (wolny tekst) na przyszlosc
    notes: List[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: str = _DEFAULT_PATH) -> "Knowledge":
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls(
                footprint_prefs=data.get("footprint_prefs", {}),
                placement_rules=data.get("placement_rules", []),
                design_rules=data.get("design_rules", {}),
                notes=data.get("notes", []),
            )
        return cls()

    def save(self, path: str = _DEFAULT_PATH) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "footprint_prefs": self.footprint_prefs,
                "placement_rules": self.placement_rules,
                "design_rules": self.design_rules,
                "notes": self.notes,
            }, f, indent=2, ensure_ascii=False)

    # --- API uczenia ---
    def set_footprint(self, part: str, footprint: str) -> None:
        self.footprint_prefs[part] = footprint

    def add_placement_rule(self, part: str, rule: str, target_ref: str = "",
                           dist: float = 3.0) -> None:
        self.placement_rules.append(
            {"part": part, "rule": rule, "target_ref": target_ref, "dist": dist})

    def add_note(self, text: str) -> None:
        self.notes.append(text)

    def footprint_for(self, part: str, default: str) -> str:
        return self.footprint_prefs.get(part, default)
