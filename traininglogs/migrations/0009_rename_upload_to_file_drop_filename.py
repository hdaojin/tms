from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('traininglogs', '0008_alter_traininglog_module_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='traininglog',
            old_name='upload',
            new_name='file',
        ),
        migrations.RemoveField(
            model_name='traininglog',
            name='filename',
        ),
    ]
