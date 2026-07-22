from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
import re


class ImportFailure(ValueError):
    pass


@dataclass
class ImportResult:
    markdown: str
    warnings: list[str] = field(default_factory=list)


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


def import_document(upload) -> ImportResult:
    suffix = Path(upload.name).suffix.lower()
    content = upload.read()
    upload.seek(0)
    if suffix == ".docx":
        return _docx(content)
    if suffix in {".xlsx", ".xlsm"}:
        return _xlsx(content)
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


def _xlsx(content):
    from openpyxl import load_workbook
    from tabulate import tabulate
    workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
    sections = []
    for sheet in workbook.worksheets:
        rows = [["" if cell is None else str(cell) for cell in row] for row in sheet.iter_rows(values_only=True)]
        while rows and not any(value for value in rows[-1]):
            rows.pop()
        if not rows:
            continue
        width = max(len(row) for row in rows)
        rows = [row + [""] * (width - len(row)) for row in rows]
        header, body = rows[0], rows[1:]
        sections.append(f"## {sheet.title}\n\n{tabulate(body, headers=header, tablefmt='github')}")
    if not sections:
        raise ImportFailure("Die Arbeitsmappe enthält keine Daten.")
    return ImportResult("\n\n".join(sections))


def import_excel_sheets(upload) -> list[ExcelSheetResult]:
    """Convert each non-empty worksheet into an individual document payload."""
    from openpyxl import load_workbook
    from openpyxl.utils import get_column_letter
    from tabulate import tabulate

    suffix = Path(upload.name).suffix.lower()
    if suffix not in {".xlsx", ".xlsm"}:
        raise ImportFailure("Der Mehrblattimport unterstützt XLSX- und XLSM-Dateien.")
    content = upload.read()
    upload.seek(0)
    workbook = load_workbook(BytesIO(content), read_only=False, data_only=True)
    results = []
    for sheet in workbook.worksheets:
        rows = [["" if cell is None else str(cell) for cell in row] for row in sheet.iter_rows(values_only=True)]
        while rows and not any(value for value in rows[-1]):
            rows.pop()
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
            try:
                image_content = image._data()
            except (AttributeError, OSError, ValueError):
                continue
            images.append(ImportedImage(
                name=f"{slugify_filename(sheet.title)}-{number}.{image_format if image_format != 'jpeg' else 'jpg'}",
                content=image_content, content_type=f"image/{image_format}", cell=cell,
            ))
        if not rows and not images:
            continue
        if rows:
            width = max(len(row) for row in rows)
            rows = [row + [""] * (width - len(row)) for row in rows]
            markdown = tabulate(rows[1:], headers=rows[0], tablefmt="github")
        else:
            markdown = ""
        results.append(ExcelSheetResult(title=sheet.title, markdown=markdown, images=images))
    if not results:
        raise ImportFailure("Die Arbeitsmappe enthält keine Daten oder unterstützten Bilder.")
    return results


def slugify_filename(value):
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.")
    return value[:80] or "arbeitsblatt"


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
