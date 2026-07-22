from netbox.filtersets import NetBoxModelFilterSet
from .models import Document, DocumentAssignment


class DocumentFilterSet(NetBoxModelFilterSet):
    class Meta:
        model = Document
        fields = ("id", "title", "slug", "is_published")

    def search(self, queryset, name, value):
        from django.db.models import Q
        return queryset.filter(Q(title__icontains=value) | Q(summary__icontains=value) | Q(body__icontains=value))


class AssignmentFilterSet(NetBoxModelFilterSet):
    class Meta:
        model = DocumentAssignment
        fields = ("id", "document_id", "assigned_object_type", "assigned_object_id")

