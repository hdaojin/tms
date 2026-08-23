from django.db import migrations, models
import django.db.models.deletion


def clear_legacy_tree_nodes(apps, schema_editor):
    """旧的分类/主题树不做转换；只保留跨版本稳定的 Skill 本体。"""

    SkillTreeNode = apps.get_model("standards", "SkillTreeNode")
    SkillTreeNode.objects.using(schema_editor.connection.alias).all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("standards", "0003_skillterm_alter_skill_options_and_more"),
    ]

    operations = [
        migrations.RunPython(clear_legacy_tree_nodes, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="skilltreenode",
            name="uniq_skilltreenode_version_code",
        ),
        migrations.RemoveConstraint(
            model_name="skilltreenode",
            name="uniq_skilltreenode_version_skill",
        ),
        migrations.RemoveField(model_name="skilltreenode", name="code"),
        migrations.RemoveField(model_name="skilltreenode", name="description"),
        migrations.RemoveField(model_name="skilltreenode", name="is_active"),
        migrations.RemoveField(model_name="skilltreenode", name="name"),
        migrations.RemoveField(model_name="skilltreenode", name="node_type"),
        migrations.AlterField(
            model_name="skilltreenode",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="children",
                to="standards.skilltreenode",
                verbose_name="父技能",
            ),
        ),
        migrations.AlterField(
            model_name="skilltreenode",
            name="skill",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="tree_nodes",
                to="standards.skill",
                verbose_name="技能",
            ),
        ),
        migrations.AlterModelOptions(
            name="skilltreenode",
            options={
                "ordering": ["tree_version", "technical_domain__order", "order", "pk"],
                "verbose_name": "技能树节点",
                "verbose_name_plural": "技能树节点",
            },
        ),
        migrations.AddConstraint(
            model_name="skilltreenode",
            constraint=models.UniqueConstraint(
                fields=("tree_version", "skill"),
                name="uniq_skilltreenode_version_skill",
            ),
        ),
    ]
