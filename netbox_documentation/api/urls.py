from netbox.api.routers import NetBoxRouter
from . import views

router = NetBoxRouter()
router.register("documents", views.DocumentViewSet)
router.register("assignments", views.DocumentAssignmentViewSet)
urlpatterns = router.urls

