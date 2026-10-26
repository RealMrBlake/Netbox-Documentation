import django
from django.conf import settings

# The importer tests load modules without NetBox; gettext still needs configured settings.
if not settings.configured:
    settings.configure(USE_I18N=True, LANGUAGE_CODE="en")
    django.setup()
