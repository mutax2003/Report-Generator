#!/usr/bin/env python3
"""CLI: merge Ecoventure Phase I workbook into engine Excel."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ecoventure_workbook import is_ecoventure_workbook, merge_into_engine_excel  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest Ecoventure DWDA workbook into engine Excel")
    parser.add_argument("--workbook", required=True, help="Ecoventure .xlsx saved from xltm")
    parser.add_argument(
        "--base",
        default=str(ROOT / "samples" / "phase1_alberta_data.xlsx"),
        help="Base engine Excel to merge into",
    )
    parser.add_argument("--out", required=True, help="Output merged .xlsx path")
    args = parser.parse_args()

    wb_path = Path(args.workbook)
    base_path = Path(args.base)
    out_path = Path(args.out)
    if not wb_path.is_file():
        print(f"Workbook not found: {wb_path}", file=sys.stderr)
        return 1
    if not base_path.is_file():
        print(f"Base Excel not found: {base_path}", file=sys.stderr)
        return 1
    eco_bytes = wb_path.read_bytes()
    if not is_ecoventure_workbook(eco_bytes):
        print("File is not a recognized Ecoventure workbook", file=sys.stderr)
        return 1
    merged = merge_into_engine_excel(base_path.read_bytes(), eco_bytes)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(merged)
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
