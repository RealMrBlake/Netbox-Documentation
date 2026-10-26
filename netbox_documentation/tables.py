import django_tables2 as tables
from django.utils.translation import gettext_lazy as _
from netbox.tables import NetBoxTable, columns
from .models import Document, DocumentAssignment, DocumentCategory


class DocumentTable(NetBoxTable):
    title = tables.Column(linkify=True)
    assignments = tables.Column(accessor="assignments.count", verbose_name=_("Assignments"), orderable=False)
    actions = columns.ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = Document
        fields = ("pk", "title", "category", "tenant_group", "tenant", "summary", "is_published", "assignments", "last_updated", "actions")


class DocumentCategoryTable(NetBoxTable):
    name = tables.Column(linkify=True, verbose_name=_("Folder"))
    document_count = tables.Column(accessor="documents.count", verbose_name=_("Documents"), orderable=False)
    actions = columns.ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = DocumentCategory
        fields = ("pk", "name", "parent", "tenant_group", "tenant", "description", "document_count", "actions")


class AssignmentTable(NetBoxTable):
    document = tables.Column(linkify=True)
    assigned_object = tables.Column(linkify=True, verbose_name=_("NetBox object"))
    actions = columns.ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = DocumentAssignment
        fields = ("pk", "document", "assigned_object_type", "assigned_object", "note", "actions")
