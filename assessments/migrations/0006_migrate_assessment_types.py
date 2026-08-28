from django.db import migrations


TYPE_DEFAULTS = (
    ("competition", "正式竞赛", 10),
    ("selection", "选拔赛", 20),
    ("exchange", "交流赛", 30),
    ("mock", "模拟赛", 40),
    ("training_assessment", "训练考核", 50),
    ("training_test", "训练测试", 60),
    ("other", "其他", 70),
)


def forwards(apps, schema_editor):
    Assessment = apps.get_model("assessments", "Assessment")
    AssessmentType = apps.get_model("assessments", "AssessmentType")
    database = schema_editor.connection.alias

    type_by_code = {}
    for code, name, order in TYPE_DEFAULTS:
        obj, _created = AssessmentType.objects.using(database).get_or_create(
            code=code,
            defaults={"name": name, "order": order, "is_active": True},
        )
        type_by_code[code] = obj

    values = Assessment.objects.using(database).values_list("assessment_type", flat=True).distinct()
    for raw_value in values:
        code = raw_value or ""
        config = type_by_code.get(code)
        if config is None:
            config, _created = AssessmentType.objects.using(database).get_or_create(
                code=code,
                defaults={
                    "name": code or "历史空值",
                    "description": "从历史竞赛与考核类型保留。",
                    "order": 9000,
                    "is_active": False,
                },
            )
            type_by_code[code] = config
        Assessment.objects.using(database).filter(assessment_type=raw_value).update(
            assessment_type_config_id=config.pk
        )

    if Assessment.objects.using(database).filter(assessment_type_config__isnull=True).exists():
        raise RuntimeError("竞赛与考核类型数据迁移未能映射全部历史记录。")


def backwards(apps, schema_editor):
    Assessment = apps.get_model("assessments", "Assessment")
    database = schema_editor.connection.alias
    for assessment in Assessment.objects.using(database).select_related("assessment_type_config").iterator():
        assessment.assessment_type = assessment.assessment_type_config.code
        assessment.save(update_fields=["assessment_type"])


class Migration(migrations.Migration):
    dependencies = [
        ("assessments", "0005_create_assessment_type"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
