from django.db import IntegrityError, transaction
from django.test import TestCase

from standards.models import SkillProject

from glossary.forms import GlossaryEntryForm
from glossary.models import GlossaryEntry, ProfessionalGlossary
from glossary.normalization import (
    english_comparison_key,
    generated_chinese_alias,
    normalize_display_text,
)


class GlossaryNormalizationTests(TestCase):
    def test_normalizes_unicode_whitespace_invisible_characters_and_nfc(self):
        value = "\u00a0 Cafe\u0301\u200b\t  network\r\n"

        self.assertEqual(normalize_display_text(value), "Café network")
        self.assertEqual(english_comparison_key("  RoUTER\u00a0  OS "), "router os")

    def test_only_matching_english_or_acronym_parenthesis_generates_alias(self):
        self.assertEqual(generated_chinese_alias("开放系统互连（OSI）", "Open Systems Interconnection", "OSI"), "开放系统互连")
        self.assertEqual(generated_chinese_alias("开放系统互连 (open systems interconnection)", "Open Systems Interconnection"), "开放系统互连")
        self.assertEqual(generated_chinese_alias("开放系统互连（网络模型）", "Open Systems Interconnection", "OSI"), "")
        self.assertEqual(generated_chinese_alias("开放系统互连（OSI)", "Open Systems Interconnection", "OSI"), "")


class GlossaryEntryUniquenessTests(TestCase):
    def setUp(self):
        project = SkillProject.objects.create(code="39", name="信息网络布线")
        self.glossary = ProfessionalGlossary.objects.create(skill_project=project, name="WSC 2026")

    def test_database_uniqueness_uses_cleaned_casefolded_english_within_glossary(self):
        GlossaryEntry.objects.create(
            glossary=self.glossary,
            english_term="Optical   Fiber ",
            chinese_translation="光纤",
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            GlossaryEntry.objects.create(
                glossary=self.glossary,
                english_term=" optical\u00a0fiber",
                chinese_translation="光学纤维",
            )

    def test_manager_form_reports_duplicate_without_database_error(self):
        GlossaryEntry.objects.create(
            glossary=self.glossary,
            english_term="Router",
            chinese_translation="路由器",
        )
        form = GlossaryEntryForm(
            data={
                "glossary": self.glossary.pk,
                "english_term": " router ",
                "acronym": "",
                "chinese_translation": "路由设备",
                "english_aliases_text": "",
                "chinese_aliases_text": "",
                "is_active": True,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("已存在相同英文词条", form.errors["english_term"][0])
