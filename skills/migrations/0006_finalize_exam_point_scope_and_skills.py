import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('skills', '0005_migrate_exam_points_to_competition_project'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='exampoint',
            name='unique_exam_point',
        ),
        migrations.AlterModelOptions(
            name='exampoint',
            options={
                'verbose_name': '考点',
                'verbose_name_plural': '考点',
                'ordering': ['competition_project', 'name'],
            },
        ),
        migrations.AlterField(
            model_name='exampoint',
            name='competition_project',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='exam_points', to='competitions.competitionproject', verbose_name='所属具体赛项'),
        ),
        migrations.RemoveField(
            model_name='exampoint',
            name='competition',
        ),
        migrations.RemoveField(
            model_name='exampoint',
            name='skills',
        ),
        migrations.AddField(
            model_name='exampoint',
            name='skills',
            field=models.ManyToManyField(related_name='exam_points', through='skills.ExamPointSkill', to='skills.skill', verbose_name='技能点'),
        ),
        migrations.AddConstraint(
            model_name='exampoint',
            constraint=models.UniqueConstraint(fields=('competition_project', 'name'), name='unique_exam_point_within_project'),
        ),
    ]