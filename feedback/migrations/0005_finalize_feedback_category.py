from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("feedback", "0004_migrate_feedback_categories")]

    operations = [
        migrations.RemoveField(model_name="feedback", name="category"),
        migrations.RenameField(model_name="feedback", old_name="category_config", new_name="category"),
        migrations.AlterField(
            model_name="feedback",
            name="category",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="feedbacks",
                to="feedback.feedbackcategory",
                verbose_name="反馈类型",
            ),
        ),
        migrations.AddIndex(
            model_name="feedback",
            index=models.Index(fields=["category", "status"], name="feedback_fe_categor_ca3927_idx"),
        ),
    ]
