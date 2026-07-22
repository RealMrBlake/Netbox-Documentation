from netbox.api.viewsets import NetBoxModelViewSet
from ..filtersets import DocumentFilterSet, AssignmentFilterSet
from ..models import Document, DocumentAssignment
from .serializers import DocumentSerializer, DocumentAssignmentSerializer


class DocumentViewSet(NetBoxModelViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    filterset_class = DocumentFilterSet


class DocumentAssignmentViewSet(NetBoxModelViewSet):
    queryset = DocumentAssignment.objects.all()
    serializer_class = DocumentAssignmentSerializer
    filterset_class = AssignmentFilterSet

