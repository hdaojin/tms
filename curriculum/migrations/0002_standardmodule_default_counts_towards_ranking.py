from django.db import migrations, models


def backfill_default_counts_towards_ranking(apps, schema_editor):
    StandardModule = apps.get_model('curriculum', 'StandardModule')
    StandardModule.objects.filter(name__icontains='english').update(
        default_counts_towards_ranking=False,
    )


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ('curriculum', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='standardmodule',
            name='default_counts_towards_ranking',
            field=models.BooleanField(
                default=True,
                help_text='新建考核模块时默认继承此设置。',
                verbose_name='默认计入排名分',
            ),
        ),
        migrations.RunPython(backfill_default_counts_towards_ranking, noop_reverse),
    ]