from django.db import migrations, models
import django.db.models.deletion


def validate_archive_integrity(apps, schema_editor):
    Competitor = apps.get_model('competitions', 'Competitor')
    CompetitionResult = apps.get_model('competitions', 'CompetitionResult')
    ModuleResult = apps.get_model('competitions', 'ModuleResult')

    db_alias = schema_editor.connection.alias

    null_competitors = Competitor.objects.using(db_alias).filter(competition_project__isnull=True).count()
    if null_competitors:
        raise RuntimeError(f'发现 {null_competitors} 条 Competitor 记录未绑定 competition_project，无法收紧为非空字段。')

    duplicate_results = {}
    for result in CompetitionResult.objects.using(db_alias).values_list('competitor_id'):
        competitor_id = result[0]
        duplicate_results[competitor_id] = duplicate_results.get(competitor_id, 0) + 1
    duplicates = {competitor_id: count for competitor_id, count in duplicate_results.items() if count > 1}
    if duplicates:
        sample = list(duplicates.items())[:10]
        raise RuntimeError(f'发现重复 CompetitionResult，示例: {sample}。请先清理后再迁移。')

    invalid_module_result_ids = []
    module_results = ModuleResult.objects.using(db_alias).select_related(
        'competition_result__competitor',
        'competition_module',
    )
    for module_result in module_results.iterator():
        competitor_project_id = module_result.competition_result.competitor.competition_project_id
        competition_module_project_id = module_result.competition_module.competition_project_id
        if competitor_project_id != competition_module_project_id:
            invalid_module_result_ids.append(module_result.pk)
            if len(invalid_module_result_ids) >= 10:
                break
    if invalid_module_result_ids:
        raise RuntimeError(
            f'发现跨具体赛项的 ModuleResult 记录，示例 ID: {invalid_module_result_ids}。请先清理后再迁移。'
        )


class Migration(migrations.Migration):

    dependencies = [
        ('competitions', '0014_competitionmodule_mapping'),
    ]

    operations = [
        migrations.RunPython(validate_archive_integrity, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='competitionproject',
            name='competition',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='competition_projects', to='competitions.competition', verbose_name='所属赛事'),
        ),
        migrations.AlterField(
            model_name='competitionproject',
            name='project',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='competition_projects', to='competitions.project', verbose_name='竞赛项目'),
        ),
        migrations.AlterField(
            model_name='competitionmodule',
            name='competition_project',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='competition_modules', to='competitions.competitionproject', verbose_name='所属具体赛项'),
        ),
        migrations.AlterField(
            model_name='competitor',
            name='competition_project',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='competitors', to='competitions.competitionproject', verbose_name='参赛项目'),
        ),
        migrations.AlterField(
            model_name='expert',
            name='competition_project',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='experts', to='competitions.competitionproject', verbose_name='所属赛项'),
        ),
        migrations.AlterField(
            model_name='skillposition',
            name='competition_project',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='skill_positions', to='competitions.competitionproject', verbose_name='所属赛项'),
        ),
        migrations.AlterField(
            model_name='competitionresult',
            name='competitor',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='results', to='competitions.competitor', verbose_name='选手'),
        ),
        migrations.AlterField(
            model_name='moduleresult',
            name='competition_module',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='competitions.competitionmodule', verbose_name='具体模块'),
        ),
        migrations.AlterField(
            model_name='moduleresult',
            name='competition_result',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='module_results', to='competitions.competitionresult', verbose_name='所属总成绩'),
        ),
        migrations.AddConstraint(
            model_name='competitionresult',
            constraint=models.UniqueConstraint(fields=('competitor',), name='unique_competition_result_per_competitor'),
        ),
    ]