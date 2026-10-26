from django.utils.translation import gettext_lazy as _
from netbox.plugins import PluginMenu, PluginMenuButton, PluginMenuItem
from netbox.choices import ButtonColorChoices

menu = PluginMenu(
    label=_("Documentation"),
    groups=((_("Wiki"), (
        PluginMenuItem(link="plugins:netbox_documentation:document_tree", link_text=_("Documents"), buttons=(
            PluginMenuButton(link="plugins:netbox_documentation:document_add", title=_("New"), icon_class="mdi mdi-plus-thick", color=ButtonColorChoices.GREEN),
            PluginMenuButton(link="plugins:netbox_documentation:document_import", title=_("Import"), icon_class="mdi mdi-file-import", color=ButtonColorChoices.BLUE),
        )),
        PluginMenuItem(link="plugins:netbox_documentation:documentassignment_list", link_text=_("Assignments"), buttons=(
            PluginMenuButton(link="plugins:netbox_documentation:documentassignment_add", title=_("Assign"), icon_class="mdi mdi-link-plus", color=ButtonColorChoices.GREEN),
        )),
        PluginMenuItem(link="plugins:netbox_documentation:documentcategory_tree", link_text=_("Folders & categories"), buttons=(
            PluginMenuButton(link="plugins:netbox_documentation:documentcategory_add", title=_("Create folder"), icon_class="mdi mdi-folder-plus", color=ButtonColorChoices.GREEN),
        )),
        PluginMenuItem(link="plugins:netbox_documentation:document_archive", link_text=_("ZIP export & import")),
    )),),
    icon_class="mdi mdi-book-open-page-variant",
)
