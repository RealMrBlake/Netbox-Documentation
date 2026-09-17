from netbox.plugins import PluginMenu, PluginMenuButton, PluginMenuItem
from netbox.choices import ButtonColorChoices

menu = PluginMenu(
    label="Dokumentation",
    groups=(("Wiki", (
        PluginMenuItem(link="plugins:netbox_documentation:document_tree", link_text="Dokumentationen", buttons=(
            PluginMenuButton(link="plugins:netbox_documentation:document_add", title="Neu", icon_class="mdi mdi-plus-thick", color=ButtonColorChoices.GREEN),
            PluginMenuButton(link="plugins:netbox_documentation:document_import", title="Import", icon_class="mdi mdi-file-import", color=ButtonColorChoices.BLUE),
        )),
        PluginMenuItem(link="plugins:netbox_documentation:documentassignment_list", link_text="Zuordnungen", buttons=(
            PluginMenuButton(link="plugins:netbox_documentation:documentassignment_add", title="Zuordnen", icon_class="mdi mdi-link-plus", color=ButtonColorChoices.GREEN),
        )),
        PluginMenuItem(link="plugins:netbox_documentation:documentcategory_tree", link_text="Ordner & Kategorien", buttons=(
            PluginMenuButton(link="plugins:netbox_documentation:documentcategory_add", title="Ordner erstellen", icon_class="mdi mdi-folder-plus", color=ButtonColorChoices.GREEN),
        )),
        PluginMenuItem(link="plugins:netbox_documentation:document_archive", link_text="ZIP Export & Import"),
    )),),
    icon_class="mdi mdi-book-open-page-variant",
)
