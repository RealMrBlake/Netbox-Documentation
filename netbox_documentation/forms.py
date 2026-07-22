from django import forms
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from utilities.forms import get_field_value
from utilities.forms.fields import ContentTypeChoiceField, DynamicModelChoiceField, SlugField
from utilities.forms.rendering import FieldSet
from utilities.forms.widgets import HTMXSelect
from netbox.forms import NetBoxModelForm
from dcim.models import Device
from .models import Document, DocumentAssignment, DocumentCategory


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
    body = forms.CharField(required=False, label="Inhalt", widget=forms.Textarea(attrs={
        "rows": 32, "class": "rich-text-editor", "data-rich-text-editor": "true"
    }), help_text="Formatierter Text mit Tabellen, Farben, Schriftarten und Größen.")
    body_format = forms.CharField(widget=forms.HiddenInput(), initial="html")
    category = DynamicModelChoiceField(queryset=DocumentCategory.objects.all(), required=False, label="Ordner")

    fieldsets = (
        FieldSet("title", "slug", "category", "summary", "is_published", "tags", name="Dokumentation"),
        FieldSet("body", "body_format", name="Inhalt"),
    )

    class Meta:
        model = Document
        fields = ("title", "slug", "category", "summary", "body", "body_format", "is_published", "tags")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Legacy Markdown remains readable. Once edited in WYSIWYG mode it is
        # converted to HTML so the editor never exposes Markdown as plain text.
        if self.instance.pk and self.instance.body_format == "markdown" and not self.is_bound:
            from markdown import markdown
            self.initial["body"] = markdown(self.instance.body, extensions=("extra", "sane_lists"))
            self.initial["body_format"] = "html"


class AssignmentForm(NetBoxModelForm):
    assigned_object_type = ContentTypeChoiceField(queryset=ContentType.objects.none(), label="Objekttyp", widget=HTMXSelect())
    assigned_object = DynamicModelChoiceField(
        queryset=Device.objects.none(), label="NetBox-Objekt", required=True, disabled=True, selector=True
    )

    fieldsets = (FieldSet("document", "assigned_object_type", "assigned_object", "note", "tags", name="Dokumentation zuordnen"),)

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
    parent = DynamicModelChoiceField(queryset=DocumentCategory.objects.all(), required=False, label="Übergeordneter Ordner")

    fieldsets = (FieldSet("name", "slug", "parent", "description", "tags", name="Ordner"),)

    class Meta:
        model = DocumentCategory
        fields = ("name", "slug", "parent", "description", "tags")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["parent"].queryset = DocumentCategory.objects.exclude(pk=self.instance.pk)


class ImportForm(forms.Form):
    file = forms.FileField(label="Word-, Excel- oder PDF-Datei")
    title = forms.CharField(max_length=200, required=False, help_text="Leer lassen, um den Dateinamen zu verwenden")
    append = forms.BooleanField(required=False, initial=False, label="An bestehende Dokumentation anhängen")
    document = forms.ModelChoiceField(queryset=Document.objects.all(), required=False, label="Bestehende Dokumentation")

    def clean(self):
        data = super().clean()
        if data.get("append") and not data.get("document"):
            self.add_error("document", "Zum Anhängen muss eine Dokumentation gewählt werden.")
        upload = data.get("file")
        limit = settings.PLUGINS_CONFIG.get("netbox_documentation", {}).get("max_import_size_mb", 25)
        if upload and upload.size > limit * 1024 * 1024:
            self.add_error("file", f"Die Datei ist größer als {limit} MB.")
        return data


class ArchiveExportForm(forms.Form):
    documents = forms.ModelMultipleChoiceField(
        queryset=Document.objects.none(), widget=forms.CheckboxSelectMultiple,
        label="Dokumentationen",
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = Document.objects.all().order_by("title")
        if user is not None:
            queryset = queryset.restrict(user, "view")
        self.fields["documents"].queryset = queryset


class ArchiveImportForm(forms.Form):
    archive = forms.FileField(label="ZIP-Archiv")
    update_existing = forms.BooleanField(
        required=False, initial=False,
        label="Bestehende Dokumentationen mit gleicher Kennung aktualisieren",
        help_text="Ohne diese Option werden bei Namenskonflikten neue Dokumentationen mit einer fortlaufenden Kennung angelegt.",
    )

    def clean_archive(self):
        upload = self.cleaned_data["archive"]
        if not upload.name.lower().endswith(".zip"):
            raise forms.ValidationError("Bitte ein vom Plugin erzeugtes ZIP-Archiv auswählen.")
        limit = settings.PLUGINS_CONFIG.get("netbox_documentation", {}).get("max_archive_size_mb", 250)
        if upload.size > limit * 1024 * 1024:
            raise forms.ValidationError(f"Das Archiv ist größer als {limit} MB.")
        return upload
