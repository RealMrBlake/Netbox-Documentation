from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.urls import reverse
from netbox.models import NetBoxModel


class Document(NetBoxModel):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    body = models.TextField(blank=True, help_text="Markdown")
    summary = models.CharField(max_length=500, blank=True)
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ("title",)
        permissions = (("import_document", "Can import office documents"),)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("plugins:netbox_documentation:document", args=[self.pk])


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

