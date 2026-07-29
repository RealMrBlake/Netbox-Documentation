from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_documentation", "0004_excelimportpreview"),
        ("tenancy", "0001_squashed_0012"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="tenant_group",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="documentation_documents", to="tenancy.tenantgroup",
            ),
        ),
        migrations.AddField(
            model_name="document",
            name="tenant",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="documentation_documents", to="tenancy.tenant",
            ),
        ),
        migrations.AddField(
            model_name="documentcategory",
            name="tenant_group",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="documentation_categories", to="tenancy.tenantgroup",
            ),
        ),
        migrations.AddField(
            model_name="documentcategory",
            name="tenant",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="documentation_categories", to="tenancy.tenant",
            ),
        ),
    ]
