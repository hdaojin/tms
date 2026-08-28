from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase

from .bootstrap import bootstrap_defaults
from .models import ScoringParserConfig
from .registry import ParserDefinition
from .services import create_scheme_from_document, default_parser_config, enabled_parser_configs


class ScoringParserBootstrapTests(TestCase):
    def setUp(self):
        ScoringParserConfig.objects.all().delete()

    def test_read_helpers_do_not_create_or_reenable_configs(self):
        self.assertFalse(enabled_parser_configs().exists())
        self.assertIsNone(default_parser_config())
        self.assertFalse(ScoringParserConfig.objects.exists())

        config = ScoringParserConfig.objects.create(
            parser_key='cmp_single_module_v1',
            display_name='管理员解析器',
            is_enabled=False,
        )
        self.assertFalse(enabled_parser_configs().exists())
        self.assertIsNone(default_parser_config())
        config.refresh_from_db()
        self.assertFalse(config.is_enabled)

    def test_empty_database_bootstrap_enables_registry_and_sets_default(self):
        stats = bootstrap_defaults()

        config = ScoringParserConfig.objects.get(parser_key='cmp_single_module_v1')
        self.assertEqual(stats, {'created': 1, 'existing': 0})
        self.assertTrue(config.is_enabled)
        self.assertTrue(config.is_default)

    def test_existing_database_keeps_existing_and_disables_new_registry_entry(self):
        existing = ScoringParserConfig.objects.create(
            parser_key='cmp_single_module_v1',
            display_name='管理员名称',
            is_enabled=False,
        )
        extra_definition = ParserDefinition(
            key='test_extra_parser',
            display_name='测试新增解析器',
            alias='',
            description='仅用于测试 Bootstrap 增量策略。',
            template_filename='unused.xlsx',
            parse_function_path='scoring.parser.parse_marking_workbook',
        )

        with patch.dict('scoring.bootstrap.PARSER_DEFINITIONS', {'test_extra_parser': extra_definition}):
            stats = bootstrap_defaults()

        existing.refresh_from_db()
        new_config = ScoringParserConfig.objects.get(parser_key='test_extra_parser')
        self.assertEqual(stats, {'created': 1, 'existing': 1})
        self.assertEqual(existing.display_name, '管理员名称')
        self.assertFalse(existing.is_enabled)
        self.assertFalse(new_config.is_enabled)
        self.assertFalse(new_config.is_default)

    def test_invalid_registry_default_is_rejected(self):
        with patch('scoring.bootstrap.default_parser_key', return_value='missing-parser'):
            with self.assertRaisesMessage(ValidationError, '默认 key 不存在'):
                bootstrap_defaults()

    def test_create_scheme_without_config_has_actionable_error(self):
        with self.assertRaisesMessage(ValidationError, 'bootstrap_tms'):
            create_scheme_from_document(document=None)
