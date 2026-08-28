from django.db import migrations


CATEGORY_DEFAULTS = (
    ("bug", "Bug反馈", False, 10),
    ("feature", "功能需求", False, 20),
    ("suggestion", "意见建议", False, 30),
    ("complaint", "我要投诉", True, 40),
)


def forwards(apps, schema_editor):
    Feedback = apps.get_model("feedback", "Feedback")
    FeedbackCategory = apps.get_model("feedback", "FeedbackCategory")
    database = schema_editor.connection.alias
    category_by_code = {}

    for code, name, default_private, order in CATEGORY_DEFAULTS:
        obj, _created = FeedbackCategory.objects.using(database).get_or_create(
            code=code,
            defaults={
                "name": name,
                "default_private": default_private,
                "order": order,
                "is_active": True,
            },
        )
        category_by_code[code] = obj

    values = Feedback.objects.using(database).values_list("category", flat=True).distinct()
    for raw_value in values:
        code = raw_value or ""
        category = category_by_code.get(code)
        if category is None:
            category, _created = FeedbackCategory.objects.using(database).get_or_create(
                code=code,
                defaults={
                    "name": code or "历史空值",
                    "description": "从历史反馈分类保留。",
                    "order": 9000,
                    "is_active": False,
                },
            )
            category_by_code[code] = category
        Feedback.objects.using(database).filter(category=raw_value).update(category_config_id=category.pk)

    if Feedback.objects.using(database).filter(category_config__isnull=True).exists():
        raise RuntimeError("反馈分类数据迁移未能映射全部历史记录。")


def backwards(apps, schema_editor):
    Feedback = apps.get_model("feedback", "Feedback")
    database = schema_editor.connection.alias
    for feedback in Feedback.objects.using(database).select_related("category_config").iterator():
        feedback.category = feedback.category_config.code
        feedback.save(update_fields=["category"])


class Migration(migrations.Migration):
    dependencies = [("feedback", "0003_create_feedback_category")]
    operations = [migrations.RunPython(forwards, backwards)]
