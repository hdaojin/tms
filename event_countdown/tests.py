from datetime import timedelta

from django.contrib.admin.sites import AdminSite
from django.core.cache import cache
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import SiteConfig

from .admin import CountdownEventAdmin, CountdownEventAdminForm
from core.bootstrap_engine import bootstrap_defaults
from .models import CountdownEvent, CountdownEventType
from .themes import COUNTDOWN_THEMES, DEFAULT_THEME_KEY


class CountdownEventCatalogAdminTests(TestCase):
    def setUp(self):
        bootstrap_defaults()

    def test_model_has_no_implicit_type_default_and_admin_prefills_active_other(self):
        self.assertFalse(CountdownEvent._meta.get_field('event_type').has_default())
        other_type = CountdownEventType.objects.get(code='other')
        model_admin = CountdownEventAdmin(CountdownEvent, AdminSite())

        initial = model_admin.get_changeform_initial_data(
            RequestFactory().get('/admin/event_countdown/countdownevent/add/')
        )

        self.assertEqual(initial['event_type'], other_type.pk)

    def test_admin_form_excludes_inactive_type_but_keeps_current_historical_value(self):
        inactive_type = CountdownEventType.objects.create(
            code='historical-event',
            name='历史事件',
            is_active=False,
        )
        self.assertNotIn(inactive_type, CountdownEventAdminForm().fields['event_type'].queryset)

        event = CountdownEvent.objects.create(
            name='历史倒计时',
            event_type=inactive_type,
            target_at=timezone.now() + timedelta(days=1),
        )
        self.assertIn(
            inactive_type,
            CountdownEventAdminForm(instance=event).fields['event_type'].queryset,
        )


class CountdownEventViewTests(TestCase):
    def setUp(self):
        bootstrap_defaults()

    def make_event(self, **kwargs):
        defaults = {
            'name': '测试倒计时事件',
            'slug': 'test-countdown',
            'subtitle': '测试倒计时',
            'event_type': CountdownEventType.objects.get(code='training'),
            'target_at': timezone.now() + timedelta(days=7),
            'is_active': True,
            'display_order': 10,
        }
        defaults.update(kwargs)
        return CountdownEvent.objects.create(**defaults)

    def test_countdown_index_is_public_and_shows_empty_state_without_event(self):
        response = self.client.get(reverse('event_countdown:countdown'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '暂无启用倒计时事件')

    def test_countdown_index_uses_first_active_event_by_order_and_target_time(self):
        later = timezone.now() + timedelta(days=20)
        earlier = timezone.now() + timedelta(days=10)
        self.make_event(name='排序靠后事件', slug='late', target_at=earlier, display_order=20)
        self.make_event(name='排序优先事件', slug='first', target_at=later, display_order=5)

        response = self.client.get(reverse('event_countdown:countdown'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '排序优先事件')
        self.assertNotContains(response, '排序靠后事件')

    def test_countdown_slug_shows_active_event(self):
        event = self.make_event(name='Slug 指定事件', slug='slug-event')

        response = self.client.get(reverse('event_countdown:countdown_detail', kwargs={'slug': event.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Slug 指定事件')

    def test_countdown_slug_returns_404_for_missing_or_inactive_event(self):
        self.make_event(slug='inactive-event', is_active=False)

        missing_response = self.client.get(
            reverse('event_countdown:countdown_detail', kwargs={'slug': 'missing-event'})
        )
        inactive_response = self.client.get(
            reverse('event_countdown:countdown_detail', kwargs={'slug': 'inactive-event'})
        )

        self.assertEqual(missing_response.status_code, 404)
        self.assertEqual(inactive_response.status_code, 404)

    def test_blank_messages_use_template_fallbacks(self):
        self.make_event(
            countdown_prefix='',
            finished_message='',
            target_at=timezone.now() - timedelta(days=1),
        )

        response = self.client.get(reverse('event_countdown:countdown'))

        self.assertContains(response, '距离开始还有')
        self.assertContains(response, '活动已经开始')
        self.assertIn('+', response.context['target_at_iso'])

    def test_countdown_uses_dynamic_event_fields_for_network_theme(self):
        target_at = timezone.now() + timedelta(days=365)
        event = self.make_event(
            name='云计算项目备战倒计时',
            subtitle='全国技能大赛冲刺',
            event_type=CountdownEventType.objects.get(code='national'),
            project_name='云平台运维项目',
            project_english_name='Cloud Platform Operations',
            location='广东深圳',
            target_at=target_at,
        )

        response = self.client.get(reverse('event_countdown:countdown_detail', kwargs={'slug': event.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '云平台运维项目')
        self.assertContains(response, 'Cloud Platform Operations')
        self.assertContains(response, '全国技能大赛冲刺')
        self.assertContains(response, '云计算项目备战倒计时')
        self.assertContains(response, f'广东深圳 · {timezone.localtime(target_at).year} · 全国技能大赛')
        self.assertContains(response, 'images/countdown/network-command-center-bg.png')
        self.assertNotContains(response, 'Training Management System')
        self.assertNotContains(response, 'NETWORK SYSTEM MANAGEMENT')
        self.assertNotContains(response, '上海 2026 · 第48届世界技能大赛')
        self.assertNotContains(response, 'https://fonts.googleapis.com')
        self.assertNotContains(response, 'https://')

    def test_blank_project_english_name_hides_hardcoded_english_heading(self):
        event = self.make_event(project_english_name='')

        response = self.client.get(reverse('event_countdown:countdown_detail', kwargs={'slug': event.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'NETWORK SYSTEM MANAGEMENT')

    def test_network_theme_keywords_render_configured_icons(self):
        self.make_event()

        response = self.client.get(reverse('event_countdown:countdown'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['theme_keywords'], COUNTDOWN_THEMES[DEFAULT_THEME_KEY]['keywords'])
        self.assertContains(response, 'icon-[mdi--linux]')
        self.assertContains(response, 'icon-[mdi--microsoft-windows]')
        self.assertContains(response, 'Linux')
        self.assertContains(response, 'Windows Server')
        self.assertNotContains(response, 'icon-[tabler--hexagon-letter-n]')

    def test_countdown_footer_uses_site_config_values(self):
        created_at = timezone.datetime(2024, 1, 1, tzinfo=timezone.get_current_timezone())
        site_info, _created = SiteConfig.objects.update_or_create(
            id=1,
            defaults={
                'site_name': 'TMS',
                'site_short_name': 'TMS',
                'site_author': 'hdaojin',
                'site_author_link': 'http://127.0.0.1:8000/',
                'site_copyright': 'TMS 版权所有',
            },
        )
        SiteConfig.objects.filter(id=site_info.id).update(created_at=created_at)
        cache.delete('site_config_solo')
        self.make_event()

        response = self.client.get(reverse('event_countdown:countdown'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'&copy; 2024 -{timezone.now().year} TMS 版权所有.')
        self.assertContains(response, 'href="http://127.0.0.1:8000/"')
        self.assertContains(response, 'HDAOJIN')
        self.assertNotContains(response, 'Competition Countdown')

    def test_unknown_theme_falls_back_to_network_theme(self):
        self.make_event(theme='missing-theme')

        response = self.client.get(reverse('event_countdown:countdown'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['active_theme'], COUNTDOWN_THEMES[DEFAULT_THEME_KEY])
        self.assertContains(response, 'images/countdown/network-command-center-bg.png')
