from django.db import migrations, models


def backfill_counts_towards_ranking(apps, schema_editor):
    AssessmentModule = apps.get_model("assessments", "AssessmentModule")
    AssessmentModule.objects.filter(module__name__icontains="english").update(
        counts_towards_ranking=False,
    )


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ("assessments", "0002_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="assessmentmodule",
            name="counts_towards_ranking",
            field=models.BooleanField(
                default=True,
                help_text="关闭后该模块仍计入总分，但不计入排名分。",
                verbose_name="计入排名分",
            ),
        ),
        migrations.RunPython(backfill_counts_towards_ranking, noop_reverse),
    ]