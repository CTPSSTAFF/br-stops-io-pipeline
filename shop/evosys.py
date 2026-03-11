"""
Purpose:
    Recreates the EvOSys sheet, which is a high-level system summary.
    It aggregates data by looking *across* the outputs of EvO9 (Stop level) 
    and EvO10 (Route level) based on formulas defined in the Excel workbook.

Data Context:
    The EvOSys sheet contains arbitrary formulas summarizing groups (e.g., "Total MBTA Commuter Rail").
    Instead of hardcoding these groups, this script dynamically reads the `SUMIF` 
    and cell reference formulas out of the Excel sheet, figures out which underlying
    data points they need, aggregates them, and writes the summary.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

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
    parser.add_argument("--calibration-workbook", type=Path, default=DEFAULT_CALIBRATION)
    parser.add_argument("--evosys-sheet", default=EVOSYS_SHEET)
    parser.add_argument("--evo9-csv", type=Path, default=DEFAULT_EVO9_CSV)
    parser.add_argument("--evo10-csv", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=Path("evosys_estimates.csv"))
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """
    Logical Process:
        1. Parse the EvOSys sheet formulas to see which summaries are requested.
        2. Based on the formulas, conditionally load the Stop totals (EvO9) and/or Route totals (EvO10).
        3. Iterate over the formulas, computing the dynamic aggregate sums.
        4. Export the resulting system-level estimates to a CSV.
    """
    args = parse_args(argv or sys.argv[1:])

    # Step 1: Parse what the system summary needs
    system_metric_formulas = extract_system_metric_formulas(args.calibration_workbook, args.evosys_sheet)
    if not system_metric_formulas:
        sys.stderr.write("No EvOSys formulas referencing EvO9.01/EvO10.01 were detected.\n")
        return 1

    requires_evo9 = any(formula_spec["source"] == "EvO9.01" for formula_spec in system_metric_formulas)
    requires_evo10 = any(formula_spec["source"] == "EvO10.01" for formula_spec in system_metric_formulas)

    # Validate and load prerequisites
    evo9_file_path = args.evo9_csv
    if requires_evo9 and (evo9_file_path is None or not evo9_file_path.exists()):
        sys.stderr.write("Warning: EvO9.01 data not provided/found; skipping EvO9.01-derived rows.\n")
        system_metric_formulas = [formula_spec for formula_spec in system_metric_formulas if formula_spec["source"] != "EvO9.01"]
        requires_evo9 = False

    evo10_file_path = args.evo10_csv
    if requires_evo10 and (evo10_file_path is None or not evo10_file_path.exists()):
        sys.stderr.write("Warning: EvO10.01 data not provided/found; skipping EvO10.01-derived rows.\n")
        system_metric_formulas = [formula_spec for formula_spec in system_metric_formulas if formula_spec["source"] != "EvO10.01"]
        requires_evo10 = False

    if not system_metric_formulas:
        sys.stderr.write("No rows available to compute after filtering.\n")
        return 1

    # Step 2: Load underlying detailed data
    if requires_evo9:
        evo9_stop_totals = load_totals_by_stop_id(evo9_file_path)
        stops_by_transit_line, stops_by_station_group = load_stop_group_mappings(args.calibration_workbook, EVO901_SHEET)
        estimated_totals_by_line = aggregate_metrics_by_label(stops_by_transit_line, evo9_stop_totals)
        estimated_totals_by_group = aggregate_metrics_by_label(stops_by_station_group, evo9_stop_totals)
    else:
        estimated_totals_by_line = {}
        estimated_totals_by_group = {}

    if requires_evo10:
        evo10_excel_row_metadata = load_evo10_excel_row_metadata(args.calibration_workbook, EVO1001_SHEET)
        evo10_route_totals, evo10_route_number_totals, evo10_mode_totals = load_evo10_ridership_totals(evo10_file_path)
    else:
        evo10_excel_row_metadata = {}
        evo10_route_totals, evo10_route_number_totals, evo10_mode_totals = {}, {}, {}

    # Step 3: Compute aggregations based on formulas
    output_csv_rows: List[List[str]] = []
    missing_metric_labels: List[str] = []
    
    for formula_spec in system_metric_formulas:
        if formula_spec["source"] == "EvO9.01":
            aggregated_totals = estimated_totals_by_line if formula_spec["reference"] == "C" else estimated_totals_by_group
            calculated_system_metric = aggregated_totals.get(formula_spec["label"])
        else:
            calculated_system_metric = evaluate_evo10_formula_spec(
                formula_spec["cells"], evo10_excel_row_metadata, evo10_route_totals, evo10_route_number_totals, evo10_mode_totals
            )
        
        if calculated_system_metric is None:
            missing_metric_labels.append(formula_spec["label"])
        output_csv_rows.append([formula_spec["label"], format_number(calculated_system_metric)])

    # Step 4: Export summary
    write_output_csv(args.output, output_csv_rows)
    sys.stdout.write(f"Wrote {len(output_csv_rows)} rows to {args.output}\n")
    return 0


def write_output_csv(file_path: Path, output_rows: Sequence[Sequence[str]]) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8", newline="") as file_handle:
        csv_writer = csv.writer(file_handle)
        csv_writer.writerow(["Line", "Estimated"])
        csv_writer.writerows(output_rows)


def extract_system_metric_formulas(workbook_path: Path, sheet_name: str) -> List[Dict[str, object]]:
    """
    Parses the EvOSys sheet. It looks for cells containing formulas like 
    `=SUMIF('EvO9.01'!C:C, ...)` or explicit additions like `='EvO10.01'!Z15 + ...` 
    and translates them into a python dictionary spec we can execute.
    """
    system_metric_formulas: List[Dict[str, object]] = []
    with WorkbookParser(workbook_path) as parser:
        for _, row_cell_values in parser.iter_rows(sheet_name, include_formulas=True):
            metric_label = (row_cell_values.get("A") or "").strip()
            if not metric_label:
                continue
            
            excel_formula = row_cell_values.get(("D", "formula")) or ""
            
            # Identify EvO9 stop-level aggregation (usually SUMIFs based on line or group name)
            if "EvO9.01" in excel_formula and "SUMIF" in excel_formula:
                column_reference = "C" if "!C:C" in excel_formula else "A" if "!A:A" in excel_formula else None
                if column_reference:
                    system_metric_formulas.append({"label": metric_label, "source": "EvO9.01", "reference": column_reference})
                    
            # Identify EvO10 route-level aggregation (usually direct cell additions)
            elif "EvO10.01" in excel_formula:
                parsed_cell_refs = re.findall(r"'EvO10\.01'!\$?([A-Z]+)(\d+)", excel_formula)
                if parsed_cell_refs:
                    system_metric_formulas.append({
                        "label": metric_label, "source": "EvO10.01",
                        "cells": [(col, int(idx)) for col, idx in parsed_cell_refs],
                    })
    return system_metric_formulas


def load_totals_by_stop_id(csv_file_path: Path) -> Dict[str, float]:
    """Reads the generated EvO9 CSV to get the total boardings per stop."""
    aggregated_totals: Dict[str, float] = {}
    with csv_file_path.open(encoding="utf-8") as file_handle:
        for csv_row in csv.DictReader(file_handle):
            stop_id = (csv_row.get("STOP_ID1") or "").strip()
            stop_total = to_number(csv_row.get("TOTAL"))
            if stop_id and stop_total is not None:
                aggregated_totals[stop_id] = aggregated_totals.get(stop_id, 0.0) + stop_total
    return aggregated_totals


def load_stop_group_mappings(workbook_path: Path, sheet_name: str) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    """Builds reverse lookups: e.g. mapping 'Red Line' to all the Stop IDs that belong to it."""
    stops_by_transit_line: Dict[str, List[str]] = defaultdict(list)
    stops_by_station_group: Dict[str, List[str]] = defaultdict(list)
    with WorkbookParser(workbook_path) as parser:
        for _, row_cell_values in parser.iter_rows(sheet_name):
            stop_id = (row_cell_values.get("H") or "").strip()
            if not stop_id:
                continue
            transit_line_value = (row_cell_values.get("C") or "").strip()
            station_group_value = (row_cell_values.get("A") or "").strip()
            if transit_line_value: stops_by_transit_line[transit_line_value].append(stop_id)
            if station_group_value: stops_by_station_group[station_group_value].append(stop_id)
    return dict(stops_by_transit_line), dict(stops_by_station_group)


def aggregate_metrics_by_label(mapping_dictionary: Dict[str, List[str]], stop_totals: Dict[str, float]) -> Dict[str, float]:
    """Given a group mapping and stop totals, calculates the sum for the group."""
    aggregated_metrics: Dict[str, float] = {}
    for group_label, mapped_stop_ids in mapping_dictionary.items():
        running_subtotal = 0.0
        contains_metric_value = False
        for stop_id in mapped_stop_ids:
            if (metric_value := stop_totals.get(stop_id)) is not None:
                running_subtotal += metric_value
                contains_metric_value = True
        if contains_metric_value:
            aggregated_metrics[group_label] = running_subtotal
    return aggregated_metrics


def load_evo10_ridership_totals(csv_file_path: Path) -> Tuple[Dict[str, float], Dict[str, float], Dict[str, float]]:
    """Reads the generated EvO10 CSV to get route boardings aggregated by ID, Route Number, and Mode."""
    evo10_route_totals: Dict[str, float] = {}
    evo10_route_number_totals: Dict[str, float] = defaultdict(float)
    evo10_mode_totals: Dict[str, float] = defaultdict(float)
    with csv_file_path.open(encoding="utf-8") as file_handle:
        for csv_row in csv.DictReader(file_handle):
            estimated_total = to_number(csv_row.get("ALL_est"))
            if estimated_total is None: continue
            if route_id := (csv_row.get("Route_ID") or "").strip(): evo10_route_totals[route_id] = estimated_total
            if route_number := (csv_row.get("Route #") or "").strip(): evo10_route_number_totals[route_number] += estimated_total
            if transit_mode := (csv_row.get("Mode") or "").strip(): evo10_mode_totals[transit_mode] += estimated_total
    return evo10_route_totals, dict(evo10_route_number_totals), dict(evo10_mode_totals)


def load_evo10_excel_row_metadata(workbook_path: Path, sheet_name: str) -> Dict[int, Dict[str, str]]:
    """Maps Excel row numbers back to their corresponding route IDs so formulas can be resolved."""
    evo10_excel_row_metadata: Dict[int, Dict[str, str]] = {}
    with WorkbookParser(workbook_path) as parser:
        for excel_row_index, row_cell_values in parser.iter_rows(sheet_name):
            evo10_excel_row_metadata[excel_row_index] = {
                "route_id": (row_cell_values.get("A") or "").strip(),
                "route_number": (row_cell_values.get("C") or "").strip(),
                "mode": (row_cell_values.get("E") or "").strip(),
            }
    return evo10_excel_row_metadata


def evaluate_evo10_formula_spec(
    parsed_cell_refs: List[Tuple[str, int]], evo10_excel_row_metadata: Dict[int, Dict[str, str]],
    evo10_route_totals: Dict[str, float], evo10_route_number_totals: Dict[str, float], evo10_mode_totals: Dict[str, float],
) -> float | None:
    """Executes the mapped formulas to sum up route totals."""
    calculated_running_total = 0.0
    contains_metric_value = False
    for _, excel_row_index in parsed_cell_refs:
        row_metadata = evo10_excel_row_metadata.get(excel_row_index)
        if not row_metadata: continue
        
        metric_value = None
        if route_id := row_metadata.get("route_id"): metric_value = evo10_route_totals.get(route_id)
        if metric_value is None and (route_number := row_metadata.get("route_number")): metric_value = evo10_route_number_totals.get(route_number)
        if metric_value is None and (transit_mode := row_metadata.get("mode")): metric_value = evo10_mode_totals.get(transit_mode)
        
        if metric_value is not None:
            calculated_running_total += metric_value
            contains_metric_value = True
    return calculated_running_total if contains_metric_value else None


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())