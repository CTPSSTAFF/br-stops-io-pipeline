"""
Purpose:
    Shared utility module for extracting data from Excel (.xlsx) files.

Data Context:
    The STOPS model heavily relies on Excel for configuration and reporting. 
    Instead of using heavy third-party libraries like `pandas` or `openpyxl`, 
    this module reads the underlying XML structure of an Excel file directly 
    from its ZIP archive. This is significantly faster and uses less memory 
    when scanning large STOPS calibration workbooks.
"""

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
        
        # In Excel XML, text strings are not stored in the cells themselves to save space.
        # They are stored in a central 'sharedStrings.xml' file, and the cells reference 
        # them by an integer index. We load this mapping into memory first.
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
        """
        Logical Process:
            1. Locates the requested sheet's XML file within the zipped XLSX.
            2. Finds the `<sheetData>` node containing all rows.
            3. Yields one row at a time. For each cell, it determines the column 
               letter, checks if it's a raw value or a shared string reference, 
               resolves the value, and returns a dictionary of column -> value.
        """
        worksheet_xml = self._get_sheet(sheet_name)
        sheet_data_node = worksheet_xml.find("m:sheetData", NS)
        if sheet_data_node is None:
            return
            
        for row_node in sheet_data_node:
            excel_row_index = int(row_node.attrib.get("r", "0"))
            row_cell_values: Dict[str, str] = {}
            
            for cell_node in row_node.findall("m:c", NS):
                # Extract just the alphabetic part of the cell reference (e.g., 'A12' -> 'A')
                column_letter = "".join(ch for ch in cell_node.attrib.get("r", "") if ch.isalpha()).upper()
                if not column_letter:
                    continue
                    
                cell_value = self._cell_value(cell_node)
                if cell_value is not None:
                    row_cell_values[column_letter] = cell_value
                    
                if include_formulas:
                    formula_node = cell_node.find("m:f", NS)
                    if formula_node is not None and formula_node.text:
                        row_cell_values[(column_letter, "formula")] = formula_node.text
                        
            yield excel_row_index, row_cell_values

    def _load_shared_strings(self) -> list[str]:
        """Reads the global string table from the Excel archive."""
        try:
            raw_xml_data = self._archive.read("xl/sharedStrings.xml")
        except KeyError:
            return []
        xml_root = ET.fromstring(raw_xml_data)
        extracted_strings = []
        for string_item in xml_root.findall("m:si", NS):
            extracted_strings.append("".join(t.text or "" for t in string_item.findall(".//m:t", NS)))
        return extracted_strings

    def _ensure_workbook_loaded(self) -> None:
        """Parses the relationships file to map sheet names to their underlying XML file paths."""
        if self._workbook_tree is not None:
            return
        self._workbook_tree = ET.fromstring(self._archive.read("xl/workbook.xml"))
        relationship_tree = ET.fromstring(self._archive.read("xl/_rels/workbook.xml.rels"))
        self._rel_map = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in relationship_tree.findall(f"{{{REL_NS}}}Relationship")
        }

    def _get_sheet(self, sheet_name: str) -> ET.Element:
        """Resolves a sheet name to its XML tree, caching it for subsequent calls."""
        if sheet_name in self._sheet_cache:
            return self._sheet_cache[sheet_name]
            
        self._ensure_workbook_loaded()
        assert self._workbook_tree is not None and self._rel_map is not None
        
        sheet_target_path = None
        for sheet_node in self._workbook_tree.findall("m:sheets/m:sheet", NS):
            if sheet_node.attrib.get("name") == sheet_name:
                sheet_rid = sheet_node.attrib.get(
                    "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
                )
                if sheet_rid:
                    sheet_target_path = self._rel_map.get(sheet_rid)
                break
                
        if sheet_target_path is None:
            raise KeyError(f"Sheet {sheet_name} not found in {self.path}")
            
        parsed_sheet_xml = ET.fromstring(self._archive.read(f"xl/{sheet_target_path}"))
        self._sheet_cache[sheet_name] = parsed_sheet_xml
        return parsed_sheet_xml

    def _cell_value(self, cell_node: ET.Element) -> str | None:
        """Determines if a cell holds a direct value or a pointer to the shared string table."""
        cell_type = cell_node.attrib.get("t")
        if cell_type == "inlineStr":
            return "".join(t.text or "" for t in cell_node.findall("m:is/m:t", NS)).strip()
            
        value_node = cell_node.find("m:v", NS)
        if value_node is None:
            return None
            
        if cell_type == "s":
            shared_string_index = int(value_node.text or "0")
            if 0 <= shared_string_index < len(self._shared_strings):
                return self._shared_strings[shared_string_index]
            return None
            
        return value_node.text


def to_number(raw_value: str | None) -> float | None:
    """Safely converts string representations of numbers (including commas) into floats."""
    if raw_value is None:
        return None
    cleaned_text = str(raw_value).replace(",", "").strip()
    if not cleaned_text:
        return None
    try:
        return float(cleaned_text)
    except ValueError:
        return None


def format_number(numeric_value: float | None) -> str:
    """Formats floats for CSV output, dropping trailing zeros and decimals for whole numbers."""
    if numeric_value is None:
        return ""
    if abs(numeric_value - round(numeric_value)) < 1e-9:
        return str(int(round(numeric_value)))
    return f"{numeric_value:.6f}".rstrip("0").rstrip(".")