from pathlib import Path
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
from django.views import View
from netbox.views import generic
from .filtersets import DocumentFilterSet, AssignmentFilterSet, DocumentCategoryFilterSet
from .forms import (
    ArchiveExportForm, ArchiveImportForm, AssignmentForm, DocumentCategoryForm,
    DocumentForm, ImportForm,
)
from .archive import ArchiveFailure, export_documents, import_archive
from .importers import ImportFailure, import_document
from .models import Document, DocumentAssignment, DocumentAttachment, DocumentCategory
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


class DocumentView(generic.ObjectView):
    queryset = Document.objects.prefetch_related("assignments", "attachments")


class DocumentEditView(generic.ObjectEditView):
    queryset = Document.objects.all()
    form = DocumentForm
    template_name = "netbox_documentation/document_edit.html"


class DocumentDeleteView(generic.ObjectDeleteView):
    queryset = Document.objects.all()


class DocumentCategoryListView(generic.ObjectListView):
    queryset = DocumentCategory.objects.select_related("parent").prefetch_related("documents")
    table = DocumentCategoryTable
    filterset = DocumentCategoryFilterSet


class DocumentCategoryView(generic.ObjectView):
    queryset = DocumentCategory.objects.prefetch_related("children", "documents")


class DocumentCategoryEditView(generic.ObjectEditView):
    queryset = DocumentCategory.objects.all()
    form = DocumentCategoryForm


class DocumentCategoryDeleteView(generic.ObjectDeleteView):
    queryset = DocumentCategory.objects.all()


class AssignmentListView(generic.ObjectListView):
    queryset = DocumentAssignment.objects.select_related("document", "assigned_object_type")
    table = AssignmentTable
    filterset = AssignmentFilterSet


class AssignmentEditView(generic.ObjectEditView):
    queryset = DocumentAssignment.objects.all()
    form = AssignmentForm


class AssignmentDeleteView(generic.ObjectDeleteView):
    queryset = DocumentAssignment.objects.all()


class DocumentImportView(PermissionRequiredMixin, View):
    permission_required = "netbox_documentation.import_document"
    template_name = "netbox_documentation/document_import.html"

    def get(self, request):
        return render(request, self.template_name, {"form": ImportForm()})

    def post(self, request):
        form = ImportForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})
        upload = form.cleaned_data["file"]
        try:
            result = import_document(upload)
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
                document = Document.objects.create(title=title, slug=slug, body=result.markdown, body_format="markdown")
            keep = settings.PLUGINS_CONFIG.get("netbox_documentation", {}).get("keep_imported_file", True)
            if keep:
                upload.seek(0)
                DocumentAttachment.objects.create(document=document, file=upload,
                    original_name=upload.name, content_type=upload.content_type or "", size=upload.size)
        for warning in result.warnings:
            messages.warning(request, warning)
        messages.success(request, f"{upload.name} wurde importiert.")
        return redirect(document)


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
            stream = export_documents(form.cleaned_data["documents"])
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
