from django.db import migrations


CATEGORIES = [
    ("官方发布", "official"),
    ("技术讨论", "technical"),
    ("竞赛规则", "rules"),
    ("评分", "marking"),
    ("竞赛环境", "environment"),
    ("基础设施", "infrastructure"),
    ("其他", "other"),
]


def seed_categories(apps, schema_editor):
    category_model = apps.get_model("worldskills_forum", "ForumCategory")
    for sort_order, (name, slug) in enumerate(CATEGORIES):
        category_model.objects.get_or_create(slug=slug, defaults={"name": name, "sort_order": sort_order})


def remove_seeded_categories(apps, schema_editor):
    category_model = apps.get_model("worldskills_forum", "ForumCategory")
    for name, slug in CATEGORIES:
        category_model.objects.filter(slug=slug, name=name, topics__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [("worldskills_forum", "0001_initial")]
    operations = [migrations.RunPython(seed_categories, remove_seeded_categories)]
