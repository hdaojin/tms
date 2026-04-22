from decimal import Decimal

from django.db import migrations


def migrate_exam_points(apps, schema_editor):
    CompetitionProject = apps.get_model('competitions', 'CompetitionProject')
    ExamPoint = apps.get_model('skills', 'ExamPoint')
    ExamPointSkill = apps.get_model('skills', 'ExamPointSkill')

    db_alias = schema_editor.connection.alias
    exam_points = ExamPoint.objects.using(db_alias).prefetch_related('skills__topic__module__project')

    for exam_point in exam_points:
        skills = list(exam_point.skills.all())
        if not skills:
            raise RuntimeError(
                f'考点 ID={exam_point.pk} 名称={exam_point.name} 未关联任何技能点，无法推断所属具体赛项。'
            )

        project_ids = {skill.topic.module.project_id for skill in skills}
        if len(project_ids) != 1:
            raise RuntimeError(
                f'考点 ID={exam_point.pk} 名称={exam_point.name} 关联了多个项目的技能点，无法唯一推断具体赛项。'
            )

        project_id = project_ids.pop()
        competition_projects = CompetitionProject.objects.using(db_alias).filter(
            competition_id=exam_point.competition_id,
            project_id=project_id,
        )
        count = competition_projects.count()
        if count != 1:
            raise RuntimeError(
                f'考点 ID={exam_point.pk} 名称={exam_point.name} 在赛事 {exam_point.competition_id} 与项目 {project_id} 下匹配到 {count} 条具体赛项记录，无法继续迁移。'
            )

        competition_project = competition_projects.get()
        ExamPoint.objects.using(db_alias).filter(pk=exam_point.pk).update(
            competition_project_id=competition_project.pk,
        )

        is_primary = len(skills) == 1
        for skill in skills:
            ExamPointSkill.objects.using(db_alias).get_or_create(
                exam_point_id=exam_point.pk,
                skill_id=skill.pk,
                defaults={
                    'is_primary': is_primary,
                    'weight': Decimal('1.00'),
                    'note': '',
                },
            )


class Migration(migrations.Migration):

    dependencies = [
        ('skills', '0004_add_exam_point_scope_and_tags'),
    ]

    operations = [
        migrations.RunPython(migrate_exam_points, migrations.RunPython.noop),
    ]