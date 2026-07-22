from io import BytesIO
import importlib.util
from pathlib import Path
import sys

import pytest
from openpyxl import Workbook


spec = importlib.util.spec_from_file_location(
    "documentation_importers", Path(__file__).parents[1] / "netbox_documentation" / "importers.py"
)
importers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = importers
spec.loader.exec_module(importers)
ImportFailure = importers.ImportFailure
import_document = importers.import_document
import_excel_sheets = importers.import_excel_sheets


class Upload(BytesIO):
    def __init__(self, value, name):
        super().__init__(value)
        self.name = name


def test_markdown_import():
    result = import_document(Upload(b"# Hallo", "test.md"))
    assert result.markdown == "# Hallo"


def test_xlsx_imports_sheets_as_tables():
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Server"
    sheet.append(["Name", "IP"])
    sheet.append(["web01", "10.0.0.1"])
    stream = BytesIO()
    workbook.save(stream)
    result = import_document(Upload(stream.getvalue(), "server.xlsx"))
    assert "## Server" in result.markdown
    assert "web01" in result.markdown


def test_rejects_legacy_excel():
    with pytest.raises(ImportFailure, match="xlsx"):
        import_document(Upload(b"", "legacy.xls"))


def test_excel_multi_sheet_import_creates_one_result_per_sheet():
    workbook = Workbook()
    first = workbook.active
    first.title = "Server"
    first.append(["Name", "IP"])
    first.append(["web01", "10.0.0.1"])
    second = workbook.create_sheet("Kontakte")
    second.append(["Name", "Telefon"])
    second.append(["Leitstelle", "1234"])
    workbook.create_sheet("Leer")
    stream = BytesIO()
    workbook.save(stream)

    results = import_excel_sheets(Upload(stream.getvalue(), "kunde.xlsx"))

    assert [result.title for result in results] == ["Server", "Kontakte"]
    assert "web01" in results[0].markdown
    assert "Leitstelle" in results[1].markdown
