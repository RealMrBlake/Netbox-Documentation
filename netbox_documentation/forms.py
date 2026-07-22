from django import forms
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from utilities.forms.fields import SlugField
from netbox.forms import NetBoxModelForm
from .models import Document, DocumentAssignment


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

    class Meta:
        model = Document
        fields = ("title", "slug", "summary", "body", "body_format", "is_published", "tags")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Legacy Markdown remains readable. Once edited in WYSIWYG mode it is
        # converted to HTML so the editor never exposes Markdown as plain text.
        if self.instance.pk and self.instance.body_format == "markdown" and not self.is_bound:
            from markdown import markdown
            self.initial["body"] = markdown(self.instance.body, extensions=("extra", "sane_lists"))
            self.initial["body_format"] = "html"


class AssignmentForm(NetBoxModelForm):
    assigned_object_type = forms.ModelChoiceField(queryset=ContentType.objects.none(), label="Objekttyp")
    assigned_object_id = forms.TypedChoiceField(coerce=int, label="NetBox-Objekt")

    class Meta:
        model = DocumentAssignment
        fields = ("document", "assigned_object_type", "assigned_object_id", "note", "tags")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_object_type"].queryset = allowed_content_types()
        content_type = None
        ct_id = (self.data.get("assigned_object_type") or self.initial.get("assigned_object_type")
                 or getattr(self.instance, "assigned_object_type_id", None))
        if ct_id:
            content_type = ContentType.objects.filter(pk=ct_id).first()
        if content_type:
            model = content_type.model_class()
            objects = model.objects.all().order_by("pk")
            self.fields["assigned_object_id"].choices = [(obj.pk, str(obj)) for obj in objects]

    def clean(self):
        cleaned = super().clean()
        object_id = cleaned.get("assigned_object_id")
        ct = cleaned.get("assigned_object_type")
        if object_id and ct and not ct.model_class().objects.filter(pk=object_id).exists():
            self.add_error("assigned_object_id", "Das Objekt existiert für diesen Objekttyp nicht.")
        return cleaned


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
