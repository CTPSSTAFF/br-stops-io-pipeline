"""Extract Table 10.01 from a STOPS PRN into an EvO10.01-style CSV."""

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
    parser = argparse.ArgumentParser(
        description="Extract Table 10.01 from a STOPS PRN file and write it to CSV."
    )
    parser.add_argument(
        "--prn-path",
        type=Path,
        default=DEFAULT_PRN,
        help="Path to the STOPS PRN file containing Table 10.01.",
    )
    parser.add_argument(
        "--calibration-workbook",
        type=Path,
        default=DEFAULT_CALIBRATION,
        help="Optional workbook that provides route metadata; if omitted, Route Name/Route #/Agency/Mode come from the PRN text.",
    )
    parser.add_argument(
        "--route-sheet",
        default=DEFAULT_ROUTE_SHEET,
        help="Sheet name holding route metadata (default: EvO10.01).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Destination CSV path (default: tmp/evo101.csv).",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """
    Docstring for main
    
    :param argv: Description
    :type argv: Sequence[str] | None
    :return: Description
    :rtype: int
    """
    args = parse_args(argv or sys.argv[1:])

    route_meta = load_route_metadata(args.calibration_workbook, args.route_sheet)
    prn_rows = parse_prn_table(args.prn_path)
    rows, totals = build_rows(prn_rows, route_meta)

    write_csv(args.output, rows, totals)
    sys.stdout.write(f"Wrote {len(rows) + 1} rows to {args.output}\n")
    return 0


def load_route_metadata(
    workbook_path: Path | None, sheet_name: str
) -> Dict[str, Dict[str, str]]:
    """Return a lookup of route_id -> metadata (name, number, agency, mode).

    Tries the preferred sheet name first, then falls back to EvO10.01 variants.
    """
    if workbook_path is None:
        return {}

    sheets_to_try = [sheet_name, "EvO10.01-2050", "EvO10.01-2045", "EvO10.01"]
    try:
        parser = WorkbookParser(workbook_path)
    except FileNotFoundError:
        sys.stderr.write(f"Warning: metadata workbook {workbook_path} not found; using PRN labels only.\n")
        return {}

    metadata: Dict[str, Dict[str, str]] = {}
    with parser:
        for candidate in sheets_to_try:
            try:
                metadata = parse_metadata_sheet(parser, candidate)
            except KeyError:
                continue
            if metadata:
                break

    if not metadata:
        sys.stderr.write(
            f"Warning: no usable metadata found in {workbook_path}; using PRN labels only.\n"
        )
    return metadata


def parse_metadata_sheet(parser: WorkbookParser, sheet_name: str) -> Dict[str, Dict[str, str]]:
    """Parse a sheet that contains Route_ID, Route Name, Route #, Agency, Mode columns."""
    header_cols = None
    mapping: Dict[str, Dict[str, str]] = {}

    for _, cells in parser.iter_rows(sheet_name):
        if header_cols is None or "route_id" not in header_cols or len(header_cols) < 3:
            candidate = detect_header_columns(cells)
            if "route_id" in candidate and len(candidate) > len(header_cols or {}):
                header_cols = candidate
            continue

        route_id_col = header_cols.get("route_id")
        if not route_id_col:
            continue
        raw_route_id = cells.get(route_id_col)
        if not raw_route_id:
            continue
        route_id = str(raw_route_id).strip()
        if not route_id or route_id.lower() == "route_id":
            continue

        mapping[route_id] = {
            "name": str(cells.get(header_cols.get("route_name", ""), "") or "").strip(),
            "number": str(cells.get(header_cols.get("route_number", ""), "") or "").strip(),
            "agency": str(cells.get(header_cols.get("agency", ""), "") or "").strip(),
            "mode": str(cells.get(header_cols.get("mode", ""), "") or "").strip(),
        }
    return mapping


def detect_header_columns(cells: Dict[str, str]) -> Dict[str, str]:
    """Identify column letters for metadata headers."""
    header_map: Dict[str, str] = {}
    for column, value in cells.items():
        key = normalize_header(value)
        if key in {"routeid", "route_id"}:
            header_map["route_id"] = column
        elif key in {"routename", "route_name"}:
            header_map["route_name"] = column
        elif key in {"route#", "route_num", "routenumber", "route"}:
            header_map["route_number"] = column
        elif key == "agency":
            header_map["agency"] = column
        elif key == "mode":
            header_map["mode"] = column
    return header_map


def normalize_header(value: str | None) -> str:
    if value is None:
        return ""
    return str(value).strip().lower().replace("_", "").replace(" ", "")


def parse_prn_table(prn_path: Path) -> List[Dict[str, object]]:
    """Parse Table 10.01 rows from the PRN file."""
    rows: List[Dict[str, object]] = []
    in_table = False
    with prn_path.open(encoding="latin-1") as handle:
        for line in handle:
            if not in_table:
                if line.startswith("Table    10.01"):
                    in_table = True
                continue

            if line.startswith("Table    "):
                break
            if not line.strip():
                continue
            if line.startswith(("*****", "Comparison", "Total Transit Trips", "Program STOPS")):
                continue
            if line.startswith((" ", "-", "=")):
                continue
            if line.lstrip().startswith("Route_ID"):
                continue

            tokens = line.split()
            if not tokens:
                continue
            if tokens[0].lower() == "total":
                # We compute totals from the parsed rows to stay consistent with metadata filtering.
                continue
            if len(tokens) < 14:
                continue

            numbers = tokens[-13:]
            try:
                numeric = [float(value) for value in numbers]
            except ValueError:
                continue

            count = numeric[0]
            nb_wlk, nb_knr, nb_pnr, nb_all = numeric[5:9]

            route_id = tokens[0]
            route_label = " ".join(tokens[1:-13]).strip()
            if route_label.startswith("--"):
                route_label = route_label[2:].strip()

            rows.append(
                {
                    "route_id": route_id,
                    "route_label": route_label,
                    "all_obs": count,
                    "wlk_est": nb_wlk,
                    "knr_est": nb_knr,
                    "pnr_est": nb_pnr,
                    "all_est": nb_all,
                }
            )
    return rows


def build_rows(
    prn_rows: List[Dict[str, object]], route_meta: Dict[str, Dict[str, str]]
) -> tuple[List[List[str]], Dict[str, float | None]]:
    rows: List[List[str]] = []
    observed_total = 0.0
    estimated_total = 0.0

    for entry in prn_rows:
        route_id = entry["route_id"]  # type: ignore[assignment]
        metadata = route_meta.get(route_id, {})
        name, number = derive_name_and_number(entry["route_label"], metadata)
        agency, mode = derive_agency_mode(route_id, metadata, number, name)

        all_obs = float(entry["all_obs"])  # type: ignore[arg-type]
        wlk_est = float(entry["wlk_est"])  # type: ignore[arg-type]
        knr_est = float(entry["knr_est"])  # type: ignore[arg-type]
        pnr_est = float(entry["pnr_est"])  # type: ignore[arg-type]
        all_est = float(entry["all_est"])  # type: ignore[arg-type]

        observed_total += all_obs
        estimated_total += all_est

        diff, pct = compute_differences(all_est, all_obs)

        rows.append(
            [
                route_id,
                name,
                number,
                agency,
                mode,
                "",
                "",
                "",
                format_number(all_obs),
                format_number(wlk_est),
                format_number(knr_est),
                format_number(pnr_est),
                format_number(all_est),
                format_number(diff),
                format_number(pct),
            ]
        )

    total_diff, total_pct = compute_differences(estimated_total, observed_total)
    totals: Dict[str, float | None] = {
        "observed": observed_total,
        "estimated": estimated_total,
        "diff": total_diff,
        "pct": total_pct,
    }
    return rows, totals


def derive_name_and_number(
    label: str, metadata: Dict[str, str] | None = None
) -> tuple[str, str]:
    """Return (name, number) preferring metadata, otherwise splitting the PRN label."""
    if metadata:
        name = metadata.get("name") or ""
        number = metadata.get("number") or ""
        if name or number:
            return name, number

    if "-" in label:
        number_part, _, remainder = label.partition("-")
        return remainder.strip(), number_part.strip()
    return label, ""


def derive_agency_mode(
    route_id: str, metadata: Dict[str, str], number: str, name: str
) -> tuple[str, str]:
    """Return agency/mode using metadata first, otherwise inference by route id."""
    agency = metadata.get("agency") or ""
    mode = metadata.get("mode") or ""
    if agency and mode:
        return agency, mode

    rid = route_id.lower()

    if rid.startswith("cr-"):
        return agency or "MBTA Commuter Rail", mode or "CR"
    if rid.startswith("boat-"):
        return agency or "MBTA Ferry", mode or "Ferry"
    if any(rid.startswith(prefix) for prefix in ("red", "blue", "orange")):
        return agency or "MBTA HRT", mode or "HR"
    if rid.startswith("mattapan") or rid.startswith("green-"):
        return agency or "MBTA LRT", mode or "LRT"

    if rid.endswith("&m"):
        return agency or "MWRTA", mode or "MWRTA Bus"
    if rid.endswith("&v"):
        return agency or "MVRTA", mode or "MVRTA Bus"
    if rid.endswith("&c"):
        return agency or "CATA", mode or "CATA Bus"
    if rid.endswith("&b"):
        return agency or "BAT", mode or "BAT Bus"
    if rid.endswith("&t"):
        # Default MBTA bus unless already covered above.
        return agency or "MBTA", mode or "MBTA Bus"

    # Fallback: keep whatever partial metadata exists.
    return agency, mode


def compute_differences(estimated_all: float, observed_all: float) -> tuple[float, float | None]:
    diff = estimated_all - observed_all
    pct = diff / observed_all if observed_all else None
    return diff, pct


def write_csv(path: Path, rows: List[List[str]], totals: Dict[str, float | None]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(CSV_COLUMNS)
        writer.writerows(rows)
        writer.writerow(
            [
                "Total",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                format_number(totals["observed"]),
                "",
                "",
                "",
                format_number(totals["estimated"]),
                format_number(totals["diff"]),
                format_number(totals["pct"]),
            ]
        )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
