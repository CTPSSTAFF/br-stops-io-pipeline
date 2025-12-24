"""Utilities for duplicating the EvO9.01 lookup behavior.

This module reads the formatted STOPS workbook (A2_Formatted_Tables.xlsx),
pulls the `T_9.01` sheet, and replicates the Excel VLOOKUPs embedded in
the EvO9.01 tab of the calibration template. The script mirrors the values
Excel places in columns O through S (WLK/KNR/PNR/XFER/TOTAL) and writes them
to CSV alongside the observed boardings and difference column.
"""

from __future__ import annotations

import argparse
import csv
import sys
import zipfile
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import xml.etree.ElementTree as ET

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

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
    parser = argparse.ArgumentParser(
        description=(
            "Replicate EvO9.01 lookups (columns O–S) using "
            "A2_Formatted_Tables.xlsx and emit a CSV summary."
        )
    )
    parser.add_argument(
        "--formatted-tables",
        type=Path,
        default=Path("calibration/A2_Formatted_Tables.xlsx"),
        help="Path to A2_Formatted_Tables.xlsx",
    )
    parser.add_argument(
        "--calibration-workbook",
        type=Path,
        default=Path("calibration/Boston_Regional_STOPS Calibration Report_2050.xlsx"),
        help="Workbook containing the EvO9.01 sheet",
    )
    parser.add_argument(
        "--route-sheet",
        default=EV0_SHEET,
        help="Template sheet name (default: EvO9.01)",
    )
    parser.add_argument(
        "--column-indices",
        type=int,
        nargs=5,
        metavar=("WLK_COL", "KNR_COL", "PNR_COL", "XFER_COL", "TOTAL_COL"),
        help="Override the O1:S1 VLOOKUP indices (1-based column positions)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evo9_01.csv"),
        help="Output CSV path (default: evo9_01.csv)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    template_rows, template_indices = parse_template(args.calibration_workbook, args.route_sheet)
    lookup = build_stop_lookup(args.formatted_tables)

    if args.column_indices:
        column_indices = tuple(args.column_indices)
    else:
        column_indices = template_indices

    rows: List[List[str]] = []
    missing_estimated: List[str] = []

    for row in template_rows:
        stop_id = row["STOP_ID1"]
        observed = row["observed"]

        data = lookup.get(stop_id)
        if data is None:
            missing_estimated.append(stop_id)
            estimated_values = [None] * 5
        else:
            estimated_values = compute_estimated_values(data, column_indices)

        difference = None
        estimated_total = estimated_values[-1] if estimated_values else None
        if estimated_total is not None and observed is not None:
            difference = estimated_total - observed

        rows.append(
            [
                row["STATION"],
                row["Route"],
                row["STAT_GRP"],
                row["GRP_NAME"],
                row["STOP_ID1"],
                row["STOP_ID2"],
                row["STOP_ID3"],
                row["STOP_ID4"],
                row["Agency"],
                row["Mode"],
                format_number(observed),
                format_number(estimated_values[0]),
                format_number(estimated_values[1]),
                format_number(estimated_values[2]),
                format_number(estimated_values[3]),
                format_number(estimated_values[4]),
                format_number(difference),
            ]
        )

    write_csv(args.output, rows)
    sys.stdout.write(f"Wrote {len(rows)} rows to {args.output}\n")

    if missing_estimated:
        sys.stderr.write(
            "Warning: {} stop ids missing from {} ({}...)\n".format(
                len(missing_estimated),
                T901_SHEET,
                ", ".join(missing_estimated[:10]) + ("..." if len(missing_estimated) > 10 else ""),
            )
        )

    return 0


def write_csv(path: Path, rows: Sequence[Sequence[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(CSV_COLUMNS)
        writer.writerows(rows)


def parse_template(
    workbook_path: Path, sheet_name: str
) -> Tuple[List[Dict[str, str | float | None]], Tuple[int, int, int, int, int]]:
    rows = read_sheet_rows(workbook_path, sheet_name)
    data_rows: List[Dict[str, str | float | None]] = []
    column_indices: Tuple[int, int, int, int, int] | None = None

    for row_idx, cells in rows:
        if row_idx == 1:
            indices = []
            for col in ("O", "P", "Q", "R", "S"):
                idx_value = to_number(cells.get(col))
                if idx_value is not None:
                    indices.append(int(idx_value))
            if len(indices) == 5:
                column_indices = tuple(indices)

        station = cells.get("D")
        stop_id = cells.get("H")
        if (
            row_idx >= 5
            and stop_id
            and stop_id not in {"STOP_ID1", "Stop_ID1"}
            and (station or cells.get("E"))
        ):
            data_rows.append(
                {
                    "STATION": station or "",
                    "Route": cells.get("E", "") or "",
                    "STAT_GRP": cells.get("F", "") or "",
                    "GRP_NAME": cells.get("G", "") or "",
                    "STOP_ID1": stop_id,
                    "STOP_ID2": cells.get("I", "") or "",
                    "STOP_ID3": cells.get("J", "") or "",
                    "STOP_ID4": cells.get("K", "") or "",
                    "Agency": cells.get("L", "") or "",
                    "Mode": cells.get("M", "") or "",
                    "observed": to_number(cells.get("N")),
                }
            )

    if column_indices is None:
        column_indices = (3, 4, 5, 6, 7)

    return data_rows, column_indices


def build_stop_lookup(formatted_tables: Path) -> Dict[str, Dict[str, str | None]]:
    rows = read_sheet_rows(formatted_tables, T901_SHEET)
    lookup: Dict[str, Dict[str, str | None]] = {}
    for _, cells in rows:
        stop_id = cells.get("A")
        if not stop_id or stop_id == "STOP_ID1":
            continue
        entry = {}
        for idx, name in enumerate(T901_COLUMNS):
            column_letter = chr(ord("A") + idx)
            entry[name] = cells.get(column_letter)
        lookup[stop_id] = entry
    return lookup


def compute_estimated_values(
    data: Dict[str, str | None], column_indices: Sequence[int]
) -> List[float | None]:
    values: List[float | None] = []
    for idx in column_indices:
        column_name = T901_COLUMNS[idx - 1]
        values.append(to_number(data.get(column_name)))
    return values


def read_sheet_rows(workbook_path: Path, sheet_name: str) -> List[Tuple[int, Dict[str, str]]]:
    with zipfile.ZipFile(workbook_path) as archive:
        shared = _load_shared_strings(archive)
        sheet = _load_sheet(archive, sheet_name)
        rows: List[Tuple[int, Dict[str, str]]] = []
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
    shared_strings: List[str] = []
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

