"""Utilities for duplicating the EvOSys lookup behavior."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shop.base import WorkbookParser, format_number, to_number

DEFAULT_CALIBRATION = Path("calibration/Boston_Regional_STOPS Calibration Report_2050.xlsx")
DEFAULT_EVO9_CSV = Path("evo9_01.csv")
DEFAULT_EVO10_CSV = Path("evo10_01.csv")
EVOSYS_SHEET = "EvOSys"
EVO901_SHEET = "EvO9.01"
EVO1001_SHEET = "EvO10.01"


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recreate EvOSys estimates via CSV inputs.")
    parser.add_argument(
        "--calibration-workbook",
        type=Path,
        default=DEFAULT_CALIBRATION,
        help="Workbook containing EvOSys/EvO9.01/EvO10.01",
    )
    parser.add_argument(
        "--evosys-sheet",
        default=EVOSYS_SHEET,
        help="EvOSys worksheet name (default: EvOSys)",
    )
    parser.add_argument(
        "--evo9-csv",
        type=Path,
        default=DEFAULT_EVO9_CSV,
        help="CSV generated from EvO9.01",
    )
    parser.add_argument(
        "--evo10-csv",
        type=Path,
        default=DEFAULT_EVO10_CSV,
        help="CSV generated from EvO10.01",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evosys_estimates.csv"),
        help="Destination CSV path",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    label_specs = extract_line_specs(args.calibration_workbook, args.evosys_sheet)
    if not label_specs:
        sys.stderr.write("No EvOSys formulas referencing EvO9.01/EvO10.01 were detected.\n")
        return 1

    need_evo9 = any(spec["source"] == "EvO9.01" for spec in label_specs)
    need_evo10 = any(spec["source"] == "EvO10.01" for spec in label_specs)

    if need_evo9:
        stop_totals = load_totals_by_stop(args.evo9_csv)
        line_map, group_map = load_stop_mappings(args.calibration_workbook, EVO901_SHEET)
        line_totals = aggregate_by_label(line_map, stop_totals)
        group_totals = aggregate_by_label(group_map, stop_totals)
    else:
        line_totals = {}
        group_totals = {}

    if need_evo10:
        evo10_meta = load_evo10_row_meta(args.calibration_workbook, EVO1001_SHEET)
        route_totals, route_number_totals, mode_totals = load_evo10_totals(args.evo10_csv)
    else:
        evo10_meta = {}
        route_totals = {}
        route_number_totals = {}
        mode_totals = {}

    rows: List[List[str]] = []
    missing: List[str] = []
    for spec in label_specs:
        if spec["source"] == "EvO9.01":
            totals = line_totals if spec["reference"] == "C" else group_totals
            value = totals.get(spec["label"])
        else:
            value = evaluate_evo10_spec(
                spec["cells"],
                evo10_meta,
                route_totals,
                route_number_totals,
                mode_totals,
            )
        if value is None:
            missing.append(spec["label"])
        rows.append([spec["label"], format_number(value)])

    write_csv(args.output, rows)
    sys.stdout.write(f"Wrote {len(rows)} rows to {args.output}\n")

    if missing:
        sys.stderr.write(
            f"Warning: {len(missing)} labels could not be populated "
            f"({', '.join(missing[:6])}{'...' if len(missing) > 6 else ''})\n"
        )
    return 0


def write_csv(path: Path, rows: Sequence[Sequence[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Line", "Estimated"])
        writer.writerows(rows)


def extract_line_specs(
    workbook_path: Path, sheet_name: str
) -> List[Dict[str, object]]:
    specs: List[Dict[str, object]] = []
    with WorkbookParser(workbook_path) as parser:
        for _, cells in parser.iter_rows(sheet_name, include_formulas=True):
            label = (cells.get("A") or "").strip()
            if not label:
                continue
            formula = cells.get(("D", "formula")) or ""
            if "EvO9.01" in formula and "SUMIF" in formula:
                reference = "C" if "!C:C" in formula else "A" if "!A:A" in formula else None
                if reference:
                    specs.append({"label": label, "source": "EvO9.01", "reference": reference})
            elif "EvO10.01" in formula:
                cell_refs = re.findall(r"'EvO10\.01'!\$?([A-Z]+)(\d+)", formula)
                if cell_refs:
                    specs.append(
                        {
                            "label": label,
                            "source": "EvO10.01",
                            "cells": [(col, int(idx)) for col, idx in cell_refs],
                        }
                    )
    return specs


def load_totals_by_stop(csv_path: Path) -> Dict[str, float]:
    totals: Dict[str, float] = {}
    with csv_path.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            stop_id = (row.get("STOP_ID1") or "").strip()
            total = to_number(row.get("TOTAL"))
            if not stop_id or total is None:
                continue
            totals[stop_id] = totals.get(stop_id, 0.0) + total
    return totals


def load_stop_mappings(
    workbook_path: Path, sheet_name: str
) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    line_map: Dict[str, List[str]] = defaultdict(list)
    group_map: Dict[str, List[str]] = defaultdict(list)
    with WorkbookParser(workbook_path) as parser:
        for _, cells in parser.iter_rows(sheet_name):
            stop_id = (cells.get("H") or "").strip()
            if not stop_id:
                continue
            line_value = (cells.get("C") or "").strip()
            group_value = (cells.get("A") or "").strip()
            if line_value:
                line_map[line_value].append(stop_id)
            if group_value:
                group_map[group_value].append(stop_id)
    return dict(line_map), dict(group_map)


def aggregate_by_label(
    mapping: Dict[str, List[str]], totals: Dict[str, float]
) -> Dict[str, float]:
    aggregates: Dict[str, float] = {}
    for label, stop_ids in mapping.items():
        subtotal = 0.0
        has_value = False
        for stop_id in stop_ids:
            value = totals.get(stop_id)
            if value is None:
                continue
            subtotal += value
            has_value = True
        if has_value:
            aggregates[label] = subtotal
    return aggregates


def load_evo10_totals(
    csv_path: Path,
) -> Tuple[Dict[str, float], Dict[str, float], Dict[str, float]]:
    route_totals: Dict[str, float] = {}
    route_number_totals: Dict[str, float] = defaultdict(float)
    mode_totals: Dict[str, float] = defaultdict(float)
    with csv_path.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            total = to_number(row.get("ALL_est"))
            if total is None:
                continue
            route_id = (row.get("Route_ID") or "").strip()
            if route_id:
                route_totals[route_id] = total
            route_number = (row.get("Route #") or "").strip()
            if route_number:
                route_number_totals[route_number] += total
            mode = (row.get("Mode") or "").strip()
            if mode:
                mode_totals[mode] += total
    return route_totals, dict(route_number_totals), dict(mode_totals)


def load_evo10_row_meta(
    workbook_path: Path, sheet_name: str
) -> Dict[int, Dict[str, str]]:
    row_meta: Dict[int, Dict[str, str]] = {}
    with WorkbookParser(workbook_path) as parser:
        for row_idx, cells in parser.iter_rows(sheet_name):
            row_meta[row_idx] = {
                "route_id": (cells.get("A") or "").strip(),
                "route_number": (cells.get("C") or "").strip(),
                "mode": (cells.get("E") or "").strip(),
            }
    return row_meta


def evaluate_evo10_spec(
    cell_refs: List[Tuple[str, int]],
    row_meta: Dict[int, Dict[str, str]],
    route_totals: Dict[str, float],
    route_number_totals: Dict[str, float],
    mode_totals: Dict[str, float],
) -> float | None:
    total = 0.0
    has_value = False
    for _, row_idx in cell_refs:
        meta = row_meta.get(row_idx)
        if not meta:
            continue
        value = None
        route_id = meta.get("route_id")
        if route_id:
            value = route_totals.get(route_id)
        if value is None:
            route_number = meta.get("route_number")
            if route_number:
                value = route_number_totals.get(route_number)
        if value is None:
            mode = meta.get("mode")
            if mode:
                value = mode_totals.get(mode)
        if value is None:
            continue
        total += value
        has_value = True
    return total if has_value else None


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
