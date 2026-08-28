from io import StringIO

from django.contrib.auth.models import Group
from django.contrib.flatpages.models import FlatPage
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase

from assessments.models import AssessmentLevel, AssessmentSeries, AssessmentType, CompetitionRole
from behaviors.models import ConductItem
from event_countdown.models import CountdownEventType
from feedback.models import FeedbackCategory
from scoring.models import ScoringParserConfig
from worldskills_forum.models import ForumPostType

from .models import SiteConfig


class BootstrapTmsCommandTests(TestCase):
    def run_bootstrap(self):
        output = StringIO()
        call_command('bootstrap_tms', stdout=output)
        return output.getvalue()

    def test_command_is_idempotent_and_preserves_admin_changes(self):
        series_count = AssessmentSeries.objects.count()
        level_count = AssessmentLevel.objects.count()
        group_count = Group.objects.count()

        first_output = self.run_bootstrap()
        counts = {
            'assessment_types': AssessmentType.objects.count(),
            'feedback_categories': FeedbackCategory.objects.count(),
            'forum_post_types': ForumPostType.objects.count(),
            'countdown_event_types': CountdownEventType.objects.count(),
            'conduct_items': ConductItem.objects.count(),
            'parser_configs': ScoringParserConfig.objects.count(),
        }

        site_config = SiteConfig.objects.get(pk=1)
        site_config.site_name = '管理员站点名'
        site_config.save()
        about_page = FlatPage.objects.get(url='/about/site/')
        about_page.content = '管理员维护的页面内容'
        about_page.save()
        assessment_type = AssessmentType.objects.get(code='mock')
        assessment_type.name = '管理员自定义模拟赛'
        assessment_type.is_active = False
        assessment_type.save()
        FeedbackCategory.objects.filter(code='complaint').update(default_private=False)
        ForumPostType.objects.filter(code='official_reply').update(is_official=False)
        CountdownEventType.objects.filter(code='training').update(is_active=False)
        ConductItem.objects.filter(category__code='attendance', code='late').update(
            default_score='-9.00'
        )
        parser_config = ScoringParserConfig.objects.get(parser_key='cmp_single_module_v1')
        parser_config.is_enabled = False
        parser_config.is_default = False
        parser_config.save()

        second_output = self.run_bootstrap()

        self.assertIn('TMS 默认业务目录初始化完成。', first_output)
        self.assertIn('created=0', second_output)
        self.assertEqual(SiteConfig.objects.get(pk=1).site_name, '管理员站点名')
        self.assertEqual(FlatPage.objects.get(url='/about/site/').content, '管理员维护的页面内容')
        assessment_type.refresh_from_db()
        self.assertEqual(assessment_type.name, '管理员自定义模拟赛')
        self.assertFalse(assessment_type.is_active)
        self.assertFalse(FeedbackCategory.objects.get(code='complaint').default_private)
        self.assertFalse(ForumPostType.objects.get(code='official_reply').is_official)
        self.assertFalse(CountdownEventType.objects.get(code='training').is_active)
        self.assertEqual(
            ConductItem.objects.get(category__code='attendance', code='late').default_score,
            -9,
        )
        parser_config.refresh_from_db()
        self.assertFalse(parser_config.is_enabled)
        self.assertFalse(parser_config.is_default)
        self.assertEqual(
            counts,
            {
                'assessment_types': AssessmentType.objects.count(),
                'feedback_categories': FeedbackCategory.objects.count(),
                'forum_post_types': ForumPostType.objects.count(),
                'countdown_event_types': CountdownEventType.objects.count(),
                'conduct_items': ConductItem.objects.count(),
                'parser_configs': ScoringParserConfig.objects.count(),
            },
        )
        self.assertEqual(AssessmentSeries.objects.count(), series_count)
        self.assertEqual(AssessmentLevel.objects.count(), level_count)
        self.assertEqual(Group.objects.count(), group_count)

    def test_catalog_collision_rolls_back_every_app(self):
        SiteConfig.objects.all().delete()
        FlatPage.objects.filter(url__in=['/about/site/', '/about/author/']).delete()
        CompetitionRole.objects.filter(code='project_manager').delete()
        FeedbackCategory.objects.filter(code='bug').delete()
        FeedbackCategory.objects.create(code='conflicting-bug', name='Bug反馈')

        with self.assertRaises(ValidationError):
            self.run_bootstrap()

        self.assertFalse(SiteConfig.objects.exists())
        self.assertFalse(FlatPage.objects.filter(url__in=['/about/site/', '/about/author/']).exists())
        self.assertFalse(CompetitionRole.objects.filter(code='project_manager').exists())
