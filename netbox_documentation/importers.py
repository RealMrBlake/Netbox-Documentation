from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from html import escape
import re


class ImportFailure(ValueError):
    pass


@dataclass
class ImportResult:
    markdown: str
    warnings: list[str] = field(default_factory=list)
    body_format: str = "markdown"


@dataclass
class ImportedImage:
    name: str
    content: bytes
    content_type: str
    cell: str = ""


@dataclass
class ExcelSheetResult:
    title: str
    markdown: str
    images: list[ImportedImage] = field(default_factory=list)
    body_format: str = "markdown"


def import_document(upload, flatten_excel=False) -> ImportResult:
    suffix = Path(upload.name).suffix.lower()
    content = upload.read()
    upload.seek(0)
    if suffix == ".docx":
        return _docx(content)
    if suffix in {".xlsx", ".xlsm"}:
        return _xlsx(content, flatten=flatten_excel)
    if suffix == ".pdf":
        return _pdf(content)
    if suffix in {".md", ".txt"}:
        return ImportResult(content.decode("utf-8-sig"))
    if suffix in {".doc", ".xls"}:
        raise ImportFailure("Alte .doc/.xls-Dateien bitte zuerst als .docx/.xlsx speichern.")
    raise ImportFailure("Unterstützt werden DOCX, XLSX, XLSM, PDF, Markdown und Text.")


def _docx(content):
    import mammoth
    result = mammoth.convert_to_markdown(BytesIO(content))
    warnings = [message.message for message in result.messages]
    return ImportResult(result.value.strip(), warnings)


def _render_excel_rows(rows, flatten=False):
    from tabulate import tabulate
    width = max(len(row) for row in rows)
    rows = [row + [""] * (width - len(row)) for row in rows]
    header, body = rows[0], rows[1:]
    if not flatten:
        return tabulate(body, headers=header, tablefmt="github")
    # Document-style flattening: retain every cell in reading order without
    # inventing record headings or field/value labels. Cells in one Excel row
    # become lines in one paragraph; Excel rows are separated by a blank line.
    blocks = []
    for row in rows:
        values = [_escape_markdown_text(value) for value in row if value != ""]
        if values:
            blocks.append("  \n".join(values))
    return "\n\n".join(blocks) or "_Keine Inhalte_"


def _escape_markdown_text(value):
    value = str(value).replace("\\", "\\\\")
    for character in ("*", "_", "[", "]", "<", ">", "#", "|"):
        value = value.replace(character, f"\\{character}")
    return value.replace("\r\n", "  \n").replace("\r", "  \n").replace("\n", "  \n")


def _xlsx(content, flatten=False):
    from openpyxl import load_workbook
    workbook = load_workbook(BytesIO(content), read_only=False, data_only=True)
    sections = []
    for sheet in workbook.worksheets:
        rows = [["" if cell is None else str(cell) for cell in row] for row in sheet.iter_rows(values_only=True)]
        while rows and not any(value for value in rows[-1]):
            rows.pop()
        if not rows:
            continue
        rendered = _render_flattened_worksheet(sheet, workbook) if flatten else _render_excel_worksheet_html(sheet, workbook)
        sections.append(f"<h2>{escape(sheet.title)}</h2>\n{rendered}")
    if not sections:
        raise ImportFailure("Die Arbeitsmappe enthält keine Daten.")
    return ImportResult("\n\n".join(sections), body_format="html")


def import_excel_sheets(
    upload, flatten=False, *, metadata_only=False, preview_max_rows=None,
    include_image_data=True,
) -> list[ExcelSheetResult]:
    """Convert each non-empty worksheet into an individual document payload."""
    from openpyxl import load_workbook
    from openpyxl.utils import get_column_letter

    suffix = Path(upload.name).suffix.lower()
    if suffix not in {".xlsx", ".xlsm"}:
        raise ImportFailure("Der Mehrblattimport unterstützt XLSX- und XLSM-Dateien.")
    upload.seek(0)
    workbook = load_workbook(upload, read_only=False, data_only=True)
    results = []
    for sheet in workbook.worksheets:
        images = []
        for number, image in enumerate(getattr(sheet, "_images", ()), 1):
            image_format = (getattr(image, "format", None) or "png").lower()
            if image_format == "jpg":
                image_format = "jpeg"
            if image_format not in {"png", "jpeg", "gif", "webp"}:
                continue
            anchor = getattr(image, "anchor", None)
            marker = getattr(anchor, "_from", None)
            cell = f"{get_column_letter(marker.col + 1)}{marker.row + 1}" if marker else ""
            image_content = b""
            if include_image_data and not metadata_only:
                try:
                    image_content = image._data()
                except (AttributeError, OSError, ValueError):
                    continue
            images.append(ImportedImage(
                name=f"{slugify_filename(sheet.title)}-{number}.{image_format if image_format != 'jpeg' else 'jpg'}",
                content=image_content, content_type=f"image/{image_format}", cell=cell,
            ))
        has_content = _worksheet_has_content(sheet)
        if not has_content and not images:
            continue
        if metadata_only:
            markdown = ""
        elif has_content:
            markdown = (
                _render_flattened_worksheet(sheet, workbook, max_rows=preview_max_rows) if flatten else
                _render_excel_worksheet_html(sheet, workbook, max_rows=preview_max_rows)
            )
        else:
            markdown = ""
        results.append(ExcelSheetResult(
            title=sheet.title, markdown=markdown, images=images,
            body_format="html",
        ))
    workbook.close()
    upload.seek(0)
    if not results:
        raise ImportFailure("Die Arbeitsmappe enthält keine Daten oder unterstützten Bilder.")
    return results


def _worksheet_has_content(sheet):
    """Check for a value without materializing the complete worksheet in memory."""
    return any(
        cell.value not in (None, "")
        for row in sheet.iter_rows()
        for cell in row
    )


def slugify_filename(value):
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.")
    return value[:80] or "arbeitsblatt"


def _excel_color(color, workbook):
    """Resolve RGB, indexed and theme-based openpyxl colors to a CSS hex value."""
    if not color or not getattr(color, "type", None):
        return None
    value = None
    if color.type == "rgb" and color.rgb:
        value = str(color.rgb)[-6:]
    elif color.type == "indexed" and color.indexed is not None:
        from openpyxl.styles.colors import COLOR_INDEX
        index = int(color.indexed)
        if 0 <= index < len(COLOR_INDEX):
            value = COLOR_INDEX[index][-6:]
    elif color.type == "theme" and color.theme is not None and workbook.loaded_theme:
        from xml.etree import ElementTree
        try:
            root = ElementTree.fromstring(workbook.loaded_theme)
            scheme = root.find(".//{http://schemas.openxmlformats.org/drawingml/2006/main}clrScheme")
            entries = list(scheme) if scheme is not None else []
            entry = entries[int(color.theme)]
            color_node = next(iter(entry))
            value = color_node.attrib.get("val") or color_node.attrib.get("lastClr")
        except (ElementTree.ParseError, IndexError, StopIteration, TypeError, ValueError):
            value = None
    if not value or not re.fullmatch(r"[0-9A-Fa-f]{6}", value):
        return None
    rgb = [int(value[index:index + 2], 16) for index in (0, 2, 4)]
    tint = float(getattr(color, "tint", 0) or 0)
    if tint:
        rgb = [round(component * (1 + tint) if tint < 0 else component + (255 - component) * tint) for component in rgb]
    return "#" + "".join(f"{max(0, min(255, component)):02x}" for component in rgb)


def _excel_cell_style(cell, workbook):
    declarations = []
    if cell.fill and cell.fill.fill_type:
        fill = (
            _excel_color(getattr(cell.fill, "fgColor", None), workbook) or
            _excel_color(getattr(cell.fill, "bgColor", None), workbook)
        )
        if not fill and cell.fill.fill_type == "linear":
            stops = getattr(cell.fill, "stop", ())
            fill = _excel_color(stops[0].color, workbook) if stops else None
        if fill:
            declarations.append(f"background-color: {fill}")
    font_color = _excel_color(cell.font.color, workbook)
    if font_color:
        declarations.append(f"color: {font_color}")
    if cell.font.bold:
        declarations.append("font-weight: bold")
    if cell.font.italic:
        declarations.append("font-style: italic")
    if cell.font.sz:
        declarations.append(f"font-size: {float(cell.font.sz):g}pt")
    if cell.alignment.horizontal in {"left", "center", "right", "justify"}:
        declarations.append(f"text-align: {cell.alignment.horizontal}")
    if cell.alignment.vertical in {"top", "center", "bottom"}:
        declarations.append(f"vertical-align: {'middle' if cell.alignment.vertical == 'center' else cell.alignment.vertical}")
    if cell.alignment.wrap_text:
        declarations.append("white-space: normal")
    return "; ".join(declarations)


def _tint_hex(value, tint):
    import colorsys
    rgb = tuple(int(value[index:index + 2], 16) / 255 for index in (1, 3, 5))
    hue, lightness, saturation = colorsys.rgb_to_hls(*rgb)
    lightness = lightness * (1 + tint) if tint < 0 else lightness + (1 - lightness) * tint
    tinted = colorsys.hls_to_rgb(hue, max(0, min(1, lightness)), saturation)
    return "#" + "".join(f"{round(component * 255):02x}" for component in tinted)


def _excel_table_cell_styles(sheet, workbook, max_row, max_column):
    """Create visual fallbacks for Excel's built-in 'Format as Table' styles."""
    from openpyxl.styles import Color
    from openpyxl.utils.cell import range_boundaries

    styles = {}
    for table in sheet.tables.values():
        info = table.tableStyleInfo
        match = re.fullmatch(r"TableStyle(Light|Medium|Dark)(\d+)", info.name or "") if info else None
        if not match:
            continue
        family, number = match.group(1), int(match.group(2))
        palette_slot = (number - 1) % 7
        theme_index = 0 if palette_slot == 0 else 3 + palette_slot
        base = _excel_color(Color(theme=theme_index), workbook) or "#4472c4"
        min_col, min_row, table_max_col, table_max_row = range_boundaries(table.ref)
        table_max_col, table_max_row = min(table_max_col, max_column), min(table_max_row, max_row)
        if min_col > table_max_col or min_row > table_max_row:
            continue
        header_fill = _tint_hex(base, 0.55) if family == "Light" else base
        header_color = "#000000" if family == "Light" else "#ffffff"
        stripe_fill = _tint_hex(base, 0.88 if family == "Light" else 0.82)
        for column in range(min_col, table_max_col + 1):
            styles[(min_row, column)] = f"background-color: {header_fill}; color: {header_color}; font-weight: bold"
        data_start = min_row + (1 if table.headerRowCount else 0)
        data_end = table_max_row - (1 if table.totalsRowShown else 0)
        if info.showRowStripes:
            for row in range(data_start, data_end + 1):
                if (row - data_start) % 2 == 1:
                    for column in range(min_col, table_max_col + 1):
                        styles[(row, column)] = f"background-color: {stripe_fill}"
        if table.totalsRowShown and table_max_row >= min_row:
            for column in range(min_col, table_max_col + 1):
                styles[(table_max_row, column)] = f"font-weight: bold; border-top: 2px solid {base}"
    return styles


def _render_excel_worksheet_html(sheet, workbook, max_rows=None, bounds=None):
    """Render worksheet values and the most relevant visual Excel cell formatting."""
    from openpyxl.utils import get_column_letter

    if bounds:
        start_column, start_row, bound_max_column, bound_max_row = bounds
    else:
        start_column, start_row, bound_max_column, bound_max_row = 1, 1, sheet.max_column, sheet.max_row
    last_row = last_column = 0
    for row in sheet.iter_rows(
        min_row=start_row, max_row=bound_max_row,
        min_col=start_column, max_col=bound_max_column,
    ):
        for cell in row:
            if cell.value not in (None, ""):
                last_row = max(last_row, cell.row)
                last_column = max(last_column, cell.column)
    if not last_row:
        return "<p><em>Keine Inhalte</em></p>"
    max_row = min(last_row, start_row + max_rows - 1) if max_rows else last_row
    max_column = last_column
    table_styles = _excel_table_cell_styles(sheet, workbook, max_row, max_column)
    merged_starts, merged_children = {}, set()
    for merged in sheet.merged_cells.ranges:
        if merged.min_row > max_row or merged.min_col > max_column:
            continue
        merged_starts[(merged.min_row, merged.min_col)] = (
            min(merged.max_row, max_row) - merged.min_row + 1,
            min(merged.max_col, max_column) - merged.min_col + 1,
        )
        for row in range(merged.min_row, min(merged.max_row, max_row) + 1):
            for column in range(merged.min_col, min(merged.max_col, max_column) + 1):
                if (row, column) != (merged.min_row, merged.min_col):
                    merged_children.add((row, column))
    columns = []
    for column in range(start_column, max_column + 1):
        width = sheet.column_dimensions[get_column_letter(column)].width
        columns.append(f'<col style="width: {max(3, min(float(width or 13), 80)):.2f}ch">')
    output = ['<table class="doc-table-bordered"><colgroup>', *columns, "</colgroup><tbody>"]
    for row in range(start_row, max_row + 1):
        row_style = ""
        if sheet.row_dimensions[row].height:
            row_style = f' style="height: {float(sheet.row_dimensions[row].height):g}pt"'
        output.append(f"<tr{row_style}>")
        for column in range(start_column, max_column + 1):
            if (row, column) in merged_children:
                continue
            cell = sheet.cell(row=row, column=column)
            attributes = []
            rowspan, colspan = merged_starts.get((row, column), (1, 1))
            if rowspan > 1:
                attributes.append(f'rowspan="{rowspan}"')
            if colspan > 1:
                attributes.append(f'colspan="{colspan}"')
            style = _excel_cell_style(cell, workbook)
            if not style and (row, column) in table_styles:
                style = table_styles[(row, column)]
            elif (row, column) in table_styles and "background-color" not in style:
                style = "; ".join(filter(None, (style, table_styles[(row, column)])))
            if style:
                attributes.append(f'style="{style}"')
            value = "" if cell.value is None else escape(str(cell.value)).replace("\n", "<br>")
            output.append(f"<td{' ' if attributes else ''}{' '.join(attributes)}>{value}</td>")
        output.append("</tr>")
    output.append("</tbody></table>")
    if max_rows and last_row > start_row + max_rows - 1:
        output.append(f"<p><em>Vorschau auf {max_rows} Zeilen begrenzt.</em></p>")
    return "".join(output)


def _render_flattened_worksheet(sheet, workbook, max_rows=None):
    """Flatten ordinary cells while preserving explicitly defined Excel tables."""
    from openpyxl.utils.cell import range_boundaries

    table_ranges = []
    for table in sheet.tables.values():
        min_col, min_row, max_col, max_row = range_boundaries(table.ref)
        table_ranges.append((min_col, min_row, max_col, max_row))
    table_ranges.sort(key=lambda item: (item[1], item[0]))

    def containing_table(row, column):
        for bounds in table_ranges:
            min_col, min_row, max_col, max_row = bounds
            if min_row <= row <= max_row and min_col <= column <= max_col:
                return bounds
        return None

    blocks = []
    rendered_tables = set()
    rendered_max_row = min(sheet.max_row, max_rows) if max_rows else sheet.max_row
    for row_number in range(1, rendered_max_row + 1):
        ordinary_values = []
        tables_starting_here = []
        for column_number in range(1, sheet.max_column + 1):
            bounds = containing_table(row_number, column_number)
            if bounds:
                if bounds[1] == row_number and bounds not in rendered_tables:
                    tables_starting_here.append(bounds)
                    rendered_tables.add(bounds)
                continue
            value = sheet.cell(row=row_number, column=column_number).value
            if value not in (None, ""):
                ordinary_values.append(escape(str(value)).replace("\n", "<br>"))
        if ordinary_values:
            blocks.append("<p>" + "<br>".join(ordinary_values) + "</p>")
        for min_col, min_row, max_col, max_row in tables_starting_here:
            blocks.append(_render_excel_worksheet_html(
                sheet, workbook,
                bounds=(min_col, min_row, max_col, min(max_row, rendered_max_row)),
            ))
    if max_rows and sheet.max_row > max_rows:
        blocks.append(f"<p><em>Vorschau auf {max_rows} von {sheet.max_row} Zeilen begrenzt.</em></p>")
    return "\n".join(blocks) or "<p><em>Keine Inhalte</em></p>"


def _pdf(content):
    from pypdf import PdfReader
    reader = PdfReader(BytesIO(content))
    pages = []
    for number, page in enumerate(reader.pages, 1):
        text = (page.extract_text() or "").strip()
        if text:
            text = re.sub(r"[ \t]+\n", "\n", text)
            pages.append(f"## Seite {number}\n\n{text}")
    if not pages:
        raise ImportFailure("Das PDF enthält keinen extrahierbaren Text. Für Scans ist OCR erforderlich.")
    return ImportResult("\n\n".join(pages), ["PDF-Layout und Bilder können nicht vollständig übernommen werden."])
