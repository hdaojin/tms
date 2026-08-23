from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class SimplifySkillTreeNodesMigrationTests(TransactionTestCase):
    migrate_from = ("standards", "0003_skillterm_alter_skill_options_and_more")
    migrate_to = ("standards", "0004_simplify_skill_tree_nodes")

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])
        old_apps = executor.loader.project_state([self.migrate_from]).apps

        SkillProject = old_apps.get_model("standards", "SkillProject")
        TechnicalDomain = old_apps.get_model("standards", "TechnicalDomain")
        Skill = old_apps.get_model("standards", "Skill")
        SkillTreeVersion = old_apps.get_model("standards", "SkillTreeVersion")
        SkillTreeNode = old_apps.get_model("standards", "SkillTreeNode")

        project = SkillProject.objects.create(code="NS", name="网络系统管理")
        domain = TechnicalDomain.objects.create(skill_project=project, code="LINUX", name="Linux")
        skill = Skill.objects.create(skill_project=project, primary_domain=domain, name="用户管理")
        tree = SkillTreeVersion.objects.create(skill_project=project, version="2026", name="2026 技能树")
        category = SkillTreeNode.objects.create(
            tree_version=tree,
            technical_domain=domain,
            node_type="CATEGORY",
            code="CAT",
            name="系统管理",
        )
        SkillTreeNode.objects.create(
            tree_version=tree,
            technical_domain=domain,
            parent=category,
            skill=skill,
            node_type="SKILL",
            code="SKILL",
        )
        self.skill_pk = skill.pk

        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_to])
        self.apps = executor.loader.project_state([self.migrate_to]).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_legacy_tree_positions_are_cleared_but_skills_are_preserved(self):
        Skill = self.apps.get_model("standards", "Skill")
        SkillTreeNode = self.apps.get_model("standards", "SkillTreeNode")

        self.assertTrue(Skill.objects.filter(pk=self.skill_pk).exists())
        self.assertFalse(SkillTreeNode.objects.exists())
