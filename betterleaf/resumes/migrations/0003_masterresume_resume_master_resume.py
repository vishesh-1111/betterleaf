from django.db import migrations
from django.db import models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("resumes", "0002_resume_structured_data"),
    ]

    operations = [
        migrations.CreateModel(
            name="MasterResume",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=200)),
                ("structured_data", models.JSONField(blank=True, default=dict)),
                ("parsed_from_file", models.CharField(blank=True, max_length=255, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("workspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="master_resumes", to="resumes.workspace")),
            ],
        ),
        migrations.AddField(
            model_name="resume",
            name="master_resume",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="resumes", to="resumes.masterresume"),
        ),
    ]
