from django.db import migrations, models
import django.db.models.deletion
import netbox.models.features
import netbox_documentation.models


class Migration(migrations.Migration):
    initial = True
    dependencies = [("contenttypes", "0002_remove_content_type_name"), ("extras", "0001_squashed")]
    operations = [
        migrations.CreateModel(name="Document", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
            ("created", models.DateTimeField(auto_now_add=True, null=True)),
            ("last_updated", models.DateTimeField(auto_now=True, null=True)),
            ("custom_field_data", models.JSONField(blank=True, default=dict, encoder=netbox.models.features.CustomFieldJSONEncoder)),
            ("title", models.CharField(max_length=200)), ("slug", models.SlugField(max_length=200, unique=True)),
            ("body", models.TextField(blank=True, help_text="Markdown")), ("summary", models.CharField(blank=True, max_length=500)),
            ("is_published", models.BooleanField(default=True)),
            ("tags", models.ManyToManyField(blank=True, related_name="netbox_documentation_document_items", to="extras.tag")),
        ], options={"ordering": ("title",), "permissions": (("import_document", "Can import office documents"),)}),
        migrations.CreateModel(name="DocumentAssignment", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
            ("created", models.DateTimeField(auto_now_add=True, null=True)), ("last_updated", models.DateTimeField(auto_now=True, null=True)),
            ("custom_field_data", models.JSONField(blank=True, default=dict, encoder=netbox.models.features.CustomFieldJSONEncoder)),
            ("assigned_object_id", models.PositiveBigIntegerField()), ("note", models.CharField(blank=True, max_length=200)),
            ("assigned_object_type", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="contenttypes.contenttype")),
            ("document", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="assignments", to="netbox_documentation.document")),
            ("tags", models.ManyToManyField(blank=True, related_name="netbox_documentation_documentassignment_items", to="extras.tag")),
        ], options={"ordering": ("document", "assigned_object_type", "assigned_object_id")}),
        migrations.CreateModel(name="DocumentAttachment", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
            ("created", models.DateTimeField(auto_now_add=True, null=True)), ("last_updated", models.DateTimeField(auto_now=True, null=True)),
            ("custom_field_data", models.JSONField(blank=True, default=dict, encoder=netbox.models.features.CustomFieldJSONEncoder)),
            ("file", models.FileField(upload_to=netbox_documentation.models.attachment_upload_path)),
            ("original_name", models.CharField(max_length=255)), ("content_type", models.CharField(blank=True, max_length=100)),
            ("size", models.PositiveBigIntegerField(default=0)),
            ("document", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attachments", to="netbox_documentation.document")),
            ("tags", models.ManyToManyField(blank=True, related_name="netbox_documentation_documentattachment_items", to="extras.tag")),
        ], options={"ordering": ("original_name",)}),
        migrations.AddConstraint(model_name="documentassignment", constraint=models.UniqueConstraint(fields=("document", "assigned_object_type", "assigned_object_id"), name="netbox_documentation_documentassignment_unique_assignment")),
    ]

