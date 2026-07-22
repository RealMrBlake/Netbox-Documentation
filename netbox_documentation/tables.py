import django_tables2 as tables
from netbox.tables import NetBoxTable, columns
from .models import Document, DocumentAssignment


class DocumentTable(NetBoxTable):
    title = tables.Column(linkify=True)
    assignments = tables.Column(accessor="assignments.count", verbose_name="Zuordnungen", orderable=False)
    actions = columns.ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = Document
        fields = ("pk", "title", "summary", "is_published", "assignments", "last_updated", "actions")


class AssignmentTable(NetBoxTable):
    document = tables.Column(linkify=True)
    assigned_object = tables.Column(linkify=True, verbose_name="NetBox-Objekt")
    actions = columns.ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = DocumentAssignment
        fields = ("pk", "document", "assigned_object_type", "assigned_object", "note", "actions")

