from django.db import migrations


POST_TYPE_DEFAULTS = (
    ("discussion", "专家讨论", False, 10),
    ("official_reply", "官方回复", True, 20),
    ("official_notice", "官方通知", True, 30),
    ("rule_change", "规则变更", True, 40),
    ("important_reminder", "重要提醒", False, 50),
)


def forwards(apps, schema_editor):
    ForumPost = apps.get_model("worldskills_forum", "ForumPost")
    ForumPostType = apps.get_model("worldskills_forum", "ForumPostType")
    database = schema_editor.connection.alias
    type_by_code = {}

    for code, name, is_official, order in POST_TYPE_DEFAULTS:
        obj, _created = ForumPostType.objects.using(database).get_or_create(
            code=code,
            defaults={"name": name, "is_official": is_official, "order": order, "is_active": True},
        )
        type_by_code[code] = obj

    values = ForumPost.objects.using(database).values_list("post_type", flat=True).distinct()
    for raw_value in values:
        code = raw_value or ""
        post_type = type_by_code.get(code)
        if post_type is None:
            post_type, _created = ForumPostType.objects.using(database).get_or_create(
                code=code,
                defaults={
                    "name": code or "历史空值",
                    "description": "从历史论坛信息类型保留。",
                    "order": 9000,
                    "is_active": False,
                },
            )
            type_by_code[code] = post_type
        ForumPost.objects.using(database).filter(post_type=raw_value).update(post_type_config_id=post_type.pk)

    if ForumPost.objects.using(database).filter(post_type_config__isnull=True).exists():
        raise RuntimeError("论坛信息类型数据迁移未能映射全部历史记录。")


def backwards(apps, schema_editor):
    ForumPost = apps.get_model("worldskills_forum", "ForumPost")
    database = schema_editor.connection.alias
    for post in ForumPost.objects.using(database).select_related("post_type_config").iterator():
        post.post_type = post.post_type_config.code
        post.save(update_fields=["post_type"])


class Migration(migrations.Migration):
    dependencies = [("worldskills_forum", "0006_create_forum_post_type")]
    operations = [migrations.RunPython(forwards, backwards)]
