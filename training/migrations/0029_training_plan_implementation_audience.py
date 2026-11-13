from django.db import migrations, models
from django.db.models.functions import Coalesce, NullIf


def copy_cycle_audience(apps, schema_editor):
    cycle = apps.get_model("training", "TrainingCycle")
    plan = apps.get_model("training", "TrainingPlan")
    database = schema_editor.connection.alias
    audience = cycle.objects.using(database).filter(pk=models.OuterRef("training_cycle_id")).values("log_class")
    plan.objects.using(database).update(
        implementation_audience=Coalesce(NullIf(models.Subquery(audience), models.Value("")), models.Value("精英班"))
    )


class Migration(migrations.Migration):
    dependencies = [("training", "0028_rename_task_overview")]

    operations = [
        migrations.AddField(
            model_name="trainingplan",
            name="implementation_audience",
            field=models.CharField(default="精英班", max_length=150, verbose_name="实施对象"),
        ),
        migrations.RunPython(copy_cycle_audience, migrations.RunPython.noop),
    ]
