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

