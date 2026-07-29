from netbox.filtersets import NetBoxModelFilterSet
from .models import Document, DocumentAssignment, DocumentCategory


class DocumentFilterSet(NetBoxModelFilterSet):
    class Meta:
        model = Document
        fields = ("id", "title", "slug", "category_id", "tenant_group_id", "tenant_id", "is_published")

    def search(self, queryset, name, value):
        from django.db.models import Q
        return queryset.filter(Q(title__icontains=value) | Q(summary__icontains=value) | Q(body__icontains=value))


class AssignmentFilterSet(NetBoxModelFilterSet):
    class Meta:
        model = DocumentAssignment
        fields = ("id", "document_id", "assigned_object_type", "assigned_object_id")


class DocumentCategoryFilterSet(NetBoxModelFilterSet):
    class Meta:
        model = DocumentCategory
        fields = ("id", "name", "slug", "parent_id", "tenant_group_id", "tenant_id")

    def search(self, queryset, name, value):
        return queryset.filter(name__icontains=value)
