# Generated manually for competitions main-data refactor.

from django.db import migrations, models
import django.db.models.deletion


def forwards_move_people(apps, schema_editor):
    CompetitionPerson = apps.get_model('competitions', 'CompetitionPerson')
    Expert = apps.get_model('competitions', 'Expert')
    SkillPosition = apps.get_model('competitions', 'SkillPosition')

    person_cache = {}

    def get_person(name, organization, user_id):
        key = (name or '', organization or '', user_id)
        person = person_cache.get(key)
        if person is None:
            person, _created = CompetitionPerson.objects.get_or_create(
                name=name or '',
                organization=organization or '',
                user_id=user_id,
            )
            person_cache[key] = person
        return person

    for expert in Expert.objects.all().iterator():
        person = get_person(expert.name, expert.organization, expert.user_id)
        Expert.objects.filter(pk=expert.pk).update(person_id=person.pk)

    for position in SkillPosition.objects.all().iterator():
        person = get_person(position.name, position.organization, position.user_id)
        SkillPosition.objects.filter(pk=position.pk).update(person_id=person.pk)

    seen_expert_pairs = set()
    for expert in Expert.objects.order_by('pk').all().iterator():
        key = (expert.competition_project_id, expert.person_id)
        if key in seen_expert_pairs:
            Expert.objects.filter(pk=expert.pk).delete()
            continue
        seen_expert_pairs.add(key)

    seen_position_pairs = set()
    for position in SkillPosition.objects.order_by('pk').all().iterator():
        key = (position.competition_project_id, position.person_id, position.position_name)
        if key in seen_position_pairs:
            SkillPosition.objects.filter(pk=position.pk).delete()
            continue
        seen_position_pairs.add(key)


class Migration(migrations.Migration):

    dependencies = [
        ('competitions', '0019_alter_competitionresult_options_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='CompetitionPerson',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='姓名')),
                ('organization', models.CharField(blank=True, max_length=100, verbose_name='所属单位')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='最后更新时间')),
                ('user', models.ForeignKey(blank=True, help_text='如果是校内人员，可关联用户账号；外部人员可留空。', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='competition_people', to='competitions.competitoruser', verbose_name='关联用户')),
            ],
            options={
                'verbose_name': '竞赛人员',
                'verbose_name_plural': '竞赛人员',
                'ordering': ['name', 'organization', 'pk'],
            },
        ),
        migrations.AddField(
            model_name='expert',
            name='person',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='expert_assignments', to='competitions.competitionperson', verbose_name='专家人员'),
        ),
        migrations.AddField(
            model_name='skillposition',
            name='person',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='skill_position_assignments', to='competitions.competitionperson', verbose_name='岗位人员'),
        ),
        migrations.RunPython(forwards_move_people, migrations.RunPython.noop),
        migrations.AlterModelOptions(
            name='project',
            options={'ordering': ['name', 'code'], 'verbose_name': '竞赛项目', 'verbose_name_plural': '竞赛项目'},
        ),
        migrations.AlterModelOptions(
            name='expert',
            options={'ordering': ['competition_project', 'person__name', 'pk'], 'verbose_name': '参赛专家(裁判)', 'verbose_name_plural': '参赛专家(裁判)'},
        ),
        migrations.AlterModelOptions(
            name='skillposition',
            options={'ordering': ['competition_project', 'position_name', 'person__name', 'pk'], 'verbose_name': '具体赛事技能岗位人员', 'verbose_name_plural': '具体赛事技能岗位人员'},
        ),
        migrations.AlterField(
            model_name='expert',
            name='person',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='expert_assignments', to='competitions.competitionperson', verbose_name='专家人员'),
        ),
        migrations.AlterField(
            model_name='skillposition',
            name='person',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='skill_position_assignments', to='competitions.competitionperson', verbose_name='岗位人员'),
        ),
        migrations.AlterField(
            model_name='project',
            name='name',
            field=models.CharField(max_length=100, verbose_name='项目名称'),
        ),
        migrations.RemoveField(
            model_name='project',
            name='competition_type',
        ),
        migrations.RemoveField(
            model_name='expert',
            name='name',
        ),
        migrations.RemoveField(
            model_name='expert',
            name='organization',
        ),
        migrations.RemoveField(
            model_name='expert',
            name='user',
        ),
        migrations.RemoveField(
            model_name='skillposition',
            name='name',
        ),
        migrations.RemoveField(
            model_name='skillposition',
            name='organization',
        ),
        migrations.RemoveField(
            model_name='skillposition',
            name='user',
        ),
        migrations.AddConstraint(
            model_name='expert',
            constraint=models.UniqueConstraint(fields=('competition_project', 'person'), name='unique_expert_per_competition_project'),
        ),
        migrations.AddConstraint(
            model_name='skillposition',
            constraint=models.UniqueConstraint(fields=('competition_project', 'person', 'position_name'), name='unique_skill_position_per_person_in_competition_project'),
        ),
    ]