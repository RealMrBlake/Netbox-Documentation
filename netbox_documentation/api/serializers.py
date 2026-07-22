from netbox.api.serializers import NetBoxModelSerializer
from rest_framework import serializers
from ..models import Document, DocumentAssignment


class DocumentSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="plugins-api:netbox_documentation-api:document-detail")

    class Meta:
        model = Document
        fields = ("id", "url", "display", "title", "slug", "summary", "body", "body_format", "is_published", "tags", "created", "last_updated")


class DocumentAssignmentSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="plugins-api:netbox_documentation-api:documentassignment-detail")

    class Meta:
        model = DocumentAssignment
        fields = ("id", "url", "display", "document", "assigned_object_type", "assigned_object_id", "note", "tags", "created", "last_updated")
