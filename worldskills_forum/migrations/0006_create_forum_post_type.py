from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("worldskills_forum", "0005_alter_forumtopic_options")]

    operations = [
        migrations.AlterField(
            model_name="forumpost",
            name="post_type",
            field=models.CharField(
                choices=[
                    ("discussion", "专家讨论"),
                    ("official_reply", "官方回复"),
                    ("official_notice", "官方通知"),
                    ("rule_change", "规则变更"),
                    ("important_reminder", "重要提醒"),
                ],
                db_index=True,
                max_length=30,
                null=True,
                verbose_name="信息类型",
            ),
        ),
        migrations.CreateModel(
            name="ForumPostType",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=30, unique=True, verbose_name="类型代码")),
                ("name", models.CharField(max_length=120, verbose_name="类型名称")),
                ("description", models.TextField(blank=True, verbose_name="说明")),
                ("order", models.PositiveIntegerField(default=0, verbose_name="排序")),
                ("is_active", models.BooleanField(default=True, verbose_name="启用")),
                ("is_official", models.BooleanField(default=False, verbose_name="官方信息")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
            ],
            options={
                "verbose_name": "论坛信息类型",
                "verbose_name_plural": "论坛信息类型",
                "ordering": ["order", "code"],
            },
        ),
        migrations.AddField(
            model_name="forumpost",
            name="post_type_config",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="worldskills_forum.forumposttype",
                verbose_name="信息类型配置",
            ),
        ),
    ]
