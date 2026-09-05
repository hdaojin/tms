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
            *[node for node in executor.loader.graph.leaf_nodes() if node[0] not in {"scoring", "assessments"}],
            ("assessments", "0007_finalize_assessment_type"),
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
        AssessmentType = old_apps.get_model("assessments", "AssessmentType")
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
        assessment_type, _created = AssessmentType.objects.get_or_create(
            code='competition',
            defaults={'name': '正式竞赛', 'order': 10},
        )
        assessment = Assessment.objects.create(
            skill_project=project,
            assessment_type=assessment_type,
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


class ScoringStandardSourceMigrationTests(TransactionTestCase):
    migrate_from = ("scoring", "0002_unify_scoring_results_with_assessment_participants")
    migrate_to = ("scoring", "0003_alter_scoringparserconfig_options_and_more")

    @staticmethod
    def migration_targets(executor, scoring_target):
        return [
            *[node for node in executor.loader.graph.leaf_nodes() if node[0] not in {"scoring", "assessments"}],
            ("assessments", "0007_finalize_assessment_type"),
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
        AssessmentType = old_apps.get_model("assessments", "AssessmentType")
        AssessmentModule = old_apps.get_model("assessments", "AssessmentModule")
        AssessmentDocument = old_apps.get_model("assessments", "AssessmentDocument")
        ScoringParserConfig = old_apps.get_model("scoring", "ScoringParserConfig")
        ScoringScheme = old_apps.get_model("scoring", "ScoringScheme")
        ScoringSchemeImport = old_apps.get_model("scoring", "ScoringSchemeImport")

        user = User.objects.create(username="legacy-standard-source")
        project = SkillProject.objects.create(code="STANDARD-SOURCE", name="评分标准迁移项目")
        assessment_type, _created = AssessmentType.objects.get_or_create(
            code="mock",
            defaults={"name": "模拟赛", "order": 40},
        )
        assessment = Assessment.objects.create(
            skill_project=project,
            assessment_type=assessment_type,
            name="评分标准迁移测试",
            code="STANDARD-SOURCE-ASSESSMENT",
            start_date=date(2026, 1, 1),
            created_by=user,
        )
        module = AssessmentModule.objects.create(assessment=assessment, code="A", name="模块 A")
        scheme_source = AssessmentDocument.objects.create(
            assessment=assessment,
            module=module,
            document_type="marking_scheme",
            title="历史来源评分表",
            file="legacy-source.xlsx",
            original_filename="legacy-source.xlsx",
            file_sha256="a" * 64,
            uploaded_by=user,
        )
        duplicate_source = AssessmentDocument.objects.create(
            assessment=assessment,
            module=module,
            document_type="marking_scheme",
            title="待合并来源评分表",
            file="duplicate-source.xlsx",
            original_filename="duplicate-source.xlsx",
            file_sha256="b" * 64,
            uploaded_by=user,
        )
        existing_standard = AssessmentDocument.objects.create(
            assessment=assessment,
            module=module,
            document_type="marking_standard",
            title="已存在评分标准",
            file="existing-standard.xlsx",
            original_filename="existing-standard.xlsx",
            file_sha256="b" * 64,
            uploaded_by=user,
        )
        scheme = ScoringScheme.objects.create(
            assessment_module=module,
            source_document=scheme_source,
            title="历史评分方案",
            module_code="A",
            module_name="模块 A",
        )
        scheme_import = ScoringSchemeImport.objects.create(
            assessment_module=module,
            source_document=duplicate_source,
            parser_key="cmp_single_module_v1",
            parser_display_name="CMP 单模块评分表",
            title="历史导入",
            module_code="A",
            module_name="模块 A",
            module_mark=Decimal("0"),
            total_mark=Decimal("0"),
        )
        ScoringParserConfig.objects.create(
            parser_key="cmp_single_module_v1",
            display_name="CMP 单模块评分表",
            description="严格解析 CMP 官方单模块评分表模板，支持 M 测量评分点和 J 评价四档分档。",
        )
        self.scheme_pk = scheme.pk
        self.scheme_source_pk = scheme_source.pk
        self.scheme_import_pk = scheme_import.pk
        self.existing_standard_pk = existing_standard.pk

        executor = MigrationExecutor(connection)
        to_targets = self.migration_targets(executor, self.migrate_to)
        executor.migrate(to_targets)
        self.apps = executor.loader.project_state(to_targets).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_sources_and_default_parser_copy_use_scoring_standard_terms(self):
        AssessmentDocument = self.apps.get_model("assessments", "AssessmentDocument")
        ScoringParserConfig = self.apps.get_model("scoring", "ScoringParserConfig")
        ScoringScheme = self.apps.get_model("scoring", "ScoringScheme")
        ScoringSchemeImport = self.apps.get_model("scoring", "ScoringSchemeImport")

        self.assertEqual(
            AssessmentDocument.objects.get(pk=self.scheme_source_pk).document_type,
            "marking_standard",
        )
        self.assertEqual(
            ScoringScheme.objects.get(pk=self.scheme_pk).source_document_id,
            self.scheme_source_pk,
        )
        self.assertEqual(
            ScoringSchemeImport.objects.get(pk=self.scheme_import_pk).source_document_id,
            self.existing_standard_pk,
        )
        parser_config = ScoringParserConfig.objects.get(parser_key="cmp_single_module_v1")
        self.assertEqual(parser_config.display_name, "CMP 单模块评分标准")
        self.assertIn("评分标准模板", parser_config.description)
