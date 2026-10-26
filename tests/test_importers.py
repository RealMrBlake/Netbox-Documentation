from io import BytesIO
import importlib.util
from pathlib import Path
import sys

import pytest
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font
from openpyxl.worksheet.table import Table, TableStyleInfo


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
    assert "<h2>Server</h2>" in result.markdown
    assert result.body_format == "html"
    assert "web01" in result.markdown


def test_xlsx_preserves_cell_fill_and_font_colors_as_html():
    workbook = Workbook()
    sheet = workbook.active
    sheet["A1"] = "Standort"
    sheet["A1"].fill = PatternFill(fill_type="solid", fgColor="A5BF60")
    sheet["A1"].font = Font(color="FFFFFF", bold=True)
    sheet["A2"] = "Verwaltung"
    sheet["A2"].fill = PatternFill(fill_type="solid", fgColor="EAF0DC")
    stream = BytesIO()
    workbook.save(stream)

    result = import_document(Upload(stream.getvalue(), "farben.xlsx"))

    assert result.body_format == "html"
    assert "background-color: #a5bf60" in result.markdown
    assert "color: #ffffff" in result.markdown
    assert "font-weight: bold" in result.markdown
    assert "background-color: #eaf0dc" in result.markdown


def test_xlsx_renders_builtin_excel_table_style_colors_in_preview_html():
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Standort", "Adresse"])
    sheet.append(["Verwaltung", "10.1.2.17"])
    sheet.append(["Büro", "10.1.2.18"])
    table = Table(displayName="Standorte", ref="A1:B3")
    table.tableStyleInfo = TableStyleInfo(
        name="TableStyleMedium4", showFirstColumn=False,
        showLastColumn=False, showRowStripes=True, showColumnStripes=False,
    )
    sheet.add_table(table)
    stream = BytesIO()
    workbook.save(stream)

    result = import_document(Upload(stream.getvalue(), "tabelle.xlsx"))

    assert result.body_format == "html"
    assert "Standort" in result.markdown
    assert result.markdown.count("background-color:") >= 4
    assert "color: #ffffff" in result.markdown


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


def test_excel_import_renders_only_selected_source_sheets():
    workbook = Workbook()
    first = workbook.active
    first.title = "Nicht gewählt"
    first.append(["Sehr viele Daten"])
    second = workbook.create_sheet("Gewählt")
    second.append(["Nur dieses Blatt"])
    third = workbook.create_sheet("Auch nicht gewählt")
    third.append(["Weitere Daten"])
    stream = BytesIO()
    workbook.save(stream)

    results = import_excel_sheets(
        Upload(stream.getvalue(), "auswahl.xlsx"), selected_indexes={1},
    )

    assert len(results) == 1
    assert results[0].title == "Gewählt"
    assert results[0].source_index == 1
    assert "Nur dieses Blatt" in results[0].markdown
    assert "Sehr viele Daten" not in results[0].markdown


def test_excel_metadata_phase_skips_document_rendering():
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Großes Blatt"
    sheet.append(["Name", "IP"])
    sheet.append(["web01", "10.0.0.1"])
    stream = BytesIO()
    workbook.save(stream)

    results = import_excel_sheets(
        Upload(stream.getvalue(), "kunde.xlsx"), metadata_only=True,
        include_image_data=False,
    )

    assert [result.title for result in results] == ["Großes Blatt"]
    assert results[0].markdown == ""


def test_excel_preview_limits_rows_without_affecting_sheet_detection():
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Nummer"])
    for number in range(1, 151):
        sheet.append([number])
    stream = BytesIO()
    workbook.save(stream)

    results = import_excel_sheets(
        Upload(stream.getvalue(), "gross.xlsx"), preview_max_rows=100,
        include_image_data=False,
    )

    assert "Preview limited to 100 rows" in results[0].markdown
    assert ">99<" in results[0].markdown
    assert ">100<" not in results[0].markdown


def test_excel_flatten_turns_cells_into_document_flow():
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Name", "IP"])
    sheet.append(["db01", "10.0.0.2"])
    stream = BytesIO()
    workbook.save(stream)

    results = import_excel_sheets(Upload(stream.getvalue(), "server.xlsx"), flatten=True)

    assert results[0].body_format == "html"
    assert results[0].markdown == "<p>Name<br>IP</p>\n<p>db01<br>10.0.0.2</p>"
    assert "Datensatz" not in results[0].markdown
    assert "Feld" not in results[0].markdown
    assert "<table" not in results[0].markdown


def test_excel_flatten_preserves_explicit_excel_tables_only():
    workbook = Workbook()
    sheet = workbook.active
    sheet["A1"] = "Name"
    sheet["B1"] = "IP"
    sheet["A2"] = "web01"
    sheet["B2"] = "10.0.0.1"
    sheet["D1"] = "Normaler Hinweis"
    sheet.add_table(Table(displayName="ServerTable", ref="A1:B2"))
    stream = BytesIO()
    workbook.save(stream)

    results = import_excel_sheets(Upload(stream.getvalue(), "server.xlsx"), flatten=True)
    markdown = results[0].markdown

    assert "Normaler Hinweis" in markdown
    assert "<table" in markdown
    assert "Name" in markdown
    assert "web01" in markdown
    assert "Datensatz" not in markdown


def test_excel_flatten_preserves_colors_of_explicit_excel_tables():
    workbook = Workbook()
    sheet = workbook.active
    sheet["A1"] = "Standort"
    sheet["B1"] = "Adresse"
    sheet["A2"] = "Verwaltung"
    sheet["B2"] = "10.1.2.17"
    for cell in (sheet["A1"], sheet["B1"]):
        cell.fill = PatternFill(fill_type="solid", fgColor="A5BF60")
        cell.font = Font(color="FFFFFF", bold=True)
    sheet.add_table(Table(displayName="Standorte", ref="A1:B2"))
    stream = BytesIO()
    workbook.save(stream)

    results = import_excel_sheets(Upload(stream.getvalue(), "farben.xlsx"), flatten=True)

    assert results[0].body_format == "html"
    assert results[0].markdown.count("background-color: #a5bf60") == 2
    assert results[0].markdown.count("color: #ffffff") == 2


def test_excel_flatten_preserves_colored_cells_outside_tables():
    workbook = Workbook()
    sheet = workbook.active
    sheet["A1"] = "Wichtiger Hinweis"
    sheet["A1"].fill = PatternFill(fill_type="solid", fgColor="FFF3BF")
    sheet["A1"].font = Font(color="9C2A2A", bold=True)
    sheet["A3"] = "Normaler Text"
    stream = BytesIO()
    workbook.save(stream)

    results = import_excel_sheets(Upload(stream.getvalue(), "hinweis.xlsx"), flatten=True)

    assert results[0].body_format == "html"
    assert '<span style="background-color: #fff3bf; color: #9c2a2a; font-weight: bold' in results[0].markdown
    assert "Wichtiger Hinweis</span>" in results[0].markdown
    assert "<table" not in results[0].markdown
