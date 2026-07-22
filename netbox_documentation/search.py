from netbox.search import SearchIndex, register_search
from .models import Document, DocumentCategory


@register_search
class DocumentIndex(SearchIndex):
    model = Document
    fields = (("title", 100), ("summary", 80), ("body", 50))
    display_attrs = ("summary",)


@register_search
class DocumentCategoryIndex(SearchIndex):
    model = DocumentCategory
    fields = (("name", 100), ("description", 60))
    display_attrs = ("description",)
