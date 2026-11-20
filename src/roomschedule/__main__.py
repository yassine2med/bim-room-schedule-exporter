"""Command line: python -m roomschedule export|summary FILE.ifc"""

from __future__ import annotations

import argparse
import sys

from .schedule import build_schedule, summarize, to_csv


def main(argv: list[str] | None = None) -> int:
    """Return 0 on success, 1 when --strict finds warnings, 2 on a missing file."""
    parser = argparse.ArgumentParser(prog="roomschedule", description="Room schedule from an IFC file")
    sub = parser.add_subparsers(dest="command", required=True)
    ex = sub.add_parser("export", help="write the room schedule as CSV")
    ex.add_argument("file")
    ex.add_argument("-o", "--output", help="CSV path (default: print to screen)")
    ex.add_argument("--strict", action="store_true", help="exit 1 when any room has a warning")
    sm = sub.add_parser("summary", help="rooms and area per level, plus warnings")
    sm.add_argument("file")
    args = parser.parse_args(argv)
    try:
        with open(args.file, encoding="utf-8", errors="replace") as fh:
            sched = build_schedule(fh.read())
    except FileNotFoundError:
        print(f"File not found: {args.file}", file=sys.stderr)
        return 2
    if args.command == "summary":
        for line in summarize(sched):
            print(line)
        for w in sched.warnings:
            print(f"warning: {w}")
        return 0
    csv_text = to_csv(sched)
    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="") as fh:
            fh.write(csv_text)
        print(f"{len(sched.rooms)} rooms written to {args.output}")
    else:
        print(csv_text, end="")
    for w in sched.warnings:
        print(f"warning: {w}", file=sys.stderr)
    return 1 if (args.strict and sched.warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
