"""Shared helpers for parsing Excel workbooks used by the shop scripts."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Dict, Iterator, Sequence, Tuple

import xml.etree.ElementTree as ET

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


class WorkbookParser:
    """Utility for reading worksheet XML data from an XLSX archive."""

    def __init__(self, workbook_path: Path | str):
        self.path = Path(workbook_path)
        self._archive = zipfile.ZipFile(self.path)
        self._shared_strings = self._load_shared_strings()
        self._sheet_cache: Dict[str, ET.Element] = {}
        self._workbook_tree: ET.Element | None = None
        self._rel_map: Dict[str, str] | None = None

    def close(self) -> None:
        self._archive.close()

    def __enter__(self) -> "WorkbookParser":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: D401
        self.close()

    def iter_rows(self, sheet_name: str, include_formulas: bool = False) -> Iterator[Tuple[int, Dict[str, str]]]:
        sheet = self._get_sheet(sheet_name)
        sheet_data = sheet.find("m:sheetData", NS)
        if sheet_data is None:
            return
        for row in sheet_data:
            row_idx = int(row.attrib.get("r", "0"))
            cells: Dict[str, str] = {}
            for cell in row.findall("m:c", NS):
                column = "".join(ch for ch in cell.attrib.get("r", "") if ch.isalpha()).upper()
                if not column:
                    continue
                value = self._cell_value(cell)
                if value is not None:
                    cells[column] = value
                if include_formulas:
                    formula_node = cell.find("m:f", NS)
                    if formula_node is not None and formula_node.text:
                        cells[(column, "formula")] = formula_node.text
            yield row_idx, cells

    # Internal helpers -------------------------------------------------

    def _load_shared_strings(self) -> list[str]:
        try:
            data = self._archive.read("xl/sharedStrings.xml")
        except KeyError:
            return []
        root = ET.fromstring(data)
        strings = []
        for si in root.findall("m:si", NS):
            strings.append("".join(t.text or "" for t in si.findall(".//m:t", NS)))
        return strings

    def _ensure_workbook_loaded(self) -> None:
        if self._workbook_tree is not None:
            return
        self._workbook_tree = ET.fromstring(self._archive.read("xl/workbook.xml"))
        rels = ET.fromstring(self._archive.read("xl/_rels/workbook.xml.rels"))
        self._rel_map = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in rels.findall(f"{{{REL_NS}}}Relationship")
        }

    def _get_sheet(self, sheet_name: str) -> ET.Element:
        if sheet_name in self._sheet_cache:
            return self._sheet_cache[sheet_name]
        self._ensure_workbook_loaded()
        assert self._workbook_tree is not None and self._rel_map is not None
        sheet_target = None
        for sheet in self._workbook_tree.findall("m:sheets/m:sheet", NS):
            if sheet.attrib.get("name") == sheet_name:
                sheet_rid = sheet.attrib.get(
                    "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
                )
                if sheet_rid:
                    sheet_target = self._rel_map.get(sheet_rid)
                break
        if sheet_target is None:
            raise KeyError(f"Sheet {sheet_name} not found in {self.path}")
        xml = ET.fromstring(self._archive.read(f"xl/{sheet_target}"))
        self._sheet_cache[sheet_name] = xml
        return xml

    def _cell_value(self, cell: ET.Element) -> str | None:
        cell_type = cell.attrib.get("t")
        if cell_type == "inlineStr":
            return "".join(t.text or "" for t in cell.findall("m:is/m:t", NS)).strip()
        value_node = cell.find("m:v", NS)
        if value_node is None:
            return None
        if cell_type == "s":
            index = int(value_node.text or "0")
            if 0 <= index < len(self._shared_strings):
                return self._shared_strings[index]
            return None
        return value_node.text


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

