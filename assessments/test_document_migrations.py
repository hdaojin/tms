from datetime import date

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class DocumentNamingMigrationTests(TransactionTestCase):
    def test_retired_sheets_become_attachments_without_renaming_or_version_conversion(self):
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        self.addCleanup(self.restore_schema)
        before = [node for node in leaves if node[0] != "assessments"] + [
            ("assessments", "0007_finalize_assessment_type")
        ]
        executor.migrate(before)
        apps = executor.loader.project_state(before).apps
        user = apps.get_model("auth", "User").objects.create(username="migration-doc")
        project = apps.get_model("standards", "SkillProject").objects.create(code="OLD-CODE", name="历史项目")
        category = apps.get_model("assessments", "AssessmentType").objects.create(code="doc-migration", name="测试")
        assessment = apps.get_model("assessments", "Assessment").objects.create(
            code="OLD-ASSESSMENT",
            name="历史评测",
            skill_project=project,
            assessment_type=category,
            start_date=date(2026, 9, 5),
            created_by=user,
        )
        documents = apps.get_model("assessments", "AssessmentDocument")
        records = []
        # 两种类型下的相同哈希，合并附件分类后也必须完整保留。
        for kind in ("marking_scheme", "attachment", "marking_standard"):
            records.append(
                documents.objects.create(
                    assessment=assessment,
                    document_type=kind,
                    title="历史标题",
                    version="final",
                    file=f"old/{kind}.xlsx",
                    original_filename="原文件.xlsx",
                    file_sha256="a" * 64,
                    uploaded_by=user,
                )
            )
        executor = MigrationExecutor(connection)
        executor.migrate(leaves)
        apps = executor.loader.project_state(leaves).apps
        documents = apps.get_model("assessments", "AssessmentDocument")
        self.assertEqual(documents.objects.filter(document_type="attachment").count(), 2)
        self.assertEqual(documents.objects.filter(document_type="marking_standard").count(), 1)
        for original in records:
            migrated = documents.objects.get(pk=original.pk)
            self.assertEqual(migrated.file.name, original.file.name)
            self.assertEqual(migrated.original_filename, "原文件.xlsx")
            self.assertEqual(migrated.title, "历史标题")
            self.assertEqual(migrated.version, "final")
            self.assertIsNone(migrated.numeric_version)
            self.assertIsNone(migrated.document_date)
            self.assertEqual(migrated.normalized_filename, "")

    @staticmethod
    def restore_schema():
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
