# Generated manually for competitor person reuse.

from django.db import migrations, models
import django.db.models.deletion


def forwards_move_competitors(apps, schema_editor):
    CompetitionPerson = apps.get_model('competitions', 'CompetitionPerson')
    Competitor = apps.get_model('competitions', 'Competitor')

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

    for competitor in Competitor.objects.all().iterator():
        person = get_person(competitor.name, competitor.organization, competitor.user_id)
        Competitor.objects.filter(pk=competitor.pk).update(person_id=person.pk)


class Migration(migrations.Migration):

    dependencies = [
        ('competitions', '0021_alter_competitionresult_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='competitor',
            name='person',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='competitor_assignments', to='competitions.competitionperson', verbose_name='选手人员'),
        ),
        migrations.RunPython(forwards_move_competitors, migrations.RunPython.noop),
        migrations.AlterModelOptions(
            name='competitor',
            options={'ordering': ['competition_project', 'person__name', 'pk'], 'verbose_name': '参赛选手', 'verbose_name_plural': '参赛选手'},
        ),
        migrations.AlterField(
            model_name='competitor',
            name='person',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='competitor_assignments', to='competitions.competitionperson', verbose_name='选手人员'),
        ),
        migrations.RemoveField(
            model_name='competitor',
            name='name',
        ),
        migrations.RemoveField(
            model_name='competitor',
            name='organization',
        ),
        migrations.RemoveField(
            model_name='competitor',
            name='user',
        ),
    ]