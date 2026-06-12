from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('event_countdown', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='countdownevent',
            name='project_english_name',
            field=models.CharField(blank=True, max_length=160, verbose_name='项目英文名称'),
        ),
    ]
