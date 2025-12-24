"""Utilities for duplicating the EvO10.01 lookup behavior.

This module reads the formatted STOPS workbook (A2_Formatted_Tables.xlsx),
pulls the `T_10.01` sheet, and replicates the Excel VLOOKUPs embedded in
the EvO10.01 tab of the calibration template.

The output mirrors the values Excel would place in columns I through Q:
Observed ALL ridership plus the Estimated walk/KNR/PNR columns defined
by cells J4:L4 (or user-provided column indices), along with the ALL
difference and percent difference.
"""

from __future__ import annotations

import argparse
import csv
import sys
import zipfile
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import xml.etree.ElementTree as ET

# XML namespaces used inside the workbook
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

EV0_SHEET = "EvO10.01"
T1001_SHEET = "T_10.01"

# Column order in T_10.01
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

# Desired CSV header order (matches Excel columns F–R)
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
        description=(
            "Replicate the EvO10.01 worksheet lookups using "
            "A2_Formatted_Tables.xlsx and write the results to CSV."
        )
    )
    parser.add_argument(
        "--formatted-tables",
        type=Path,
        default=Path("calibration/A2_Formatted_Tables.xlsx"),
        help="Path to A2_Formatted_Tables.xlsx (default: calibration/...)",
    )
    parser.add_argument(
        "--calibration-workbook",
        type=Path,
        default=Path("calibration/Boston_Regional_STOPS Calibration Report_2050.xlsx"),
        help="Workbook that hosts the EvO10.01 sheet (default: 2050 report)",
    )
    parser.add_argument(
        "--route-sheet",
        default=EV0_SHEET,
        help="Sheet name that defines the EvO10.01 layout (default: EvO10.01)",
    )
    parser.add_argument(
        "--column-indices",
        type=int,
        nargs=3,
        metavar=("WLK_COL", "KNR_COL", "PNR_COL"),
        help=(
            "Override the VLOOKUP column indices (J4:L4). "
            "Values are 1-based positions in T_10.01."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evo10_01.csv"),
        help="Destination CSV path (default: evo10_01.csv)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    route_rows, observed_map, template_indices = parse_template_data(
        args.calibration_workbook, args.route_sheet
    )
    lookup = build_route_lookup(args.formatted_tables)

    if args.column_indices:
        column_indices = tuple(args.column_indices)
    else:
        column_indices = template_indices

    rows = []
    observed_sum = 0.0
    estimated_sum = 0.0
    observed_has_value = False
    estimated_has_value = False
    missing_observed: List[str] = []
    missing_estimated: List[str] = []

    for route in route_rows:
        route_id = route["route_id"]
        is_total_row = route_id.strip().lower() == "total"

        observed_all = observed_map.get(route_id)
        if observed_all is None and not is_total_row:
            missing_observed.append(route_id)

        data = lookup.get(route_id)
        if data is None and not is_total_row:
            missing_estimated.append(route_id)
            est_wlk = est_knr = est_pnr = estimated_all = None
        elif is_total_row:
            est_wlk = est_knr = est_pnr = None
            observed_all = observed_sum if observed_has_value else None
            estimated_all = estimated_sum if estimated_has_value else None
        else:
            (
                est_wlk,
                est_knr,
                est_pnr,
                estimated_all,
            ) = compute_estimated_values(data, column_indices)
            if observed_all is not None:
                observed_sum += observed_all
                observed_has_value = True
            if estimated_all is not None:
                estimated_sum += estimated_all
                estimated_has_value = True

        all_diff, pct_diff = compute_differences(estimated_all, observed_all)

        row = [
            route_id,
            route["name"],
            route["number"],
            route["agency"],
            route["mode"],
            "",  # Observed WLK placeholder (Excel leaves blank)
            "",
            "",
            format_number(observed_all),
            format_number(est_wlk),
            format_number(est_knr),
            format_number(est_pnr),
            format_number(estimated_all),
            format_number(all_diff),
            format_number(pct_diff),
        ]
        rows.append(row)

    write_csv(args.output, rows)
    sys.stdout.write(f"Wrote {len(rows)} rows to {args.output}\n")

    if missing_estimated:
        sys.stderr.write(
            "Warning: {} route ids not found in {} ({}...)\n".format(
                len(missing_estimated),
                T1001_SHEET,
                ", ".join(missing_estimated[:10]) + ("..." if len(missing_estimated) > 10 else ""),
            )
        )
    if missing_observed:
        sys.stderr.write(
            "Warning: {} route ids missing observed values ({}...)\n".format(
                len(missing_observed),
                ", ".join(missing_observed[:10]) + ("..." if len(missing_observed) > 10 else ""),
            )
        )

    return 0


def write_csv(path: Path, rows: Sequence[Sequence[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(CSV_COLUMNS)
        writer.writerows(rows)


def parse_template_data(
    workbook_path: Path = Path("../calibration/Boston_Regional_STOPS Calibration Report_2050.xlsx"), 
    sheet_name: str = EV0_SHEET,
) -> Tuple[List[Dict[str, str]], Dict[str, float], Tuple[int, int, int]]:
    rows = read_sheet_rows(workbook_path, sheet_name)
    route_rows: List[Dict[str, str]] = []
    observed_table: Dict[str, float] = {}
    route_ids_seen: set[str] = set()
    column_indices: Tuple[int, int, int] | None = None

    for row_idx, cells in rows:
        if row_idx == 4:
            indices = []
            for col in ("J", "K", "L"):
                idx_value = to_number(cells.get(col))
                if idx_value is not None:
                    indices.append(int(idx_value))
            if len(indices) == 3:
                column_indices = tuple(indices)

        route_id = cells.get("A")
        if (
            row_idx >= 8
            and route_id
            and route_id not in {"Route_ID", "Route ID"}
            and route_id not in route_ids_seen
        ):
            route_ids_seen.add(route_id)
            route_rows.append(
                {
                    "route_id": route_id,
                    "name": cells.get("B", "") or "",
                    "number": cells.get("C", "") or "",
                    "agency": cells.get("D", "") or "",
                    "mode": cells.get("E", "") or "",
                }
            )

        observed_id = cells.get("T")
        if observed_id and observed_id.lower() != "route_id":
            observed_table[observed_id] = to_number(cells.get("W"))

    if column_indices is None:
        column_indices = (4, 5, 6)

    return route_rows, observed_table, column_indices


def build_route_lookup(formatted_tables: Path) -> Dict[str, Dict[str, str | None]]:
    rows = read_sheet_rows(formatted_tables, T1001_SHEET)
    lookup: Dict[str, Dict[str, str | None]] = {}
    for _, cells in rows:
        route_id = cells.get("A")
        if not route_id or route_id == "Route_ID":
            continue
        entry = {}
        for letter, name in zip(COLUMN_LETTERS, OUTPUT_COLUMNS):
            entry[name] = cells.get(letter)
        lookup[route_id] = entry
    return lookup


def compute_estimated_values(
    data: Dict[str, str | None], column_indices: Sequence[int]
) -> Tuple[float | None, float | None, float | None, float | None]:
    values = []
    for idx in column_indices:
        col_name = OUTPUT_COLUMNS[idx - 1]
        values.append(to_number(data.get(col_name)))

    est_wlk = values[0] if len(values) > 0 else None
    est_knr = values[1] if len(values) > 1 else None
    est_pnr = values[2] if len(values) > 2 else None
    estimated_all = sum_values(values)
    return est_wlk, est_knr, est_pnr, estimated_all


def compute_differences(
    estimated_all: float | None, observed_all: float | None
) -> Tuple[float | None, float | None]:
    if estimated_all is None or observed_all is None:
        return None, None
    diff = estimated_all - observed_all
    pct = diff / observed_all if observed_all else None
    return diff, pct


def read_sheet_rows(workbook_path: Path, sheet_name: str) -> List[Tuple[int, Dict[str, str]]]:
    with zipfile.ZipFile(workbook_path) as archive:
        shared = _load_shared_strings(archive)
        sheet = _load_sheet(archive, sheet_name)
        rows = []
        sheet_data = sheet.find("m:sheetData", NS)
        if sheet_data is None:
            return rows
        for row in sheet_data:
            row_idx = int(row.attrib.get("r", "0"))
            rows.append((row_idx, _extract_row_cells(row, shared)))
        return rows


def _extract_row_cells(row: ET.Element, shared_strings: Sequence[str]) -> Dict[str, str]:
    cells: Dict[str, str] = {}
    for cell in row.findall("m:c", NS):
        column = _cell_column(cell.attrib.get("r", ""))
        if not column:
            continue
        value = _cell_value(cell, shared_strings)
        if value is not None:
            cells[column] = value
    return cells


def _cell_column(cell_ref: str) -> str:
    return "".join(ch for ch in cell_ref if ch.isalpha()).upper()


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
    shared_strings = []
    for si in root.findall("m:si", NS):
        text = "".join(t.text or "" for t in si.findall(".//m:t", NS))
        shared_strings.append(text)
    return shared_strings


def _load_sheet(archive: zipfile.ZipFile, sheet_name: str) -> ET.Element:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    rel_map = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in relationships.findall(f"{{{REL_NS}}}Relationship")
    }
    for sheet in workbook.findall("m:sheets/m:sheet", NS):
        if sheet.attrib.get("name") == sheet_name:
            sheet_rid = sheet.attrib.get(
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
            )
            if sheet_rid is None:
                break
            target = rel_map.get(sheet_rid)
            if target is None:
                break
            return ET.fromstring(archive.read(f"xl/{target}"))
    raise KeyError(f"Sheet {sheet_name} not found")


def sum_values(values: Iterable[float | None]) -> float | None:
    total = 0.0
    has_number = False
    for value in values:
        if value is None:
            continue
        total += value
        has_number = True
    return total if has_number else None


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
