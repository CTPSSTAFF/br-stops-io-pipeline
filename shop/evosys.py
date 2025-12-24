"""Utilities for duplicating the EvOSys lookup behavior.

This module reads the EvOSys sheet definitions and reproduces the SUMIF
calculations by combining the exported CSVs (`evo9_01.csv`, `evo10_01.csv`)
with lookup metadata pulled directly from the workbook. The output is a CSV
with two columns: ["Line", "Estimated"].
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import xml.etree.ElementTree as ET

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

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
        help="Workbook containing EvOSys/EvO9.01/EvO10.01 (default: 2050 report)",
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
        help="CSV generated from EvO9.01 (default: evo9_01.csv)",
    )
    parser.add_argument(
        "--evo10-csv",
        type=Path,
        default=DEFAULT_EVO10_CSV,
        help="CSV generated from EvO10.01 (default: evo10_01.csv)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evosys_estimates.csv"),
        help="Destination CSV path (default: evosys_estimates.csv)",
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
        line_totals = group_totals = {}

    if need_evo10:
        evo10_row_meta = load_evo10_row_meta(args.calibration_workbook, EVO1001_SHEET)
        route_totals, route_number_totals, mode_totals = load_evo10_totals(args.evo10_csv)
    else:
        evo10_row_meta = {}
        route_totals = route_number_totals = mode_totals = {}

    rows: List[List[str]] = []
    missing: List[str] = []
    for spec in label_specs:
        if spec["source"] == "EvO9.01":
            totals = line_totals if spec["reference"] == "C" else group_totals
            value = totals.get(spec["label"])
        else:  # EvO10.01
            value = evaluate_evo10_spec(
                spec["cells"],
                evo10_row_meta,
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
    with zipfile.ZipFile(workbook_path) as archive:
        sheet = _load_sheet(archive, sheet_name)
        shared = _load_shared_strings(archive)
        sheet_data = sheet.find("m:sheetData", NS)
        if sheet_data is None:
            return specs

        for row in sheet_data:
            cells = _extract_row_cells(row, shared, include_formulas=True)
            label = (cells.get(("A", "value")) or "").strip()
            formula = cells.get(("D", "formula")) or ""
            if not label or not formula:
                continue
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
                            "cells": [(col, int(row_num)) for col, row_num in cell_refs],
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
    line_assignments: Dict[str, str] = {}
    group_assignments: Dict[str, str] = {}
    with zipfile.ZipFile(workbook_path) as archive:
        sheet = _load_sheet(archive, sheet_name)
        shared = _load_shared_strings(archive)
        sheet_data = sheet.find("m:sheetData", NS)
        if sheet_data is None:
            return {}, {}

        for row in sheet_data:
            cells = _extract_row_cells(row, shared)
            stop_id = (cells.get(("H", "value")) or "").strip()
            if not stop_id:
                continue
            if stop_id not in line_assignments:
                line_value = (cells.get(("C", "value")) or "").strip()
                if line_value:
                    line_assignments[stop_id] = line_value
            if stop_id not in group_assignments:
                group_value = (cells.get(("A", "value")) or "").strip()
                if group_value:
                    group_assignments[stop_id] = group_value

    line_map: Dict[str, List[str]] = defaultdict(list)
    for stop_id, label in line_assignments.items():
        line_map[label].append(stop_id)

    group_map: Dict[str, List[str]] = defaultdict(list)
    for stop_id, label in group_assignments.items():
        group_map[label].append(stop_id)

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
    with zipfile.ZipFile(workbook_path) as archive:
        sheet = _load_sheet(archive, sheet_name)
        shared = _load_shared_strings(archive)
        sheet_data = sheet.find("m:sheetData", NS)
        if sheet_data is None:
            return row_meta

        for row in sheet_data:
            row_idx = int(row.attrib.get("r", "0"))
            cells = _extract_row_cells(row, shared)
            row_meta[row_idx] = {
                "route_id": (cells.get(("A", "value")) or "").strip(),
                "route_number": (cells.get(("C", "value")) or "").strip(),
                "mode": (cells.get(("E", "value")) or "").strip(),
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
        route_number = meta.get("route_number")
        mode = meta.get("mode")
        if route_id:
            value = route_totals.get(route_id)
        if value is None and route_number:
            value = route_number_totals.get(route_number)
        if value is None and mode:
            value = mode_totals.get(mode)
        if value is None:
            continue
        total += value
        has_value = True
    return total if has_value else None


def _extract_row_cells(
    row: ET.Element,
    shared_strings: Sequence[str],
    include_formulas: bool = False,
) -> Dict[Tuple[str, str], str]:
    cells: Dict[Tuple[str, str], str] = {}
    for cell in row.findall("m:c", NS):
        column = "".join(ch for ch in cell.attrib.get("r", "") if ch.isalpha()).upper()
        if not column:
            continue
        value = _cell_value(cell, shared_strings)
        if value is not None:
            cells[(column, "value")] = value
        if include_formulas:
            formula = cell.find("m:f", NS)
            if formula is not None and formula.text:
                cells[(column, "formula")] = formula.text
    return cells


def _cell_value(cell: ET.Element, shared_strings: Sequence[str]) -> str | None:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        text_parts = [t.text or "" for t in cell.findall("m:is/m:t", NS)]
        return "".join(text_parts).strip()
    value_node = cell.find("m:v", NS)
    if value_node is None:
        return None
    if cell_type == "s":
        index = int(value_node.text or "0")
        if 0 <= index < len(shared_strings):
            return shared_strings[index]
        return None
    return value_node.text


def _load_shared_strings(archive: zipfile.ZipFile) -> List[str]:
    try:
        xml_data = archive.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(xml_data)
    return ["".join(t.text or "" for t in si.findall(".//m:t", NS)) for si in root.findall("m:si", NS)]


def _load_sheet(archive: zipfile.ZipFile, sheet_name: str) -> ET.Element:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    rel_map = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels.findall(f"{{{REL_NS}}}Relationship")}
    for sheet in workbook.findall("m:sheets/m:sheet", NS):
        if sheet.attrib.get("name") == sheet_name:
            sheet_rid = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            if sheet_rid:
                target = rel_map.get(sheet_rid)
                if target:
                    return ET.fromstring(archive.read(f"xl/{target}"))
    raise KeyError(f"Sheet {sheet_name} not found")


def to_number(value: str | None) -> float | None:
    if value is None:
        return None
    text = str(value).replace(",", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def format_number(value: float | None) -> str:
    if value is None:
        return ""
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.6f}".rstrip("0").rstrip(".")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

