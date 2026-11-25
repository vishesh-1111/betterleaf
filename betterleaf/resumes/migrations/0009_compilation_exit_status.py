from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("resumes", "0008_tailorrequest_followups"),
    ]

    operations = [
        migrations.AddField(
            model_name="compilation",
            name="exit_status",
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
