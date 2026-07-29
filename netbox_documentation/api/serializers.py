from netbox.api.serializers import NetBoxModelSerializer
from rest_framework import serializers
from ..models import Document, DocumentAssignment, DocumentAttachment, DocumentCategory


class DocumentSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="plugins-api:netbox_documentation-api:document-detail")

    class Meta:
        model = Document
        fields = ("id", "url", "display", "title", "slug", "category", "tenant_group", "tenant", "summary", "body", "body_format", "is_published", "tags", "created", "last_updated")


class DocumentAssignmentSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="plugins-api:netbox_documentation-api:documentassignment-detail")

    class Meta:
        model = DocumentAssignment
        fields = ("id", "url", "display", "document", "assigned_object_type", "assigned_object_id", "note", "tags", "created", "last_updated")


class DocumentCategorySerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="plugins-api:netbox_documentation-api:documentcategory-detail")

    class Meta:
        model = DocumentCategory
        fields = ("id", "url", "display", "name", "slug", "parent", "tenant_group", "tenant", "description", "tags", "created", "last_updated")


class DocumentAttachmentSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="plugins-api:netbox_documentation-api:documentattachment-detail")

    class Meta:
        model = DocumentAttachment
        fields = (
            "id", "url", "display", "document", "file", "original_name",
            "content_type", "size", "tags", "created", "last_updated",
        )
