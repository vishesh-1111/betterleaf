from django.db import migrations
from django.db import models


class Migration(migrations.Migration):

    dependencies = [
        ("resumes", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="resume",
            name="structured_data",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
