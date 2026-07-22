from netbox.api.viewsets import NetBoxModelViewSet
from ..filtersets import DocumentFilterSet, AssignmentFilterSet, DocumentCategoryFilterSet
from ..models import Document, DocumentAssignment, DocumentAttachment, DocumentCategory
from .serializers import (
    DocumentSerializer, DocumentAssignmentSerializer, DocumentAttachmentSerializer,
    DocumentCategorySerializer,
)


class DocumentViewSet(NetBoxModelViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    filterset_class = DocumentFilterSet


class DocumentAssignmentViewSet(NetBoxModelViewSet):
    queryset = DocumentAssignment.objects.all()
    serializer_class = DocumentAssignmentSerializer
    filterset_class = AssignmentFilterSet


class DocumentCategoryViewSet(NetBoxModelViewSet):
    queryset = DocumentCategory.objects.all()
    serializer_class = DocumentCategorySerializer
    filterset_class = DocumentCategoryFilterSet


class DocumentAttachmentViewSet(NetBoxModelViewSet):
    queryset = DocumentAttachment.objects.all()
    serializer_class = DocumentAttachmentSerializer
    filterset_fields = ("id", "document_id", "content_type")
