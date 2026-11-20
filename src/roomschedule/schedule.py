"""Build a room schedule (one row per IfcSpace) from parsed IFC entities."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

from .ifc import Entity, read_entities

FIELDS = ["global_id", "level", "elevation_m", "number", "name", "area_m2"]
AREA_NAMES = ("NetFloorArea", "GrossFloorArea", "Area")


@dataclass
class Room:
    global_id: str
    level: str
    elevation_m: float | None
    number: str
    name: str
    area_m2: float | None

    def row(self) -> list:
        return [self.global_id, self.level, "" if self.elevation_m is None else f"{self.elevation_m:g}",
                self.number, self.name, "" if self.area_m2 is None else f"{self.area_m2:.2f}"]


@dataclass
class Schedule:
    rooms: list[Room] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _ref(v):
    return v[1] if isinstance(v, tuple) and v and v[0] == "ref" else None


def _refs(v) -> list[int]:
    return [r for r in (_ref(x) for x in (v or [])) if r is not None]


def _arg(e: Entity, i: int):
    return e.args[i] if i < len(e.args) else None


def _areas(ents: dict[int, Entity]) -> dict[int, float]:
    """Map an object id to its area, read from IfcElementQuantity via IfcRelDefinesByProperties."""
    by_quantity: dict[int, float] = {}
    for e in ents.values():
        if e.type != "IFCELEMENTQUANTITY":
            continue
        best = None
        for q in _refs(_arg(e, 5)):
            qe = ents.get(q)
            if qe and qe.type == "IFCQUANTITYAREA" and _arg(qe, 3) is not None and _arg(qe, 0) in AREA_NAMES:
                rank = AREA_NAMES.index(_arg(qe, 0))
                if best is None or rank < best[0]:
                    best = (rank, float(_arg(qe, 3)))
        if best:
            by_quantity[e.id] = best[1]
    out: dict[int, float] = {}
    for e in ents.values():
        if e.type == "IFCRELDEFINESBYPROPERTIES":
            qid = _ref(_arg(e, 5))
            if qid in by_quantity:
                for obj in _refs(_arg(e, 4)):
                    out[obj] = by_quantity[qid]
    return out


def build_schedule(text: str) -> Schedule:
    ents = read_entities(text)
    sched = Schedule()
    storey_of: dict[int, Entity] = {}
    for e in ents.values():
        if e.type == "IFCRELAGGREGATES":
            parent, kids = _ref(_arg(e, 4)), _refs(_arg(e, 5))
        elif e.type == "IFCRELCONTAINEDINSPATIALSTRUCTURE":
            parent, kids = _ref(_arg(e, 5)), _refs(_arg(e, 4))
        else:
            continue
        p = ents.get(parent)
        if p and p.type == "IFCBUILDINGSTOREY":
            for k in kids:
                storey_of[k] = p
    areas = _areas(ents)
    for e in sorted(ents.values(), key=lambda x: x.id):
        if e.type != "IFCSPACE":
            continue
        number = str(_arg(e, 2) or "")
        name = str(_arg(e, 7) or _arg(e, 3) or "")
        storey = storey_of.get(e.id)
        level = str(_arg(storey, 2) or "") if storey else ""
        elev = _arg(storey, 9) if storey else None
        area = areas.get(e.id)
        label = number or f"#{e.id}"
        if storey is None:
            sched.warnings.append(f"{label}: not placed on a building storey")
        if area is None:
            sched.warnings.append(f"{label}: no area quantity found")
        if not number:
            sched.warnings.append(f"#{e.id}: space has no number")
        sched.rooms.append(Room(str(_arg(e, 0) or ""), level, float(elev) if elev is not None else None, number, name, area))
    sched.rooms.sort(key=lambda r: (r.elevation_m if r.elevation_m is not None else 1e9, r.number))
    return sched


def to_csv(sched: Schedule) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(FIELDS)
    for r in sched.rooms:
        w.writerow(r.row())
    return buf.getvalue()


def summarize(sched: Schedule) -> list[str]:
    """Return one line per level (room count, total area), then a total line."""
    levels: dict[str, list[Room]] = {}
    for r in sched.rooms:
        levels.setdefault(r.level or "(no level)", []).append(r)
    lines = []
    for lvl, rooms in levels.items():
        total = sum(r.area_m2 or 0 for r in rooms)
        lines.append(f"{lvl:<12} {len(rooms):>3} rooms {total:>8.2f} m2")
    lines.append(f"{'TOTAL':<12} {len(sched.rooms):>3} rooms {sum(r.area_m2 or 0 for r in sched.rooms):>8.2f} m2")
    return lines
