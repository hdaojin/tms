from types import SimpleNamespace
from unittest.mock import patch

from bs4 import BeautifulSoup
from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase
from django.urls import NoReverseMatch, resolve, reverse, reverse_lazy
from django.views.generic import TemplateView

from core.utils.breadcrumbs import Breadcrumb, breadcrumb_link, build_breadcrumbs
from core.utils.mixins import TitleMixin


class BreadcrumbTests(SimpleTestCase):
    def request(self, permissions=()):
        request = RequestFactory().get(reverse('training:cycle_list'))
        request.resolver_match = resolve(request.path)
        request.user = SimpleNamespace(
            is_authenticated=True,
            is_staff=False,
            is_superuser=False,
            has_perms=lambda required: set(required) <= set(permissions),
        )
        return request

    def test_home_section_and_current(self):
        crumbs = build_breadcrumbs(self.request(['training.view_trainingcycle']), '训练周期')
        self.assertEqual([item.label for item in crumbs], ['首页', '训练', '训练周期'])
        self.assertEqual(crumbs[0].url, reverse('home'))
        self.assertEqual(crumbs[1].url, reverse('training:cycle_list'))
        self.assertIsNone(crumbs[-1].url)

    def test_section_uses_only_visible_navigation(self):
        request = self.request(['training.view_trainingplan'])
        crumbs = build_breadcrumbs(request, '我的计划')
        self.assertEqual(crumbs[1].url, reverse('training:plan_list'))
        self.assertEqual([c.label for c in build_breadcrumbs(self.request(), '页面')], ['首页', '页面'])
        request.user = AnonymousUser()
        self.assertEqual([c.label for c in build_breadcrumbs(request, '页面')], ['首页', '页面'])

    def test_adjacent_duplicates_keep_current_non_clickable(self):
        crumbs = build_breadcrumbs(None, '相同', [Breadcrumb('相同', '/first/'), Breadcrumb('相同', '/last/')])
        self.assertEqual([c.label for c in crumbs], ['首页', '相同'])
        self.assertIsNone(crumbs[-1].url)
        crumbs = build_breadcrumbs(None, '甲', [Breadcrumb('甲'), Breadcrumb('乙')])
        self.assertEqual([c.label for c in crumbs], ['首页', '甲', '乙', '甲'])

    def test_missing_request_title_resolver_and_reverse(self):
        self.assertEqual(build_breadcrumbs(None, None), [])
        request = RequestFactory().get('/unmatched/')
        self.assertEqual([c.label for c in build_breadcrumbs(request, '页面')], ['首页', '页面'])
        self.assertIsNone(breadcrumb_link('缺失', 'missing:route').url)
        crumbs = build_breadcrumbs(None, '页面', [Breadcrumb('缺失', reverse_lazy('missing:route'))])
        self.assertIsNone(crumbs[1].url)
        with patch('core.utils.breadcrumbs.reverse', side_effect=NoReverseMatch):
            self.assertIsNone(build_breadcrumbs(None, '页面')[0].url)

    def test_dynamic_title_and_cooperative_context(self):
        class Page(TitleMixin, TemplateView):
            title = '{name}'
            breadcrumb_parents = (Breadcrumb('父级'),)

            def get_context_data(self, **kwargs):
                context = super().get_context_data(**kwargs)
                context['preserved'] = True
                return context

        view = Page()
        view.object = SimpleNamespace(name='动态名称')
        context = view.get_context_data()
        self.assertTrue(context['preserved'])
        self.assertEqual(context['breadcrumbs'][-1].label, '动态名称')
        context = view.get_context_data()
        context['title'] = '最终标题'
        self.assertEqual(context['breadcrumbs'][-1].label, '最终标题')
        view.show_breadcrumbs = False
        with patch.object(view, 'get_breadcrumb_parents', side_effect=AssertionError):
            self.assertEqual(view.get_context_data()['breadcrumbs'], [])

    def test_template_accessibility_and_standard_links(self):
        html = render_to_string('partials/breadcrumbs.html', {'breadcrumbs': build_breadcrumbs(None, '当前页面')})
        soup = BeautifulSoup(html, 'html.parser')
        nav = soup.select_one('nav[aria-label="面包屑"]')
        self.assertIsNotNone(nav)
        self.assertIn('overflow-x-auto', nav['class'])
        self.assertEqual(nav.select_one('.sr-only').text, '首页')
        current = nav.select_one('[aria-current="page"]')
        self.assertEqual(current.text, '当前页面')
        self.assertIsNone(current.find_parent('a'))
        self.assertNotIn('hx-get', html)
        self.assertNotIn('x-data', html)
