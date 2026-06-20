from pathlib import Path
import shutil
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from notes.models import NoteRepo
from notes.permissions import can_access_note_content, can_access_note_repo
from notes.utils import NoteContent


User = get_user_model()


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
		self.note_repo = NoteRepo.objects.create(slug="private-repo", title="私有笔记")
		self.note_repo.allowed_groups.add(self.allowed_group)

	def test_can_access_note_repo_requires_allowed_group(self):
		self.assertTrue(can_access_note_repo(self.allowed_user, "private-repo"))
		self.assertFalse(can_access_note_repo(self.denied_user, "private-repo"))

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


class NoteAssetViewTests(TestCase):
	def setUp(self):
		self.allowed_group = Group.objects.create(name="资产访问组")
		self.allowed_user = User.objects.create_user(username="asset-allowed", password="testpass123")
		self.allowed_user.groups.add(self.allowed_group)
		self.denied_user = User.objects.create_user(username="asset-denied", password="testpass123")
		self.note_repo = NoteRepo.objects.create(slug="private-repo", title="私有笔记")
		self.note_repo.allowed_groups.add(self.allowed_group)

		self.temp_dir = Path.cwd() / ".tmp-test-notes"
		shutil.rmtree(self.temp_dir, ignore_errors=True)
		self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

		repo_dir = self.temp_dir / "private-repo" / "assets"
		repo_dir.mkdir(parents=True)
		(repo_dir / "diagram.png").write_bytes(b"fake-image-bytes")

		self.notes_root_patcher = patch("notes.views.NOTES_ROOT", self.temp_dir)
		self.notes_root_patcher.start()
		self.addCleanup(self.notes_root_patcher.stop)

	def test_asset_view_forbids_user_without_repo_access(self):
		self.client.force_login(self.denied_user)

		response = self.client.get(
			reverse("note_asset", kwargs={"repo": "private-repo", "asset_path": "assets/diagram.png"})
		)

		self.assertEqual(response.status_code, 403)

	def test_asset_view_hides_missing_asset_from_user_without_repo_access(self):
		self.client.force_login(self.denied_user)

		response = self.client.get(
			reverse("note_asset", kwargs={"repo": "private-repo", "asset_path": "assets/missing.png"})
		)

		self.assertEqual(response.status_code, 403)

	def test_asset_view_allows_user_with_repo_access(self):
		self.client.force_login(self.allowed_user)

		response = self.client.get(
			reverse("note_asset", kwargs={"repo": "private-repo", "asset_path": "assets/diagram.png"})
		)

		self.assertEqual(response.status_code, 200)
		response.close()
