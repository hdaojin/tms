from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from bs4 import BeautifulSoup
from django.conf import settings
from django.template import Context, Template
from django.template.loader import render_to_string
from django.test import SimpleTestCase
from django.utils.html import strip_tags

from core.tables import BaseDateColumn, BaseDateTimeColumn, BaseTable
from core.templatetags.date_display import keep_date_parts
from training.tables import TrainingLogTable


class DateDisplayTests(SimpleTestCase):
    def test_date_and_time_are_separate_complete_parts(self):
        html = keep_date_parts("2026-06-25 15:11:43")
        soup = BeautifulSoup(html, "html.parser")
        self.assertEqual([part.text for part in soup.select('.date-part')], ["2026-06-25", "15:11:43"])
        self.assertEqual(soup.get_text(), "2026-06-25 15:11:43")
        self.assertEqual(strip_tags(keep_date_parts("2026年06月25日 15:11")), "2026年06月25日 15:11")

    def test_escaping_and_missing_values(self):
        self.assertNotIn("<script>", keep_date_parts("<script>alert(1)</script>"))
        self.assertEqual(keep_date_parts(None), "")
        self.assertEqual(keep_date_parts(""), "")

    def test_shared_columns_preserve_local_time_format_and_export_values(self):
        class Table(BaseTable):
            day = BaseDateColumn()
            instant = BaseDateTimeColumn()
            minute = BaseDateTimeColumn(format="Y-m-d H:i")

        instant = datetime(2026, 6, 25, 7, 11, 43, tzinfo=timezone.utc)
        table = Table(
            [
                {"day": date(2026, 6, 25), "instant": instant, "minute": instant},
                {"day": None, "instant": None, "minute": None},
            ]
        )
        row = table.rows[0]
        self.assertEqual(strip_tags(row.get_cell("day")), "2026-06-25")
        self.assertEqual(strip_tags(row.get_cell("instant")), "2026-06-25 15:11:43")
        self.assertEqual(strip_tags(row.get_cell("minute")), "2026-06-25 15:11")
        self.assertIn('class="date-part"', row.get_cell("instant"))
        self.assertEqual(row.get_cell_value("instant"), instant.isoformat(sep=" "))
        self.assertNotIn("date-part", table.rows[1].get_cell("instant"))

    def test_localized_bare_datetime_and_default_are_preserved(self):
        value = datetime(2026, 6, 25, 7, 11, 43, tzinfo=timezone.utc)
        original = Template("{{ value }}").render(Context({"value": value}))
        wrapped = Template("{% load date_display %}{{ value|keep_date_parts }}").render(Context({"value": value}))
        self.assertEqual(strip_tags(wrapped), original)
        missing = Template('{% load date_display %}{{ value|default:"未设置"|keep_date_parts }}')
        self.assertEqual(strip_tags(missing.render(Context({"value": None}))), "未设置")

    def test_backfill_highlight_and_accessible_label(self):
        value = datetime(2026, 6, 25, 7, 11, tzinfo=timezone.utc)
        for backfill in (False, True):
            html = TrainingLogTable([]).render_created_at(value, SimpleNamespace(is_backfill=backfill))
            soup = BeautifulSoup(html, "html.parser")
            self.assertEqual(len(soup.select('.date-part')), 2)
            self.assertEqual(bool(soup.select('.text-warning')), backfill)
            if backfill:
                self.assertEqual(
                    soup.select_one('.text-warning')['aria-label'], '历史补交日志，提交时间2026-06-25 15:11'
                )

    def test_record_timestamps_and_frontend_date_templates_compile(self):
        html = render_to_string("components/record_timestamps.html", {"created_at": None, "updated_at": None})
        self.assertEqual(BeautifulSoup(html, "html.parser").get_text().count("—"), 2)
        for path in Path(settings.BASE_DIR).rglob('*.html'):
            if 'templates' in path.parts and not any(
                part.startswith('.') or part in {'node_modules', 'backups', 'archives'} for part in path.parts
            ):
                if '|keep_date_parts' in path.read_text(encoding='utf-8'):
                    relative = path.relative_to(next(parent for parent in path.parents if parent.name == 'templates'))
                    with self.subTest(template=str(relative)):
                        Template(path.read_text(encoding='utf-8'))
