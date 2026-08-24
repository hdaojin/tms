from datetime import date

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class CompetitionParticipantMigrationTests(TransactionTestCase):
    migrate_from = [("assessments", "0001_initial")]
    migrate_to = [("assessments", "0002_competition_people_roles_and_assessment_times")]

    @staticmethod
    def migration_targets(executor, assessment_target):
        return [
            *[
                node
                for node in executor.loader.graph.leaf_nodes()
                if node[0] not in {"assessments", "scoring", "evidence"}
            ],
            ("evidence", "0001_initial"),
            ("scoring", "0001_initial"),
            assessment_target,
        ]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        from_targets = self.migration_targets(executor, self.migrate_from[0])
        executor.migrate(from_targets)
        old_apps = executor.loader.project_state(from_targets).apps

        User = old_apps.get_model("auth", "User")
        SkillProject = old_apps.get_model("standards", "SkillProject")
        Assessment = old_apps.get_model("assessments", "Assessment")
        AssessmentParticipant = old_apps.get_model("assessments", "AssessmentParticipant")

        user = User.objects.create(username="legacy-expert", first_name="三", last_name="张")
        project = SkillProject.objects.create(code="LEGACY", name="历史项目")
        assessment = Assessment.objects.create(
            skill_project=project,
            assessment_type="competition",
            name="历史竞赛",
            code="LEGACY-ASSESSMENT",
            start_date=date(2025, 1, 1),
            created_by=user,
        )
        self.named_participant_pk = AssessmentParticipant.objects.create(
            assessment=assessment,
            user=user,
            display_name="历史姓名快照",
            role="expert",
            organization="历史单位",
            metadata={"legacy": True},
        ).pk
        self.blank_name_participant_pk = AssessmentParticipant.objects.create(
            assessment=assessment,
            external_code="EXT-001",
            display_name="",
            role="competitor",
            metadata={"source": "legacy"},
        ).pk

        executor = MigrationExecutor(connection)
        to_targets = self.migration_targets(executor, self.migrate_to[0])
        executor.migrate(to_targets)
        self.apps = executor.loader.project_state(to_targets).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_legacy_roles_and_snapshots_are_preserved(self):
        AssessmentParticipant = self.apps.get_model("assessments", "AssessmentParticipant")
        CompetitionRole = self.apps.get_model("assessments", "CompetitionRole")

        named = AssessmentParticipant.objects.select_related("role").get(pk=self.named_participant_pk)
        self.assertEqual(named.role.code, "expert")
        self.assertEqual(named.display_name, "历史姓名快照")
        self.assertEqual(named.organization, "历史单位")
        self.assertEqual(named.metadata, {"legacy": True})

        blank_name = AssessmentParticipant.objects.select_related("role").get(pk=self.blank_name_participant_pk)
        self.assertEqual(blank_name.role.code, "competitor")
        self.assertEqual(blank_name.display_name, "EXT-001")
        self.assertEqual(blank_name.metadata, {"source": "legacy"})
        self.assertTrue(CompetitionRole.objects.filter(code="project_manager", category="official").exists())
