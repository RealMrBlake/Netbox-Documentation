from netbox.plugins import PluginConfig


class DocumentationConfig(PluginConfig):
    name = "netbox_documentation"
    verbose_name = "Dokumentation"
    description = "Wiki und Office-Dokumentation direkt in NetBox"
    version = "0.2.0"
    author = "NetBox Documentation Contributors"
    base_url = "documentation"
    min_version = "4.0.0"
    default_settings = {
        "allowed_object_types": [
            "dcim.region", "dcim.site", "dcim.location", "dcim.rack",
            "dcim.device", "virtualization.virtualmachine",
            "virtualization.cluster", "tenancy.tenant",
        ],
        "max_import_size_mb": 25,
        "keep_imported_file": True,
        # Can be replaced with a locally hosted TinyMCE bundle for offline use.
        "editor_script_url": "https://cdn.jsdelivr.net/npm/tinymce@7/tinymce.min.js",
    }


config = DocumentationConfig
