from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("worldskills_forum", "0007_migrate_forum_post_types")]

    operations = [
        migrations.RemoveField(model_name="forumpost", name="post_type"),
        migrations.RenameField(model_name="forumpost", old_name="post_type_config", new_name="post_type"),
        migrations.AlterField(
            model_name="forumpost",
            name="post_type",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="posts",
                to="worldskills_forum.forumposttype",
                verbose_name="信息类型",
            ),
        ),
    ]
