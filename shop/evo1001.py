"""
Purpose:
    Replicates the EvO10.01 lookup behavior from the STOPS calibration workbook.
    This script generates a CSV that compares estimated route-level boardings 
    against observed real-world boardings.

Data Context:
    - Route_ID: The unique identifier for a transit route.
    - WLK (Walk): Riders who access the transit stop by walking.
    - KNR (Kiss-and-Ride): Riders dropped off at the station by car.
    - PNR (Park-and-Ride): Riders who drive and park their car at the station.
    - _est / _E: Model Estimated values.
    - _obs / _B: Observed (ground-truth) baseline values.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shop.base import WorkbookParser, format_number, to_number

EV0_SHEET = "EvO10.01"
T1001_SHEET = "T_10.01"

OUTPUT_COLUMNS: Sequence[str] = (
    "Route_ID",
    "Route.Name",
    "Count_E",
    "WLK_E",
    "KNR_E",
    "PNR_E",
    "ALL_E",
    "WLK_NB",
    "KNR_NB",
    "PNR_NB",
    "ALL_NB",
    "WLK_B",
    "KNR_B",
    "PNR_B",
    "ALL_B",
)

COLUMN_LETTERS = [chr(ord("A") + idx) for idx in range(len(OUTPUT_COLUMNS))]

CSV_COLUMNS: Sequence[str] = (
    "Route_ID",
    "Route Name",
    "Route #",
    "Agency",
    "Mode",
    "WLK_obs",
    "KNR_obs",
    "PNR_obs",
    "ALL_obs",
    "WLK_est",
    "KNR_est",
    "PNR_est",
    "ALL_est",
    "ALL",
    "Diff",
)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replicate the EvO10.01 worksheet lookups using A2_Formatted_Tables.xlsx and write the results to CSV."
    )
    parser.add_argument("--formatted-tables", type=Path, default=Path("calibration/A2_Formatted_Tables.xlsx"))
    parser.add_argument("--calibration-workbook", type=Path, default=Path("calibration/Boston_Regional_STOPS Calibration Report_2050.xlsx"))
    parser.add_argument("--route-sheet", default=EV0_SHEET)
    parser.add_argument("--column-indices", type=int, nargs=3, metavar=("WLK_COL", "KNR_COL", "PNR_COL"))
    parser.add_argument("--output", type=Path, default=Path("evo10_01.csv"))
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """
    Logical Process:
        1. Parse the calibration template to find out *which* routes we care about,
           and grab their observed baseline values.
        2. Parse the formatted tables workbook to build a fast lookup dictionary of 
           the model's estimated values for all routes.
        3. Loop through the requested routes, match the estimated data with the 
           observed data, calculate the differences, and output to a CSV.
    """
    args = parse_args(argv or sys.argv[1:])

    # Step 1: Extract template data
    template_route_rows, observed_ridership_by_route, template_column_indices = parse_evo10_template_data(
        args.calibration_workbook, args.route_sheet
    )
    
    # Step 2: Build estimation lookup
    estimated_ridership_lookup = build_estimated_route_lookup(args.formatted_tables)
    active_column_indices = tuple(args.column_indices) if args.column_indices else template_column_indices

    output_csv_rows: List[List[str]] = []
    total_observed_sum = 0.0
    total_estimated_sum = 0.0
    has_valid_observed_total = False
    has_valid_estimated_total = False
    missing_observed_routes: List[str] = []
    missing_estimated_routes: List[str] = []

    # Step 3: Match and Calculate
    for route_info in template_route_rows:
        route_id = route_info["route_id"]
        is_total_row = route_id.strip().lower() == "total"

        total_observed_ridership = observed_ridership_by_route.get(route_id)
        if total_observed_ridership is None and not is_total_row:
            missing_observed_routes.append(route_id)

        route_estimates_data = estimated_ridership_lookup.get(route_id)
        
        # Handle missing data or the special 'Total' summary row
        if route_estimates_data is None and not is_total_row:
            missing_estimated_routes.append(route_id)
            estimated_walk_access = estimated_knr_access = estimated_pnr_access = total_estimated_ridership = None
        elif is_total_row:
            estimated_walk_access = estimated_knr_access = estimated_pnr_access = None
            total_observed_ridership = total_observed_sum if has_valid_observed_total else None
            total_estimated_ridership = total_estimated_sum if has_valid_estimated_total else None
        else:
            estimated_walk_access, estimated_knr_access, estimated_pnr_access, total_estimated_ridership = extract_estimated_boarding_values(
                route_estimates_data, active_column_indices
            )
            
            # Accumulate totals for the summary row
            if total_observed_ridership is not None:
                total_observed_sum += total_observed_ridership
                has_valid_observed_total = True
            if total_estimated_ridership is not None:
                total_estimated_sum += total_estimated_ridership
                has_valid_estimated_total = True

        ridership_difference, percent_difference = compute_ridership_differences(total_estimated_ridership, total_observed_ridership)

        output_csv_rows.append(
            [
                route_id,
                route_info["name"],
                route_info["number"],
                route_info["agency"],
                route_info["mode"],
                "",
                "",
                "",
                format_number(total_observed_ridership),
                format_number(estimated_walk_access),
                format_number(estimated_knr_access),
                format_number(estimated_pnr_access),
                format_number(total_estimated_ridership),
                format_number(ridership_difference),
                format_number(percent_difference),
            ]
        )

    write_output_csv(args.output, output_csv_rows)
    sys.stdout.write(f"Wrote {len(output_csv_rows)} rows to {args.output}\n")

    # Warn the user if the formatted tables were missing routes that the template expected
    if missing_estimated_routes:
        sys.stderr.write(f"Warning: {len(missing_estimated_routes)} route ids not found in {T1001_SHEET}\n")
    if missing_observed_routes:
        sys.stderr.write(f"Warning: {len(missing_observed_routes)} route ids missing observed values\n")
    return 0


def parse_evo10_template_data(
    workbook_path: Path, sheet_name: str = EV0_SHEET
) -> Tuple[List[Dict[str, str]], Dict[str, float], Tuple[int, int, int]]:
    """Extracts target routes and observed baseline data from the calibration workbook."""
    template_route_rows: List[Dict[str, str]] = []
    observed_ridership_table: Dict[str, float] = {}
    processed_route_ids: set[str] = set()
    template_column_indices: Tuple[int, int, int] | None = None

    with WorkbookParser(workbook_path) as parser:
        for excel_row_index, row_cell_values in parser.iter_rows(sheet_name):
            
            # Row 4 contains the column mapping indices indicating where WLK, KNR, and PNR data lives
            if excel_row_index == 4:
                parsed_indices = [int(to_number(row_cell_values.get(col)) or 0) for col in ("J", "K", "L") if to_number(row_cell_values.get(col))]
                if len(parsed_indices) == 3:
                    template_column_indices = tuple(parsed_indices)

            # Rows 8 and beyond contain the actual route data
            route_id = row_cell_values.get("A")
            if excel_row_index >= 8 and route_id and route_id not in {"Route_ID", "Route ID"} and route_id not in processed_route_ids:
                processed_route_ids.add(route_id)
                template_route_rows.append({
                    "route_id": route_id,
                    "name": row_cell_values.get("B", "") or "",
                    "number": row_cell_values.get("C", "") or "",
                    "agency": row_cell_values.get("D", "") or "",
                    "mode": row_cell_values.get("E", "") or "",
                })

            # Column T holds the observed route ID, Column W holds the observed count
            observed_route_id = row_cell_values.get("T")
            if observed_route_id and observed_route_id.lower() != "route_id":
                observed_ridership_table[observed_route_id] = to_number(row_cell_values.get("W"))

    # Fallback default indices if row 4 is malformed
    return template_route_rows, observed_ridership_table, template_column_indices or (4, 5, 6)


def build_estimated_route_lookup(formatted_tables_path: Path) -> Dict[str, Dict[str, str | None]]:
    """Reads the formatted STOPS output to build a dictionary of route estimates."""
    estimated_ridership_lookup: Dict[str, Dict[str, str | None]] = {}
    with WorkbookParser(formatted_tables_path) as parser:
        for _, row_cell_values in parser.iter_rows(T1001_SHEET):
            route_id = row_cell_values.get("A")
            if not route_id or route_id == "Route_ID":
                continue
            # Maps columns A, B, C... to their respective metric names based on OUTPUT_COLUMNS
            estimated_ridership_lookup[route_id] = {metric_name: row_cell_values.get(col_letter) for col_letter, metric_name in zip(COLUMN_LETTERS, OUTPUT_COLUMNS)}
    return estimated_ridership_lookup


def extract_estimated_boarding_values(
    route_estimates_data: Dict[str, str | None], column_indices: Sequence[int]
) -> Tuple[float | None, float | None, float | None, float | None]:
    """Pulls Walk, Kiss-and-Ride, Park-and-Ride, and computes the Total for a single route."""
    extracted_metrics = [to_number(route_estimates_data.get(OUTPUT_COLUMNS[idx - 1])) for idx in column_indices]
    return (
        extracted_metrics[0] if len(extracted_metrics) > 0 else None,
        extracted_metrics[1] if len(extracted_metrics) > 1 else None,
        extracted_metrics[2] if len(extracted_metrics) > 2 else None,
        sum_boarding_values(extracted_metrics)
    )


def compute_ridership_differences(
    total_estimated_ridership: float | None, total_observed_ridership: float | None
) -> Tuple[float | None, float | None]:
    if total_estimated_ridership is None or total_observed_ridership is None:
        return None, None
    ridership_difference = total_estimated_ridership - total_observed_ridership
    percent_difference = ridership_difference / total_observed_ridership if total_observed_ridership else None
    return ridership_difference, percent_difference


def sum_boarding_values(numeric_values: Iterable[float | None]) -> float | None:
    valid_values = [v for v in numeric_values if v is not None]
    return sum(valid_values) if valid_values else None


def write_output_csv(file_path: Path, output_rows: Sequence[Sequence[str]]) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8", newline="") as file_handle:
        csv_writer = csv.writer(file_handle)
        csv_writer.writerow(CSV_COLUMNS)
        csv_writer.writerows(output_rows)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())