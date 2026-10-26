import json
from pathlib import Path, PurePosixPath
from tempfile import SpooledTemporaryFile
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.text import slugify
from django.utils.translation import gettext as _
from tenancy.models import Tenant, TenantGroup

from .models import Document, DocumentAssignment, DocumentAttachment, DocumentCategory


ARCHIVE_FORMAT = "netbox-documentation"
ARCHIVE_VERSION = 1
MAX_ENTRIES = 5000


class ArchiveFailure(ValueError):
    pass


def _save_imported_object(instance, context, **save_kwargs):
    try:
        instance.save(**save_kwargs)
    except ValidationError as exc:
        messages = getattr(exc, "messages", None) or [str(exc)]
        raise ArchiveFailure(f"{context}: {'; '.join(messages)}") from exc


def documents_for_categories(categories, include_subfolders=True, user=None):
    """Return distinct permitted documents contained in the selected category trees."""
    category_ids = set(categories.values_list("pk", flat=True))
    frontier = set(category_ids)
    while include_subfolders and frontier:
        children = set(DocumentCategory.objects.filter(parent_id__in=frontier).values_list("pk", flat=True))
        frontier = children - category_ids
        category_ids.update(children)
    documents = Document.objects.filter(category_id__in=category_ids).distinct().order_by("title")
    if user is not None:
        documents = documents.restrict(user, "view")
    return documents


def _category_path(category):
    path, seen = [], set()
    while category and category.pk not in seen:
        path.append(category.name)
        seen.add(category.pk)
        category = category.parent
    return list(reversed(path))


def _category_tenancy_path(category):
    path, seen = [], set()
    while category and category.pk not in seen:
        path.append({
            "tenant": category.tenant.slug if category.tenant else None,
            "tenant_group": category.tenant_group.slug if category.tenant_group else None,
        })
        seen.add(category.pk)
        category = category.parent
    return list(reversed(path))


def export_documents(documents):
    stream = SpooledTemporaryFile(max_size=10 * 1024 * 1024, mode="w+b")
    manifest = {"format": ARCHIVE_FORMAT, "version": ARCHIVE_VERSION, "documents": []}
    with ZipFile(stream, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for document in documents.prefetch_related("assignments__assigned_object_type", "attachments").select_related(
            "category", "tenant", "tenant_group", "category__tenant", "category__tenant_group",
        ):
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
                "category_tenancy": _category_tenancy_path(document.category),
                "tenant": document.tenant.slug if document.tenant else None,
                "tenant_group": document.tenant_group.slug if document.tenant_group else None,
                "assignments": assignments, "attachments": attachments,
            })
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))
    stream.seek(0)
    return stream


def _validate_archive(archive):
    infos = archive.infolist()
    if len(infos) > MAX_ENTRIES:
        raise ArchiveFailure(_("The archive contains more than %(count)s files.") % {"count": MAX_ENTRIES})
    limit = settings.PLUGINS_CONFIG.get("netbox_documentation", {}).get("max_archive_size_mb", 250) * 1024 * 1024
    if sum(info.file_size for info in infos) > limit:
        raise ArchiveFailure(_("The total extracted size exceeds the configured limit."))
    for info in infos:
        path = PurePosixPath(info.filename)
        if path.is_absolute() or ".." in path.parts:
            raise ArchiveFailure(_("The archive contains an unsafe file path."))
        if info.compress_size and info.file_size / info.compress_size > 200:
            raise ArchiveFailure(_("The archive contains a suspiciously highly compressed file."))


def _read_json(archive, name):
    try:
        return json.loads(archive.read(name).decode("utf-8"))
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArchiveFailure(_("The archive contains no valid manifest.json.")) from exc


def _resolve_tenant_group(slug, context):
    """Look up a tenant group by slug for an imported record.

    Returns None if no slug was recorded (i.e. the object genuinely had no
    tenant group). Raises ArchiveFailure if a slug *was* recorded but no
    matching TenantGroup exists on this instance, instead of silently
    dropping the assignment - a missing tenant group later tripping over
    an unrelated validation rule further downstream is far more confusing
    than failing here with a precise message.
    """
    if not slug:
        return None
    group = TenantGroup.objects.filter(slug=slug).first()
    if group is None:
        raise ArchiveFailure(
            _(
                "%(context)s: The tenant group “%(slug)s” does not exist on this instance. "
                "Create the tenant group first or repeat the import with an adjusted manifest.json."
            ) % {"context": context, "slug": slug}
        )
    return group


def _resolve_tenant(slug, context):
    """Look up a tenant by slug for an imported record.

    Same reasoning as _resolve_tenant_group(): fail loudly and specifically
    instead of leaving the field empty and letting a generic "a tenant is
    required" validation error surface later with no indication of which
    tenant or which record was actually the problem.
    """
    if not slug:
        return None
    tenant = Tenant.objects.filter(slug=slug).first()
    if tenant is None:
        raise ArchiveFailure(
            _(
                "%(context)s: The tenant “%(slug)s” does not exist on this instance. "
                "Create the tenant first or repeat the import with an adjusted manifest.json."
            ) % {"context": context, "slug": slug}
        )
    return tenant


def _category_from_path(names, tenancy_path=None):
    parent = None
    tenancy_path = tenancy_path or []
    for index, name in enumerate(names):
        name = str(name).strip()[:100]
        if not name:
            continue
        slug = slugify(name)[:100] or "folder"
        tenancy = tenancy_path[index] if index < len(tenancy_path) and isinstance(tenancy_path[index], dict) else {}
        context = _("Folder “%(name)s”") % {"name": name}
        tenant_group = _resolve_tenant_group(tenancy.get("tenant_group"), context)
        tenant = _resolve_tenant(tenancy.get("tenant"), context)
        if tenant and tenant_group and tenant.group_id != tenant_group.pk:
            raise ArchiveFailure(
                _("%(context)s: The tenant “%(tenant)s” does not belong to the tenant group “%(group)s” on this instance.")
                % {"context": context, "tenant": tenant.slug, "group": tenant_group.slug}
            )
        category = DocumentCategory.objects.filter(parent=parent, slug=slug).first()
        if not category:
            # Set tenancy before the first save. NetBox installations may
            # enforce a tenant via custom validation rules, so creating the
            # category first and assigning its tenant in a second save fails.
            category = DocumentCategory(
                name=name, slug=slug, parent=parent,
                tenant_group=tenant_group, tenant=tenant,
            )
            _save_imported_object(category, context)
        elif tenancy:
            category.tenant_group = tenant_group
            category.tenant = tenant
            _save_imported_object(
                category, context,
                update_fields=("tenant_group", "tenant", "last_updated"),
            )
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
        raise ArchiveFailure(_("The uploaded file is not a valid ZIP archive.")) from exc
    with archive:
        _validate_archive(archive)
        manifest = _read_json(archive, "manifest.json")
        if manifest.get("format") != ARCHIVE_FORMAT or manifest.get("version") != ARCHIVE_VERSION:
            raise ArchiveFailure(_("Archive format or version is not supported."))
        records = manifest.get("documents")
        if not isinstance(records, list):
            raise ArchiveFailure(_("The document list in the archive is invalid."))
        allowed = set(settings.PLUGINS_CONFIG.get("netbox_documentation", {}).get("allowed_object_types", []))
        created, updated, skipped_assignments = 0, 0, 0
        for record in records:
            if not isinstance(record, dict) or not record.get("title") or not record.get("body_path"):
                raise ArchiveFailure(_("The archive contains an incomplete document entry."))
            try:
                body = archive.read(record["body_path"]).decode("utf-8")
            except (KeyError, UnicodeDecodeError) as exc:
                raise ArchiveFailure(_("A document body is missing or not UTF-8 encoded.")) from exc
            source_slug = str(record.get("slug") or record["title"])
            document = Document.objects.filter(slug=source_slug).first() if update_existing else None
            category = _category_from_path(
                record.get("category_path") or [], record.get("category_tenancy") or [],
            )
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
            context = _("Document “%(title)s”") % {"title": document.title}
            document.tenant_group = _resolve_tenant_group(record.get("tenant_group"), context)
            document.tenant = _resolve_tenant(record.get("tenant"), context)
            if document.tenant and document.tenant_group and document.tenant.group_id != document.tenant_group_id:
                raise ArchiveFailure(
                    _("%(context)s: The tenant “%(tenant)s” does not belong to the tenant group “%(group)s” on this instance.")
                    % {"context": context, "tenant": document.tenant.slug, "group": document.tenant_group.slug}
                )
            _save_imported_object(document, context)
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
                    raise ArchiveFailure(_("Attachment %(name)s is missing from the archive.") % {"name": member}) from exc
                from django.core.files.base import ContentFile
                original_name = Path(str(item.get("original_name") or "attachment")).name[:255]
                allowed_extensions = {".docx", ".xlsx", ".xlsm", ".pdf", ".md", ".txt", ".jpg", ".jpeg", ".png", ".gif", ".webp"}
                if Path(original_name).suffix.lower() not in allowed_extensions:
                    raise ArchiveFailure(_("The attachment %(name)s uses a file type that is not allowed.") % {"name": original_name})
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
