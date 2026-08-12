import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


MODULES = [
    ("综合", "general"),
    ("模块 A", "module-a"),
    ("模块 B", "module-b"),
    ("模块 C", "module-c"),
    ("模块 D", "module-d"),
    ("其他", "other"),
]

OLD_TO_SLUG = {
    "general": "general",
    "A": "module-a",
    "B": "module-b",
    "C": "module-c",
    "D": "module-d",
    "other": "other",
}
SLUG_TO_OLD = {slug: old for old, slug in OLD_TO_SLUG.items()}


def create_modules_and_migrate_topics(apps, schema_editor):
    module_model = apps.get_model("worldskills_forum", "ForumModule")
    topic_model = apps.get_model("worldskills_forum", "ForumTopic")
    modules = {}
    for sort_order, (name, slug) in enumerate(MODULES):
        module, _created = module_model.objects.get_or_create(
            slug=slug,
            defaults={"name": name, "sort_order": sort_order},
        )
        modules[slug] = module
    for topic in topic_model.objects.all().iterator():
        topic.module_config = modules[OLD_TO_SLUG.get(topic.module, "other")]
        topic.save(update_fields=["module_config"])


def restore_module_codes(apps, schema_editor):
    topic_model = apps.get_model("worldskills_forum", "ForumTopic")
    for topic in topic_model.objects.select_related("module_config").all().iterator():
        topic.module = SLUG_TO_OLD.get(topic.module_config.slug, "other")
        topic.save(update_fields=["module"])


class Migration(migrations.Migration):
    dependencies = [("worldskills_forum", "0002_seed_default_categories")]

    operations = [
        migrations.CreateModel(
            name="ForumModule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, unique=True, verbose_name="名称")),
                ("slug", models.SlugField(allow_unicode=True, blank=True, max_length=120, unique=True, verbose_name="标识")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                ("sort_order", models.PositiveIntegerField(default=0, verbose_name="排序")),
                ("is_active", models.BooleanField(default=True, verbose_name="启用")),
            ],
            options={
                "verbose_name": "论坛模块",
                "verbose_name_plural": "论坛模块",
                "ordering": ["sort_order", "name", "pk"],
            },
        ),
        migrations.AddField(
            model_name="forumtopic",
            name="module_config",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="topics_pending_migration",
                to="worldskills_forum.forummodule",
                verbose_name="模块",
            ),
        ),
        migrations.RunPython(create_modules_and_migrate_topics, restore_module_codes),
        migrations.RemoveField(model_name="forumtopic", name="module"),
        migrations.RenameField(model_name="forumtopic", old_name="module_config", new_name="module"),
        migrations.AlterField(
            model_name="forumtopic",
            name="module",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="topics",
                to="worldskills_forum.forummodule",
                verbose_name="模块",
            ),
        ),
        migrations.AlterField(
            model_name="forumpost",
            name="posted_at",
            field=models.DateTimeField(default=django.utils.timezone.now, verbose_name="论坛原始发布时间"),
        ),
        migrations.AlterField(
            model_name="forumpost",
            name="source_post_id",
            field=models.CharField(blank=True, db_index=True, max_length=120, verbose_name="论坛帖子 ID"),
        ),
        migrations.AlterField(
            model_name="forumpost",
            name="source_role",
            field=models.CharField(
                choices=[
                    ("worldskills_official", "世界技能组织官方"),
                    ("chief_expert", "首席专家"),
                    ("deputy_chief_expert", "副首席专家"),
                    ("expert", "专家"),
                    ("organizer", "竞赛组织方"),
                    ("other", "其他"),
                ],
                max_length=40,
                verbose_name="来源身份",
            ),
        ),
        migrations.AlterField(
            model_name="forumtopic",
            name="original_title",
            field=models.CharField(max_length=500, verbose_name="论坛原始标题"),
        ),
        migrations.AlterField(
            model_name="forumtopic",
            name="source_topic_id",
            field=models.CharField(blank=True, max_length=120, verbose_name="论坛主题 ID"),
        ),
        migrations.AlterField(
            model_name="forumtopic",
            name="translated_title",
            field=models.CharField(max_length=300, verbose_name="主题中文标题"),
        ),
    ]
