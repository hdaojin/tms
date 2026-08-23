from datetime import date

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class DomainSkillTreeMigrationTests(TransactionTestCase):
    migrate_from = [
        ("standards", "0004_simplify_skill_tree_nodes"),
        ("training", "0001_initial"),
    ]
    migrate_to = [
        ("standards", "0007_finalize_domain_skill_tree_versions"),
        ("training", "0003_finalize_cycle_domain_tree_versions"),
    ]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps

        SkillProject = old_apps.get_model("standards", "SkillProject")
        TechnicalDomain = old_apps.get_model("standards", "TechnicalDomain")
        Skill = old_apps.get_model("standards", "Skill")
        SkillTreeVersion = old_apps.get_model("standards", "SkillTreeVersion")
        SkillTreeNode = old_apps.get_model("standards", "SkillTreeNode")
        TrainingCycle = old_apps.get_model("training", "TrainingCycle")

        project = SkillProject.objects.create(code="NS", name="网络系统管理")
        linux = TechnicalDomain.objects.create(
            skill_project=project,
            code="LINUX",
            name="Linux",
            order=20,
        )
        network = TechnicalDomain.objects.create(
            skill_project=project,
            code="NETWORK",
            name="Network",
            order=10,
        )
        windows = TechnicalDomain.objects.create(
            skill_project=project,
            code="WINDOWS",
            name="Windows",
            order=30,
        )
        linux_skill = Skill.objects.create(
            skill_project=project,
            primary_domain=linux,
            name="Linux 服务",
        )
        network_skill = Skill.objects.create(
            skill_project=project,
            primary_domain=network,
            name="网络服务",
        )
        current = SkillTreeVersion.objects.create(
            skill_project=project,
            version="V2",
            name="当前版本",
            is_current=True,
        )
        history = SkillTreeVersion.objects.create(
            skill_project=project,
            version="V1",
            name="历史版本",
        )
        SkillTreeNode.objects.create(
            tree_version=current,
            technical_domain=linux,
            skill=linux_skill,
            order=20,
        )
        SkillTreeNode.objects.create(
            tree_version=current,
            technical_domain=network,
            skill=network_skill,
            order=10,
        )
        cycle = TrainingCycle.objects.create(
            skill_project=project,
            skill_tree_version=current,
            code="C1",
            name="周期",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )
        self.project_pk = project.pk
        self.domain_ids = {linux.pk, network.pk, windows.pk}
        self.first_domain_pk = network.pk
        self.current_pk = current.pk
        self.history_pk = history.pk
        self.cycle_pk = cycle.pk
        self.skill_domain = {
            linux_skill.pk: linux.pk,
            network_skill.pk: network.pk,
        }

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        self.apps = executor.loader.project_state(self.migrate_to).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_versions_nodes_and_cycle_snapshot_are_split_without_loss(self):
        SkillTreeVersion = self.apps.get_model("standards", "SkillTreeVersion")
        SkillTreeNode = self.apps.get_model("standards", "SkillTreeNode")
        CycleTreeLink = self.apps.get_model("training", "TrainingCycleSkillTreeVersion")

        versions = SkillTreeVersion.objects.filter(technical_domain_id__in=self.domain_ids)
        self.assertEqual(versions.count(), 6)
        self.assertEqual(
            set(versions.filter(is_current=True).values_list("technical_domain_id", flat=True)),
            self.domain_ids,
        )
        self.assertEqual(
            SkillTreeVersion.objects.get(pk=self.current_pk).technical_domain_id,
            self.first_domain_pk,
        )
        self.assertEqual(
            SkillTreeVersion.objects.get(pk=self.history_pk).technical_domain_id,
            self.first_domain_pk,
        )
        self.assertEqual(SkillTreeNode.objects.count(), 2)
        for skill_id, domain_id in self.skill_domain.items():
            node = SkillTreeNode.objects.get(skill_id=skill_id)
            self.assertEqual(node.tree_version.technical_domain_id, domain_id)

        links = CycleTreeLink.objects.filter(training_cycle_id=self.cycle_pk)
        self.assertEqual(links.count(), 3)
        self.assertEqual(set(links.values_list("technical_domain_id", flat=True)), self.domain_ids)
        self.assertTrue(
            all(link.skill_tree_version.is_current for link in links.select_related("skill_tree_version"))
        )
