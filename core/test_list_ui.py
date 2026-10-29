from pathlib import Path

from bs4 import BeautifulSoup
from django import forms
from django.conf import settings
from django.template import Context, Engine
from django.template.loader import render_to_string
from django.test import SimpleTestCase


class ListPageTemplateTests(SimpleTestCase):
    def setUp(self):
        # 隔离外层导航，仅验证真实公共列表模板的继承和区域边界。
        templates = {
            "layouts/app.html": "{% block content %}{% endblock %}",
            "common/table_page.html": (Path(settings.BASE_DIR) / "templates/common/table_page.html").read_text(
                encoding="utf-8"
            ),
            "components/table_wrapper.html": '<section data-test-table>结果</section>',
            "components/list_filter_toolbar.html": '<form method="get" data-test-filters>筛选</form>',
            "legacy.html": '{% extends "common/table_page.html" %}{% block content %}<a>新增</a>{{ block.super }}{% endblock %}',
            "slots.html": (
                '{% extends "common/table_page.html" %}'
                '{% block list_filters %}<div>专用筛选</div>{% endblock %}'
                '{% block list_bulk_actions %}<div>批量操作</div>{% endblock %}'
                '{% block list_table %}<div>自定义矩阵</div>{% endblock %}'
            ),
        }
        self.engine = Engine(loaders=[("django.template.loaders.locmem.Loader", templates)])

    def test_default_page_has_no_empty_filters_bulk_form_or_selection(self):
        html = self.engine.get_template("common/table_page.html").render(Context())
        soup = BeautifulSoup(html, "html.parser")
        self.assertIsNotNone(soup.select_one("#list-results [data-test-table]"))
        self.assertIsNone(soup.find("form"))
        self.assertIsNone(soup.find("input"))

    def test_filters_are_outside_result_container_and_legacy_content_is_preserved(self):
        html = self.engine.get_template("legacy.html").render(Context({"list_filter_controls": ["q"]}))
        soup = BeautifulSoup(html, "html.parser")
        results = soup.select_one("#list-results")
        self.assertEqual(soup.find("a").get_text(), "新增")
        self.assertIsNotNone(soup.select_one("[data-test-filters]"))
        self.assertIsNone(results.find("form"))
        self.assertLess(html.index("新增"), html.index("筛选"))
        self.assertLess(html.index("筛选"), html.index("结果"))

    def test_independent_blocks_keep_three_area_order_and_support_custom_results(self):
        html = self.engine.get_template("slots.html").render(Context({"list_filter_target_id": "records-results"}))
        soup = BeautifulSoup(html, "html.parser")
        self.assertIsNotNone(soup.select_one("#records-results"))
        self.assertLess(html.index("专用筛选"), html.index("批量操作"))
        self.assertLess(html.index("批量操作"), html.index("自定义矩阵"))
        self.assertIsNone(soup.select_one("[data-test-table]"))


class BulkToolbarTests(SimpleTestCase):
    class ActionForm(forms.Form):
        operation = forms.ChoiceField(
            label="操作",
            choices=[("", "请选择操作"), ("export", "导出")],
            widget=forms.Select(attrs={"data-bulk-operation": ""}),
        )

    def render_toolbar(self, **kwargs):
        html = render_to_string(
            "components/list_bulk_actions.html",
            {
                "operation_field": self.ActionForm()["operation"],
                "matching_count": 25,
                **kwargs,
            },
        )
        return BeautifulSoup(html, "html.parser")

    def test_default_toolbar_is_generic_and_does_not_create_a_post_form(self):
        soup = self.render_toolbar()
        self.assertIsNone(soup.find("form"))
        self.assertIsNone(soup.select_one("[data-select-all]"))
        self.assertEqual(soup.select_one("[data-selection-mode]")["name"], "selection")
        self.assertEqual(soup.select_one("[data-selection-mode]")["value"], "selected")
        self.assertEqual(soup.select_one("[data-selection-status]").get_text(), "已选择 0 条记录")
        self.assertIsNotNone(soup.select_one("select[data-bulk-operation]"))

    def test_backend_explicitly_enables_all_matching_and_business_labels(self):
        soup = self.render_toolbar(allow_select_all=True, selection_label="位用户", selection_name="target_mode")
        self.assertTrue(soup.select_one("[data-select-all]").has_attr("hidden"))
        self.assertIn("25 位用户", soup.select_one("[data-select-all]").get_text())
        self.assertEqual(soup.select_one("[data-selection-mode]")["name"], "target_mode")

    def test_empty_results_disable_execution_and_omit_all_matching(self):
        soup = self.render_toolbar(matching_count=0, allow_select_all=True)
        self.assertTrue(soup.select_one('button[type="submit"]').has_attr("disabled"))
        self.assertIsNone(soup.select_one("[data-select-all]"))
