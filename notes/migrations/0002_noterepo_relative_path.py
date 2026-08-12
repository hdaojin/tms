from django.db import migrations, models


def copy_slug_to_relative_path(apps, schema_editor):
    NoteRepo = apps.get_model("notes", "NoteRepo")
    for repo in NoteRepo.objects.all().iterator():
        repo.relative_path = repo.slug
        repo.save(update_fields=["relative_path"])


class Migration(migrations.Migration):
    dependencies = [
        ("notes", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="noterepo",
            name="relative_path",
            field=models.CharField(blank=True, default="", max_length=500, verbose_name="相对路径"),
            preserve_default=False,
        ),
        migrations.RunPython(copy_slug_to_relative_path, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="noterepo",
            name="relative_path",
            field=models.CharField(
                help_text="相对于 NOTES_ROOT 的目录路径，例如 teaching-notes-debian/debian-basics",
                max_length=500,
                unique=True,
                verbose_name="相对路径",
            ),
        ),
        migrations.AlterField(
            model_name="noterepo",
            name="slug",
            field=models.SlugField(
                help_text="用于 URL、权限和缓存，例如 teaching-notes-Debian；不能包含斜杠",
                max_length=100,
                unique=True,
                verbose_name="访问标识",
            ),
        ),
    ]
