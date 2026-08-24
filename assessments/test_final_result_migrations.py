from datetime import date
from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class FinalResultMigrationTests(TransactionTestCase):
    migrate_from = ("assessments", "0002_competition_people_roles_and_assessment_times")
    migrate_to = ("assessments", "0003_final_results_scores_and_awards")

    @staticmethod
    def migration_targets(executor, assessment_target):
        return [
            *[node for node in executor.loader.graph.leaf_nodes() if node[0] != "assessments"],
            assessment_target,
        ]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        from_targets = self.migration_targets(executor, self.migrate_from)
        executor.migrate(from_targets)
        old_apps = executor.loader.project_state(from_targets).apps

        User = old_apps.get_model("auth", "User")
        SkillProject = old_apps.get_model("standards", "SkillProject")
        Assessment = old_apps.get_model("assessments", "Assessment")
        AssessmentParticipant = old_apps.get_model("assessments", "AssessmentParticipant")
        CompetitionRole = old_apps.get_model("assessments", "CompetitionRole")
        AssessmentResultSummary = old_apps.get_model("assessments", "AssessmentResultSummary")

        user = User.objects.create(username="legacy-final-result")
        project = SkillProject.objects.create(code="LEGACY-FINAL", name="历史最终结果项目")
        assessment = Assessment.objects.create(
            skill_project=project,
            assessment_type="competition",
            name="历史最终结果竞赛",
            code="LEGACY-FINAL-ASSESSMENT",
            start_date=date(2025, 2, 1),
            created_by=user,
        )
        competitor_role = CompetitionRole.objects.create(
            code="legacy-final-competitor",
            name="选手",
            category="competitor",
        )
        expert_role = CompetitionRole.objects.create(
            code="legacy-final-expert",
            name="专家",
            category="expert",
        )
        competitor = AssessmentParticipant.objects.create(
            assessment=assessment,
            role=competitor_role,
            display_name="历史选手",
        )
        expert = AssessmentParticipant.objects.create(
            assessment=assessment,
            role=expert_role,
            display_name="历史专家",
            metadata={"participant": "expert-kept"},
        )
        self.original_expert_pk = expert.pk
        self.competitor_result_pk = AssessmentResultSummary.objects.create(
            assessment=assessment,
            participant=competitor,
            total_score=Decimal("86.35"),
            rank=1,
            award="金牌",
            metadata={"summary": "competitor-kept"},
        ).pk
        self.expert_result_pk = AssessmentResultSummary.objects.create(
            assessment=assessment,
            participant=expert,
            total_score=Decimal("70.00"),
            rank=2,
            award="金牌",
            metadata={"summary": "expert-kept"},
        ).pk

        executor = MigrationExecutor(connection)
        to_targets = self.migration_targets(executor, self.migrate_to)
        executor.migrate(to_targets)
        self.apps = executor.loader.project_state(to_targets).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_summary_rows_scores_awards_and_metadata_are_preserved(self):
        AssessmentParticipant = self.apps.get_model("assessments", "AssessmentParticipant")
        AssessmentFinalResult = self.apps.get_model("assessments", "AssessmentFinalResult")
        AssessmentFinalScore = self.apps.get_model("assessments", "AssessmentFinalScore")
        AssessmentAward = self.apps.get_model("assessments", "AssessmentAward")
        AssessmentResultAward = self.apps.get_model("assessments", "AssessmentResultAward")

        competitor_result = AssessmentFinalResult.objects.select_related("participant__role").get(
            pk=self.competitor_result_pk
        )
        expert_result = AssessmentFinalResult.objects.select_related("participant__role").get(pk=self.expert_result_pk)
        self.assertEqual(AssessmentFinalResult.objects.count(), 2)
        self.assertEqual(competitor_result.rank, 1)
        self.assertTrue(competitor_result.is_official)
        self.assertIsNotNone(competitor_result.confirmed_at)
        self.assertIsNone(competitor_result.confirmed_by_id)
        self.assertEqual(competitor_result.metadata["summary"], "competitor-kept")
        self.assertEqual(expert_result.metadata["summary"], "expert-kept")

        self.assertNotEqual(expert_result.participant_id, self.original_expert_pk)
        self.assertEqual(expert_result.participant.role.category, "competitor")
        original_expert = AssessmentParticipant.objects.select_related("role").get(pk=self.original_expert_pk)
        self.assertEqual(original_expert.role.category, "expert")
        self.assertEqual(original_expert.metadata, {"participant": "expert-kept"})

        self.assertEqual(AssessmentFinalScore.objects.filter(score_type="raw").count(), 2)
        self.assertEqual(
            AssessmentFinalScore.objects.get(final_result_id=self.competitor_result_pk).value,
            Decimal("86.3500"),
        )
        self.assertEqual(AssessmentAward.objects.count(), 1)
        award = AssessmentAward.objects.get()
        self.assertEqual(award.code, "gold")
        self.assertEqual(award.category, "gold")
        self.assertEqual(award.name, "金牌")
        self.assertEqual(AssessmentResultAward.objects.filter(award=award).count(), 2)
