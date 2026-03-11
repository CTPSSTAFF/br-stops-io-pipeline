"""
Purpose:
    Replicates the EvO9.01 lookup behavior from the STOPS calibration workbook.
    While EvO10.01 focuses on Routes, EvO9.01 focuses on specific STOPS/STATIONS.

Data Context:
    - STOP_ID1: The unique identifier for a physical transit stop or station platform.
    - XFER (Transfers): Unlike routes, stops track riders who arrive via a transfer 
      from another transit line, so XFER is tracked in addition to WLK, KNR, and PNR.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shop.base import WorkbookParser, format_number, to_number

EV0_SHEET = "EvO9.01"
T901_SHEET = "T_9.01"

T901_COLUMNS: Sequence[str] = (
    "STOP_ID1",
    "STOP_Name",
    "WLK_E",
    "KNR_E",
    "PNR_E",
    "XFR_E",
    "ALL_E",
    "WLK_NB",
    "KNR_NB",
    "PNR_NB",
    "XFR_NB",
    "ALL_NB",
    "WLK_B",
    "KNR_B",
    "PNR_B",
    "XFR_B",
    "ALL_B",
)

CSV_COLUMNS: Sequence[str] = (
    "STATION",
    "Route",
    "STAT_GRP",
    "GRP_NAME",
    "STOP_ID1",
    "STOP_ID2",
    "STOP_ID3",
    "STOP_ID4",
    "Agency",
    "Mode",
    "DAILYBOARD",
    "WLK",
    "KNR",
    "PNR",
    "XFER",
    "TOTAL",
    "DIFFERENCE",
)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replicate EvO9.01 lookups and emit a CSV summary.")
    parser.add_argument("--formatted-tables", type=Path, default=Path("calibration/A2_Formatted_Tables.xlsx"))
    parser.add_argument("--calibration-workbook", type=Path, default=Path("calibration/Boston_Regional_STOPS Calibration Report_2050.xlsx"))
    parser.add_argument("--route-sheet",default=EV0_SHEET)
    parser.add_argument("--column-indices", type=int, nargs=5, metavar=("WLK", "KNR", "PNR", "XFER", "TOTAL"))
    parser.add_argument("--output", type=Path, default=Path("evo9_01.csv"))
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """
    Logical Process:
        1. Parse the calibration template to find out which stops we care about.
        2. Build a lookup dictionary of estimates for all stops from the formatted tables.
        3. Match the stop IDs, extract the access metrics (Walk, Transfer, etc.), 
           calculate the difference against observed, and write to CSV.
    """
    args = parse_args(argv or sys.argv[1:])

    stop_template_rows, template_column_indices = parse_evo9_stop_template(args.calibration_workbook, args.route_sheet)
    stop_estimates_lookup = build_estimated_stop_lookup(args.formatted_tables)
    active_column_indices = tuple(args.column_indices) if args.column_indices else template_column_indices

    output_csv_rows: List[List[str]] = []
    missing_estimated_stops: List[str] = []

    for template_row_data in stop_template_rows:
        stop_id = template_row_data["STOP_ID1"]
        observed_stop_boardings = template_row_data["observed_boardings"]
        
        stop_estimates_data = stop_estimates_lookup.get(stop_id)
        if stop_estimates_data is None:
            missing_estimated_stops.append(stop_id)
            estimated_boarding_metrics = [None] * 5
        else:
            estimated_boarding_metrics = extract_estimated_stop_values(stop_estimates_data, active_column_indices)

        boardings_difference = None
        estimated_total_boardings = estimated_boarding_metrics[-1] if estimated_boarding_metrics else None
        if estimated_total_boardings is not None and observed_stop_boardings is not None:
            boardings_difference = estimated_total_boardings - observed_stop_boardings

        output_csv_rows.append(
            [
                template_row_data["STATION"],
                template_row_data["Route"],
                template_row_data["STAT_GRP"],
                template_row_data["GRP_NAME"],
                template_row_data["STOP_ID1"],
                template_row_data["STOP_ID2"],
                template_row_data["STOP_ID3"],
                template_row_data["STOP_ID4"],
                template_row_data["Agency"],
                template_row_data["Mode"],
                format_number(observed_stop_boardings),
                format_number(estimated_boarding_metrics[0]),
                format_number(estimated_boarding_metrics[1]),
                format_number(estimated_boarding_metrics[2]),
                format_number(estimated_boarding_metrics[3]),
                format_number(estimated_boarding_metrics[4]),
                format_number(boardings_difference),
            ]
        )

    write_output_csv(args.output, output_csv_rows)
    sys.stdout.write(f"Wrote {len(output_csv_rows)} rows to {args.output}\n")

    if missing_estimated_stops:
        sys.stderr.write(f"Warning: {len(missing_estimated_stops)} stop ids missing from {T901_SHEET}\n")
    return 0


def write_output_csv(file_path: Path, output_rows: Sequence[Sequence[str]]) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8", newline="") as file_handle:
        csv_writer = csv.writer(file_handle)
        csv_writer.writerow(CSV_COLUMNS)
        csv_writer.writerows(output_rows)


def parse_evo9_stop_template(
    workbook_path: Path, sheet_name: str
) -> Tuple[List[Dict[str, str | float | None]], Tuple[int, int, int, int, int]]:
    """Reads the EvO9 template to identify which stops to extract and their observed boardings."""
    stop_template_rows: List[Dict[str, str | float | None]] = []
    template_column_indices: Tuple[int, int, int, int, int] | None = None

    with WorkbookParser(workbook_path) as parser:
        for excel_row_index, row_cell_values in parser.iter_rows(sheet_name):
            
            # Row 1 dictates the column indices for metrics
            if excel_row_index == 1:
                parsed_indices = [int(to_number(row_cell_values.get(col)) or 0) for col in ("O", "P", "Q", "R", "S") if to_number(row_cell_values.get(col))]
                if len(parsed_indices) == 5:
                    template_column_indices = tuple(parsed_indices)

            # Rows 5+ contain the stop data definitions
            station_name = row_cell_values.get("D")
            stop_id = row_cell_values.get("H")
            if excel_row_index >= 5 and stop_id and stop_id not in {"STOP_ID1", "Stop_ID1"} and (station_name or row_cell_values.get("E")):
                stop_template_rows.append({
                    "STATION": station_name or "",
                    "Route": row_cell_values.get("E", "") or "",
                    "STAT_GRP": row_cell_values.get("F", "") or "",
                    "GRP_NAME": row_cell_values.get("G", "") or "",
                    "STOP_ID1": stop_id,
                    "STOP_ID2": row_cell_values.get("I", "") or "",
                    "STOP_ID3": row_cell_values.get("J", "") or "",
                    "STOP_ID4": row_cell_values.get("K", "") or "",
                    "Agency": row_cell_values.get("L", "") or "",
                    "Mode": row_cell_values.get("M", "") or "",
                    "observed_boardings": to_number(row_cell_values.get("N")),
                })

    return stop_template_rows, template_column_indices or (3, 4, 5, 6, 7)


def build_estimated_stop_lookup(formatted_tables_path: Path) -> Dict[str, Dict[str, str | None]]:
    """Builds a lookup mapping stop IDs to their estimated metrics."""
    stop_estimates_lookup: Dict[str, Dict[str, str | None]] = {}
    with WorkbookParser(formatted_tables_path) as parser:
        for _, row_cell_values in parser.iter_rows(T901_SHEET):
            stop_id = row_cell_values.get("A")
            if not stop_id or stop_id == "STOP_ID1":
                continue
            stop_estimates_lookup[stop_id] = {metric_name: row_cell_values.get(chr(ord("A") + index)) for index, metric_name in enumerate(T901_COLUMNS)}
    return stop_estimates_lookup


def extract_estimated_stop_values(
    stop_estimates_data: Dict[str, str | None], column_indices: Sequence[int]
) -> List[float | None]:
    return [to_number(stop_estimates_data.get(T901_COLUMNS[index - 1])) for index in column_indices]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())