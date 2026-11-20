"""Minimal reader for IFC STEP text files (ISO 10303-21). Standard library only."""

from __future__ import annotations

import re
from dataclasses import dataclass

ENTITY = re.compile(r"#(\d+)\s*=\s*([A-Za-z0-9_]+)\s*\((.*)\)\s*$", re.S)
TOKEN = re.compile(r"[^,()\s]+")


@dataclass
class Entity:
    id: int
    type: str
    args: list


class _Parser:
    def __init__(self, raw: str):
        self.raw = raw
        self.pos = 0

    def skip(self) -> None:
        while self.pos < len(self.raw) and self.raw[self.pos].isspace():
            self.pos += 1

    def value(self):
        self.skip()
        ch = self.raw[self.pos]
        if ch == "(":
            return self.list()
        if ch == "'":
            return self.string()
        tok = TOKEN.match(self.raw, self.pos)
        text = tok.group(0)
        self.pos = tok.end()
        if self.pos < len(self.raw) and self.raw[self.pos] == "(":
            inner = self.list()  # typed value such as IFCLABEL('x')
            return inner[0] if len(inner) == 1 else inner
        if text == "$":
            return None
        if text.startswith("#"):
            return ("ref", int(text[1:]))
        if re.fullmatch(r"-?\d+", text):
            return int(text)
        if re.fullmatch(r"-?\d*\.\d*([eE][-+]?\d+)?|-?\d+[eE][-+]?\d+", text):
            return float(text)
        return text.strip(".")

    def string(self) -> str:
        self.pos += 1
        buf = []
        while True:
            ch = self.raw[self.pos]
            if ch == "'":
                if self.raw[self.pos + 1:self.pos + 2] == "'":
                    buf.append("'")
                    self.pos += 2
                    continue
                self.pos += 1
                return "".join(buf)
            buf.append(ch)
            self.pos += 1

    def list(self) -> list:
        self.pos += 1
        items = []
        while True:
            self.skip()
            if self.raw[self.pos] == ")":
                self.pos += 1
                return items
            items.append(self.value())
            self.skip()
            if self.raw[self.pos] == ",":
                self.pos += 1


def parse_args(raw: str) -> list:
    """Parse the text between the outer parentheses of an entity into a list."""
    return _Parser("(" + raw + ")").list()


def split_statements(text: str) -> list[str]:
    """Return the statements of the DATA section, splitting on ';' outside strings."""
    upper = text.upper()
    start = upper.find("DATA;")
    end = upper.rfind("ENDSEC;")
    body = text[start + 5:end] if start >= 0 and end > start else text
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
    out, cur, quoted = [], [], False
    for ch in body:
        if ch == "'":
            quoted = not quoted
        if ch == ";" and not quoted:
            out.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    return [s for s in out if s]


def read_entities(text: str) -> dict[int, Entity]:
    """Parse every '#id=TYPE(...)' statement into a dict keyed by id."""
    found: dict[int, Entity] = {}
    for stmt in split_statements(text):
        m = ENTITY.match(stmt)
        if not m:
            continue
        found[int(m.group(1))] = Entity(int(m.group(1)), m.group(2).upper(), parse_args(m.group(3)))
    return found
