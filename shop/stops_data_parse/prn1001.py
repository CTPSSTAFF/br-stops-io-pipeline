"""
Purpose:
    Extracts Table 10.01 from a raw STOPS `.prn` file into a structured CSV.

Data Context:
    The core STOPS modeling software is written in Fortran and outputs results 
    into legacy fixed-width text files (.prn). Table 10.01 contains the route-level 
    ridership estimates. Because text files lack descriptive metadata (like transit agency), 
    this script reads the .prn file, extracts the raw numbers, and joins them with 
    descriptive metadata pulled from an Excel calibration workbook.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Dict, List, Sequence

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shop.base import WorkbookParser, format_number  # noqa: E402

DEFAULT_PRN = Path(
    "calibration/"
    "A2_MBTA-CATA-MWRTA-BATA-MVRTA#MBTA50-CATA-MWRTA-BATA-MVRTA"
    "#MBTA50-CATA-MWRTA-BATA-MVRTA_STOPSY2050Results.prn"
)
DEFAULT_CALIBRATION = Path(
    "shop/Boston_Regional_STOPS _mbta50_2045_2050_comparison_2024.xlsx"
)
DEFAULT_ROUTE_SHEET = "EvO10.01"
DEFAULT_OUTPUT = Path("tmp/evo101.csv")

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
    parser = argparse.ArgumentParser(description="Extract Table 10.01 from a STOPS PRN file and write it to CSV.")
    parser.add_argument("--prn-path", type=Path, default=DEFAULT_PRN)
    parser.add_argument("--calibration-workbook", type=Path, default=DEFAULT_CALIBRATION)
    parser.add_argument("--route-sheet", default=DEFAULT_ROUTE_SHEET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """
    Logical Process:
        1. Ingest metadata from the Excel workbook so we know what agency/mode 
           each route ID belongs to.
        2. Scan the PRN text file, locate the start of Table 10.01, and parse the 
           fixed-width columns into raw ridership numbers.
        3. Merge the parsed PRN data with the Excel metadata.
        4. Calculate differences and export to CSV.
    """
    args = parse_args(argv or sys.argv[1:])

    route_metadata_lookup = load_route_metadata(args.calibration_workbook, args.route_sheet)
    parsed_prn_ridership_rows = parse_prn_table(args.prn_path)
    output_csv_rows, aggregate_ridership_totals = build_csv_rows(parsed_prn_ridership_rows, route_metadata_lookup)

    write_output_csv(args.output, output_csv_rows, aggregate_ridership_totals)
    sys.stdout.write(f"Wrote {len(output_csv_rows) + 1} rows to {args.output}\n")
    return 0


def load_route_metadata(workbook_path: Path | None, sheet_name: str) -> Dict[str, Dict[str, str]]:
    """Loads a mapping of route_id -> (name, number, agency, mode) from Excel."""
    if workbook_path is None: return {}
    candidate_sheet_names = [sheet_name, "EvO10.01-2050", "EvO10.01-2045", "EvO10.01"]
    
    try:
        parser = WorkbookParser(workbook_path)
    except FileNotFoundError:
        sys.stderr.write(f"Warning: metadata workbook {workbook_path} not found; using PRN labels only.\n")
        return {}

    route_metadata_lookup: Dict[str, Dict[str, str]] = {}
    with parser:
        for candidate_sheet in candidate_sheet_names:
            try:
                route_metadata_lookup = parse_metadata_sheet(parser, candidate_sheet)
            except KeyError:
                continue
            if route_metadata_lookup:
                break

    if not route_metadata_lookup:
        sys.stderr.write(f"Warning: no usable metadata found in {workbook_path}; using PRN labels only.\n")
    return route_metadata_lookup


def parse_metadata_sheet(parser: WorkbookParser, sheet_name: str) -> Dict[str, Dict[str, str]]:
    """Finds the metadata header row in the Excel sheet and reads all subsequent route entries."""
    mapped_header_cols = None
    route_metadata_mapping: Dict[str, Dict[str, str]] = {}

    for _, row_cell_values in parser.iter_rows(sheet_name):
        
        # Determine which columns hold which pieces of metadata dynamically
        if mapped_header_cols is None or "route_id" not in mapped_header_cols or len(mapped_header_cols) < 3:
            candidate_headers = detect_header_columns(row_cell_values)
            if "route_id" in candidate_headers and len(candidate_headers) > len(mapped_header_cols or {}):
                mapped_header_cols = candidate_headers
            continue

        route_id_col = mapped_header_cols.get("route_id")
        if not route_id_col: continue
        
        raw_route_id = row_cell_values.get(route_id_col)
        if not raw_route_id: continue
        
        route_id = str(raw_route_id).strip()
        if not route_id or route_id.lower() == "route_id": continue

        route_metadata_mapping[route_id] = {
            "name": str(row_cell_values.get(mapped_header_cols.get("route_name", ""), "") or "").strip(),
            "number": str(row_cell_values.get(mapped_header_cols.get("route_number", ""), "") or "").strip(),
            "agency": str(row_cell_values.get(mapped_header_cols.get("agency", ""), "") or "").strip(),
            "mode": str(row_cell_values.get(mapped_header_cols.get("mode", ""), "") or "").strip(),
        }
    return route_metadata_mapping


def parse_prn_table(prn_file_path: Path) -> List[Dict[str, object]]:
    """Scans the PRN text file, locates 'Table 10.01', and extracts the delimited numeric data."""
    parsed_prn_ridership_rows: List[Dict[str, object]] = []
    is_reading_table = False
    with prn_file_path.open(encoding="latin-1") as file_handle:
        for prn_line in file_handle:
            
            # Wait until we reach the exact table we want
            if not is_reading_table:
                if prn_line.startswith("Table    10.01"): is_reading_table = True
                continue

            # Stop parsing if a new table begins
            if prn_line.startswith("Table    "): break
            
            # Skip empty lines, separators, and headers
            if not prn_line.strip() or prn_line.startswith(("*****", "Comparison", "Total Transit Trips", "Program STOPS", " ", "-", "=")): continue
            if prn_line.lstrip().startswith("Route_ID"): continue

            parsed_tokens = prn_line.split()
            if not parsed_tokens or parsed_tokens[0].lower() == "total" or len(parsed_tokens) < 14:
                continue

            # The last 13 tokens in this table format are always the ridership counts
            numeric_tokens = parsed_tokens[-13:]
            try:
                numeric_values = [float(value) for value in numeric_tokens]
            except ValueError:
                continue

            route_id = parsed_tokens[0]
            # Reconstruct the route label (which can contain spaces) from the remaining tokens
            extracted_route_label = " ".join(parsed_tokens[1:-13]).strip()
            if extracted_route_label.startswith("--"): extracted_route_label = extracted_route_label[2:].strip()

            parsed_prn_ridership_rows.append({
                "route_id": route_id,
                "route_label": extracted_route_label,
                "all_obs": numeric_values[0],
                "wlk_est": numeric_values[5],
                "knr_est": numeric_values[6],
                "pnr_est": numeric_values[7],
                "all_est": numeric_values[8],
            })
    return parsed_prn_ridership_rows


def build_csv_rows(
    parsed_prn_ridership_rows: List[Dict[str, object]], route_metadata_lookup: Dict[str, Dict[str, str]]
) -> tuple[List[List[str]], Dict[str, float | None]]:
    """Merges the extracted PRN metrics with the Excel metadata to build the final CSV rows."""
    output_csv_rows: List[List[str]] = []
    cumulative_observed_total = 0.0
    cumulative_estimated_total = 0.0

    for prn_route_record in parsed_prn_ridership_rows:
        route_id = prn_route_record["route_id"]  # type: ignore[assignment]
        metadata_info = route_metadata_lookup.get(route_id, {})
        
        # Fill in metadata: prefer Excel, fallback to string splitting the PRN label, fallback to hardcoded inference
        route_name, route_number = derive_name_and_number(prn_route_record["route_label"], metadata_info)
        transit_agency, transit_mode = derive_agency_mode(route_id, metadata_info, route_number, route_name)

        total_observed_ridership = float(prn_route_record["all_obs"])  # type: ignore[arg-type]
        estimated_walk_access = float(prn_route_record["wlk_est"])  # type: ignore[arg-type]
        estimated_knr_access = float(prn_route_record["knr_est"])  # type: ignore[arg-type]
        estimated_pnr_access = float(prn_route_record["pnr_est"])  # type: ignore[arg-type]
        total_estimated_ridership = float(prn_route_record["all_est"])  # type: ignore[arg-type]

        cumulative_observed_total += total_observed_ridership
        cumulative_estimated_total += total_estimated_ridership

        ridership_difference, percent_difference = compute_ridership_differences(total_estimated_ridership, total_observed_ridership)

        output_csv_rows.append([
            route_id,
            route_name,
            route_number,
            transit_agency,
            transit_mode,
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
        ])

    aggregate_ridership_diff, aggregate_percent_diff = compute_ridership_differences(cumulative_estimated_total, cumulative_observed_total)
    aggregate_ridership_totals: Dict[str, float | None] = {
        "observed": cumulative_observed_total, "estimated": cumulative_estimated_total,
        "diff": aggregate_ridership_diff, "pct": aggregate_percent_diff,
    }
    return output_csv_rows, aggregate_ridership_totals


def detect_header_columns(row_cell_values: Dict[str, str]) -> Dict[str, str]:
    identified_header_map: Dict[str, str] = {}
    for column_letter, cell_value in row_cell_values.items():
        normalized_key = normalize_header(cell_value)
        if normalized_key in {"routeid", "route_id"}: identified_header_map["route_id"] = column_letter
        elif normalized_key in {"routename", "route_name"}: identified_header_map["route_name"] = column_letter
        elif normalized_key in {"route#", "route_num", "routenumber", "route"}: identified_header_map["route_number"] = column_letter
        elif normalized_key == "agency": identified_header_map["agency"] = column_letter
        elif normalized_key == "mode": identified_header_map["mode"] = column_letter
    return identified_header_map

def normalize_header(raw_header_value: str | None) -> str:
    if raw_header_value is None: return ""
    return str(raw_header_value).strip().lower().replace("_", "").replace(" ", "")

def derive_name_and_number(prn_route_label: str, metadata_info: Dict[str, str] | None = None) -> tuple[str, str]:
    if metadata_info:
        metadata_name = metadata_info.get("name") or ""
        metadata_number = metadata_info.get("number") or ""
        
        if metadata_name or metadata_number:
            return metadata_name, metadata_number
            
    if "-" in prn_route_label:
        number_segment, _, remainder_segment = prn_route_label.partition("-")
        return remainder_segment.strip(), number_segment.strip()
        
    return prn_route_label, ""
def derive_agency_mode(route_id: str, metadata_info: Dict[str, str], route_number: str, route_name: str) -> tuple[str, str]:
    """Infers agency and mode for the Boston regional area if not explicitly provided in metadata."""
    mapped_agency, mapped_mode = metadata_info.get("agency") or "", metadata_info.get("mode") or ""
    if mapped_agency and mapped_mode: return mapped_agency, mapped_mode

    normalized_route_id = route_id.lower()
    if normalized_route_id.startswith("cr-"): return mapped_agency or "MBTA Commuter Rail", mapped_mode or "CR"
    if normalized_route_id.startswith("boat-"): return mapped_agency or "MBTA Ferry", mapped_mode or "Ferry"
    if any(normalized_route_id.startswith(m) for m in ("red", "blue", "orange")): return mapped_agency or "MBTA HRT", mapped_mode or "HR"
    if normalized_route_id.startswith("mattapan") or normalized_route_id.startswith("green-"): return mapped_agency or "MBTA LRT", mapped_mode or "LRT"
    if normalized_route_id.endswith("&m"): return mapped_agency or "MWRTA", mapped_mode or "MWRTA Bus"
    if normalized_route_id.endswith("&v"): return mapped_agency or "MVRTA", mapped_mode or "MVRTA Bus"
    if normalized_route_id.endswith("&c"): return mapped_agency or "CATA", mapped_mode or "CATA Bus"
    if normalized_route_id.endswith("&b"): return mapped_agency or "BAT", mapped_mode or "BAT Bus"
    if normalized_route_id.endswith("&t"): return mapped_agency or "MBTA", mapped_mode or "MBTA Bus"

    return mapped_agency, mapped_mode

def compute_ridership_differences(total_estimated_ridership: float, total_observed_ridership: float) -> tuple[float, float | None]:
    ridership_difference = total_estimated_ridership - total_observed_ridership
    percent_difference = ridership_difference / total_observed_ridership if total_observed_ridership else None
    return ridership_difference, percent_difference

def write_output_csv(file_path: Path, output_rows: List[List[str]], aggregate_ridership_totals: Dict[str, float | None]) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8", newline="") as file_handle:
        csv_writer = csv.writer(file_handle)
        csv_writer.writerow(CSV_COLUMNS)
        csv_writer.writerows(output_rows)
        csv_writer.writerow([
            "Total",
            "",
            "",
            "",
            "",
            "",
            "",
            format_number(aggregate_ridership_totals["observed"]),
            "",
            "",
            "",
            format_number(aggregate_ridership_totals["estimated"]),
            format_number(aggregate_ridership_totals["diff"]),
            format_number(aggregate_ridership_totals["pct"]),
        ])

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())