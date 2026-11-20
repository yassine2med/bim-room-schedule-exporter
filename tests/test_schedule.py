from pathlib import Path

import pytest

from roomschedule.__main__ import main
from roomschedule.ifc import parse_args, read_entities, split_statements
from roomschedule.schedule import build_schedule, summarize, to_csv

SAMPLE = Path(__file__).resolve().parent.parent / "examples" / "office.ifc"


@pytest.fixture(scope="module")
def sched():
    return build_schedule(SAMPLE.read_text(encoding="utf-8"))


def test_parse_args_basic():
    assert parse_args("'a',$,3,.5,.X.,#7") == ["a", None, 3, 0.5, "X", ("ref", 7)]


def test_parse_args_nested_list_and_typed_value():
    assert parse_args("(#1,#2),IFCLABEL('x')") == [[("ref", 1), ("ref", 2)], "x"]


def test_parse_args_escaped_quote():
    assert parse_args("'it''s'") == ["it's"]


def test_split_statements_ignores_semicolon_in_string():
    stmts = split_statements("DATA;\n#1=IFCSPACE('a;b');\n#2=IFCSPACE('c');\nENDSEC;")
    assert len(stmts) == 2


def test_comments_are_removed():
    ents = read_entities("DATA;\n/* note; here */\n#1=IFCSPACE('a');\nENDSEC;")
    assert list(ents) == [1]


def test_reads_all_sample_entities():
    ents = read_entities(SAMPLE.read_text(encoding="utf-8"))
    assert sum(1 for e in ents.values() if e.type == "IFCSPACE") == 6


def test_room_count_and_order(sched):
    assert [r.number for r in sched.rooms] == ["101", "102", "103", "201", "202", "203"]


def test_levels_and_elevation(sched):
    assert sched.rooms[0].level == "Level 1" and sched.rooms[0].elevation_m == 0
    assert sched.rooms[3].level == "Level 2" and sched.rooms[3].elevation_m == 3.5


def test_area_read_from_quantities(sched):
    assert sched.rooms[1].area_m2 == 212.25


def test_long_name_used_as_name(sched):
    assert sched.rooms[3].name == "Conference Room (Large)"


def test_unplaced_room_warns(sched):
    assert "203: not placed on a building storey" in sched.warnings
    assert "203: no area quantity found" in sched.warnings


def test_csv_header_and_rows(sched):
    lines = to_csv(sched).splitlines()
    assert lines[0] == "global_id,level,elevation_m,number,name,area_m2"
    assert len(lines) == 7
    assert lines[2].endswith("102,Open Office,212.25")


def test_summary_totals(sched):
    lines = summarize(sched)
    assert lines[0].startswith("Level 1") and "265.50" in lines[0]
    assert lines[-1].startswith("TOTAL") and "6 rooms" in lines[-1] and "351.90" in lines[-1]


def test_cli_missing_file(capsys):
    assert main(["summary", "nope.ifc"]) == 2


def test_cli_export_to_file_and_strict(tmp_path, capsys):
    out = tmp_path / "rooms.csv"
    assert main(["export", str(SAMPLE), "-o", str(out)]) == 0
    assert out.read_text().count("\n") == 7
    assert main(["export", str(SAMPLE), "--strict"]) == 1


def test_containment_relation_places_space():
    text = ("DATA;\n#1=IFCBUILDINGSTOREY('g',$,'L9',$,$,$,$,$,.ELEMENT.,9.);\n"
            "#2=IFCSPACE('s',$,'900',$,$,$,$,'Lab',.ELEMENT.,.INTERNAL.,$);\n"
            "#3=IFCRELCONTAINEDINSPATIALSTRUCTURE('r',$,$,$,(#2),#1);\nENDSEC;")
    room = build_schedule(text).rooms[0]
    assert room.level == "L9" and room.elevation_m == 9
