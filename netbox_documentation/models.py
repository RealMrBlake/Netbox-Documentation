from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.urls import reverse
from netbox.models import NetBoxModel


BODY_FORMAT_CHOICES = (("html", "Rich Text"), ("markdown", "Markdown"))


class Document(NetBoxModel):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    body = models.TextField(blank=True, help_text="Markdown")
    body_format = models.CharField(max_length=10, choices=BODY_FORMAT_CHOICES, default="html")
    summary = models.CharField(max_length=500, blank=True)
    is_published = models.BooleanField(default=True)
    category = models.ForeignKey("DocumentCategory", on_delete=models.SET_NULL, null=True, blank=True, related_name="documents")

    class Meta:
        ordering = ("title",)
        permissions = (("import_document", "Can import office documents"),)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("plugins:netbox_documentation:document", args=[self.pk])

    def rendered_body(self):
        """Render Markdown/HTML and remove executable or unsafe markup."""
        import bleach
        from bleach.css_sanitizer import CSSSanitizer
        from markdown import markdown

        value = markdown(self.body, extensions=("extra", "sane_lists")) if self.body_format == "markdown" else self.body
        tags = {
            "a", "abbr", "blockquote", "br", "caption", "code", "col", "colgroup", "div",
            "em", "h1", "h2", "h3", "h4", "h5", "h6", "hr", "img", "li", "ol", "p",
            "pre", "span", "strong", "sub", "sup", "table", "tbody", "td", "tfoot", "th",
            "thead", "tr", "u", "ul",
        }
        attributes = {
            "a": ("href", "title", "target", "rel"),
            "img": ("src", "alt", "title", "width", "height"),
            "table": ("class", "style"),
            "th": ("colspan", "rowspan", "scope", "style"),
            "td": ("colspan", "rowspan", "style"),
            "col": ("span", "style"),
            "*": ("class", "style"),
        }
        css = CSSSanitizer(allowed_css_properties={
            "background-color", "border", "border-color", "border-style", "border-width",
            "color", "font-family", "font-size", "font-style", "font-weight", "height",
            "border-collapse", "line-height", "list-style-type", "margin", "margin-bottom",
            "margin-left", "margin-right", "margin-top", "padding", "padding-bottom",
            "padding-left", "padding-right", "padding-top", "text-align", "text-decoration",
            "text-indent", "vertical-align", "white-space", "width",
        })
        return bleach.clean(value, tags=tags, attributes=attributes, protocols=("http", "https", "mailto"), css_sanitizer=css)


class DocumentCategory(NetBoxModel):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="children")
    description = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ("name",)
        constraints = [models.UniqueConstraint(fields=("parent", "slug"), name="%(app_label)s_%(class)s_unique_parent_slug")]
        verbose_name_plural = "document categories"

    def __str__(self):
        names = [self.name]
        parent = self.parent
        seen = {self.pk}
        while parent and parent.pk not in seen:
            names.append(parent.name)
            seen.add(parent.pk)
            parent = parent.parent
        return " / ".join(reversed(names))

    def get_absolute_url(self):
        return reverse("plugins:netbox_documentation:documentcategory", args=[self.pk])

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        parent = self.parent
        seen = {self.pk} if self.pk else set()
        while parent:
            if parent.pk in seen:
                raise ValidationError({"parent": "Ein Ordner kann nicht sich selbst oder einem Unterordner untergeordnet werden."})
            seen.add(parent.pk)
            parent = parent.parent


class DocumentAssignment(NetBoxModel):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="assignments")
    assigned_object_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    assigned_object_id = models.PositiveBigIntegerField()
    assigned_object = GenericForeignKey("assigned_object_type", "assigned_object_id")
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ("document", "assigned_object_type", "assigned_object_id")
        constraints = [models.UniqueConstraint(
            fields=("document", "assigned_object_type", "assigned_object_id"),
            name="%(app_label)s_%(class)s_unique_assignment",
        )]

    def __str__(self):
        return f"{self.document} → {self.assigned_object}"

    def get_absolute_url(self):
        # No separate detail page exists for an assignment. NetBox's generic
        # edit view nevertheless needs a valid URL for its success message.
        return reverse("plugins:netbox_documentation:documentassignment_list")


def attachment_upload_path(instance, filename):
    return f"netbox_documentation/{instance.document_id}/{filename}"


class DocumentAttachment(NetBoxModel):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to=attachment_upload_path)
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100, blank=True)
    size = models.PositiveBigIntegerField(default=0)

    class Meta:
        ordering = ("original_name",)

    def __str__(self):
        return self.original_name
