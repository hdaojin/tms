from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase

from core.bootstrap_engine import (
    CREATE,
    SKIP,
    UNCHANGED,
    UPDATE,
    apply_bootstrap_plan,
    build_bootstrap_plan,
)

from .models import ScoringParserConfig
from .registry import ParserDefinition
from .services import create_scheme_from_document, default_parser_config, enabled_parser_configs


class ScoringParserBootstrapTests(TestCase):
    def setUp(self):
        ScoringParserConfig.objects.all().delete()

    def parser_record(self, plan):
        return next(
            record
            for record in plan.records
            if record.dataset.model_label == "scoring.ScoringParserConfig"
            and record.key_values == ("cmp_single_module_v1",)
        )

    def test_read_helpers_do_not_create_or_reenable_configs(self):
        self.assertFalse(enabled_parser_configs().exists())
        self.assertIsNone(default_parser_config())
        self.assertFalse(ScoringParserConfig.objects.exists())

        config = ScoringParserConfig.objects.create(
            parser_key="cmp_single_module_v1",
            display_name="管理员解析器",
            is_enabled=False,
        )
        self.assertFalse(enabled_parser_configs().exists())
        self.assertIsNone(default_parser_config())
        config.refresh_from_db()
        self.assertFalse(config.is_enabled)

    def test_empty_database_plan_creates_enabled_registry_default(self):
        plan = build_bootstrap_plan()
        record = self.parser_record(plan)

        self.assertEqual(record.action, CREATE)
        self.assertTrue(record.create_values["is_enabled"])
        self.assertTrue(record.create_values["is_default"])

        apply_bootstrap_plan(plan)
        config = ScoringParserConfig.objects.get(parser_key="cmp_single_module_v1")
        self.assertTrue(config.is_enabled)
        self.assertTrue(config.is_default)

    def test_existing_database_keeps_existing_and_disables_new_registry_entry(self):
        existing = ScoringParserConfig.objects.create(
            parser_key="cmp_single_module_v1",
            display_name="管理员名称",
            is_enabled=False,
        )
        extra_definition = ParserDefinition(
            key="test_extra_parser",
            display_name="测试新增解析器",
            alias="",
            description="仅用于测试 Bootstrap 增量策略。",
            template_filename="unused.xlsx",
            parse_function_path="scoring.parser.parse_marking_workbook",
        )

        with patch.dict(
            "scoring.bootstrap.PARSER_DEFINITIONS",
            {"test_extra_parser": extra_definition},
        ):
            plan = build_bootstrap_plan()
            existing_record = self.parser_record(plan)
            new_record = next(
                record for record in plan.records if record.key_values == ("test_extra_parser",)
            )
            self.assertEqual(existing_record.action, SKIP)
            self.assertEqual(new_record.action, CREATE)
            self.assertFalse(new_record.create_values["is_enabled"])
            self.assertFalse(new_record.create_values["is_default"])
            apply_bootstrap_plan(plan)

        existing.refresh_from_db()
        self.assertEqual(existing.display_name, "管理员名称")
        self.assertFalse(existing.is_enabled)
        new_config = ScoringParserConfig.objects.get(parser_key="test_extra_parser")
        self.assertFalse(new_config.is_enabled)
        self.assertFalse(new_config.is_default)

    def test_force_restores_registry_fields_and_switches_default(self):
        config = ScoringParserConfig.objects.create(
            parser_key="cmp_single_module_v1",
            display_name="管理员名称",
            is_enabled=False,
        )

        normal = self.parser_record(build_bootstrap_plan())
        force = self.parser_record(build_bootstrap_plan(force=True))

        self.assertEqual(normal.action, SKIP)
        self.assertEqual(force.action, UPDATE)
        apply_bootstrap_plan(build_bootstrap_plan(force=True))
        config.refresh_from_db()
        self.assertEqual(config.display_name, "CMP 单模块评分标准")
        self.assertTrue(config.is_enabled)
        self.assertTrue(config.is_default)
        self.assertEqual(self.parser_record(build_bootstrap_plan(force=True)).action, UNCHANGED)

    def test_force_switches_registry_default_without_unique_constraint_error(self):
        extra_definition = ParserDefinition(
            key="test_extra_parser",
            display_name="测试新增解析器",
            alias="",
            description="仅用于测试默认项切换。",
            template_filename="unused.xlsx",
            parse_function_path="scoring.parser.parse_marking_workbook",
        )
        with patch.dict(
            "scoring.bootstrap.PARSER_DEFINITIONS",
            {"test_extra_parser": extra_definition},
        ):
            apply_bootstrap_plan(build_bootstrap_plan())
            ScoringParserConfig.objects.filter(is_default=True).update(is_default=False)
            ScoringParserConfig.objects.filter(parser_key="test_extra_parser").update(
                is_enabled=True,
                is_default=True,
            )

            apply_bootstrap_plan(build_bootstrap_plan(force=True))

            defaults = ScoringParserConfig.objects.filter(is_default=True)
            self.assertEqual(defaults.count(), 1)
            self.assertEqual(defaults.get().parser_key, "cmp_single_module_v1")

    def test_invalid_registry_default_is_preflight_error(self):
        with patch("scoring.bootstrap.default_parser_key", return_value="missing-parser"):
            plan = build_bootstrap_plan()

        self.assertTrue(plan.has_errors)
        self.assertTrue(any("默认 key missing-parser 不存在" in issue.message for issue in plan.issues))

    def test_create_scheme_without_config_has_actionable_error(self):
        with self.assertRaisesMessage(ValidationError, "bootstrap_tms"):
            create_scheme_from_document(document=None)
