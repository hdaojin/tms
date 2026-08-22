from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("standards", "0007_finalize_domain_skill_tree_versions"),
        ("training", "0002_prepare_cycle_domain_tree_versions"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="trainingcycle",
            name="skill_tree_version",
        ),
        migrations.AddConstraint(
            model_name="trainingcycleskilltreeversion",
            constraint=models.UniqueConstraint(
                fields=("training_cycle", "technical_domain"),
                name="uniq_trainingcycle_domain_tree",
            ),
        ),
        migrations.AddConstraint(
            model_name="trainingcycleskilltreeversion",
            constraint=models.UniqueConstraint(
                fields=("training_cycle", "skill_tree_version"),
                name="uniq_trainingcycle_tree_version",
            ),
        ),
    ]
