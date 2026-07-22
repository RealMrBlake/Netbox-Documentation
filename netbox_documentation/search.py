from netbox.search import SearchIndex, register_search
from .models import Document


@register_search
class DocumentIndex(SearchIndex):
    model = Document
    fields = (("title", 100), ("summary", 80), ("body", 50))
    display_attrs = ("summary",)

