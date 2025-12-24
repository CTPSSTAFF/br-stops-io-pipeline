"""Utilities for duplicating the EvO9.01 lookup behavior."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import sys

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
    parser = argparse.ArgumentParser(
        description=(
            "Replicate EvO9.01 lookups (columns O–S) using the formatted STOPS workbook "
            "and emit a CSV summary."
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
        help="Override the O1:S1 indices (values are 1-based column positions)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evo9_01.csv"),
        help="Destination CSV path",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    template_rows, template_indices = parse_template(args.calibration_workbook, args.route_sheet)
    lookup = build_stop_lookup(args.formatted_tables)
    column_indices = tuple(args.column_indices) if args.column_indices else template_indices

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
    data_rows: List[Dict[str, str | float | None]] = []
    column_indices: Tuple[int, int, int, int, int] | None = None

    with WorkbookParser(workbook_path) as parser:
        for row_idx, cells in parser.iter_rows(sheet_name):
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
    lookup: Dict[str, Dict[str, str | None]] = {}
    with WorkbookParser(formatted_tables) as parser:
        for _, cells in parser.iter_rows(T901_SHEET):
            stop_id = cells.get("A")
            if not stop_id or stop_id == "STOP_ID1":
                continue
            entry = {name: cells.get(chr(ord("A") + idx)) for idx, name in enumerate(T901_COLUMNS)}
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


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
