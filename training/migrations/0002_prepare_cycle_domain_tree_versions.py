from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("standards", "0005_prepare_domain_skill_tree_versions"),
        ("training", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="TrainingCycleSkillTreeVersion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "skill_tree_version",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="training_cycle_links",
                        to="standards.skilltreeversion",
                        verbose_name="技能树版本",
                    ),
                ),
                (
                    "technical_domain",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="training_cycle_version_links",
                        to="standards.technicaldomain",
                        verbose_name="技术领域",
                    ),
                ),
                (
                    "training_cycle",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="skill_tree_version_links",
                        to="training.trainingcycle",
                        verbose_name="训练周期",
                    ),
                ),
            ],
            options={
                "verbose_name": "训练周期领域技能树版本",
                "verbose_name_plural": "训练周期领域技能树版本",
                "ordering": ["training_cycle", "technical_domain__order", "technical_domain_id"],
            },
        ),
        migrations.AddField(
            model_name="trainingcycle",
            name="skill_tree_versions",
            field=models.ManyToManyField(
                related_name="training_cycles",
                through="training.TrainingCycleSkillTreeVersion",
                to="standards.skilltreeversion",
                verbose_name="各技术领域技能树版本",
            ),
        ),
    ]
