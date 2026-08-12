from pathlib import Path
import shutil
from unittest.mock import patch

from bs4 import BeautifulSoup
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from notes.models import NoteRepo
from notes.paths import (
    InvalidNotePathError,
    normalize_note_relative_path,
    resolve_note_repo_root,
    resolve_repo_relative_path,
)
from notes.permissions import can_access_note_content, can_access_note_repo
from notes.utils import NoteContent, get_readme_navigation, render_note_markdown


User = get_user_model()


class NoteRepoMigrationTests(TransactionTestCase):
    migrate_from = ("notes", "0001_initial")
    migrate_to = ("notes", "0002_noterepo_relative_path")

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])
        old_apps = executor.loader.project_state([self.migrate_from]).apps
        old_apps.get_model("notes", "NoteRepo").objects.create(slug="legacy-notes", title="旧笔记")
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_to])
        self.apps = executor.loader.project_state([self.migrate_to]).apps

    def test_migration_copies_slug_to_relative_path(self):
        repo = self.apps.get_model("notes", "NoteRepo").objects.get(slug="legacy-notes")
        self.assertEqual(repo.relative_path, "legacy-notes")


class NoteRepoPathTests(TestCase):
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


class NotePathBoundaryTests(TestCase):
    def setUp(self):
        self.temp_dir = Path.cwd() / ".tmp-test-note-paths"
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))
        self.temp_dir.mkdir(parents=True)
        self.root_patcher = patch("notes.paths.NOTES_ROOT", self.temp_dir)
        self.root_patcher.start()
        self.addCleanup(self.root_patcher.stop)

    def test_resolver_allows_parent_segments_only_inside_registered_root(self):
        repo_root = self.temp_dir / "parent" / "repo"
        (repo_root / "chapter").mkdir(parents=True)
        relative, resolved = resolve_repo_relative_path(repo_root, "chapter", "../README.md")
        self.assertEqual(relative, "README.md")
        self.assertEqual(resolved, repo_root / "README.md")
        with self.assertRaises(InvalidNotePathError):
            resolve_repo_relative_path(repo_root, "", "../outside.md")

    def test_configured_repo_symlink_cannot_escape_notes_root(self):
        outside = self.temp_dir.parent / ".tmp-test-note-paths-outside"
        shutil.rmtree(outside, ignore_errors=True)
        outside.mkdir(parents=True)
        self.addCleanup(lambda: shutil.rmtree(outside, ignore_errors=True))
        link = self.temp_dir / "escaped"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"当前平台不允许创建目录软链接：{exc}")
        with self.assertRaises(InvalidNotePathError):
            resolve_note_repo_root("escaped")

    def test_normalizer_accepts_both_separators(self):
        self.assertEqual(normalize_note_relative_path(r"parent\child"), "parent/child")


class NoteViewTests(TestCase):
    def setUp(self):
        self.allowed_group = Group.objects.create(name="资料访问组")
        self.allowed_user = User.objects.create_user(username="asset-allowed", password="testpass123")
        self.allowed_user.groups.add(self.allowed_group)
        self.denied_user = User.objects.create_user(username="asset-denied", password="testpass123")
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

        self.temp_dir = Path.cwd() / ".tmp-test-notes"
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))
        self.repo_root = self.temp_dir / "container" / "debian-basics"
        (self.repo_root / "assets").mkdir(parents=True)
        (self.repo_root / "assets" / "diagram.png").write_bytes(b"fake-image-bytes")
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
            "## 第一章\n\n### 第一节\n\n#### 第一小节\n\n##### 第四级标题\n",
            encoding="utf-8",
        )
        for name in ("two", "three", "four"):
            (self.repo_root / f"{name}.md").write_text(f"# {name}\n", encoding="utf-8")

        self.path_patcher = patch("notes.paths.NOTES_ROOT", self.temp_dir)
        self.view_patcher = patch("notes.views.NOTES_ROOT", self.temp_dir)
        self.path_patcher.start()
        self.view_patcher.start()
        self.addCleanup(self.path_patcher.stop)
        self.addCleanup(self.view_patcher.stop)

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

    def test_asset_view_serves_file_inside_nested_repo(self):
        self.client.force_login(self.allowed_user)
        response = self.client.get(
            reverse("note_asset", kwargs={"repo": "course", "asset_path": "assets/diagram.png"})
        )
        self.assertEqual(response.status_code, 200)
        response.close()

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

    def test_outline_uses_relative_three_heading_levels(self):
        note = render_note_markdown(self.repo_root / "one.md", "course", self.repo_root, "one")
        self.assertIn("第一章", note.toc_tokens)
        self.assertIn("第一节", note.toc_tokens)
        self.assertIn("第一小节", note.toc_tokens)
        self.assertNotIn("第四级标题", note.toc_tokens)

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
        self.assertContains(response, "移动端课程目录")
        self.assertContains(response, "移动端本文大纲")
        self.assertContains(response, "lg:grid-cols-[minmax(0,1fr)_16rem]")
        self.assertNotContains(response, "xl:grid-cols-[minmax(0,1fr)_16rem]")
        self.assertContains(response, "js/mermaid.min.js")
        self.assertContains(response, "js/notes-mermaid.js")

    def test_print_page_loads_mermaid_and_marks_light_theme_rendering_scope(self):
        self.client.force_login(self.allowed_user)
        response = self.client.get(
            reverse("notes:note_print", kwargs={"repo": "course", "slug": "one"})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-note-print-page")
        self.assertContains(response, "js/mermaid.min.js")
        self.assertContains(response, "js/notes-mermaid.js")

    def test_superuser_stats_treat_registered_subdirectory_as_covering_top_level(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("notes:repo_list"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("container", response.context["unregistered_repos"])
        self.assertIn(self.note_repo, response.context["repos"])
