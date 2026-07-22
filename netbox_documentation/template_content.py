from netbox.plugins import PluginTemplateExtension
from django.contrib.contenttypes.models import ContentType
from .models import DocumentAssignment


class ObjectDocumentation(PluginTemplateExtension):
    models = [
        "dcim.region", "dcim.site", "dcim.location", "dcim.rack", "dcim.device",
        "virtualization.virtualmachine", "virtualization.cluster", "tenancy.tenant",
    ]

    def right_page(self):
        obj = self.context["object"]
        content_type = ContentType.objects.get_for_model(obj)
        assignments = DocumentAssignment.objects.filter(
            assigned_object_type=content_type, assigned_object_id=obj.pk,
            document__is_published=True,
        ).select_related("document")
        return self.render("netbox_documentation/inc/object_documents.html", extra_context={
            "documentation_assignments": assignments,
            "content_type": content_type,
        })


template_extensions = [ObjectDocumentation]

