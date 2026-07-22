import json
from pathlib import Path, PurePosixPath
from tempfile import SpooledTemporaryFile
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils.text import slugify

from .models import Document, DocumentAssignment, DocumentAttachment, DocumentCategory


ARCHIVE_FORMAT = "netbox-documentation"
ARCHIVE_VERSION = 1
MAX_ENTRIES = 5000


class ArchiveFailure(ValueError):
    pass


def _category_path(category):
    path, seen = [], set()
    while category and category.pk not in seen:
        path.append(category.name)
        seen.add(category.pk)
        category = category.parent
    return list(reversed(path))


def export_documents(documents):
    stream = SpooledTemporaryFile(max_size=10 * 1024 * 1024, mode="w+b")
    manifest = {"format": ARCHIVE_FORMAT, "version": ARCHIVE_VERSION, "documents": []}
    with ZipFile(stream, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for document in documents.prefetch_related("assignments__assigned_object_type", "attachments").select_related("category"):
            root = f"documents/{document.pk}"
            extension = "html" if document.body_format == "html" else "md"
            body_path = f"{root}/content.{extension}"
            archive.writestr(body_path, document.body.encode("utf-8"))
            attachments = []
            for attachment in document.attachments.all():
                safe_name = Path(attachment.original_name).name or f"attachment-{attachment.pk}"
                member = f"{root}/attachments/{attachment.pk}-{safe_name}"
                try:
                    with attachment.file.open("rb") as source:
                        archive.writestr(member, source.read())
                except (FileNotFoundError, OSError):
                    continue
                attachments.append({
                    "path": member, "original_name": safe_name,
                    "content_type": attachment.content_type, "size": attachment.size,
                    "source_url": attachment.file.url,
                })
            assignments = [{
                "app_label": item.assigned_object_type.app_label,
                "model": item.assigned_object_type.model,
                "object_id": item.assigned_object_id,
                "note": item.note,
            } for item in document.assignments.all()]
            manifest["documents"].append({
                "title": document.title, "slug": document.slug, "summary": document.summary,
                "body_format": document.body_format, "is_published": document.is_published,
                "category_path": _category_path(document.category), "body_path": body_path,
                "assignments": assignments, "attachments": attachments,
            })
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))
    stream.seek(0)
    return stream


def _validate_archive(archive):
    infos = archive.infolist()
    if len(infos) > MAX_ENTRIES:
        raise ArchiveFailure(f"Das Archiv enthält mehr als {MAX_ENTRIES} Dateien.")
    limit = settings.PLUGINS_CONFIG.get("netbox_documentation", {}).get("max_archive_size_mb", 250) * 1024 * 1024
    if sum(info.file_size for info in infos) > limit:
        raise ArchiveFailure("Die entpackte Gesamtgröße überschreitet das konfigurierte Limit.")
    for info in infos:
        path = PurePosixPath(info.filename)
        if path.is_absolute() or ".." in path.parts:
            raise ArchiveFailure("Das Archiv enthält einen unsicheren Dateipfad.")
        if info.compress_size and info.file_size / info.compress_size > 200:
            raise ArchiveFailure("Das Archiv enthält eine verdächtig stark komprimierte Datei.")


def _read_json(archive, name):
    try:
        return json.loads(archive.read(name).decode("utf-8"))
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArchiveFailure("Das Archiv enthält kein gültiges manifest.json.") from exc


def _category_from_path(names):
    parent = None
    for name in names:
        name = str(name).strip()[:100]
        if not name:
            continue
        slug = slugify(name)[:100] or "ordner"
        category = DocumentCategory.objects.filter(parent=parent, slug=slug).first()
        if not category:
            category = DocumentCategory.objects.create(name=name, slug=slug, parent=parent)
        parent = category
    return parent


def _unique_slug(value):
    base = (slugify(value) or "dokumentation")[:180]
    candidate, number = base, 2
    while Document.objects.filter(slug=candidate).exists():
        candidate = f"{base[:190-len(str(number))]}-{number}"
        number += 1
    return candidate


@transaction.atomic
def import_archive(upload, update_existing=False):
    try:
        archive = ZipFile(upload)
    except BadZipFile as exc:
        raise ArchiveFailure("Die hochgeladene Datei ist kein gültiges ZIP-Archiv.") from exc
    with archive:
        _validate_archive(archive)
        manifest = _read_json(archive, "manifest.json")
        if manifest.get("format") != ARCHIVE_FORMAT or manifest.get("version") != ARCHIVE_VERSION:
            raise ArchiveFailure("Archivformat oder Version wird nicht unterstützt.")
        records = manifest.get("documents")
        if not isinstance(records, list):
            raise ArchiveFailure("Die Dokumentliste im Archiv ist ungültig.")
        allowed = set(settings.PLUGINS_CONFIG.get("netbox_documentation", {}).get("allowed_object_types", []))
        created, updated, skipped_assignments = 0, 0, 0
        for record in records:
            if not isinstance(record, dict) or not record.get("title") or not record.get("body_path"):
                raise ArchiveFailure("Das Archiv enthält einen unvollständigen Dokumenteintrag.")
            try:
                body = archive.read(record["body_path"]).decode("utf-8")
            except (KeyError, UnicodeDecodeError) as exc:
                raise ArchiveFailure("Ein Dokumentinhalt fehlt oder ist nicht UTF-8-kodiert.") from exc
            source_slug = str(record.get("slug") or record["title"])
            document = Document.objects.filter(slug=source_slug).first() if update_existing else None
            category = _category_from_path(record.get("category_path") or [])
            if document:
                updated += 1
            else:
                document = Document(slug=_unique_slug(source_slug))
                created += 1
            document.title = str(record["title"])[:200]
            document.summary = str(record.get("summary") or "")[:500]
            document.body = body
            document.body_format = record.get("body_format") if record.get("body_format") in {"html", "markdown"} else "html"
            document.is_published = bool(record.get("is_published", True))
            document.category = category
            document.save()
            for assignment in record.get("assignments") or []:
                label = f"{assignment.get('app_label')}.{assignment.get('model')}"
                if label not in allowed:
                    skipped_assignments += 1
                    continue
                content_type = ContentType.objects.filter(app_label=assignment.get("app_label"), model=assignment.get("model")).first()
                model = content_type.model_class() if content_type else None
                if not model or not model.objects.filter(pk=assignment.get("object_id")).exists():
                    skipped_assignments += 1
                    continue
                DocumentAssignment.objects.get_or_create(
                    document=document, assigned_object_type=content_type,
                    assigned_object_id=assignment["object_id"],
                    defaults={"note": str(assignment.get("note") or "")[:200]},
                )
            for item in record.get("attachments") or []:
                member = item.get("path")
                if not member:
                    continue
                try:
                    content = archive.read(member)
                except KeyError as exc:
                    raise ArchiveFailure(f"Anhang {member} fehlt im Archiv.") from exc
                from django.core.files.base import ContentFile
                original_name = Path(str(item.get("original_name") or "attachment")).name[:255]
                allowed_extensions = {".docx", ".xlsx", ".xlsm", ".pdf", ".md", ".txt", ".jpg", ".jpeg", ".png", ".gif", ".webp"}
                if Path(original_name).suffix.lower() not in allowed_extensions:
                    raise ArchiveFailure(f"Der Anhang {original_name} verwendet einen nicht erlaubten Dateityp.")
                existing = document.attachments.filter(original_name=original_name, size=len(content)).first()
                if existing:
                    if item.get("source_url"):
                        document.body = document.body.replace(str(item["source_url"]), existing.file.url)
                    continue
                attachment = DocumentAttachment(
                    document=document, original_name=original_name,
                    content_type=str(item.get("content_type") or "")[:100], size=len(content),
                )
                attachment.file.save(original_name, ContentFile(content), save=False)
                attachment.save()
                if item.get("source_url"):
                    document.body = document.body.replace(str(item["source_url"]), attachment.file.url)
            document.save(update_fields=("body", "last_updated"))
        return {"created": created, "updated": updated, "skipped_assignments": skipped_assignments}
