from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.conf import settings
from django.contrib.flatpages.models import FlatPage
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

import assessments.bootstrap
import behaviors.bootstrap
from assessments.models import AssessmentLevel, AssessmentSeries, AssessmentType, CompetitionRole
from behaviors.models import ConductCategory, ConductItem, ConductSeverity, ConductSeverityRule
from core.bootstrap_engine import (
    CREATE,
    SKIP,
    UNCHANGED,
    UPDATE,
    BootstrapPlanError,
    apply_bootstrap_plan,
    bootstrap_defaults,
    build_bootstrap_plan,
)
from event_countdown.models import CountdownEventType
from feedback.models import Feedback, FeedbackCategory
from scoring.models import ScoringParserConfig
from worldskills_forum.models import ForumCategory, ForumModule, ForumPostType, ForumSourceRole

from .models import SiteConfig


def find_record(plan, model_label, *key_values):
    return next(
        record
        for record in plan.records
        if record.dataset.model_label == model_label and record.key_values == key_values
    )


class BootstrapTestMixin:
    def clear_bootstrap_data(self):
        ScoringParserConfig.objects.all().delete()
        ConductItem.objects.all().delete()
        ConductSeverityRule.objects.all().delete()
        ConductCategory.objects.all().delete()
        ConductSeverity.objects.all().delete()
        ForumPostType.objects.all().delete()
        ForumSourceRole.objects.all().delete()
        ForumModule.objects.all().delete()
        ForumCategory.objects.all().delete()
        Feedback.objects.all().delete()
        FeedbackCategory.objects.all().delete()
        CountdownEventType.objects.all().delete()
        CompetitionRole.objects.all().delete()
        AssessmentType.objects.all().delete()
        AssessmentLevel.objects.all().delete()
        AssessmentSeries.objects.all().delete()
        FlatPage.objects.filter(url__in=["/about/site/", "/about/author/"]).delete()
        SiteConfig.objects.all().delete()

    def run_command(self, **options):
        output = StringIO()
        call_command("bootstrap_tms", stdout=output, **options)
        return output.getvalue()


class BootstrapPlanTests(BootstrapTestMixin, TestCase):
    def test_empty_database_plan_is_create_only_and_does_not_write(self):
        self.clear_bootstrap_data()

        plan = build_bootstrap_plan()

        self.assertFalse(plan.has_errors)
        self.assertTrue(plan.records)
        self.assertTrue(all(record.action == CREATE for record in plan.records))
        self.assertFalse(SiteConfig.objects.exists())
        self.assertFalse(FeedbackCategory.objects.exists())
        self.assertFalse(ConductItem.objects.exists())

    def test_equal_decimal_bool_and_fk_values_are_unchanged(self):
        bootstrap_defaults()

        plan = build_bootstrap_plan()

        self.assertEqual(
            find_record(plan, "assessments.AssessmentLevel", "national").action,
            UNCHANGED,
        )
        self.assertEqual(
            find_record(plan, "behaviors.ConductSeverityRule", "REWARD", ("MODERATE",)).action,
            UNCHANGED,
        )
        self.assertEqual(
            find_record(plan, "feedback.FeedbackCategory", "complaint").action,
            UNCHANGED,
        )

    def test_changed_fields_are_skip_normally_and_update_with_force(self):
        bootstrap_defaults()
        AssessmentLevel.objects.filter(code="national").update(
            name="管理员级别", weight=Decimal("2.50"), order=99, is_active=False
        )

        normal_record = find_record(
            build_bootstrap_plan(), "assessments.AssessmentLevel", "national"
        )
        force_record = find_record(
            build_bootstrap_plan(force=True), "assessments.AssessmentLevel", "national"
        )

        self.assertEqual(normal_record.action, SKIP)
        self.assertEqual(force_record.action, UPDATE)
        self.assertEqual(
            {diff.field_name for diff in force_record.diffs},
            {"name", "weight", "order", "is_active"},
        )

    def test_duplicate_stable_key_is_preflight_error(self):
        declaration = dict(assessments.bootstrap.BOOTSTRAP_DATA[0])
        declaration["records"] = [
            dict(assessments.bootstrap.ASSESSMENT_LEVELS[0]),
            dict(assessments.bootstrap.ASSESSMENT_LEVELS[0]),
        ]

        with patch.object(assessments.bootstrap, "BOOTSTRAP_DATA", [declaration]):
            plan = build_bootstrap_plan()

        self.assertTrue(plan.has_errors)
        self.assertTrue(any("重复稳定键" in issue.message for issue in plan.issues))

    def test_database_name_collision_is_preflight_error(self):
        AssessmentLevel.objects.filter(code="world").delete()
        AssessmentLevel.objects.create(code="conflict", name="世界级")

        plan = build_bootstrap_plan()

        self.assertTrue(plan.has_errors)
        self.assertTrue(any("已被其他稳定键占用" in issue.message for issue in plan.issues))

    def test_missing_fk_natural_key_is_preflight_error(self):
        ConductItem.objects.all().delete()
        ConductSeverityRule.objects.all().delete()
        ConductSeverity.objects.all().delete()
        rule_dataset = dict(behaviors.bootstrap.BOOTSTRAP_DATA[1])

        with patch.object(behaviors.bootstrap, "BOOTSTRAP_DATA", [rule_dataset]):
            plan = build_bootstrap_plan()

        self.assertTrue(plan.has_errors)
        self.assertTrue(any("关系 severity" in issue.message for issue in plan.issues))


class BootstrapCommandTests(BootstrapTestMixin, TestCase):
    def test_preview_is_written_before_confirmation_and_yes_creates(self):
        self.clear_bootstrap_data()
        output = StringIO()

        def confirm(_prompt):
            self.assertIn("TMS 默认业务数据预览", output.getvalue())
            self.assertIn("CREATE", output.getvalue())
            return "yes"

        with patch("builtins.input", side_effect=confirm):
            call_command("bootstrap_tms", stdout=output)

        self.assertTrue(SiteConfig.objects.exists())
        self.assertTrue(
            FlatPage.objects.get(url="/about/site/").sites.filter(
                pk=settings.SITE_ID
            ).exists()
        )
        self.assertIn("初始化完成", output.getvalue())

    def test_default_no_cancels_without_writes(self):
        self.clear_bootstrap_data()

        with patch("builtins.input", return_value="n"):
            output = self.run_command()

        self.assertIn("已取消", output)
        self.assertFalse(SiteConfig.objects.exists())

    def test_dry_run_never_prompts_or_writes(self):
        self.clear_bootstrap_data()

        with patch("builtins.input", side_effect=AssertionError("不应询问")):
            output = self.run_command(dry_run=True)

        self.assertIn("Dry-run 完成", output)
        self.assertFalse(SiteConfig.objects.exists())

    def test_force_does_not_imply_yes(self):
        bootstrap_defaults()
        SiteConfig.objects.filter(pk=1).update(site_name="管理员站点")

        with patch("builtins.input", return_value=""):
            output = self.run_command(force=True)

        self.assertIn("强制覆盖", output)
        self.assertIn("已取消", output)
        self.assertEqual(SiteConfig.objects.get(pk=1).site_name, "管理员站点")

    def test_force_dry_run_shows_update_without_prompt_or_write(self):
        bootstrap_defaults()
        SiteConfig.objects.filter(pk=1).update(site_name="管理员站点")

        with patch("builtins.input", side_effect=AssertionError("不应询问")):
            output = self.run_command(force=True, dry_run=True)

        self.assertIn("UPDATE", output)
        self.assertIn("Dry-run 完成", output)
        self.assertEqual(SiteConfig.objects.get(pk=1).site_name, "管理员站点")

    def test_yes_skips_input_but_keeps_preview(self):
        self.clear_bootstrap_data()

        with patch("builtins.input", side_effect=AssertionError("不应询问")):
            output = self.run_command(yes=True)

        self.assertIn("TMS 默认业务数据预览", output)
        self.assertTrue(SiteConfig.objects.exists())

    def test_preflight_error_does_not_prompt_or_apply(self):
        self.clear_bootstrap_data()
        FeedbackCategory.objects.create(code="conflict", name="Bug反馈")

        with patch("builtins.input", side_effect=AssertionError("不应询问")):
            with self.assertRaises(CommandError):
                self.run_command()

        self.assertFalse(SiteConfig.objects.exists())

    def test_eof_has_actionable_noninteractive_hint(self):
        self.clear_bootstrap_data()

        with patch("builtins.input", side_effect=EOFError):
            with self.assertRaisesMessage(CommandError, "--yes 或 --dry-run"):
                self.run_command()


class BootstrapForceTests(BootstrapTestMixin, TestCase):
    def setUp(self):
        bootstrap_defaults()

    def test_normal_preserves_changes_and_force_restores_managed_fields(self):
        site_config = SiteConfig.objects.get(pk=1)
        site_pk = site_config.pk
        SiteConfig.objects.filter(pk=1).update(site_name="管理员站点名")
        AssessmentLevel.objects.filter(code="national").update(name="管理员级别", order=88, is_active=False)
        FeedbackCategory.objects.filter(code="complaint").update(default_private=False)
        ForumPostType.objects.filter(code="official_reply").update(is_official=False)
        CountdownEventType.objects.filter(code="training").update(is_active=False)
        ConductItem.objects.filter(category__code="attendance", code="late").update(default_score="-9.00")
        ScoringParserConfig.objects.filter(parser_key="cmp_single_module_v1").update(
            display_name="管理员解析器", is_enabled=False, is_default=False
        )
        extra_type = AssessmentType.objects.create(code="custom", name="自定义类型")
        extra_category = FeedbackCategory.objects.create(code="custom", name="自定义反馈")

        self.run_command(yes=True)
        self.assertEqual(SiteConfig.objects.get(pk=1).site_name, "管理员站点名")
        self.assertEqual(AssessmentLevel.objects.get(code="national").name, "管理员级别")

        output = self.run_command(force=True, yes=True)

        self.assertIn("UPDATE", output)
        self.assertEqual(SiteConfig.objects.get(pk=1).pk, site_pk)
        self.assertEqual(SiteConfig.objects.get(pk=1).site_name, "Training management system")
        level = AssessmentLevel.objects.get(code="national")
        self.assertEqual((level.name, level.order, level.is_active), ("国家级", 20, True))
        self.assertTrue(FeedbackCategory.objects.get(code="complaint").default_private)
        self.assertTrue(ForumPostType.objects.get(code="official_reply").is_official)
        self.assertTrue(CountdownEventType.objects.get(code="training").is_active)
        self.assertEqual(
            ConductItem.objects.get(category__code="attendance", code="late").default_score,
            Decimal("-1.00"),
        )
        parser = ScoringParserConfig.objects.get(parser_key="cmp_single_module_v1")
        self.assertEqual(parser.display_name, "CMP 单模块评分表")
        self.assertTrue(parser.is_enabled)
        self.assertTrue(parser.is_default)
        self.assertTrue(AssessmentType.objects.filter(pk=extra_type.pk).exists())
        self.assertTrue(FeedbackCategory.objects.filter(pk=extra_category.pk).exists())

    def test_force_preserves_primary_key_and_business_reference(self):
        category = FeedbackCategory.objects.get(code="bug")
        feedback = Feedback.objects.create(category=category, title="测试", content="内容")
        category.name = "管理员 Bug 分类"
        category.save(update_fields=["name"])

        self.run_command(force=True, yes=True)

        feedback.refresh_from_db()
        self.assertEqual(feedback.category_id, category.pk)
        self.assertEqual(FeedbackCategory.objects.get(pk=category.pk).code, "bug")

    def test_flatpage_site_binding_preview_and_force_only_adds_current_site(self):
        page = FlatPage.objects.get(url="/about/site/")
        current_site = Site.objects.get(pk=settings.SITE_ID)
        other_site = Site.objects.create(domain="other.example", name="其他站点")
        page.sites.remove(current_site)
        page.sites.add(other_site)

        normal = find_record(build_bootstrap_plan(), "flatpages.FlatPage", "/about/site/")
        force = find_record(build_bootstrap_plan(force=True), "flatpages.FlatPage", "/about/site/")

        self.assertEqual(normal.action, SKIP)
        self.assertEqual(force.action, UPDATE)
        self.run_command(force=True, yes=True)
        self.assertEqual(
            set(page.sites.values_list("pk", flat=True)),
            {current_site.pk, other_site.pk},
        )

    def test_force_switches_behavior_defaults_without_unique_constraint_error(self):
        ConductSeverityRule.objects.filter(nature="REWARD", is_default=True).update(is_default=False)
        ConductSeverityRule.objects.filter(nature="REWARD", severity__code="MINOR").update(is_default=True)

        self.run_command(force=True, yes=True)

        defaults = ConductSeverityRule.objects.filter(nature="REWARD", is_default=True)
        self.assertEqual(defaults.count(), 1)
        self.assertEqual(defaults.get().severity.code, "MODERATE")

    def test_registry_drift_is_error_and_extra_row_is_not_deleted(self):
        ScoringParserConfig.objects.bulk_create(
            [
                ScoringParserConfig(
                    parser_key="removed_parser",
                    display_name="已移除解析器",
                    is_enabled=False,
                )
            ]
        )

        plan = build_bootstrap_plan(force=True)

        self.assertTrue(plan.has_errors)
        self.assertTrue(any("已不在 Registry" in issue.message for issue in plan.issues))
        with self.assertRaises(CommandError):
            self.run_command(force=True, yes=True)
        self.assertTrue(ScoringParserConfig.objects.filter(parser_key="removed_parser").exists())

    def test_late_apply_failure_rolls_back_earlier_apps(self):
        self.clear_bootstrap_data()
        plan = build_bootstrap_plan()
        late_record = find_record(plan, "behaviors.ConductItem", ("attendance",), "late")
        late_record.create_values["default_score"] = Decimal("0.00")

        with self.assertRaises(ValidationError):
            apply_bootstrap_plan(plan)

        self.assertFalse(SiteConfig.objects.exists())
        self.assertFalse(FeedbackCategory.objects.exists())
        self.assertFalse(ConductItem.objects.exists())

    def test_stale_plan_refuses_to_overwrite_post_preview_change(self):
        SiteConfig.objects.filter(pk=1).update(site_name="预览前管理员值")
        plan = build_bootstrap_plan(force=True)
        SiteConfig.objects.filter(pk=1).update(site_name="确认后新值")

        with self.assertRaises(BootstrapPlanError):
            apply_bootstrap_plan(plan)

        self.assertEqual(SiteConfig.objects.get(pk=1).site_name, "确认后新值")
