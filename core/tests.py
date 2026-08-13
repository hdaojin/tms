from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import django_tables2 as tables
from django.contrib.flatpages.models import FlatPage
from django.contrib.sites.models import Site
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db.migrations.writer import MigrationWriter
from django.template import Context, Template
from django.test import RequestFactory, TestCase, override_settings
from django.urls import resolve, reverse

from accounts.services.permission_bundles import sync_user_permission_bundles
from accounts.models import GroupProfile
from behaviors.models import ConductSummary
from core import navigation
from core.forms.fields import MultipleFileField
from core.uploads import (
    CONDUCT_ATTACHMENT_UPLOAD_SPEC,
    MEETING_FILE_UPLOAD_SPEC,
    NOTICE_ATTACHMENT_UPLOAD_SPEC,
    FileUploadMixin,
    PrivateMediaStorage,
    UploadSignatureValidator,
    UploadSizeValidator,
    UploadSpec,
    format_file_size,
    get_file_icon_class,
    is_image_file,
    validate_upload_file,
)
from core.tables import ActionsColumn, BaseTable
from core.utils.admin_deletion import discard_registered_delete_permissions, register_delete_permission_exemptions
from core.permissions.roles import ROLE_COACH, ROLE_COMPETITOR, get_user_role_codenames
from core.utils.mixins import CrossGroupAccessMixin


User = get_user_model()
PDF_BYTES = b"%PDF-1.7\n% test pdf\n"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
ZIP_BYTES = b"PK\x03\x04" + b"\x00" * 16
JSON_BYTES = b'{"ok": true}'


class RoleCodenameAccessTests(TestCase):
    def setUp(self):
        self.coach_group = Group.objects.create(name="教练显示名")
        GroupProfile.objects.create(group=self.coach_group, codename=ROLE_COACH)
        self.competitor_group = Group.objects.create(name="选手显示名")
        GroupProfile.objects.create(group=self.competitor_group, codename=ROLE_COMPETITOR)
        self.coach = User.objects.create_user(username="role-coach", password="testpass123")
        self.coach.groups.add(self.coach_group)
        self.competitor = User.objects.create_user(username="role-competitor", password="testpass123")
        self.competitor.groups.add(self.competitor_group)

    def test_role_lookup_uses_profile_codename_and_is_one_query(self):
        with self.assertNumQueries(1):
            roles = get_user_role_codenames(self.coach)

        self.assertSetEqual(roles, {ROLE_COACH})

        self.coach_group.name = "任意新的教练显示名称"
        self.coach_group.save(update_fields=["name"])
        self.assertSetEqual(get_user_role_codenames(self.coach), {ROLE_COACH})

    def test_cross_group_access_uses_stable_codenames_and_handles_missing_profile(self):
        class AccessProbe(CrossGroupAccessMixin):
            pass

        probe = AccessProbe()
        probe.request = SimpleNamespace(user=self.competitor)
        obj = SimpleNamespace(uploaded_by=self.coach)
        self.assertTrue(probe.check_cross_group_access(obj))

        self.competitor_group.name = "选手的新显示名称"
        self.competitor_group.save(update_fields=["name"])
        self.assertTrue(probe.check_cross_group_access(obj))

        unprofiled_group = Group.objects.create(name="没有 profile 的历史组")
        unprofiled_user = User.objects.create_user(username="unprofiled-user", password="testpass123")
        unprofiled_user.groups.add(unprofiled_group)
        probe.request = SimpleNamespace(user=unprofiled_user)
        self.assertFalse(probe.check_cross_group_access(obj))


class DeletePermissionExemptionRegistryTests(TestCase):
    def test_registered_source_model_discards_registered_target_permission(self):
        register_delete_permission_exemptions(
            "auth.User",
            ["behaviors.ConductSummary"],
        )
        user = User(username="registry-user")
        perms_needed = {str(ConductSummary._meta.verbose_name), "其他模型"}

        discard_registered_delete_permissions([user], perms_needed)

        self.assertSetEqual(perms_needed, {"其他模型"})

    def test_unregistered_source_model_keeps_permission_set_unchanged(self):
        group = Group(name="registry-group")
        perms_needed = {str(ConductSummary._meta.verbose_name)}

        discard_registered_delete_permissions([group], perms_needed)

        self.assertSetEqual(perms_needed, {str(ConductSummary._meta.verbose_name)})


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


class NavigationConfigCacheTests(TestCase):
    def tearDown(self):
        cache.clear()
        super().tearDown()

    @override_settings(CACHE_TIMEOUT=10)
    @patch("core.navigation.yaml.safe_load", return_value={"themes": ["light"]})
    @patch("core.navigation.cache.set")
    @patch("core.navigation.cache.get", return_value=None)
    def test_load_config_uses_global_cache_timeout(self, mock_cache_get, mock_cache_set, mock_safe_load):
        config = navigation._load_config()

        self.assertEqual(config, {"themes": ["light"]})
        mock_cache_get.assert_called_once_with("tms:navigation:v1:config")
        mock_cache_set.assert_called_once_with(
            "tms:navigation:v1:config",
            {"themes": ["light"]},
            timeout=10,
        )
        mock_safe_load.assert_called_once()


class MobileNavigationTemplateTests(TestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

    def _render_menu_tag(self, source: str, path: str, user) -> str:
        request = self.factory.get(path)
        request.user = user
        request.resolver_match = resolve(request.path)
        return Template(source).render(Context({"request": request}))

    def _grant_permissions(self, user, *permission_codes: str):
        permissions = []
        for permission_code in permission_codes:
            app_label, _, codename = permission_code.partition(".")
            permissions.append(
                Permission.objects.get(
                    content_type__app_label=app_label,
                    codename=codename,
                )
            )
        user.user_permissions.add(*permissions)
        return User.objects.get(pk=user.pk)

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def test_render_mobile_navigation_shows_current_section_and_permitted_nested_items(self):
        user = User.objects.create_user(username="mobile-nav-user", password="testpass123")
        sync_user_permission_bundles(user, ["training.maintain_training"])

        request = self.factory.get(reverse("training:log_upload"))
        request.user = user
        request.resolver_match = resolve(request.path)

        html = Template("{% load menu_tags %}{% render_mobile_navigation %}").render(
            Context({"request": request})
        )

        self.assertIn("当前位于“训练”", html)
        self.assertIn("训练日志", html)
        self.assertIn("提交统计", html)

    def test_render_mobile_navigation_hides_notice_create_without_permission(self):
        user = User.objects.create_user(username="notice-nav-user", password="testpass123")

        request = self.factory.get(reverse("notices:notice_list"))
        request.user = user
        request.resolver_match = resolve(request.path)

        html = Template("{% load menu_tags %}{% render_mobile_navigation %}").render(
            Context({"request": request})
        )

        self.assertIn("通知公告列表", html)
        self.assertNotIn("创建通知公告", html)

    def test_render_mobile_navigation_shows_notice_create_with_publish_bundle(self):
        user = User.objects.create_user(username="notice-nav-editor", password="testpass123")
        sync_user_permission_bundles(user, ["notices.publish_notice"])
        user = User.objects.get(pk=user.pk)

        request = self.factory.get(reverse("notices:notice_list"))
        request.user = user
        request.resolver_match = resolve(request.path)

        html = Template("{% load menu_tags %}{% render_mobile_navigation %}").render(
            Context({"request": request})
        )

        self.assertIn("创建通知公告", html)

    def test_render_mobile_navigation_shows_node_list_but_hides_new_permissioned_entries_without_permissions(self):
        user = User.objects.create_user(username="menu-default-user", password="testpass123")

        html = self._render_menu_tag(
            "{% load menu_tags %}{% render_mobile_navigation %}",
            reverse("accounts:home"),
            user,
        )

        self.assertIn("技能节点", html)
        self.assertIn(f'href="{reverse("samba:accounts")}"', html)
        for label in [
            "新增训练周期",
            "上传训练日志",
            "新增赛事系列",
            "新增赛事级别",
            "新增事件",
            "新增事件模块",
            "新增参与人员",
            "导入评分表",
            "新增参评对象",
            "录入评分结果",
            "新增技能项目",
            "新增能力领域",
            "新增标准技能树版本",
            "新增技能节点",
            "新增技能映射",
            "上传资料资产",
            "新增试题",
            "新增试题要求",
            "新增考点证据",
            "上传会议记录",
            "录入奖惩记录",
        ]:
            self.assertNotIn(label, html)

    def test_render_mobile_navigation_shows_new_permissioned_entries_when_allowed(self):
        user = User.objects.create_user(username="menu-privileged-user", password="testpass123")
        user = self._grant_permissions(
            user,
            "training.add_trainingcycle",
            "training.add_traininglog",
            "events.add_competitionseries",
            "events.add_competitionlevel",
            "events.add_event",
            "events.add_eventmodule",
            "events.add_eventparticipant",
            "scoring.add_scoringscheme",
            "scoring.add_scoringparticipant",
            "scoring.add_scoringresult",
            "standards.add_skillproject",
            "standards.add_capabilitydomain",
            "standards.add_skilltreeversion",
            "standards.add_skillnode",
            "archives.add_archiveasset",
            "examcontent.add_exampaper",
            "examcontent.add_examrequirement",
            "knowledge.add_knowledgeevidence",
            "knowledge.add_knowledgeevidenceskillmap",
            "meetings.add_meeting",
            "behaviors.add_conduct_record",
        )

        html = self._render_menu_tag(
            "{% load menu_tags %}{% render_mobile_navigation %}",
            reverse("accounts:home"),
            user,
        )

        for label in [
            "新增训练周期",
            "上传训练日志",
            "新增赛事系列",
            "新增赛事级别",
            "新增事件",
            "新增事件模块",
            "新增参与人员",
            "导入评分表",
            "新增参评对象",
            "录入评分结果",
            "新增技能项目",
            "新增能力领域",
            "新增标准技能树版本",
            "技能节点",
            "新增技能节点",
            "新增技能映射",
            "上传资料资产",
            "新增试题",
            "新增试题要求",
            "新增考点证据",
            "上传会议记录",
            "录入奖惩记录",
        ]:
            self.assertIn(label, html)

    def test_render_sections_cards_keeps_dashboard_members_unchanged(self):
        user = User.objects.create_user(username="dashboard-nav-user", password="testpass123")

        html = self._render_menu_tag(
            "{% load menu_tags %}{% render_sections_cards %}",
            reverse("accounts:home"),
            user,
        )

        for label in ["通知", "会议", "训练", "竞赛", "标准", "资料", "奖惩"]:
            self.assertIn(label, html)
        for hidden_label in ["账户", "关于"]:
            self.assertNotIn(hidden_label, html)

    def test_mobile_navigation_marks_reorganized_business_sections_active(self):
        user = User.objects.create_user(username="business-section-user", password="testpass123")

        expected_sections = [
            (reverse("standards:project_list"), "标准"),
            (reverse("knowledge:evidence_list"), "标准"),
            (reverse("archives:asset_list"), "资料"),
            (reverse("notes:repo_list"), "资料"),
            (reverse("examcontent:paper_list"), "竞赛"),
            (reverse("scoring:scheme_list"), "竞赛"),
        ]
        for path, label in expected_sections:
            with self.subTest(path=path, label=label):
                html = self._render_menu_tag(
                    "{% load menu_tags %}{% render_mobile_navigation %}",
                    path,
                    user,
                )

                self.assertIn(f"当前位于“{label}”", html)

    def test_authenticated_page_header_includes_mobile_navigation_trigger_and_panel(self):
        user = User.objects.create_user(username="mobile-nav-header", password="testpass123")
        self.client.force_login(user)

        response = self.client.get(reverse("accounts:home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-mobile-nav-trigger")
        self.assertContains(response, "data-mobile-nav-panel")

    def test_authenticated_page_keeps_horizontal_overflow_on_body_not_header(self):
        user = User.objects.create_user(username="mobile-nav-overflow", password="testpass123")
        self.client.force_login(user)

        response = self.client.get(reverse("accounts:home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'body class="flex min-h-dvh flex-col overflow-x-hidden bg-base-100 text-base-content"',
        )
        self.assertNotContains(
            response,
            'class="navbar sticky top-0 z-20 w-full max-w-full overflow-x-hidden',
        )

    def test_header_logout_button_uses_full_width_click_target(self):
        user = User.objects.create_user(username="logout-hit-area", password="testpass123")
        self.client.force_login(user)

        response = self.client.get(reverse("accounts:home"))
        html = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn('action="{}"'.format(reverse("accounts:logout")), html)
        self.assertIn('class="m-0 w-full"', html)
        self.assertIn("data-logout-button", html)
        self.assertIn("btn btn-ghost btn-block justify-start", html)


class PublicShellNavigationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()
        self.site, _created = Site.objects.get_or_create(
            id=1,
            defaults={"domain": "testserver", "name": "testserver"},
        )
        self.flatpage = FlatPage.objects.create(
            url="/about/site/",
            title="关于 TMS",
            content="<p>关于页面内容</p>",
            registration_required=False,
        )
        self.flatpage.sites.add(self.site)

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def test_flatpage_about_is_public_and_uses_public_shell(self):
        response = self.client.get("/about/site/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "关于页面内容")
        self.assertContains(response, "navbar sticky")
        self.assertContains(response, "tms-app-drawer")
        self.assertContains(response, "footer footer-center")

    def test_homepage_uses_full_screen_public_landing_without_navigation_shell(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "tms-home-hero")
        self.assertContains(response, "home-floating-footer")
        self.assertContains(response, "min-h-dvh")
        self.assertNotContains(response, "navbar sticky")
        self.assertNotContains(response, "tms-app-drawer")

    def test_auth_pages_render_top_navigation_and_footer_without_sidebar(self):
        for url in [reverse("accounts:login"), reverse("accounts:signup")]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "navbar sticky")
                self.assertContains(response, "footer footer-center")
                self.assertNotContains(response, "tms-app-drawer")
                self.assertNotContains(response, "data-mobile-nav-trigger")
                self.assertNotContains(response, "card card-border w-full max-w-md")

    def test_header_navigation_is_limited_to_primary_text_entries(self):
        user = User.objects.create_user(username="header-nav-user", password="testpass123")
        request = self.factory.get(reverse("accounts:home"))
        request.user = user
        request.resolver_match = resolve(request.path)

        html = Template("{% load menu_tags %}{% render_sections_nav %}").render(
            Context({"request": request})
        )

        for label in ["首页", "竞赛", "标准", "训练", "奖惩", "关于"]:
            self.assertIn(label, html)
        for hidden_label in ["通知", "会议", "资料"]:
            self.assertNotIn(hidden_label, html)
        self.assertNotIn("新架构", html)
        self.assertNotIn("icon-[", html)
        self.assertIn("menu menu-horizontal gap-1 font-semibold", html)

    def test_menu_active_uses_base_gray_tokens(self):
        css = (Path.cwd() / "static" / "css" / "main.css").read_text(encoding="utf-8")

        self.assertIn(".menu .menu-active", css)
        self.assertIn("--menu-active-bg: var(--color-base-200);", css)
        self.assertIn("--menu-active-fg: var(--color-base-content);", css)
        self.assertIn("background-color: var(--color-base-200);", css)
        self.assertIn("color: var(--color-base-content);", css)

    def test_sidebar_marks_only_current_leaf_active(self):
        user = User.objects.create_user(username="sidebar-active-user", password="testpass123")
        request = self.factory.get(reverse("training:monthly_stats"))
        request.user = user
        request.resolver_match = resolve(request.path)

        html = Template("{% load menu_tags %}{% render_section_menu_auto %}").render(
            Context({"request": request})
        )

        self.assertIn("<details open>", html)
        self.assertIn("提交统计", html)
        self.assertEqual(html.count("menu-active"), 1)


class ResponsiveTableTemplateTests(TestCase):
    def test_table_wrapper_does_not_reuse_page_title_as_section_title(self):
        html = Template('{% include "components/table_wrapper.html" %}').render(
            Context({"title": "奖惩记录列表"})
        )

        self.assertNotIn("奖惩记录列表", html)

    def test_table_wrapper_renders_explicit_table_title(self):
        html = Template('{% include "components/table_wrapper.html" %}').render(
            Context({"title": "页面标题", "table_title": "表格标题"})
        )

        self.assertIn("表格标题", html)
        self.assertNotIn("页面标题", html)

    def test_base_table_uses_daisyui_table_template(self):
        class DemoTable(BaseTable):
            name = tables.Column(verbose_name="名称")

            class Meta(BaseTable.Meta):
                pass

        table = DemoTable([{"name": "示例数据"}])
        request = RequestFactory().get(reverse("home"))

        html = Template("{% load django_tables2 %}{% render_table table %}").render(
            Context({"table": table, "request": request})
        )

        self.assertIn('class="table w-full"', html)


class ActionsColumnRenderingTests(TestCase):
    @patch("core.tables.reverse")
    def test_actions_column_renders_nowrap_buttons_with_mobile_gap(self, mock_reverse):
        mock_reverse.side_effect = lambda name, args: f"/{name}/{args[0]}/"

        class DummyMeta:
            app_label = "core"
            model_name = "dummy"

        record = SimpleNamespace(pk=7, _meta=DummyMeta())
        user = User.objects.create_user(username="actions-user", password="testpass123")
        table = SimpleNamespace(request=SimpleNamespace(user=user))
        column = ActionsColumn(view_url="core:view", edit_url="core:edit", delete_url="core:delete")

        html = column.render(None, record=record, table=table)

        self.assertIn("flex flex-col items-center gap-2 sm:flex-row sm:flex-wrap sm:justify-center", html)
        self.assertIn("btn btn-soft btn-primary btn-xs whitespace-nowrap", html)
        self.assertIn("btn btn-soft btn-warning btn-xs whitespace-nowrap", html)
        self.assertIn("btn btn-soft btn-error btn-xs whitespace-nowrap", html)


class InternalCutoverOrchestratorCommandTests(TestCase):
    def test_reconcile_internal_app_cutovers_is_noop_for_current_state(self):
        output = StringIO()

        call_command("reconcile_internal_app_cutovers", stdout=output)

        value = output.getvalue()
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


class UploadSpecTests(TestCase):
    def test_upload_spec_builds_accept_help_widget_attrs_and_validators(self):
        spec = UploadSpec(["pdf", ".docx"], 12)

        self.assertEqual(spec.accept, ".pdf,.docx")
        self.assertEqual(spec.help_text("上传资料"), "上传资料，支持 pdf, docx，大小不超过 12MB")
        self.assertEqual(spec.widget_attrs(type="file"), {"type": "file", "accept": ".pdf,.docx"})
        self.assertEqual(len(spec.validators()), 2)

    def test_upload_size_validator_reports_chinese_error(self):
        validator = UploadSizeValidator(1)
        upload = SimpleUploadedFile("large.pdf", b"x" * (1024 * 1024 + 1))

        with self.assertRaises(ValidationError) as context:
            validator(upload)

        self.assertIn("上传文件大小不能超过 1MB。", context.exception.messages)

    def test_upload_signature_validator_accepts_matching_common_file_headers(self):
        validator = UploadSignatureValidator()

        validator(SimpleUploadedFile("sample.pdf", PDF_BYTES))
        validator(SimpleUploadedFile("sample.png", PNG_BYTES))
        validator(SimpleUploadedFile("sample.xlsx", ZIP_BYTES))
        validator(SimpleUploadedFile("sample.json", JSON_BYTES))

    def test_upload_signature_validator_rejects_mismatched_file_header(self):
        validator = UploadSignatureValidator()

        with self.assertRaises(ValidationError) as context:
            validator(SimpleUploadedFile("fake.pdf", b"not a pdf"))

        self.assertIn("文件扩展名与实际文件类型不一致", context.exception.messages[0])

    def test_upload_signature_validator_restores_file_pointer(self):
        validator = UploadSignatureValidator()
        upload = SimpleUploadedFile("sample.pdf", PDF_BYTES + b"body")
        upload.seek(5)

        validator(upload)

        self.assertEqual(upload.tell(), 5)

    def test_private_media_storage_serializes_without_absolute_path(self):
        storage = PrivateMediaStorage("archives")

        serialized, _ = MigrationWriter.serialize(storage)

        self.assertIn("core.uploads.PrivateMediaStorage('archives')", serialized)
        self.assertNotIn(str(Path.cwd()), serialized)
        self.assertNotIn("media-private", serialized)

    def test_private_media_storage_uses_private_media_root_setting(self):
        tmpdir = Path.cwd() / ".tmp-private-media-root"
        with override_settings(PRIVATE_MEDIA_ROOT=tmpdir):
            storage = PrivateMediaStorage("archives")

            self.assertEqual(
                storage.path("sample.pdf"),
                str(Path(tmpdir) / "archives" / "sample.pdf"),
            )


class UploadUtilityTests(TestCase):
    def test_validate_upload_file_uses_upload_spec_rules(self):
        validate_upload_file(
            SimpleUploadedFile("ok.pdf", PDF_BYTES),
            allowed_extensions=["pdf"],
            max_size_mb=1,
        )

        with self.assertRaises(ValidationError):
            validate_upload_file(
                SimpleUploadedFile("bad.txt", b"bad"),
                allowed_extensions=["pdf"],
                max_size_mb=1,
            )

    def test_validate_upload_file_rejects_mismatched_signature(self):
        with self.assertRaises(ValidationError) as context:
            validate_upload_file(
                SimpleUploadedFile("fake.pdf", b"plain text"),
                allowed_extensions=["pdf"],
                max_size_mb=1,
            )

        self.assertIn("文件扩展名与实际文件类型不一致", context.exception.messages[0])

    def test_file_upload_mixin_exposes_old_validation_method_name(self):
        mixin = FileUploadMixin()
        mixin.allowed_extensions = ["pdf"]
        mixin.max_size_mb = 1

        self.assertEqual(mixin.validate_file(SimpleUploadedFile("ok.pdf", PDF_BYTES)), [])
        self.assertTrue(mixin.validate_file(SimpleUploadedFile("bad.txt", b"bad")))
        self.assertTrue(mixin.validate_file(SimpleUploadedFile("fake.pdf", b"not pdf")))

    def test_file_display_helpers_live_in_core_uploads(self):
        self.assertEqual(get_file_icon_class("report.pdf"), "icon-[tabler--file-type-pdf]")
        self.assertEqual(get_file_icon_class("archive.unknown"), "icon-[tabler--file]")
        self.assertTrue(is_image_file("photo.PNG"))
        self.assertFalse(is_image_file("report.pdf"))
        self.assertEqual(format_file_size(1024), "1.0 KB")
        self.assertEqual(format_file_size(1024 * 1024), "1.00 MB")


class MultipleFileFieldTests(TestCase):
    def test_multiple_file_field_returns_file_list(self):
        field = MultipleFileField(
            upload_spec=UploadSpec(["pdf"], 1),
            required=False,
        )
        files = [
            SimpleUploadedFile("first.pdf", PDF_BYTES),
            SimpleUploadedFile("second.pdf", PDF_BYTES),
        ]

        cleaned = field.clean(files)

        self.assertEqual([file.name for file in cleaned], ["first.pdf", "second.pdf"])

    def test_multiple_file_field_wraps_single_file_in_list(self):
        field = MultipleFileField(upload_spec=UploadSpec(["pdf"], 1), required=False)

        cleaned = field.clean(SimpleUploadedFile("single.pdf", PDF_BYTES))

        self.assertEqual(len(cleaned), 1)
        self.assertEqual(cleaned[0].name, "single.pdf")

    def test_multiple_file_field_returns_empty_list_when_optional_and_empty(self):
        field = MultipleFileField(upload_spec=UploadSpec(["pdf"], 1), required=False)

        self.assertEqual(field.clean(None), [])

    def test_multiple_file_field_rejects_invalid_extension(self):
        field = MultipleFileField(upload_spec=UploadSpec(["pdf"], 1), required=False)

        with self.assertRaises(ValidationError):
            field.clean([SimpleUploadedFile("bad.txt", b"bad")])

    def test_multiple_file_field_rejects_oversized_file(self):
        field = MultipleFileField(upload_spec=UploadSpec(["pdf"], 1), required=False)
        upload = SimpleUploadedFile("large.pdf", b"x" * (1024 * 1024 + 1))

        with self.assertRaises(ValidationError):
            field.clean([upload])

    def test_multiple_file_field_rejects_mismatched_file_signature(self):
        field = MultipleFileField(upload_spec=UploadSpec(["pdf"], 1), required=False)

        with self.assertRaises(ValidationError):
            field.clean([SimpleUploadedFile("fake.pdf", b"not a pdf")])


class UploadSpecAdoptionTests(TestCase):
    def test_upload_forms_use_upload_spec_accept_attrs(self):
        from archives.forms import ArchiveAssetForm
        from behaviors.forms import ConductRecordForm
        from meetings.forms import MeetingUploadForm
        from notices.forms import NoticeForm
        from training.forms import TrainingLogForm

        self.assertIn("accept", ArchiveAssetForm().fields["file"].widget.attrs)
        self.assertEqual(
            NoticeForm().fields["attachments"].widget.attrs["accept"],
            NOTICE_ATTACHMENT_UPLOAD_SPEC.accept,
        )
        self.assertIn("accept", TrainingLogForm().fields["file"].widget.attrs)
        self.assertEqual(
            ConductRecordForm().fields["attachment"].widget.attrs["accept"],
            CONDUCT_ATTACHMENT_UPLOAD_SPEC.accept,
        )
        self.assertEqual(
            MeetingUploadForm().fields["file"].widget.attrs["accept"],
            MEETING_FILE_UPLOAD_SPEC.accept,
        )

    def test_archive_asset_file_uses_upload_spec_help_text(self):
        from archives.models import ARCHIVE_ASSET_UPLOAD_SPEC, ArchiveAsset

        field = ArchiveAsset._meta.get_field("file")

        self.assertEqual(field.help_text, ARCHIVE_ASSET_UPLOAD_SPEC.help_text("上传资料文件"))
