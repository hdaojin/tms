from contextlib import closing
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from bs4 import BeautifulSoup
from django.contrib.auth import get_user_model
from django.contrib import admin
from django.contrib.auth.models import AnonymousUser, Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import RequestFactory, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from PIL import Image

from notes.admin import NoteRepoAdmin
from notes.models import NoteRepo
from notes.paths import (
    InvalidNotePathError,
    normalize_note_relative_path,
    resolve_note_repo_root,
    resolve_repo_relative_path,
)
from notes.permissions import NoteRepoReadAccess, can_access_note_content, can_access_note_repo, get_note_repo_read_access
from notes.utils import NoteContent, get_readme_navigation, render_note_markdown


User = get_user_model()


class NoteRepoMigrationTests(TransactionTestCase):
    migrate_from = ("notes", "0001_initial")
    migrate_to = ("notes", "0004_noterepo_allow_anonymous_access")

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])
        old_apps = executor.loader.project_state([self.migrate_from]).apps
        old_apps.get_model("notes", "NoteRepo").objects.create(slug="legacy-notes", title="旧笔记")
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_to])
        self.apps = executor.loader.project_state([self.migrate_to]).apps

    def test_migration_copies_slug_to_relative_path_and_keeps_old_repo_private(self):
        repo = self.apps.get_model("notes", "NoteRepo").objects.get(slug="legacy-notes")
        self.assertEqual(repo.relative_path, "legacy-notes")
        self.assertIs(repo.allow_anonymous_access, False)

    def tearDown(self):
        # 归还最新迁移状态，避免后续历史迁移测试混合前进和回退计划。
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()


class NoteRepoPathTests(TestCase):
    def test_new_and_changed_paths_cannot_overlap_on_segment_boundaries(self):
        parent = NoteRepo.objects.create(slug="parent", relative_path="a/b", title="笔记")
        sibling = NoteRepo.objects.create(slug="sibling", relative_path="a/bc", title="笔记")
        self.assertIs(parent.allow_anonymous_access, False)
        for repo in (
            NoteRepo(slug="child", relative_path=r"a\b\c", title="笔记"),
            NoteRepo(slug="ancestor", relative_path="a", title="笔记"),
            sibling,
        ):
            if repo is sibling:
                repo.relative_path = "a/b/another"
            for validate in (repo.full_clean, repo.save):
                with (
                    self.subTest(repo=repo.slug, validate=validate.__name__),
                    self.assertRaises(ValidationError) as exc,
                ):
                    validate()
                self.assertIn("relative_path", exc.exception.message_dict)

    def test_legacy_parent_can_edit_title_but_cannot_enable_anonymous_access(self):
        parent, child = NoteRepo.objects.bulk_create(
            [
                NoteRepo(slug="parent", relative_path="a/b", title="原名"),
                NoteRepo(slug="child", relative_path="a/b/c", title="子仓库"),
            ]
        )
        parent.title = "新名称"
        parent.full_clean()
        parent.save()
        parent.allow_anonymous_access = True
        with self.assertRaises(ValidationError):
            parent.full_clean()
        with self.assertRaises(ValidationError):
            parent.save(update_fields=["allow_anonymous_access"])
        parent.refresh_from_db()
        self.assertEqual(parent.title, "新名称")
        self.assertFalse(parent.allow_anonymous_access)
        child.allow_anonymous_access = True
        child.save(update_fields=["allow_anonymous_access"])
        self.assertEqual(child.anonymous_access_block_reason(), "")

    def test_model_normalizes_windows_separator(self):
        repo = NoteRepo.objects.create(
            slug="nested-notes",
            relative_path=r"teaching-notes-debian\debian-basics",
            title="嵌套笔记",
        )
        self.assertEqual(repo.relative_path, "teaching-notes-debian/debian-basics")

    def test_model_rejects_unsafe_relative_paths(self):
        invalid_paths = ("", ".", "../outside", "root/../outside", "C:/notes", r"\\server\notes", "/notes")
        for index, relative_path in enumerate(invalid_paths):
            with self.subTest(relative_path=relative_path):
                repo = NoteRepo(slug=f"invalid-{index}", relative_path=relative_path, title="非法路径")
                with self.assertRaises(ValidationError):
                    repo.full_clean()

    def test_missing_directory_is_allowed_at_model_validation_time(self):
        repo = NoteRepo(slug="future-notes", relative_path="future/path", title="稍后同步")
        repo.full_clean()

    def test_relative_path_is_unique(self):
        self.assertTrue(NoteRepo._meta.get_field("relative_path").unique)


class NotePermissionTests(TestCase):
    def setUp(self):
        self.allowed_group = Group.objects.create(name="笔记访问组")
        self.allowed_user = User.objects.create_user(username="notes-allowed", password="testpass123")
        self.allowed_user.groups.add(self.allowed_group)
        self.denied_user = User.objects.create_user(username="notes-denied", password="testpass123")
        self.superuser = User.objects.create_superuser(
            username="notes-admin",
            email="notes-admin@example.com",
            password="testpass123",
        )
        self.note_repo = NoteRepo.objects.create(
            slug="private-repo",
            relative_path="sources/private-repo",
            title="私有笔记",
        )
        self.note_repo.allowed_groups.add(self.allowed_group)

    def test_can_access_note_repo_requires_registration_and_allowed_group(self):
        self.assertTrue(can_access_note_repo(self.allowed_user, "private-repo"))
        self.assertFalse(can_access_note_repo(self.denied_user, "private-repo"))
        self.assertFalse(can_access_note_repo(self.allowed_user, "unregistered-repo"))

    def test_can_access_note_content_uses_note_repo_permissions(self):
        note = NoteContent(
            repo="private-repo",
            slug="README",
            meta={},
            html="",
            source_path=Path("private-repo/README.md"),
            toc_tokens=None,
        )
        self.assertTrue(can_access_note_content(self.allowed_user, note))
        self.assertFalse(can_access_note_content(self.denied_user, note))

    def test_invisible_repo_allows_superuser_only(self):
        self.note_repo.is_visible = False
        self.note_repo.save(update_fields=["is_visible"])
        self.assertFalse(can_access_note_repo(self.allowed_user, "private-repo"))
        self.assertTrue(can_access_note_repo(self.superuser, "private-repo"))

    def test_public_read_keeps_original_repo_authorization_separate(self):
        anonymous = AnonymousUser()
        no_permission = self.allowed_user
        self.denied_user.user_permissions.add(
            Permission.objects.get(content_type__app_label="notes", codename="view_noterepo")
        )
        for user, expected in (
            (anonymous, NoteRepoReadAccess.LOGIN_REQUIRED),
            (no_permission, NoteRepoReadAccess.FORBIDDEN),
            (self.denied_user, NoteRepoReadAccess.FORBIDDEN),
        ):
            with self.subTest(user=user):
                self.assertIs(get_note_repo_read_access(user, self.note_repo), expected)
        self.note_repo.allow_anonymous_access = True
        self.note_repo.save(update_fields=["allow_anonymous_access"])
        for user in (anonymous, no_permission, self.denied_user):
            with self.subTest(user=user):
                self.assertIs(get_note_repo_read_access(user, self.note_repo), NoteRepoReadAccess.ALLOWED)
        self.assertFalse(can_access_note_repo(anonymous, self.note_repo.slug))
        self.assertFalse(can_access_note_repo(self.denied_user, self.note_repo.slug))

    def test_hidden_repo_with_public_flag_still_requires_private_authorization(self):
        self.note_repo.allow_anonymous_access = True
        self.note_repo.is_visible = False
        self.assertIs(get_note_repo_read_access(AnonymousUser(), self.note_repo), NoteRepoReadAccess.LOGIN_REQUIRED)
        self.assertIs(get_note_repo_read_access(self.allowed_user, self.note_repo), NoteRepoReadAccess.FORBIDDEN)
        self.assertIs(get_note_repo_read_access(self.superuser, self.note_repo), NoteRepoReadAccess.ALLOWED)


class NotePathBoundaryTests(TestCase):
    def setUp(self):
        self.temp_dir = Path(self.enterContext(TemporaryDirectory(prefix="tms-note-paths-")))
        self.settings_override = override_settings(NOTES_ROOT=self.temp_dir)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

    def test_resolver_allows_parent_segments_only_inside_registered_root(self):
        repo_root = self.temp_dir / "parent" / "repo"
        (repo_root / "chapter").mkdir(parents=True)
        relative, resolved = resolve_repo_relative_path(repo_root, "chapter", "../README.md")
        self.assertEqual(relative, "README.md")
        self.assertEqual(resolved, repo_root / "README.md")
        with self.assertRaises(InvalidNotePathError):
            resolve_repo_relative_path(repo_root, "", "../outside.md")

    def test_configured_repo_symlink_cannot_escape_notes_root(self):
        outside = Path(self.enterContext(TemporaryDirectory(prefix="tms-note-outside-")))
        link = self.temp_dir / "escaped"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"当前平台不允许创建目录软链接：{exc}")
        with self.assertRaises(InvalidNotePathError):
            resolve_note_repo_root("escaped")

    def test_normalizer_accepts_both_separators(self):
        self.assertEqual(normalize_note_relative_path(r"parent\child"), "parent/child")


class NoteRepoAdminTests(TestCase):
    def setUp(self):
        self.repo = NoteRepo.objects.create(slug="course", relative_path="a/course", title="课程")
        self.url = reverse("admin:notes_noterepo_change", args=[self.repo.pk])
        self.staff = User.objects.create_user(username="note-staff", is_staff=True)
        self.staff.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="notes",
                codename__in=["add_noterepo", "change_noterepo"],
            )
        )
        self.superuser = User.objects.create_superuser(username="note-superuser")
        self.data = {
            "slug": self.repo.slug,
            "relative_path": self.repo.relative_path,
            "title": "更新课程名称",
            "description": "课程简介",
            "tags": "教案",
            "order": 0,
            "is_visible": "on",
            "allow_anonymous_access": "on",
        }

    def test_superuser_can_toggle_and_get_public_link(self):
        self.client.force_login(self.superuser)
        self.assertContains(self.client.get(self.url), 'name="allow_anonymous_access"')
        self.assertEqual(self.client.post(self.url, self.data).status_code, 302)
        self.repo.refresh_from_db()
        self.assertTrue(self.repo.allow_anonymous_access)
        public_url = reverse("notes:note_repo_index", args=[self.repo.slug])
        self.assertContains(self.client.get(self.url), f'href="{public_url}"')
        self.data.pop("allow_anonymous_access")
        self.assertEqual(self.client.post(self.url, self.data).status_code, 302)
        self.repo.refresh_from_db()
        self.assertFalse(self.repo.allow_anonymous_access)

    def test_ordinary_admin_can_edit_other_fields_but_cannot_forge_public_flag(self):
        self.client.force_login(self.staff)
        self.assertNotContains(self.client.get(self.url), 'name="allow_anonymous_access"')
        self.assertEqual(self.client.post(self.url, self.data).status_code, 302)
        self.repo.refresh_from_db()
        self.assertFalse(self.repo.allow_anonymous_access)
        self.assertEqual((self.repo.title, self.repo.description, self.repo.tags), ("更新课程名称", "课程简介", "教案"))

        add_url = reverse("admin:notes_noterepo_add")
        self.assertEqual(
            self.client.post(add_url, {**self.data, "slug": "new", "relative_path": "new"}).status_code, 302
        )
        self.assertFalse(NoteRepo.objects.get(slug="new").allow_anonymous_access)

    def test_save_model_rejects_non_superuser_changing_or_setting_public_flag(self):
        model_admin = NoteRepoAdmin(NoteRepo, admin.site)
        request = RequestFactory().post(self.url)
        request.user = self.staff
        self.repo.allow_anonymous_access = True
        new_repo = NoteRepo(slug="new", relative_path="new", title="新课程", allow_anonymous_access=True)
        for repo, change in ((self.repo, True), (new_repo, False)):
            with self.subTest(change=change), self.assertRaises(PermissionDenied):
                model_admin.save_model(request, repo, None, change)

    def test_public_link_is_hidden_for_blocked_legacy_parent(self):
        child = NoteRepo(slug="child", relative_path=f"{self.repo.relative_path}/child", title="子仓库")
        NoteRepo.objects.bulk_create([child])
        self.client.force_login(self.superuser)
        response = self.client.post(self.url, self.data)
        self.assertContains(response, "请先调整目录结构")
        self.repo.refresh_from_db()
        self.assertFalse(self.repo.allow_anonymous_access)

        NoteRepo.objects.filter(pk=self.repo.pk).update(allow_anonymous_access=True)
        public_url = reverse("notes:note_repo_index", args=[self.repo.slug])
        for url in (self.url, reverse("admin:notes_noterepo_changelist")):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, "公开配置因目录问题暂未生效")
                self.assertNotContains(response, f'href="{public_url}"')


class NoteViewTests(TestCase):
    def test_login_and_audience_membership_do_not_replace_view_permission(self):
        unassigned = User.objects.create_user(username="notes-unassigned")
        unassigned.groups.add(self.allowed_group)
        self.client.force_login(unassigned)
        for url in (
            reverse("notes:repo_list"),
            reverse("notes:note_repo_index", kwargs={"repo": "course"}),
            reverse("notes:note_detail", kwargs={"repo": "course", "slug": "one"}),
            reverse("notes:note_print", kwargs={"repo": "course", "slug": "one"}),
            reverse("note_asset", kwargs={"repo": "course", "asset_path": "assets/diagram.png"}),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        self.note_repo.allowed_groups.clear()
        self.assertEqual(self.client.get(reverse("notes:repo_list")).status_code, 403)

    def setUp(self):
        self.allowed_group = Group.objects.create(name="资料访问组")
        self.allowed_user = User.objects.create_user(username="asset-allowed", password="testpass123")
        self.allowed_user.groups.add(self.allowed_group)
        self.denied_user = User.objects.create_user(username="asset-denied", password="testpass123")
        view_permission = Permission.objects.get(
            content_type__app_label="notes", codename="view_noterepo"
        )
        self.allowed_user.user_permissions.add(view_permission)
        self.denied_user.user_permissions.add(view_permission)
        self.superuser = User.objects.create_superuser(
            username="notes-superuser",
            email="notes-superuser@example.com",
            password="testpass123",
        )
        self.note_repo = NoteRepo.objects.create(
            slug="course",
            relative_path="container/debian-basics",
            title="Debian 基础",
        )
        self.note_repo.allowed_groups.add(self.allowed_group)

        self.temp_dir = Path(self.enterContext(TemporaryDirectory(prefix="tms-notes-")))
        self.repo_root = self.temp_dir / "container" / "debian-basics"
        (self.repo_root / "assets").mkdir(parents=True)
        Image.new("RGB", (1, 1)).save(self.repo_root / "assets" / "diagram.png")
        (self.temp_dir / "container" / "outside.md").write_text("# Outside", encoding="utf-8")
        (self.repo_root / "README.md").write_text(
            """# Course

<!-- TOC -->
- [第一课](one.md)
    - [第二课](two.md)
        - [第三课](three.md)
            - [第四课](four.md)
- [越界内容](../outside.md)
- [缺失讲义](missing.md)
- [外部资料](https://example.com/docs)
<!-- /TOC -->
""",
            encoding="utf-8",
        )
        (self.repo_root / "one.md").write_text(
            "# 文档标题\n\n## 第二级标题\n\n### 第三级标题\n\n#### 第四级标题\n\n##### 第五级标题\n",
            encoding="utf-8",
        )
        for name in ("two", "three", "four"):
            (self.repo_root / f"{name}.md").write_text(f"# {name}\n", encoding="utf-8")

        self.settings_override = override_settings(NOTES_ROOT=self.temp_dir)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

    def _read_urls(self):
        return (
            reverse("notes:note_repo_index", args=["course"]),
            reverse("notes:note_detail", args=["course", "one"]),
            reverse("notes:note_print", args=["course", "one"]),
            reverse("note_asset", args=["course", "assets/diagram.png"]),
        )

    def test_anonymous_public_read_and_immediate_revocation(self):
        self.note_repo.allow_anonymous_access = True
        self.note_repo.save(update_fields=["allow_anonymous_access"])
        index, detail, print_url, image = self._read_urls()
        (self.repo_root / "assets" / "guide.pdf").write_bytes(b"%PDF-1.4\n")
        (self.repo_root / "assets" / "guide.txt").write_bytes(b"guide")
        (self.repo_root / "one.md").write_text(
            "# 文档标题\n\n## 第二级标题\n\n![图示](assets/diagram.png)\n\n[讲义](assets/guide.pdf)\n",
            encoding="utf-8",
        )
        for url, content_type, disposition in (
            (index, "text/html", None),
            (detail, "text/html", None),
            (print_url, "text/html", None),
            (image, "image/png", "inline"),
            (reverse("note_asset", args=["course", "assets/guide.pdf"]), "application/pdf", "inline"),
            (reverse("note_asset", args=["course", "assets/guide.txt"]), "application/octet-stream", "attachment"),
        ):
            with self.subTest(url=url):
                with closing(self.client.get(url)) as response:
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")
                    self.assertIn("private", response["Cache-Control"])
                    self.assertIn("no-store", response["Cache-Control"])
                    self.assertTrue(response["Content-Type"].startswith(content_type))
                    if disposition:
                        self.assertEqual(response["Cache-Control"], "private, no-store")
                        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
                        self.assertTrue(response["Content-Disposition"].startswith(f"{disposition};"))
                    if url == detail:
                        self.assertContains(response, f'src="{image}"')
                        self.assertContains(response, "第二级标题")
                        self.assertContains(response, "第二课")
                        self.assertContains(response, f'href="{print_url}"')
                        self.assertNotContains(response, f'href="{reverse("notes:repo_list")}"')
                        self.assertEqual(response.context["prev_note"]["url"], index)
                        self.assertEqual(response.context["next_note"]["title"], "第二课")

        user_without_permission = User.objects.create_user(username="public-note-reader")
        self.client.force_login(user_without_permission)
        self.assertEqual(self.client.get(detail).status_code, 200)
        self.assertEqual(self.client.get(reverse("notes:repo_list")).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("notes:repo_list")).status_code, 302)
        self.note_repo.allow_anonymous_access = False
        self.note_repo.save(update_fields=["allow_anonymous_access"])
        for url in self._read_urls():
            with self.subTest(url=url):
                response = self.client.get(f"{url}?test=1")
                self.assertEqual(response.status_code, 302)
                self.assertEqual(parse_qs(urlsplit(response.url).query)["next"], [f"{url}?test=1"])

    def test_hidden_public_repo_and_unregistered_repo_are_not_anonymously_readable(self):
        NoteRepo.objects.filter(pk=self.note_repo.pk).update(allow_anonymous_access=True, is_visible=False)
        for url in self._read_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 302)
                self.assertEqual(self.client.get(url.replace("/course/", "/unregistered/")).status_code, 404)

    def test_public_parent_with_legacy_child_falls_back_to_private_permissions(self):
        child_path = f"{self.note_repo.relative_path}/assets"
        NoteRepo.objects.bulk_create([NoteRepo(slug="child", relative_path=child_path, title="私有子仓库")])
        NoteRepo.objects.filter(pk=self.note_repo.pk).update(allow_anonymous_access=True)
        for user, status in ((None, 404), (self.denied_user, 403), (self.allowed_user, 200)):
            if user is not None:
                self.client.force_login(user)
            for url in self._read_urls():
                with self.subTest(user=user, url=url), closing(self.client.get(url)) as response:
                    self.assertEqual(response.status_code, status)

    def test_public_repo_blocks_other_registered_roots_resolved_through_symlinks(self):
        self.note_repo.allow_anonymous_access = True
        self.note_repo.save(update_fields=["allow_anonymous_access"])
        alias = self.temp_dir / "alias"
        try:
            alias.symlink_to(self.repo_root / "assets", target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"当前平台不允许创建目录软链接：{exc}")
        NoteRepo.objects.create(slug="alias", relative_path="alias", title="私有子仓库")
        for url in self._read_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_registered_child_remains_public_below_parent_with_different_path_casing(self):
        if Path("container") != Path("CONTAINER") or not (self.temp_dir / "CONTAINER").is_dir():
            self.skipTest("此测试需要大小写不敏感的笔记目录")
        parent = NoteRepo(slug="parent", relative_path="CONTAINER", title="私有父仓库")
        with self.assertRaises(ValidationError):
            parent.save()
        NoteRepo.objects.bulk_create([parent])
        self.assertIn("重叠", parent.anonymous_access_block_reason())
        self.note_repo.allow_anonymous_access = True
        self.note_repo.save(update_fields=["allow_anonymous_access"])
        self.assertEqual(self.client.get(self._read_urls()[0]).status_code, 200)

    def test_unregistered_physical_directory_is_not_accessible(self):
        unregistered = self.temp_dir / "unregistered"
        unregistered.mkdir()
        (unregistered / "README.md").write_text("# Hidden", encoding="utf-8")
        self.client.force_login(self.allowed_user)
        response = self.client.get(reverse("notes:note_repo_index", kwargs={"repo": "unregistered"}))
        self.assertEqual(response.status_code, 404)

    def test_denied_user_cannot_probe_content_or_assets(self):
        self.client.force_login(self.denied_user)
        note_response = self.client.get(reverse("notes:note_repo_index", kwargs={"repo": "course"}))
        asset_response = self.client.get(
            reverse("note_asset", kwargs={"repo": "course", "asset_path": "assets/diagram.png"})
        )
        self.assertEqual(note_response.status_code, 403)
        self.assertEqual(asset_response.status_code, 403)
        self.assertEqual(self.client.get(reverse("notes:note_print", kwargs={"repo": "course", "slug": "one"})).status_code, 403)

    def test_asset_view_serves_file_inside_nested_repo(self):
        self.client.force_login(self.allowed_user)
        response = self.client.get(
            reverse("note_asset", kwargs={"repo": "course", "asset_path": "assets/diagram.png"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertTrue(response["Content-Disposition"].startswith("inline;"))
        response.close()

    def test_asset_content_and_headers(self):
        self.client.force_login(self.allowed_user)
        files = [
            ("guide.pdf", b"%PDF-1.4\n", "application/pdf"),
            ("unsafe.html", b"<script>alert(1)</script>", None),
            ("unsafe.svg", b'<svg onload="alert(1)"/>', None),
            ("unsafe.xml", b"<xml/>", None),
            ("fake.png", b"<html>not an image</html>", None),
            ("empty.pdf", b"", None),
            ("unknown", b"unknown", None),
        ]
        for ext, fmt in [("jpg", "JPEG"), ("gif", "GIF"), ("webp", "WEBP")]:
            image = BytesIO()
            Image.new("RGB", (1, 1)).save(image, format=fmt)
            files.append((f"image.{ext}", image.getvalue(), f"image/{fmt.lower()}"))
        for name, content, inline_type in files:
            with self.subTest(name=name):
                (self.repo_root / "assets" / name).write_bytes(content)
                url = reverse("note_asset", kwargs={"repo": "course", "asset_path": f"assets/{name}"})
                response = self.client.get(url)
                self.addCleanup(response.close)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["X-Content-Type-Options"], "nosniff")
                self.assertEqual(response["Cache-Control"], "private, no-store")
                self.assertEqual(response["Content-Type"], inline_type or "application/octet-stream")
                disposition = "inline;" if inline_type else "attachment;"
                self.assertTrue(response["Content-Disposition"].startswith(disposition))
                if name == "guide.pdf":
                    self.assertEqual(response["X-Frame-Options"], "SAMEORIGIN")

    def test_teaching_markup_preserves_safe_links_code_and_table(self):
        path = self.repo_root / "one.md"
        path.write_text(
            "## Lesson\n\n![Diagram](assets/diagram.png)\n\n[Next](two.md)\n\n"
            "| Key | Value |\n| --- | --- |\n| x | 1 |\n\n"
            "```python\nprint('hello')\n```\n\n.. note::\n   练习提醒\n\n- [x] 已完成\n",
            encoding="utf-8",
        )
        note = render_note_markdown(path, "course", self.repo_root, "one")
        soup = BeautifulSoup(note.html, "html.parser")
        self.assertEqual(soup.select_one("img")["src"], "/notes-files/course/assets/diagram.png")
        self.assertEqual(soup.select_one("a")["href"], "/notes/course/two/")
        self.assertEqual(soup.select_one("table td").text, "x")
        self.assertIn("print", soup.select_one("pre code.language-python").text)
        self.assertIn("练习提醒", soup.select_one("aside.admonition.note").text)
        self.assertTrue(soup.select_one('input[type="checkbox"]').has_attr("disabled"))
        self.assertIn(f'#{soup.h2["id"]}"', note.toc_tokens)

    def test_note_and_print_strip_active_content_including_details(self):
        (self.repo_root / "one.md").write_text(
            """## 安全示例

<script>script_payload()</script>
<iframe src="https://example.com/"></iframe>
<svg onload="alert(1)"><a href="javascript:alert(1)">svg</a></svg>
<img src="data:text/html,evil" onerror="alert(1)">
<a href="jAvA&#x73;cript:alert(1)" hx-get="/accounts/">危险链接</a>

<details open>
<summary>教学折叠内容</summary>

<img src="assets/diagram.png" onerror="alert(1)">
</details>
""",
            encoding="utf-8",
        )
        self.client.force_login(self.allowed_user)
        for route in ("notes:note_detail", "notes:note_print"):
            with self.subTest(route=route):
                response = self.client.get(reverse(route, kwargs={"repo": "course", "slug": "one"}))
                self.assertContains(response, "教学折叠内容")
                for marker in ("script_payload", "<iframe", 'onerror="alert', 'onload="alert',
                               "data:text/html", "javascript:alert", 'hx-get="/accounts/"'):
                    self.assertNotContains(response, marker)

    def test_note_render_failure_is_visible_without_logging_input(self):
        (self.repo_root / "README.md").write_text("# Course", encoding="utf-8")
        self.client.force_login(self.allowed_user)
        url = reverse("notes:note_detail", kwargs={"repo": "course", "slug": "one"})
        with (
            patch("core.utils.markdown.markdown2.markdown", side_effect=ValueError("private-source-canary")),
            self.assertLogs("core.utils.markdown", level="WARNING") as logs,
        ):
            response = self.client.get(url)
        self.assertContains(response, "无法显示笔记正文")
        self.assertNotContains(response, "private-source-canary")
        self.assertEqual(len(logs.output), 1)
        self.assertIn("ValueError", logs.output[0])
        self.assertNotIn("private-source-canary", logs.output[0])

    def test_asset_rejects_missing_directory_and_parent_traversal(self):
        self.note_repo.allow_anonymous_access = True
        self.note_repo.save(update_fields=["allow_anonymous_access"])
        for path in ("assets/missing.png", "assets", "%2e%2e/outside.md"):
            with self.subTest(path=path):
                url = reverse("note_asset", kwargs={"repo": "course", "asset_path": path})
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_asset_symlink_cannot_escape_its_repository(self):
        self.note_repo.allow_anonymous_access = True
        self.note_repo.save(update_fields=["allow_anonymous_access"])
        try:
            (self.repo_root / "assets" / "escape.md").symlink_to(self.temp_dir / "container" / "outside.md")
        except OSError:
            self.skipTest("当前环境无法创建符号链接")
        url = reverse("note_asset", kwargs={"repo": "course", "asset_path": "assets/escape.md"})
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_readme_navigation_supports_three_levels_and_omits_escape(self):
        navigation = get_readme_navigation(self.repo_root, "course")
        self.assertIn("第一课", navigation.html)
        self.assertIn("第二课", navigation.html)
        self.assertIn("第三课", navigation.html)
        self.assertNotIn("第四课", navigation.html)
        self.assertNotIn("越界内容", navigation.html)
        self.assertNotIn("缺失讲义", navigation.html)
        self.assertIn("https://example.com/docs", navigation.html)
        self.assertEqual([item["slug"] for item in navigation.items], ["one", "two", "three"])

    def test_legacy_toc_markers_are_supported(self):
        (self.repo_root / "README.md").write_text(
            "<!-- TOC_START -->\n- [第一课](one.md)\n<!-- TOC_END -->\n",
            encoding="utf-8",
        )
        navigation = get_readme_navigation(self.repo_root, "course")
        self.assertEqual(navigation.items, [{"slug": "one", "title": "第一课"}])

    def test_outline_includes_only_h2_through_h4(self):
        note = render_note_markdown(self.repo_root / "one.md", "course", self.repo_root, "one")
        outline = BeautifulSoup(note.toc_tokens, "lxml")

        self.assertNotIn("文档标题", note.toc_tokens)
        self.assertIn("第二级标题", note.toc_tokens)
        self.assertIn("第三级标题", note.toc_tokens)
        self.assertIn("第四级标题", note.toc_tokens)
        self.assertNotIn("第五级标题", note.toc_tokens)
        links = outline.find_all("a")
        self.assertEqual(
            [link.get_text(strip=True) for link in links],
            ["第二级标题", "第三级标题", "第四级标题"],
        )
        self.assertEqual([len(link.find_parents("ul")) for link in links], [1, 2, 3])

    def test_details_body_markdown_stays_inside_collapsible_content(self):
        (self.repo_root / "one.md").write_text(
            """# 练习

<details>
<summary>参考答案</summary>

1. 第一项答案
2. 第二项答案

```console
$ pwd
```

[查看附件](assets/diagram.png)
</details>
""",
            encoding="utf-8",
        )

        note = render_note_markdown(self.repo_root / "one.md", "course", self.repo_root, "one")
        soup = BeautifulSoup(note.html, "lxml")
        details = soup.find("details", class_="note-details")

        self.assertIsNotNone(details)
        self.assertFalse(details.has_attr("open"))
        self.assertEqual(details.summary.get_text(strip=True), "参考答案")
        self.assertIn("第一项答案", details.select_one(".collapse-content").get_text(" ", strip=True))
        self.assertIsNotNone(details.select_one("pre code.language-console"))
        self.assertEqual(
            details.select_one("a")["href"],
            "/notes-files/course/assets/diagram.png",
        )

    def test_details_preserves_open_and_ignores_examples_in_fenced_code(self):
        (self.repo_root / "one.md").write_text(
            """<details open>
<summary>默认展开</summary>

答案正文
</details>

```html
<details>
<summary>示例</summary>
</details>
```
""",
            encoding="utf-8",
        )

        note = render_note_markdown(self.repo_root / "one.md", "course", self.repo_root, "one")
        soup = BeautifulSoup(note.html, "lxml")

        self.assertTrue(soup.find("details", class_="note-details").has_attr("open"))
        self.assertEqual(len(soup.find_all("details")), 1)
        self.assertIn("&lt;details&gt;", note.html)

    def test_nested_details_returns_safe_parse_error(self):
        source = """<details>
<summary>外层</summary>
<details>
<summary>内层</summary>
答案
</details>
</details>
"""
        (self.repo_root / "one.md").write_text(source, encoding="utf-8")

        note = render_note_markdown(self.repo_root / "one.md", "course", self.repo_root, "one")

        self.assertTrue(note.meta["_parse_error"])
        self.assertIn("不支持嵌套", note.meta["_parse_error_message"])
        self.assertIn("折叠内容解析失败", note.html)
        self.assertIn("&lt;details&gt;", note.html)
        self.assertNotIn('<details class="note-details', note.html)

    def test_incomplete_details_returns_safe_parse_error(self):
        (self.repo_root / "one.md").write_text(
            "<details>\n<summary>参考答案</summary>\n\n答案正文\n",
            encoding="utf-8",
        )

        note = render_note_markdown(self.repo_root / "one.md", "course", self.repo_root, "one")

        self.assertTrue(note.meta["_parse_error"])
        self.assertIn("缺少结束标签", note.meta["_parse_error_message"])
        self.assertIn("&lt;details&gt;", note.html)

    def test_mermaid_fence_emits_render_target_instead_of_code_block(self):
        (self.repo_root / "one.md").write_text(
            """# 流程

```mermaid
flowchart TD
    A --> B
```
""",
            encoding="utf-8",
        )

        note = render_note_markdown(self.repo_root / "one.md", "course", self.repo_root, "one")
        soup = BeautifulSoup(note.html, "lxml")

        diagram = soup.select_one("pre.mermaid-pre > .mermaid[data-mermaid-diagram]")
        self.assertIsNotNone(diagram)
        self.assertIn("flowchart TD", diagram.get_text())
        self.assertIsNone(soup.select_one("code.language-mermaid"))

    def test_detail_uses_depth_first_previous_next_and_responsive_navigation(self):
        self.client.force_login(self.allowed_user)
        response = self.client.get(
            reverse("notes:note_detail", kwargs={"repo": "course", "slug": "two"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["prev_note"]["title"], "第一课")
        self.assertEqual(response.context["next_note"]["title"], "第三课")
        self.assertTrue(response.context["show_right_sidebar"])
        self.assertTrue(response.context["wide_sidebars"])
        self.assertContains(response, "移动端课程目录")
        self.assertContains(response, "移动端本文大纲")
        self.assertContains(response, "data-app-right-sidebar")
        self.assertNotContains(response, "lg:grid-cols-[minmax(0,1fr)_16rem]")
        self.assertContains(response, "js/mermaid.min.js")
        self.assertContains(response, "js/notes-mermaid.js")

        page = BeautifulSoup(response.content, "lxml")
        left_sidebar = page.select_one("aside[data-app-left-sidebar]")
        right_sidebar = page.select_one("aside[data-app-right-sidebar]")
        self.assertIsNotNone(left_sidebar)
        self.assertIsNotNone(right_sidebar)
        self.assertIsNone(right_sidebar.find_parent("main"))
        self.assertIsNotNone(right_sidebar.select_one('nav[aria-label="本文大纲"]'))
        mermaid_script = page.find(
            "script",
            src=lambda value: value and value.endswith("/js/notes-mermaid.js"),
        )
        self.assertIsNotNone(mermaid_script)
        csp_nonce = mermaid_script.get("data-csp-nonce")
        self.assertTrue(csp_nonce)
        self.assertIn(
            f"'nonce-{csp_nonce}'",
            response.headers["Content-Security-Policy"],
        )
        for sidebar in (left_sidebar, right_sidebar):
            self.assertIn("w-72", sidebar["class"])
            self.assertIn("xl:w-80", sidebar["class"])
        left_sidebar_content = left_sidebar.select_one("[data-app-left-sidebar-content]")
        right_sidebar_content = right_sidebar.select_one(":scope > div")
        for sidebar_content in (left_sidebar_content, right_sidebar_content):
            self.assertIn("sticky", sidebar_content["class"])
            self.assertIn("top-16", sidebar_content["class"])
            self.assertIn("max-h-[calc(100dvh_-_4rem)]", sidebar_content["class"])
            self.assertIn("overflow-y-auto", sidebar_content["class"])
        self.assertIn("text-center", left_sidebar.select_one(".font-semibold")["class"])
        self.assertIn("text-center", right_sidebar.select_one(".font-semibold")["class"])

    def test_mermaid_client_uses_fixed_light_intrinsic_sequence_layout(self):
        script = (Path.cwd() / "static" / "js" / "notes-mermaid.js").read_text(encoding="utf-8")

        self.assertIn('theme: "default"', script)
        self.assertIn("darkMode: false", script)
        self.assertIn("htmlLabels: false", script)
        self.assertIn("width: 200", script)
        self.assertIn("wrap: true", script)
        self.assertIn("window.mermaid.render", script)
        self.assertIn('document.createElement("template")', script)
        self.assertIn("style.nonce = cspNonce", script)
        self.assertIn('style.setAttribute("nonce", cspNonce)', script)
        self.assertNotIn("window.mermaid.run", script)
        self.assertNotIn('"tms:theme-changed"', script)

    def test_print_page_loads_mermaid_and_marks_light_theme_rendering_scope(self):
        self.client.force_login(self.allowed_user)
        response = self.client.get(
            reverse("notes:note_print", kwargs={"repo": "course", "slug": "one"})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-note-print-page")
        self.assertContains(response, "js/mermaid.min.js")
        self.assertContains(response, "js/notes-mermaid.js")
        page = BeautifulSoup(response.content, "lxml")
        mermaid_script = page.find(
            "script",
            src=lambda value: value and value.endswith("/js/notes-mermaid.js"),
        )
        self.assertTrue(mermaid_script.get("data-csp-nonce"))
