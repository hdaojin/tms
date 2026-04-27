# Generated manually for competition project member associations.

import django.db.models.deletion
from django.db import migrations, models


def forwards_backfill_competition_project_members(apps, schema_editor):
    CompetitionProjectMember = apps.get_model('competitions', 'CompetitionProjectMember')
    Competitor = apps.get_model('competitions', 'Competitor')
    Expert = apps.get_model('competitions', 'Expert')

    for competition_project_id, member_id in Competitor.objects.values_list(
        'competition_project_id',
        'member_id',
    ).distinct().iterator():
        CompetitionProjectMember.objects.get_or_create(
            competition_project_id=competition_project_id,
            member_id=member_id,
        )

    for competition_project_id, member_id in Expert.objects.values_list(
        'competition_project_id',
        'member_id',
    ).distinct().iterator():
        CompetitionProjectMember.objects.get_or_create(
            competition_project_id=competition_project_id,
            member_id=member_id,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('competitions', '0025_alter_competitiontype_level'),
    ]

    operations = [
        migrations.CreateModel(
            name='CompetitionProjectMember',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='最后更新时间')),
                ('competition_project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='member_links', to='competitions.competitionproject', verbose_name='具体赛项')),
                ('member', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='competition_project_links', to='competitions.member', verbose_name='代表队')),
            ],
            options={
                'verbose_name': '赛项代表队关联',
                'verbose_name_plural': '赛项代表队关联',
                'ordering': ['competition_project', 'member__level', 'member__name', 'pk'],
            },
        ),
        migrations.AddConstraint(
            model_name='competitionprojectmember',
            constraint=models.UniqueConstraint(fields=('competition_project', 'member'), name='unique_member_per_competition_project'),
        ),
        migrations.RunPython(forwards_backfill_competition_project_members, migrations.RunPython.noop),
    ]