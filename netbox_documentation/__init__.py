from netbox.plugins import PluginConfig


class DocumentationConfig(PluginConfig):
    name = "netbox_documentation"
    verbose_name = "NetBox Dokumentation"
    description = "Wiki und Office-Dokumentation direkt in NetBox"
    version = "0.4.2"
    author = "LKE"
    base_url = "documentation"
    min_version = "4.0.0"
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
