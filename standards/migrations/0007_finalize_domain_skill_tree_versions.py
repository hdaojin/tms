from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("standards", "0006_split_project_skill_tree_versions"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="skilltreeversion",
            options={
                "ordering": ["technical_domain", "-is_current", "-created_at", "version"],
                "verbose_name": "标准技能树版本",
                "verbose_name_plural": "标准技能树版本",
            },
        ),
        migrations.AlterModelOptions(
            name="skilltreenode",
            options={
                "ordering": ["tree_version", "order", "pk"],
                "verbose_name": "技能树节点",
                "verbose_name_plural": "技能树节点",
            },
        ),
        migrations.AlterField(
            model_name="skilltreeversion",
            name="technical_domain",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="skill_tree_versions",
                to="standards.technicaldomain",
                verbose_name="技术领域",
            ),
        ),
        migrations.RemoveField(
            model_name="skilltreenode",
            name="technical_domain",
        ),
        migrations.RemoveField(
            model_name="skilltreeversion",
            name="skill_project",
        ),
        migrations.AddConstraint(
            model_name="skilltreeversion",
            constraint=models.UniqueConstraint(
                fields=("technical_domain", "version"),
                name="uniq_skilltreeversion_domain_version",
            ),
        ),
        migrations.AddConstraint(
            model_name="skilltreeversion",
            constraint=models.UniqueConstraint(
                condition=Q(is_current=True),
                fields=("technical_domain",),
                name="uniq_current_skilltreeversion_per_domain",
            ),
        ),
        migrations.AlterField(
            model_name="skillwsosmap",
            name="wsos_section",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="skill_mappings",
                to="standards.wsossection",
                verbose_name="WSOS 章节",
            ),
        ),
    ]
