from django.db import migrations


def remove_unpublished_board_plans(apps, schema_editor):
    board_plan = apps.get_model("training", "TrainingBoardPlan")
    board_plan.objects.using(schema_editor.connection.alias).filter(
        training_plan__published_at__isnull=True,
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("training", "0022_trainingboardplan"),
    ]

    operations = [
        migrations.RunPython(remove_unpublished_board_plans, migrations.RunPython.noop),
    ]
