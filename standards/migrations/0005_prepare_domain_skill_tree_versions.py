from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("standards", "0004_simplify_skill_tree_nodes"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="skilltreeversion",
            name="uniq_skilltreeversion_project_version",
        ),
        migrations.RemoveConstraint(
            model_name="skilltreeversion",
            name="uniq_current_skilltreeversion_per_project",
        ),
        migrations.AddField(
            model_name="skilltreeversion",
            name="technical_domain",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="skill_tree_versions",
                to="standards.technicaldomain",
                verbose_name="技术领域",
            ),
        ),
        migrations.AddField(
            model_name="skilltreeversion",
            name="based_on",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="derived_versions",
                to="standards.skilltreeversion",
                verbose_name="基于版本",
            ),
        ),
    ]
