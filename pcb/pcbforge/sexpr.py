"""Minimalny budowniczy i parser S-expression (format plikow KiCad).

KiCad zapisuje schematy (.kicad_sch) i plytki (.kicad_pcb) w notacji
S-expression. Tu mamy lekki serializer (do generowania) oraz parser
(do walidacji round-trip i kontroli zbilansowania nawiasow).
"""
from __future__ import annotations

import math
from typing import Iterable, List, Union

Atom = Union[str, int, float, "Sym", "SExpr"]


class Sym(str):
    """Symbol/token bez cudzyslowow (np. yes, no, default, R)."""
    __slots__ = ()


def num(value: float) -> str:
    """Formatuje liczbe tak jak KiCad: bez zbednych zer, kropka dziesietna."""
    if isinstance(value, int) or (isinstance(value, float) and value.is_integer()):
        return str(int(value))
    return ("%f" % value).rstrip("0").rstrip(".")


def quote(s: str) -> str:
    out = s.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{out}"'


class SExpr:
    """Wezel S-expression: (head child child ...)."""

    __slots__ = ("head", "items")

    def __init__(self, head: str, *items: Atom):
        self.head = head
        self.items: List[Atom] = list(items)

    def add(self, *items: Atom) -> "SExpr":
        self.items.extend(items)
        return self

    def render(self, indent: int = 0, level: int = 0) -> str:
        pad = " " * (indent * level)
        inline = not any(isinstance(it, SExpr) for it in self.items)
        if inline:
            inner = " ".join(self._atom(it) for it in self.items)
            sep = " " if inner else ""
            return f"{pad}({self.head}{sep}{inner})"
        # tryb wielolinijkowy: kazdy element w osobnej linii z wcieciem
        lines = []
        for it in self.items:
            if isinstance(it, SExpr):
                lines.append(it.render(indent, level + 1))
            else:
                lines.append(" " * (indent * (level + 1)) + self._atom(it))
        body = "\n".join(lines)
        return f"{pad}({self.head}\n{body}\n{pad})"

    def _atom(self, it: Atom) -> str:
        if isinstance(it, SExpr):
            return it.render(0, 0)
        if isinstance(it, Sym):
            return str(it)
        if isinstance(it, bool):
            return "yes" if it else "no"
        if isinstance(it, (int, float)):
            return num(it)
        return quote(str(it))

    def __str__(self) -> str:  # pragma: no cover - wygoda
        return self.render(indent=2)


def S(head: str, *items: Atom) -> SExpr:
    return SExpr(head, *items)


# ---------------------------------------------------------------------------
# Parser (uzywany w testach/walidacji)
# ---------------------------------------------------------------------------
def parse(text: str):
    """Parsuje S-expression do zagniezdzonych list. Rzuca ValueError przy
    niezbilansowanych nawiasach -> wykrywa uszkodzone pliki."""
    tokens = _tokenize(text)
    pos = 0
    result, pos = _parse_list(tokens, pos)
    # pomijamy ewentualne biale tokeny na koncu
    if pos != len(tokens):
        # moze byc wiele top-level? KiCad ma jeden korzen
        rest = tokens[pos:]
        if any(t not in ("",) for t in rest):
            raise ValueError(f"Niezbilansowane wyrazenie: zostalo {len(rest)} tokenow")
    return result


def _tokenize(text: str) -> List[str]:
    tokens: List[str] = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
            continue
        if c in "()":
            tokens.append(c)
            i += 1
            continue
        if c == '"':
            j = i + 1
            buf = []
            while j < n:
                if text[j] == "\\" and j + 1 < n:
                    buf.append(text[j + 1])
                    j += 2
                    continue
                if text[j] == '"':
                    break
                buf.append(text[j])
                j += 1
            tokens.append('"' + "".join(buf))  # prefiks " oznacza string
            i = j + 1
            continue
        j = i
        while j < n and text[j] not in " \t\r\n()":
            j += 1
        tokens.append(text[i:j])
        i = j
    return tokens


def _parse_list(tokens: List[str], pos: int):
    if tokens[pos] != "(":
        raise ValueError("Oczekiwano '('")
    pos += 1
    out: list = []
    while pos < len(tokens):
        t = tokens[pos]
        if t == "(":
            sub, pos = _parse_list(tokens, pos)
            out.append(sub)
        elif t == ")":
            return out, pos + 1
        else:
            out.append(t)
            pos += 1
    raise ValueError("Brak zamykajacego ')'")
