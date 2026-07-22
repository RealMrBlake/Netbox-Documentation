from django.urls import path
from netbox.views.generic import ObjectChangeLogView
from . import models, views

urlpatterns = (
    path("editor-assets/<path:asset_path>", views.EditorAssetView.as_view(), name="editor_asset"),
    path("", views.DocumentListView.as_view(), name="document_list"),
    path("documents/add/", views.DocumentEditView.as_view(), name="document_add"),
    path("documents/import/", views.DocumentImportView.as_view(), name="document_import"),
    path("documents/<int:pk>/", views.DocumentView.as_view(), name="document"),
    path("documents/<int:pk>/edit/", views.DocumentEditView.as_view(), name="document_edit"),
    path("documents/<int:pk>/delete/", views.DocumentDeleteView.as_view(), name="document_delete"),
    path("documents/<int:pk>/changelog/", ObjectChangeLogView.as_view(), name="document_changelog", kwargs={"model": models.Document}),
    path("assignments/", views.AssignmentListView.as_view(), name="documentassignment_list"),
    path("assignments/add/", views.AssignmentEditView.as_view(), name="documentassignment_add"),
    path("assignments/<int:pk>/edit/", views.AssignmentEditView.as_view(), name="documentassignment_edit"),
    path("assignments/<int:pk>/delete/", views.AssignmentDeleteView.as_view(), name="documentassignment_delete"),
)
