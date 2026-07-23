from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("netbox_documentation", "0004_excelimportpreview"),
    ]

    operations = [
        migrations.CreateModel(
            name="DocumentEditLock",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("token", models.UUIDField(default=uuid.uuid4, editable=False)),
                ("acquired", models.DateTimeField(auto_now_add=True)),
                ("heartbeat", models.DateTimeField(auto_now=True)),
                ("document", models.OneToOneField(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="edit_lock", to="netbox_documentation.document")),
                ("user", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
