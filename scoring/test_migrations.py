from datetime import date, datetime
from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class ScoringParticipantMigrationTests(TransactionTestCase):
    migrate_from = ("scoring", "0001_initial")
    migrate_to = ("scoring", "0002_unify_scoring_results_with_assessment_participants")

    @staticmethod
    def migration_targets(executor, scoring_target):
        return [
            *[node for node in executor.loader.graph.leaf_nodes() if node[0] != "scoring"],
            scoring_target,
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
        AssessmentModule = old_apps.get_model("assessments", "AssessmentModule")
        AssessmentParticipant = old_apps.get_model("assessments", "AssessmentParticipant")
        CompetitionRole = old_apps.get_model("assessments", "CompetitionRole")
        ScoringScheme = old_apps.get_model("scoring", "ScoringScheme")
        ScoringSubCriterion = old_apps.get_model("scoring", "ScoringSubCriterion")
        ScoringAspect = old_apps.get_model("scoring", "ScoringAspect")
        ScoringParticipant = old_apps.get_model("scoring", "ScoringParticipant")
        ScoringResult = old_apps.get_model("scoring", "ScoringResult")

        user = User.objects.create(username="legacy-competitor", first_name="一", last_name="选手")
        project = SkillProject.objects.create(code="LEGACY-SCORE", name="历史评分项目")
        assessment = Assessment.objects.create(
            skill_project=project,
            assessment_type="competition",
            name="历史评分竞赛",
            code="LEGACY-SCORE-ASSESSMENT",
            start_date=date(2025, 1, 1),
            created_by=user,
        )
        module = AssessmentModule.objects.create(assessment=assessment, code="A", name="模块 A")
        competitor_role = CompetitionRole.objects.create(
            code="legacy-competitor-role",
            name="选手",
            category="competitor",
        )
        expert_role = CompetitionRole.objects.create(
            code="legacy-expert-role",
            name="专家",
            category="expert",
        )
        competitor = AssessmentParticipant.objects.create(
            assessment=assessment,
            user=user,
            role=competitor_role,
            display_name="选手一",
            metadata={"participant": "kept"},
        )
        expert = AssessmentParticipant.objects.create(
            assessment=assessment,
            role=expert_role,
            display_name="专家一",
            metadata={"expert": "kept"},
        )
        self.original_competitor_pk = competitor.pk
        self.original_expert_pk = expert.pk

        scheme = ScoringScheme.objects.create(
            assessment_module=module,
            title="历史方案",
            module_code="A",
            module_name="模块 A",
            total_mark=Decimal("20"),
        )
        subcriterion = ScoringSubCriterion.objects.create(scheme=scheme, code="A1", name="评分子项")
        first_aspect = ScoringAspect.objects.create(
            scheme=scheme,
            subcriterion=subcriterion,
            code="A1.1",
            aspect_type="M",
            description="评分点一",
            max_mark=Decimal("10"),
            source_row_number=1,
        )
        second_aspect = ScoringAspect.objects.create(
            scheme=scheme,
            subcriterion=subcriterion,
            code="A1.2",
            aspect_type="M",
            description="评分点二",
            max_mark=Decimal("10"),
            source_row_number=2,
        )
        direct = ScoringParticipant.objects.create(
            scheme=scheme,
            assessment_participant=competitor,
            display_name="选手一快照",
            metadata={"mode": "direct"},
        )
        duplicate_user = ScoringParticipant.objects.create(
            scheme=scheme,
            user=user,
            display_name="选手一用户快照",
            metadata={"mode": "user"},
        )
        non_competitor = ScoringParticipant.objects.create(
            scheme=scheme,
            assessment_participant=expert,
            display_name="专家但有历史得分",
            metadata={"mode": "legacy-invalid-role"},
        )
        ScoringParticipant.objects.create(
            scheme=scheme,
            external_identifier="NO-RESULT",
            display_name="无得分历史对象",
            metadata={"mode": "no-result"},
        )

        graded_at = timezone.make_aware(datetime(2025, 1, 1, 9, 30))
        self.direct_result_pk = ScoringResult.objects.create(
            participant=direct,
            aspect=first_aspect,
            score_awarded=Decimal("8"),
            source="cmp",
            graded_at=graded_at,
            raw_payload={"row": 1},
        ).pk
        self.duplicate_result_pk = ScoringResult.objects.create(
            participant=duplicate_user,
            aspect=first_aspect,
            score_awarded=Decimal("7"),
            source="imported",
            raw_payload={"row": 2},
        ).pk
        self.non_competitor_result_pk = ScoringResult.objects.create(
            participant=non_competitor,
            aspect=second_aspect,
            score_awarded=Decimal("6"),
            source="manual",
            raw_payload={"row": 3},
        ).pk
        self.graded_at = graded_at

        executor = MigrationExecutor(connection)
        to_targets = self.migration_targets(executor, self.migrate_to)
        executor.migrate(to_targets)
        self.apps = executor.loader.project_state(to_targets).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_results_and_legacy_scoring_snapshots_are_preserved(self):
        AssessmentParticipant = self.apps.get_model("assessments", "AssessmentParticipant")
        ScoringResult = self.apps.get_model("scoring", "ScoringResult")

        self.assertEqual(ScoringResult.objects.count(), 3)
        direct = ScoringResult.objects.select_related("participant__role").get(pk=self.direct_result_pk)
        duplicate = ScoringResult.objects.select_related("participant__role").get(pk=self.duplicate_result_pk)
        invalid_role = ScoringResult.objects.select_related("participant__role").get(pk=self.non_competitor_result_pk)

        self.assertEqual(direct.participant_id, self.original_competitor_pk)
        self.assertNotEqual(duplicate.participant_id, direct.participant_id)
        self.assertNotEqual(invalid_role.participant_id, self.original_expert_pk)
        self.assertEqual(direct.source, "cmp_import")
        self.assertEqual(duplicate.source, "excel_import")
        self.assertEqual(direct.entered_at, self.graded_at)
        self.assertTrue(
            all(result.participant.role.category == "competitor" for result in (direct, duplicate, invalid_role))
        )
        self.assertEqual(direct.raw_payload, {"row": 1})
        self.assertEqual(duplicate.raw_payload, {"row": 2})

        original_expert = AssessmentParticipant.objects.select_related("role").get(pk=self.original_expert_pk)
        self.assertEqual(original_expert.role.category, "expert")
        self.assertEqual(original_expert.metadata, {"expert": "kept"})
        self.assertTrue(
            AssessmentParticipant.objects.filter(
                external_code="NO-RESULT",
                metadata__legacy_scoring_participants__isnull=False,
            ).exists()
        )
