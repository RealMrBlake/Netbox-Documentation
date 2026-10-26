from django import forms
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.db.models import Q
from django.utils.functional import lazy
from django.utils.html import format_html
from django.utils.safestring import SafeString
from django.utils.translation import gettext_lazy as _
from utilities.forms import get_field_value
from utilities.forms.fields import (
    ContentTypeChoiceField, DynamicModelChoiceField, DynamicModelMultipleChoiceField, SlugField,
)
from utilities.forms.rendering import FieldSet
from utilities.forms.widgets import HTMXSelect
from netbox.forms import NetBoxModelForm
from dcim.models import Device
from tenancy.models import Tenant, TenantGroup
from .embedded_images import EmbeddedImageError, store_embedded_images, validate_embedded_images
from .models import Document, DocumentAssignment, DocumentAttachment, DocumentCategory


def _help_label(label, description):
    return format_html(
        '{} <span class="mdi mdi-help-circle-outline text-muted" title="{}" '
        'data-bs-toggle="tooltip" aria-label="{}"></span>',
        label, description, description,
    )


help_label = lazy(_help_label, SafeString)  # labels are built at import time, render in the request language


def allowed_content_types():
    labels = settings.PLUGINS_CONFIG.get("netbox_documentation", {}).get(
        "allowed_object_types", []
    )
    pairs = [value.split(".", 1) for value in labels if "." in value]
    query = Q()
    for app_label, model in pairs:
        query |= Q(app_label=app_label, model=model)
    return ContentType.objects.filter(query).order_by("app_label", "model")


class DocumentForm(NetBoxModelForm):
    slug = SlugField(slug_source="title")
    body = forms.CharField(required=False, label=_("Content"), widget=forms.Textarea(attrs={
        "rows": 32, "class": "rich-text-editor", "data-rich-text-editor": "true"
    }), help_text=_("Formatted text with tables, colours, fonts and sizes."))
    body_format = forms.CharField(widget=forms.HiddenInput(), initial="html")
    category = DynamicModelChoiceField(queryset=DocumentCategory.objects.all(), required=False, label=_("Folder"))
    tenant_group = DynamicModelChoiceField(
        queryset=TenantGroup.objects.all(), required=False, selector=True, label=_("Tenant group"),
    )
    tenant = DynamicModelChoiceField(
        queryset=Tenant.objects.all(), required=False, selector=True, label=_("Tenant"),
        query_params={"group_id": "$tenant_group"},
    )

    fieldsets = (
        FieldSet("title", "slug", "category", "tenant_group", "tenant", "summary", "is_published", "tags", name=_("Document")),
        FieldSet("body", "body_format", name=_("Content")),
    )

    class Meta:
        model = Document
        fields = ("title", "slug", "category", "tenant_group", "tenant", "summary", "body", "body_format", "is_published", "tags")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Legacy Markdown remains readable. Once edited in WYSIWYG mode it is
        # converted to HTML so the editor never exposes Markdown as plain text.
        if self.instance.pk and self.instance.body_format == "markdown" and not self.is_bound:
            from markdown import markdown
            self.initial["body"] = markdown(self.instance.body, extensions=("extra", "sane_lists"))
            self.initial["body_format"] = "html"

    def clean_body(self):
        body = self.cleaned_data.get("body", "")
        limit = settings.PLUGINS_CONFIG.get("netbox_documentation", {}).get("max_import_size_mb", 25)
        try:
            validate_embedded_images(body, limit * 1024 * 1024)
        except EmbeddedImageError as exc:
            raise forms.ValidationError(str(exc)) from exc
        return body

    def clean(self):
        super().clean()
        cleaned = self.cleaned_data
        tenant, group = cleaned.get("tenant"), cleaned.get("tenant_group")
        if tenant and group and tenant.group_id != group.pk:
            self.add_error("tenant", _("The tenant does not belong to the selected tenant group."))
        return cleaned

    def save(self, commit=True):
        document = super().save(commit=commit)
        if not commit or not document.pk or "data:image/" not in (document.body or "").lower():
            return document

        limit = settings.PLUGINS_CONFIG.get("netbox_documentation", {}).get("max_import_size_mb", 25)
        counter = 0

        def save_image(mime, content):
            nonlocal counter
            counter += 1
            extension = {"image/jpeg": "jpg", "image/png": "png", "image/gif": "gif", "image/webp": "webp"}[mime]
            name = f"editor-image-{document.pk}-{counter}.{extension}"
            attachment = DocumentAttachment(
                document=document, original_name=name, content_type=mime, size=len(content),
            )
            attachment.file.save(name, ContentFile(content), save=False)
            attachment.save()
            return attachment.file.url

        document.body = store_embedded_images(document.body, limit * 1024 * 1024, save_image)
        document.save(update_fields=("body", "last_updated"))
        return document


class AssignmentForm(NetBoxModelForm):
    assigned_object_type = ContentTypeChoiceField(queryset=ContentType.objects.none(), label=_("Object type"), widget=HTMXSelect())
    assigned_object = DynamicModelChoiceField(
        queryset=Device.objects.none(), label=_("NetBox object"), required=True, disabled=True, selector=True
    )

    fieldsets = (FieldSet("document", "assigned_object_type", "assigned_object", "note", "tags", name=_("Assign document")),)

    class Meta:
        model = DocumentAssignment
        fields = ("document", "assigned_object_type", "note", "tags")

    def __init__(self, *args, **kwargs):
        instance = kwargs.get("instance")
        initial = kwargs.setdefault("initial", {})
        if instance and instance.pk and instance.assigned_object:
            initial["assigned_object"] = instance.assigned_object
        super().__init__(*args, **kwargs)
        self.fields["assigned_object_type"].queryset = allowed_content_types()
        ct_id = get_field_value(self, "assigned_object_type")
        if ct_id:
            content_type = self.fields["assigned_object_type"].queryset.filter(pk=ct_id).first()
        else:
            content_type = None
        if content_type and content_type.model_class():
            model = content_type.model_class()
            self.fields["assigned_object"].queryset = model.objects.all()
            self.fields["assigned_object"].widget.attrs["selector"] = model._meta.label_lower
            self.fields["assigned_object"].disabled = False
            self.fields["assigned_object"].label = model._meta.verbose_name.title()

    def clean(self):
        super().clean()
        self.instance.assigned_object = self.cleaned_data.get("assigned_object")


class DocumentCategoryForm(NetBoxModelForm):
    slug = SlugField(slug_source="name")
    parent = DynamicModelChoiceField(queryset=DocumentCategory.objects.all(), required=False, label=_("Parent folder"))
    tenant_group = DynamicModelChoiceField(
        queryset=TenantGroup.objects.all(), required=False, selector=True, label=_("Tenant group"),
    )
    tenant = DynamicModelChoiceField(
        queryset=Tenant.objects.all(), required=False, selector=True, label=_("Tenant"),
        query_params={"group_id": "$tenant_group"},
    )

    fieldsets = (FieldSet("name", "slug", "parent", "tenant_group", "tenant", "description", "tags", name=_("Folder")),)

    class Meta:
        model = DocumentCategory
        fields = ("name", "slug", "parent", "tenant_group", "tenant", "description", "tags")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["parent"].queryset = DocumentCategory.objects.exclude(pk=self.instance.pk)

    def clean(self):
        super().clean()
        cleaned = self.cleaned_data
        tenant, group = cleaned.get("tenant"), cleaned.get("tenant_group")
        if tenant and group and tenant.group_id != group.pk:
            self.add_error("tenant", _("The tenant does not belong to the selected tenant group."))
        return cleaned


class ImportForm(forms.Form):
    file = forms.FileField(label=_("Word, Excel or PDF file"))
    title = forms.CharField(max_length=200, required=False, label=help_label(
        _("Title"), _("Leave empty to use the file name as title. Multi-sheet imports use the sheet names.")
    ))
    append = forms.BooleanField(required=False, initial=False, label=help_label(
        _("Append to existing document"), _("Adds the imported content to the end of an existing document.")
    ))
    document = forms.ModelChoiceField(queryset=Document.objects.all(), required=False, label=help_label(
        _("Existing document"), _("Target document for appending.")
    ))
    excel_sheets_as_documents = forms.BooleanField(
        required=False,
        label=help_label(
            _("Excel with multiple worksheets – one document per sheet"),
            _("Creates a separate document in the selected target folder from every non-empty Excel worksheet."),
        ),
    )
    flatten_excel_tables = forms.BooleanField(
        required=False,
        label=help_label(
            _("Flatten Excel tables"),
            _("Imports plain cells outside tables as document-style text. Only ranges explicitly defined in Excel via Insert → Table remain tables."),
        ),
    )
    category = forms.ModelChoiceField(
        queryset=DocumentCategory.objects.none(), required=False,
        label=help_label(_("Target folder / category"), _("Required for the Excel multi-sheet import.")),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["document"].queryset = Document.objects.restrict(user, "change")
            self.fields["category"].queryset = DocumentCategory.objects.restrict(user, "view")

    def clean(self):
        data = super().clean()
        if data.get("append") and not data.get("document"):
            self.add_error("document", _("Select a document to append to."))
        upload = data.get("file")
        if data.get("excel_sheets_as_documents"):
            if upload and not upload.name.lower().endswith((".xlsx", ".xlsm")):
                self.add_error("file", _("The multi-sheet import requires an XLSX or XLSM file."))
            if not data.get("category"):
                self.add_error("category", _("Select a target folder for the generated documents."))
            if data.get("append"):
                self.add_error("append", _("Multi-sheet import and appending cannot be combined."))
        limit = settings.PLUGINS_CONFIG.get("netbox_documentation", {}).get("max_import_size_mb", 25)
        if upload and upload.size > limit * 1024 * 1024:
            self.add_error("file", _("The file is larger than %(limit)s MB.") % {"limit": limit})
        return data


class ArchiveExportForm(forms.Form):
    categories = DynamicModelMultipleChoiceField(
        queryset=DocumentCategory.objects.all(), selector=True,
        label=_("Folders and categories"),
        help_text=_("Search for and add one or more folders."),
    )
    include_subfolders = forms.BooleanField(
        required=False, initial=True, label=_("Include subfolders"),
        help_text=_("Exports documents from all subfolders."),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = DocumentCategory.objects.all().order_by("name")
        if user is not None:
            queryset = queryset.restrict(user, "view")
        self.fields["categories"].queryset = queryset


class ArchiveImportForm(forms.Form):
    archive = forms.FileField(label=_("ZIP archive"))
    update_existing = forms.BooleanField(
        required=False, initial=False,
        label=_("Update existing documents with the same slug"),
        help_text=_("Without this option, name conflicts create new documents with a numbered slug."),
    )

    def clean_archive(self):
        upload = self.cleaned_data["archive"]
        if not upload.name.lower().endswith(".zip"):
            raise forms.ValidationError(_("Select a ZIP archive created by this plugin."))
        limit = settings.PLUGINS_CONFIG.get("netbox_documentation", {}).get("max_archive_size_mb", 250)
        if upload.size > limit * 1024 * 1024:
            raise forms.ValidationError(_("The archive is larger than %(limit)s MB.") % {"limit": limit})
        return upload


class ExcelSheetSelectionForm(forms.Form):
    include = forms.BooleanField(
        required=False, initial=True, label=_("Import"),
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    index = forms.IntegerField(widget=forms.HiddenInput())
    title = forms.CharField(
        max_length=200, required=False, label=_("Document title"),
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    def clean(self):
        data = super().clean()
        if data.get("include") and not (data.get("title") or "").strip():
            self.add_error("title", _("A selected worksheet requires a title."))
        return data


class BaseExcelSheetSelectionFormSet(forms.BaseFormSet):
    def clean(self):
        super().clean()
        if any(form.errors for form in self.forms):
            return
        selected = [form.cleaned_data for form in self.forms if form.cleaned_data.get("include")]
        if not selected:
            raise forms.ValidationError(_("Select at least one worksheet."))
        indices = [item["index"] for item in selected]
        if len(indices) != len(set(indices)):
            raise forms.ValidationError(_("The worksheet selection is invalid."))
        titles = [item["title"].strip().casefold() for item in selected]
        if len(titles) != len(set(titles)):
            raise forms.ValidationError(_("Selected worksheets must not have the same document title."))


ExcelSheetSelectionFormSet = forms.formset_factory(
    ExcelSheetSelectionForm, formset=BaseExcelSheetSelectionFormSet, extra=0
)
