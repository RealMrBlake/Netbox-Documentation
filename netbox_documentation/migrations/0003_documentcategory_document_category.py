from django.db import migrations, models
import django.db.models.deletion
import netbox.models.features


class Migration(migrations.Migration):
    dependencies = [
        ("extras", "0001_squashed"),
        ("netbox_documentation", "0002_document_body_format"),
    ]

    operations = [
        migrations.CreateModel(
            name="DocumentCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                ("custom_field_data", models.JSONField(blank=True, default=dict, encoder=netbox.models.features.CustomFieldJSONEncoder)),
                ("name", models.CharField(max_length=100)),
                ("slug", models.SlugField(max_length=100)),
                ("description", models.CharField(blank=True, max_length=500)),
                ("parent", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="children", to="netbox_documentation.documentcategory")),
                ("tags", models.ManyToManyField(blank=True, related_name="netbox_documentation_documentcategory_items", to="extras.tag")),
            ],
            options={"verbose_name_plural": "document categories", "ordering": ("name",)},
        ),
        migrations.AddConstraint(
            model_name="documentcategory",
            constraint=models.UniqueConstraint(fields=("parent", "slug"), name="netbox_documentation_documentcategory_unique_parent_slug"),
        ),
        migrations.AddField(
            model_name="document",
            name="category",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="documents", to="netbox_documentation.documentcategory"),
        ),
    ]
