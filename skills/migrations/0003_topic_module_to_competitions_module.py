import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('competitions', '0012_alter_competitionproject_document'),
        ('skills', '0002_rename_skill_add_difficulty_validators'),
    ]

    operations = [
        migrations.AlterField(
            model_name='topic',
            name='module',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='topics',
                to='competitions.module',
                verbose_name='所属模块',
            ),
        ),
        migrations.DeleteModel(
            name='Module',
        ),
    ]