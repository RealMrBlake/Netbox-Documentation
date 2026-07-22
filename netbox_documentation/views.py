from pathlib import Path
import mimetypes
import tinymce
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.utils.text import slugify
from django.views import View
from netbox.views import generic
from .filtersets import DocumentFilterSet, AssignmentFilterSet
from .forms import DocumentForm, AssignmentForm, ImportForm
from .importers import ImportFailure, import_document
from .models import Document, DocumentAssignment, DocumentAttachment
from .tables import DocumentTable, AssignmentTable


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
