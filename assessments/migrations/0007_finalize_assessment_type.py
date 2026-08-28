from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("assessments", "0006_migrate_assessment_types"),
    ]

    operations = [
        migrations.RemoveField(model_name="assessment", name="assessment_type"),
        migrations.RenameField(
            model_name="assessment",
            old_name="assessment_type_config",
            new_name="assessment_type",
        ),
        migrations.AlterField(
            model_name="assessment",
            name="assessment_type",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="assessments",
                to="assessments.assessmenttype",
                verbose_name="类型",
            ),
        ),
    ]
