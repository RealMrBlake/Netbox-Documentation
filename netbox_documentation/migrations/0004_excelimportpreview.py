from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import netbox_documentation.models
import uuid


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("netbox_documentation", "0003_documentcategory_document_category"),
    ]

    operations = [
        migrations.CreateModel(
            name="ExcelImportPreview",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("file", models.FileField(upload_to=netbox_documentation.models.preview_upload_path)),
                ("original_name", models.CharField(max_length=255)),
                ("content_type", models.CharField(blank=True, max_length=100)),
                ("flatten", models.BooleanField(default=False)),
                ("sheet_metadata", models.JSONField(default=list)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("category", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to="netbox_documentation.documentcategory")),
                ("user", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-created",)},
        ),
    ]
