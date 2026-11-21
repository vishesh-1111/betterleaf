import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('resumes', '0006_compilation_pdf_base64'),
    ]

    operations = [
        migrations.CreateModel(
            name='TailorRequest',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('job_text', models.TextField()),
                ('status', models.CharField(choices=[('analysing', 'Analysing'), ('ready', 'Ready'), ('failed', 'Failed')], default='analysing', max_length=20)),
                ('result', models.JSONField(blank=True, default=dict)),
                ('counted', models.BooleanField(default=False)),
                ('error', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('master_resume', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tailor_requests', to='resumes.masterresume')),
                ('resume', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tailor_request', to='resumes.resume')),
                ('workspace', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tailor_requests', to='resumes.workspace')),
            ],
        ),
    ]
