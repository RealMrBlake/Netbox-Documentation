from django.utils.translation import gettext_lazy as _
from netbox.plugins import PluginConfig


class DocumentationConfig(PluginConfig):
    name = "netbox_documentation"
    verbose_name = _("NetBox Documentation")
    description = _("Wiki and office documentation directly in NetBox")
    version = "0.12.1"
    author = "LKE"
    base_url = "documentation"
    min_version = "4.4.0"  # netbox.object_actions
    max_version = "4.7.99"
    django_apps = ["tinymce"]
    default_settings = {
        "allowed_object_types": [
            "dcim.region", "dcim.site", "dcim.location", "dcim.rack",
            "dcim.device", "virtualization.virtualmachine",
            "virtualization.cluster", "tenancy.tenant",
        ],
        "max_import_size_mb": 25,
        "max_archive_size_mb": 250,
        "keep_imported_file": True,
    }


config = DocumentationConfig
