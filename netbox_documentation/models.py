from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.conf import settings
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from pathlib import Path
import uuid
from netbox.models import NetBoxModel


BODY_FORMAT_CHOICES = (("html", _("Rich text")), ("markdown", _("Markdown")))


class Document(NetBoxModel):
    title = models.CharField(_("title"), max_length=200)
    slug = models.SlugField(_("slug"), max_length=200, unique=True)
    body = models.TextField(_("body"), blank=True, help_text=_("Markdown"))
    body_format = models.CharField(_("body format"), max_length=10, choices=BODY_FORMAT_CHOICES, default="html")
    summary = models.CharField(_("summary"), max_length=500, blank=True)
    is_published = models.BooleanField(_("published"), default=True)
    category = models.ForeignKey("DocumentCategory", on_delete=models.SET_NULL, null=True, blank=True, related_name="documents", verbose_name=_("folder"))
    tenant_group = models.ForeignKey(
        "tenancy.TenantGroup", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="documentation_documents", verbose_name=_("tenant group"),
    )
    tenant = models.ForeignKey(
        "tenancy.Tenant", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="documentation_documents", verbose_name=_("tenant"),
    )

    class Meta:
        ordering = ("title",)
        verbose_name = _("document")
        verbose_name_plural = _("documents")
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
            "background", "background-color", "border", "border-color", "border-style", "border-width",
            "color", "font-family", "font-size", "font-style", "font-weight", "height",
            "border-collapse", "line-height", "list-style-type", "margin", "margin-bottom",
            "margin-left", "margin-right", "margin-top", "padding", "padding-bottom",
            "padding-left", "padding-right", "padding-top", "text-align", "text-decoration",
            "text-indent", "vertical-align", "white-space", "width",
        })
        from .highlighting import highlight_code_blocks

        cleaned = bleach.clean(value, tags=tags, attributes=attributes, protocols=("http", "https", "mailto"), css_sanitizer=css)
        return highlight_code_blocks(cleaned)


class DocumentCategory(NetBoxModel):
    name = models.CharField(_("name"), max_length=100)
    slug = models.SlugField(_("slug"), max_length=100)
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="children", verbose_name=_("parent folder"))
    description = models.CharField(_("description"), max_length=500, blank=True)
    tenant_group = models.ForeignKey(
        "tenancy.TenantGroup", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="documentation_categories", verbose_name=_("tenant group"),
    )
    tenant = models.ForeignKey(
        "tenancy.Tenant", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="documentation_categories", verbose_name=_("tenant"),
    )

    class Meta:
        ordering = ("name",)
        constraints = [models.UniqueConstraint(fields=("parent", "slug"), name="%(app_label)s_%(class)s_unique_parent_slug")]
        verbose_name = _("folder")
        verbose_name_plural = _("folders")

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

    @property
    def ancestors(self):
        """Ancestor folders from the root down to (excluding) this one, for breadcrumbs."""
        result = []
        parent = self.parent
        seen = {self.pk}
        while parent and parent.pk not in seen:
            result.append(parent)
            seen.add(parent.pk)
            parent = parent.parent
        return list(reversed(result))

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        parent = self.parent
        seen = {self.pk} if self.pk else set()
        while parent:
            if parent.pk in seen:
                raise ValidationError({"parent": _("A folder cannot be placed inside itself or one of its subfolders.")})
            seen.add(parent.pk)
            parent = parent.parent


class DocumentAssignment(NetBoxModel):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="assignments", verbose_name=_("document"))
    assigned_object_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, verbose_name=_("object type"))
    assigned_object_id = models.PositiveBigIntegerField(_("object ID"))
    assigned_object = GenericForeignKey("assigned_object_type", "assigned_object_id")
    note = models.CharField(_("note"), max_length=200, blank=True)

    class Meta:
        ordering = ("document", "assigned_object_type", "assigned_object_id")
        verbose_name = _("document assignment")
        verbose_name_plural = _("document assignments")
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
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="attachments", verbose_name=_("document"))
    file = models.FileField(_("file"), upload_to=attachment_upload_path)
    original_name = models.CharField(_("original name"), max_length=255)
    content_type = models.CharField(_("content type"), max_length=100, blank=True)
    size = models.PositiveBigIntegerField(_("size"), default=0)

    class Meta:
        ordering = ("original_name",)
        verbose_name = _("attachment")
        verbose_name_plural = _("attachments")

    def __str__(self):
        return self.original_name

    def get_absolute_url(self):
        # Attachments are displayed on their parent document and intentionally
        # have no standalone detail view. This is also used by NetBox's delete
        # dependency collector when rendering the confirmation dialog.
        return self.document.get_absolute_url()


def preview_upload_path(instance, filename):
    return f"netbox_documentation/import-previews/{instance.pk}/{Path(filename).name}"


class ExcelImportPreview(models.Model):
    """Short-lived, user-bound state for the two-step Excel import workflow."""
    _netbox_private = True

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    category = models.ForeignKey(DocumentCategory, on_delete=models.SET_NULL, null=True)
    file = models.FileField(upload_to=preview_upload_path)
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100, blank=True)
    flatten = models.BooleanField(default=False)
    sheet_metadata = models.JSONField(default=list)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created",)

    def __str__(self):
        return self.original_name
