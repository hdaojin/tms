from django.db import migrations


def split_project_skill_tree_versions(apps, schema_editor):
    SkillTreeVersion = apps.get_model("standards", "SkillTreeVersion")
    SkillTreeNode = apps.get_model("standards", "SkillTreeNode")
    TechnicalDomain = apps.get_model("standards", "TechnicalDomain")
    TrainingCycle = apps.get_model("training", "TrainingCycle")
    CycleTreeLink = apps.get_model("training", "TrainingCycleSkillTreeVersion")

    # 固定迁移开始时的旧版本集合，避免循环内创建的新领域版本再次被迭代。
    for old_tree in list(SkillTreeVersion.objects.order_by("pk")):
        domains = list(
            TechnicalDomain.objects.filter(skill_project_id=old_tree.skill_project_id).order_by("order", "pk")
        )
        if not domains:
            raise RuntimeError(
                f"技能树版本 {old_tree.pk} 所属技能项目没有技术领域；请先修复数据后再迁移。"
            )

        domain_versions = {}
        for index, domain in enumerate(domains):
            if index == 0:
                tree = old_tree
                tree.technical_domain_id = domain.pk
                tree.save(update_fields=["technical_domain"])
            else:
                tree = SkillTreeVersion.objects.create(
                    skill_project_id=old_tree.skill_project_id,
                    technical_domain_id=domain.pk,
                    version=old_tree.version,
                    name=old_tree.name,
                    description=old_tree.description,
                    is_current=old_tree.is_current,
                    created_by_id=old_tree.created_by_id,
                )
                SkillTreeVersion.objects.filter(pk=tree.pk).update(
                    created_at=old_tree.created_at,
                    updated_at=old_tree.updated_at,
                )
            domain_versions[domain.pk] = tree

        for domain_id, tree in domain_versions.items():
            SkillTreeNode.objects.filter(
                tree_version_id=old_tree.pk,
                technical_domain_id=domain_id,
            ).update(tree_version_id=tree.pk)

        cycle_ids = TrainingCycle.objects.filter(skill_tree_version_id=old_tree.pk).values_list("pk", flat=True)
        CycleTreeLink.objects.bulk_create(
            [
                CycleTreeLink(
                    training_cycle_id=cycle_id,
                    technical_domain_id=domain_id,
                    skill_tree_version_id=tree.pk,
                )
                for cycle_id in cycle_ids
                for domain_id, tree in domain_versions.items()
            ]
        )


class Migration(migrations.Migration):
    dependencies = [
        ("standards", "0005_prepare_domain_skill_tree_versions"),
        ("training", "0002_prepare_cycle_domain_tree_versions"),
    ]

    operations = [
        migrations.RunPython(split_project_skill_tree_versions, migrations.RunPython.noop),
    ]
