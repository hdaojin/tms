from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("feedback", "0002_alter_feedback_category")]

    operations = [
        migrations.AlterField(
            model_name="feedback",
            name="category",
            field=models.CharField(
                choices=[
                    ("bug", "Bug反馈"),
                    ("feature", "功能需求"),
                    ("suggestion", "意见建议"),
                    ("complaint", "我要投诉"),
                ],
                db_index=True,
                max_length=20,
                null=True,
                verbose_name="反馈类型",
            ),
        ),
        migrations.CreateModel(
            name="FeedbackCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=20, unique=True, verbose_name="分类代码")),
                ("name", models.CharField(max_length=120, verbose_name="分类名称")),
                ("description", models.TextField(blank=True, verbose_name="说明")),
                ("order", models.PositiveIntegerField(default=0, verbose_name="排序")),
                ("is_active", models.BooleanField(default=True, verbose_name="启用")),
                ("default_private", models.BooleanField(default=False, verbose_name="默认设为私密")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
            ],
            options={
                "verbose_name": "反馈分类",
                "verbose_name_plural": "反馈分类",
                "ordering": ["order", "code"],
            },
        ),
        migrations.AddField(
            model_name="feedback",
            name="category_config",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="feedback.feedbackcategory",
                verbose_name="反馈类型配置",
            ),
        ),
        migrations.RemoveIndex(
            model_name="feedback",
            name="feedback_fe_categor_ca3927_idx",
        ),
    ]
