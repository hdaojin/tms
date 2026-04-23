from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse


class SiteRobotsDirectiveTests(TestCase):
    """站点应通过 robots.txt 与 meta 指令禁止搜索引擎收录。"""

    def test_robots_txt_is_public_and_blocks_all_crawlers(self):
        response = self.client.get(reverse("robots_txt"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/plain"))
        self.assertContains(response, "User-agent: *")
        self.assertContains(response, "Disallow: /")

    def test_homepage_includes_noindex_meta_tags(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            '<meta name="robots" content="noindex, nofollow" />',
            html=True,
        )
        self.assertContains(
            response,
            '<meta name="googlebot" content="noindex, nofollow" />',
            html=True,
        )


class InternalCutoverOrchestratorCommandTests(TestCase):
    def test_reconcile_internal_app_cutovers_is_noop_for_current_state(self):
        output = StringIO()

        call_command("reconcile_internal_app_cutovers", stdout=output)

        value = output.getvalue()
        self.assertIn("cutover_assessment_to_assessments", value)
        self.assertIn("当前数据库与文件目录已经使用 assessments，无需切换。", value)
        self.assertIn("当前数据库与文件目录已经使用 behaviors，无需切换。", value)
        self.assertIn("当前数据库与文件目录已经使用 meetings，无需切换。", value)
        self.assertIn("以上为统一预检查结果。确认无误后，请追加 --execute 执行实际收尾。", value)

    @patch("core.management.commands.reconcile_internal_app_cutovers.subprocess.run")
    def test_reconcile_internal_app_cutovers_runs_migrate_in_fresh_process(self, mock_run):
        output = StringIO()
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "No migrations to apply.\n"
        mock_run.return_value.stderr = ""

        call_command("reconcile_internal_app_cutovers", execute=True, stdout=output)

        mock_run.assert_called_once()
        command = mock_run.call_args.args[0]
        self.assertEqual(command[1:], ["manage.py", "migrate", "--database=default"])
        value = output.getvalue()
        self.assertIn("==> migrate", value)
        self.assertIn("No migrations to apply.", value)
        self.assertIn("内部切换收尾与 migrate 已执行完成。", value)