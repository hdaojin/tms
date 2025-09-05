from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('meeting', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='meeting',
            name='filename',
        ),
    ]
