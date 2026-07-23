from pathlib import Path
from datetime import timedelta
from html import escape
import mimetypes
import tinymce
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.utils import timezone
from django.views import View
from netbox.views import generic
from netbox.object_actions import AddObject, BulkDelete, BulkImport
from .filtersets import DocumentFilterSet, AssignmentFilterSet, DocumentCategoryFilterSet
from .forms import (
    ArchiveExportForm, ArchiveImportForm, AssignmentForm, DocumentCategoryForm,
    DocumentForm, ExcelSheetSelectionFormSet, ImportForm,
)
from .archive import ArchiveFailure, documents_for_categories, export_documents, import_archive
from .importers import ImportFailure, import_document, import_excel_sheets
from .models import (
    Document, DocumentAssignment, DocumentAttachment, DocumentCategory,
    ExcelImportPreview,
)
from .tables import DocumentTable, AssignmentTable, DocumentCategoryTable


class EditorAssetView(View):
    """Serve the bundled editor assets when NetBox's static proxy is unavailable."""

    def get(self, request, asset_path):
        root = (Path(tinymce.__file__).resolve().parent / "static" / "tinymce").resolve()
        candidate = (root / asset_path).resolve()
        if root not in candidate.parents or not candidate.is_file():
            raise Http404
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        response = FileResponse(candidate.open("rb"), content_type=content_type)
        response["Cache-Control"] = "public, max-age=31536000, immutable"
        response["X-Content-Type-Options"] = "nosniff"
        return response


class DocumentListView(generic.ObjectListView):
    queryset = Document.objects.prefetch_related("assignments")
    table = DocumentTable
    filterset = DocumentFilterSet
    actions = (AddObject, BulkImport, BulkDelete)


class DocumentView(generic.ObjectView):
    queryset = Document.objects.prefetch_related("assignments", "attachments")


class DocumentPrintView(PermissionRequiredMixin, View):
    permission_required = "netbox_documentation.view_document"
    template_name = "netbox_documentation/document_print.html"

    def get(self, request, pk):
        document = get_object_or_404(
            Document.objects.restrict(request.user, "view").select_related("category").prefetch_related("assignments"),
            pk=pk,
        )
        return render(request, self.template_name, {"object": document})


class DocumentEditView(generic.ObjectEditView):
    queryset = Document.objects.all()
    form = DocumentForm
    template_name = "netbox_documentation/document_edit.html"


class DocumentDeleteView(generic.ObjectDeleteView):
    queryset = Document.objects.all()


class DocumentBulkDeleteView(generic.BulkDeleteView):
    queryset = Document.objects.all()
    table = DocumentTable
    filterset = DocumentFilterSet


class DocumentCategoryListView(generic.ObjectListView):
    queryset = DocumentCategory.objects.select_related("parent").prefetch_related("documents")
    table = DocumentCategoryTable
    filterset = DocumentCategoryFilterSet
    actions = (AddObject, BulkImport, BulkDelete)


class DocumentCategoryView(generic.ObjectView):
    queryset = DocumentCategory.objects.prefetch_related("children", "documents")


class DocumentCategoryEditView(generic.ObjectEditView):
    queryset = DocumentCategory.objects.all()
    form = DocumentCategoryForm


class DocumentCategoryDeleteView(generic.ObjectDeleteView):
    queryset = DocumentCategory.objects.all()


class DocumentCategoryBulkDeleteView(generic.BulkDeleteView):
    queryset = DocumentCategory.objects.all()
    table = DocumentCategoryTable
    filterset = DocumentCategoryFilterSet


class AssignmentListView(generic.ObjectListView):
    queryset = DocumentAssignment.objects.select_related("document", "assigned_object_type")
    table = AssignmentTable
    filterset = AssignmentFilterSet
    actions = (AddObject, BulkImport, BulkDelete)


class AssignmentEditView(generic.ObjectEditView):
    queryset = DocumentAssignment.objects.all()
    form = AssignmentForm


class AssignmentDeleteView(generic.ObjectDeleteView):
    queryset = DocumentAssignment.objects.all()


class AssignmentBulkDeleteView(generic.BulkDeleteView):
    queryset = DocumentAssignment.objects.all()
    table = AssignmentTable
    filterset = AssignmentFilterSet


class DocumentImportView(PermissionRequiredMixin, View):
    permission_required = "netbox_documentation.import_document"
    template_name = "netbox_documentation/document_import.html"

    def get(self, request):
        return render(request, self.template_name, {"form": ImportForm(user=request.user)})

    def post(self, request):
        form = ImportForm(request.POST, request.FILES, user=request.user)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})
        upload = form.cleaned_data["file"]
        if form.cleaned_data.get("excel_sheets_as_documents"):
            return self._import_excel_sheets(request, form, upload)
        try:
            result = import_document(upload, flatten_excel=form.cleaned_data.get("flatten_excel_tables", False))
        except (ImportFailure, Exception) as exc:
            # Known conversion/library errors are presented without exposing a traceback.
            form.add_error("file", f"Import fehlgeschlagen: {exc}")
            return render(request, self.template_name, {"form": form})
        with transaction.atomic():
            document = form.cleaned_data.get("document")
            if document:
                imported_body = result.markdown
                if document.body_format == "html":
                    from markdown import markdown
                    imported_body = markdown(imported_body, extensions=("extra", "sane_lists"))
                separator = "\n\n---\n\n" if document.body else ""
                document.body += separator + imported_body
                document.save()
            else:
                title = form.cleaned_data.get("title") or Path(upload.name).stem
                base_slug = slugify(title)[:180] or "dokumentation"
                slug = base_slug
                counter = 2
                while Document.objects.filter(slug=slug).exists():
                    slug = f"{base_slug}-{counter}"
                    counter += 1
                document = Document.objects.create(
                    title=title, slug=slug, body=result.markdown, body_format=result.body_format,
                )
            keep = settings.PLUGINS_CONFIG.get("netbox_documentation", {}).get("keep_imported_file", True)
            if keep:
                upload.seek(0)
                DocumentAttachment.objects.create(document=document, file=upload,
                    original_name=upload.name, content_type=upload.content_type or "", size=upload.size)
        for warning in result.warnings:
            messages.warning(request, warning)
        messages.success(request, f"{upload.name} wurde importiert.")
        return redirect(document)

    def _import_excel_sheets(self, request, form, upload):
        try:
            sheets = import_excel_sheets(upload, flatten=form.cleaned_data.get("flatten_excel_tables", False))
        except (ImportFailure, Exception) as exc:
            form.add_error("file", f"Excel-Mehrblattimport fehlgeschlagen: {exc}")
            return render(request, self.template_name, {"form": form})
        # Remove abandoned previews owned by this user before creating a new one.
        stale = ExcelImportPreview.objects.filter(created__lt=timezone.now() - timedelta(hours=24))
        for preview in stale:
            preview.file.delete(save=False)
            preview.delete()
        upload.seek(0)
        preview = ExcelImportPreview.objects.create(
            user=request.user, category=form.cleaned_data["category"], file=upload,
            original_name=upload.name, content_type=upload.content_type or "",
            flatten=form.cleaned_data.get("flatten_excel_tables", False),
            sheet_metadata=[{"title": sheet.title, "image_count": len(sheet.images)} for sheet in sheets],
        )
        return redirect("plugins:netbox_documentation:excel_import_preview", token=preview.pk)


class ExcelImportPreviewView(PermissionRequiredMixin, View):
    permission_required = "netbox_documentation.import_document"
    template_name = "netbox_documentation/excel_import_preview.html"

    def get_preview(self, request, token):
        return get_object_or_404(ExcelImportPreview, pk=token, user=request.user)

    def read_sheets(self, preview):
        preview.file.open("rb")
        try:
            return import_excel_sheets(preview.file, flatten=preview.flatten)
        finally:
            preview.file.close()

    def render_preview(self, request, preview, sheets, formset):
        items = []
        for form, sheet in zip(formset.forms, sheets):
            sample = sheet.markdown
            if sheet.images:
                image_notice = f"{len(sheet.images)} eingebettete Bilder werden beim Import angefügt."
                if sheet.body_format == "html":
                    sample += f"\n<h2>Bilder</h2><p><em>{image_notice}</em></p>"
                else:
                    sample += f"\n\n## Bilder\n\n_{image_notice}_"
            truncated = len(sample) > 100000
            if truncated:
                notice = "… Vorschau gekürzt …"
                sample = sample[:100000] + (
                    f"<p><em>{notice}</em></p>" if sheet.body_format == "html" else f"\n\n_{notice}_"
                )
            preview_document = Document(body=sample, body_format=sheet.body_format)
            items.append({
                "form": form, "sheet": sheet,
                "preview_html": preview_document.rendered_body(), "truncated": truncated,
            })
        return render(request, self.template_name, {
            "batch": preview, "formset": formset, "items": items,
        })

    def get(self, request, token):
        preview = self.get_preview(request, token)
        if preview.created < timezone.now() - timedelta(hours=24):
            self.delete_preview(preview)
            messages.error(request, "Diese Importvorschau ist abgelaufen. Bitte die Exceldatei erneut hochladen.")
            return redirect("plugins:netbox_documentation:document_import")
        try:
            sheets = self.read_sheets(preview)
        except (ImportFailure, Exception) as exc:
            self.delete_preview(preview)
            messages.error(request, f"Die Excel-Vorschau konnte nicht erzeugt werden: {exc}")
            return redirect("plugins:netbox_documentation:document_import")
        initial = [{"include": True, "index": index, "title": sheet.title} for index, sheet in enumerate(sheets)]
        return self.render_preview(request, preview, sheets, ExcelSheetSelectionFormSet(initial=initial))

    def post(self, request, token):
        preview = self.get_preview(request, token)
        if request.POST.get("action") == "cancel":
            self.delete_preview(preview)
            messages.info(request, "Excel-Import wurde abgebrochen.")
            return redirect("plugins:netbox_documentation:document_import")
        try:
            sheets = self.read_sheets(preview)
        except (ImportFailure, Exception) as exc:
            self.delete_preview(preview)
            messages.error(request, f"Die Exceldatei konnte nicht erneut gelesen werden: {exc}")
            return redirect("plugins:netbox_documentation:document_import")
        formset = ExcelSheetSelectionFormSet(request.POST)
        if not formset.is_valid():
            return self.render_preview(request, preview, sheets, formset)
        if not preview.category:
            self.delete_preview(preview)
            messages.error(request, "Der gewählte Zielordner existiert nicht mehr. Bitte den Import erneut starten.")
            return redirect("plugins:netbox_documentation:document_import")
        selections = {}
        for form in formset.forms:
            data = form.cleaned_data
            if data.get("include"):
                if data["index"] < 0 or data["index"] >= len(sheets):
                    raise PermissionDenied
                selections[data["index"]] = data["title"].strip()
        result = self.create_documents(preview, sheets, selections)
        self.delete_preview(preview)
        messages.success(request, (
            f"{result['documents']} Arbeitsblätter als Dokumentationen in „{result['category']}“ importiert; "
            f"{result['images']} Bilder übernommen."
        ))
        return redirect("plugins:netbox_documentation:document_list")

    @staticmethod
    @transaction.atomic
    def create_documents(preview, sheets, selections):
        from django.core.files.base import ContentFile
        preview.file.open("rb")
        try:
            original_content = preview.file.read()
        finally:
            preview.file.close()
        created_documents, image_count = [], 0
        for index, title in selections.items():
            sheet = sheets[index]
            base_slug = slugify(title)[:180] or "arbeitsblatt"
            document_slug, counter = base_slug, 2
            while Document.objects.filter(slug=document_slug).exists():
                document_slug = f"{base_slug[:190-len(str(counter))]}-{counter}"
                counter += 1
            document = Document.objects.create(
                title=title[:200], slug=document_slug, body=sheet.markdown,
                body_format=sheet.body_format, category=preview.category,
                summary=f"Importiert aus {preview.original_name}",
            )
            if sheet.images:
                image_lines = []
                for image in sheet.images:
                    attachment = DocumentAttachment(
                        document=document, original_name=image.name,
                        content_type=image.content_type, size=len(image.content),
                    )
                    attachment.file.save(image.name, ContentFile(image.content), save=False)
                    attachment.save()
                    location = f" ({image.cell})" if image.cell else ""
                    if document.body_format == "html":
                        image_lines.append(
                            f'<p><img src="{escape(attachment.file.url)}" alt="{escape(image.name + location)}"></p>'
                        )
                    else:
                        image_lines.append(f"![{image.name}{location}]({attachment.file.url})")
                if document.body_format == "html":
                    document.body += "\n<h2>Bilder</h2>\n" + "\n".join(image_lines)
                else:
                    document.body += "\n\n## Bilder\n\n" + "\n\n".join(image_lines)
                document.save(update_fields=("body", "last_updated"))
                image_count += len(sheet.images)
            created_documents.append(document)
        if settings.PLUGINS_CONFIG.get("netbox_documentation", {}).get("keep_imported_file", True):
            for document in created_documents:
                attachment = DocumentAttachment(
                    document=document, original_name=preview.original_name,
                    content_type=preview.content_type, size=len(original_content),
                )
                attachment.file.save(preview.original_name, ContentFile(original_content), save=False)
                attachment.save()
        return {"documents": len(created_documents), "images": image_count, "category": preview.category}

    @staticmethod
    def delete_preview(preview):
        preview.file.delete(save=False)
        preview.delete()


class DocumentMediaUploadView(PermissionRequiredMixin, View):
    permission_required = "netbox_documentation.change_document"

    def post(self, request, pk):
        document = get_object_or_404(Document.objects.restrict(request.user, "change"), pk=pk)
        upload = request.FILES.get("file")
        if not upload:
            return JsonResponse({"error": "Keine Datei empfangen."}, status=400)
        limit = settings.PLUGINS_CONFIG.get("netbox_documentation", {}).get("max_import_size_mb", 25)
        if upload.size > limit * 1024 * 1024:
            return JsonResponse({"error": f"Die Datei ist größer als {limit} MB."}, status=400)
        allowed = {"image/jpeg", "image/png", "image/gif", "image/webp"}
        if upload.content_type not in allowed:
            return JsonResponse({"error": "Im Editor sind JPEG, PNG, GIF und WebP erlaubt."}, status=400)
        try:
            from PIL import Image
            image = Image.open(upload)
            image.verify()
            upload.seek(0)
        except Exception:
            return JsonResponse({"error": "Die hochgeladene Datei ist kein gültiges Bild."}, status=400)
        attachment = DocumentAttachment.objects.create(
            document=document, file=upload, original_name=upload.name,
            content_type=upload.content_type or "", size=upload.size,
        )
        return JsonResponse({"location": attachment.file.url})


class DocumentArchiveView(View):
    template_name = "netbox_documentation/document_archive.html"

    def _render(self, request, export_form=None, import_form=None):
        return render(request, self.template_name, {
            "export_form": export_form or ArchiveExportForm(user=request.user),
            "import_form": import_form or ArchiveImportForm(),
        })

    def get(self, request):
        if not request.user.has_perm("netbox_documentation.view_document"):
            raise PermissionDenied
        return self._render(request)

    def post(self, request):
        action = request.POST.get("action")
        if action == "export":
            if not request.user.has_perm("netbox_documentation.view_document"):
                raise PermissionDenied
            form = ArchiveExportForm(request.POST, user=request.user)
            if not form.is_valid():
                return self._render(request, export_form=form)
            documents = documents_for_categories(
                form.cleaned_data["categories"], form.cleaned_data["include_subfolders"], request.user
            )
            if not documents.exists():
                form.add_error("categories", "Die ausgewählten Ordner enthalten keine exportierbaren Dokumentationen.")
                return self._render(request, export_form=form)
            stream = export_documents(documents)
            response = FileResponse(stream, content_type="application/zip")
            response["Content-Disposition"] = 'attachment; filename="netbox-documentation-export.zip"'
            return response
        if action == "import":
            required = (
                "netbox_documentation.import_document",
                "netbox_documentation.add_document",
                "netbox_documentation.change_document",
                "netbox_documentation.add_documentassignment",
                "netbox_documentation.add_documentattachment",
                "netbox_documentation.add_documentcategory",
            )
            if not all(request.user.has_perm(permission) for permission in required):
                raise PermissionDenied
            form = ArchiveImportForm(request.POST, request.FILES)
            if not form.is_valid():
                return self._render(request, import_form=form)
            try:
                result = import_archive(form.cleaned_data["archive"], form.cleaned_data["update_existing"])
            except ArchiveFailure as exc:
                form.add_error("archive", str(exc))
                return self._render(request, import_form=form)
            messages.success(request, (
                f"Archiv importiert: {result['created']} erstellt, {result['updated']} aktualisiert."
            ))
            if result["skipped_assignments"]:
                messages.warning(request, f"{result['skipped_assignments']} nicht verfügbare Objektzuordnungen wurden übersprungen.")
            return redirect("plugins:netbox_documentation:document_list")
        return self._render(request)
