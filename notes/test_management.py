from pathlib import Path
from tempfile import TemporaryDirectory

from bs4 import BeautifulSoup
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse

from .models import NoteRepo


class NoteRepoManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.superuser = user_model.objects.create_superuser(username="notes-owner")
        cls.staff = user_model.objects.create_user(username="notes-staff", is_staff=True)
        cls.staff.user_permissions.add(*Permission.objects.filter(content_type__app_label="notes"))
        cls.group = Group.objects.create(name="教学笔记组")
        cls.repo = NoteRepo.objects.create(slug="manage", relative_path="course", title="原有笔记")

    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.enterContext(self.settings(NOTES_ROOT=self.root))
        for name in ("course", "new-course", "second-course"):
            folder = self.root / name
            folder.mkdir()
            (folder / "README.md").write_text(f"# {name}", encoding="utf-8")
        self.management = reverse("notes:repo_manage_list")
        self.add = reverse("notes:repo_manage_add")
        self.edit = reverse("notes:repo_manage_edit", args=[self.repo.pk])
        self.data = {
            "title": "更新笔记",
            "slug": self.repo.slug,
            "relative_path": self.repo.relative_path,
            "description": "笔记简介",
            "tags": "训练,笔记",
            "order": "5",
            "is_visible": "on",
            "allowed_groups": [str(self.group.pk)],
        }

    def confirmation(self, response):
        self.assertContains(response, "确认匿名访问范围")
        return BeautifulSoup(response.content, "html.parser").select_one('input[name="confirmation"]')["value"]

    def test_management_permissions_and_links_do_not_shadow_registered_notes(self):
        reader = reverse("notes:repo_list")
        detail = reverse("notes:note_repo_index", args=[self.repo.slug])
        for user, status in ((None, 302), (self.staff, 403)):
            if user:
                self.client.force_login(user)
            for url in (self.management, self.add, self.edit):
                with self.subTest(user=user, url=url):
                    self.assertEqual(self.client.get(url).status_code, status)
                    self.assertEqual(self.client.post(url, self.data).status_code, status)
        self.assertNotContains(self.client.get(reader), self.management)
        self.assertContains(self.client.get(detail), "course")
        self.client.force_login(self.superuser)
        self.assertContains(self.client.get(reader), self.management)
        self.assertContains(self.client.get(self.management), self.edit)
        self.assertContains(self.client.get(self.edit), "旧链接失效")
        self.repo.refresh_from_db()
        self.assertEqual(self.repo.title, "原有笔记")

    def test_register_and_edit_private_repo_without_preview(self):
        self.client.force_login(self.superuser)
        data = {**self.data, "slug": "new", "relative_path": "new-course"}
        self.assertRedirects(self.client.post(self.add, data), self.management)
        created = NoteRepo.objects.get(slug="new")
        self.assertEqual((created.relative_path, created.tags, created.order), ("new-course", "训练,笔记", 5))
        self.assertFalse(created.allow_anonymous_access)
        self.assertEqual(list(created.allowed_groups.all()), [self.group])
        self.assertRedirects(self.client.post(self.edit, self.data), self.management)
        self.repo.refresh_from_db()
        self.assertEqual(self.repo.title, "更新笔记")
        self.assertEqual(list(self.repo.allowed_groups.all()), [self.group])

    def test_directory_stats_are_grouped_on_the_management_page(self):
        (self.root / "course" / "lessons").mkdir()
        self.repo.relative_path = "course/lessons"
        self.repo.save()
        NoteRepo.objects.create(slug="hidden", relative_path="new-course", title="隐藏仓库", is_visible=False)
        NoteRepo.objects.create(slug="missing", relative_path="course-missing/subdir", title="缺失仓库")
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("notes:repo_list"))
        self.assertNotContains(response, "笔记库目录统计")
        self.assertEqual(response.context["repos"], [self.repo])

        response = self.client.get(self.management)
        self.assertContains(response, "笔记库目录统计")
        cards = BeautifulSoup(response.content, "html.parser").select(
            "section[aria-labelledby=repo-directory-stats-title] details"
        )
        self.assertEqual(
            [card.select_one("summary .badge").get_text(strip=True) for card in cards], ["3", "1", "1", "1", "1"]
        )
        self.assertEqual(
            dict(response.context["repo_stats_rows"]),
            {
                "全部顶层目录": ["course", "new-course", "second-course"],
                "已显示的笔记仓库": ["manage → course/lessons"],
                "已隐藏的笔记仓库": ["hidden → new-course"],
                "未登记的顶层目录": ["second-course"],
                "目录缺失或不可用": ["missing → course-missing/subdir"],
            },
        )

    def test_opening_access_requires_confirmation_and_closing_is_immediate(self):
        self.client.force_login(self.superuser)
        public_data = {**self.data, "allow_anonymous_access": "on"}
        url = reverse("notes:note_repo_index", args=[self.repo.slug])
        response = self.client.post(self.edit, public_data)
        self.assertContains(response, url)
        token = self.confirmation(response)
        self.repo.refresh_from_db()
        self.assertFalse(self.repo.allow_anonymous_access)
        self.assertEqual(self.repo.title, "原有笔记")
        self.assertRedirects(self.client.post(self.edit, {**public_data, "confirmation": token}), self.management)
        self.repo.refresh_from_db()
        self.assertTrue(self.repo.allow_anonymous_access)
        self.assertContains(self.client.get(self.management), f'href="{url}"')
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(self.superuser)
        self.assertRedirects(self.client.post(self.edit, self.data), self.management)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)

    def test_confirmation_binds_the_directory_link_and_saved_state(self):
        self.client.force_login(self.superuser)
        self.repo.allow_anonymous_access = True
        self.repo.save()
        public_data = {**self.data, "allow_anonymous_access": "on", "relative_path": "new-course", "slug": "new"}
        token = self.confirmation(self.client.post(self.edit, public_data))
        changed = {**public_data, "relative_path": "second-course", "slug": "second"}
        changed_token = self.confirmation(self.client.post(self.edit, {**changed, "confirmation": token}))
        self.repo.refresh_from_db()
        self.assertEqual((self.repo.relative_path, self.repo.slug), ("course", "manage"))

        self.repo.description = "后台并发修改"
        self.repo.save()
        response = self.client.post(self.edit, {**changed, "confirmation": changed_token})
        new_token = self.confirmation(response)
        self.assertContains(response, "/notes/second/")
        self.assertRedirects(self.client.post(self.edit, {**changed, "confirmation": new_token}), self.management)
        self.repo.refresh_from_db()
        self.assertEqual((self.repo.relative_path, self.repo.slug), ("second-course", "second"))

    def test_hidden_open_flag_needs_confirmation_before_becoming_visible(self):
        self.client.force_login(self.superuser)
        self.repo.is_visible = False
        self.repo.allow_anonymous_access = True
        self.repo.save()
        data = {**self.data, "allow_anonymous_access": "on"}
        token = self.confirmation(self.client.post(self.edit, data))
        self.repo.refresh_from_db()
        self.assertFalse(self.repo.is_visible)

        NoteRepo.objects.bulk_create(
            [
                NoteRepo(slug="child", relative_path=f"{self.repo.relative_path}/child", title="子仓库"),
            ]
        )
        response = self.client.post(self.edit, {**data, "confirmation": token})
        self.assertContains(response, "请先调整目录结构")
        self.repo.refresh_from_db()
        self.assertFalse(self.repo.is_visible)
