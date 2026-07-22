from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("netbox_documentation", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="document",
            name="body_format",
            field=models.CharField(
                choices=(("html", "Rich Text"), ("markdown", "Markdown")),
                default="html",
                max_length=10,
            ),
        ),
    ]
