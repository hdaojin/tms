from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from core.documents.limits import MAX_CONTENT_BYTES
from notes.models import NoteRepo

from .models import TrainingTask
from .teaching_notes import read_task_note, task_note_route
from .test_process_refactor import ProcessFixture


class TaskTeachingNoteTests(ProcessFixture, TestCase):
    def setUp(self):
        super().setUp()
        directory = self.enterContext(TemporaryDirectory())
        self.enterContext(self.settings(NOTES_ROOT=directory))
        self.root = Path(directory) / "debian"
        self.root.mkdir()
        (self.root / "命令行.md").write_text("# 命令行", encoding="utf-8")
        self.repo = NoteRepo.objects.create(slug="debian", relative_path="debian", title="教学笔记库")
        self.link = reverse("notes:note_detail", args=["debian", "命令行"])
        self.coach.user_permissions.add(Permission.objects.get(content_type__app_label="notes", codename="view_noterepo"))
        self.coach = type(self.coach).objects.get(pk=self.coach.pk)

    def test_single_field_and_same_origin_link(self):
        self.client.force_login(self.coach)
        url = reverse("training:slot_task_create", args=[self.slot.pk])
        response = self.client.get(url)
        self.assertNotContains(response, 'name="teaching_note"')
        self.assertContains(response, 'name="coach_link"')
        with self.settings(ALLOWED_HOSTS=["test.example"]):
            response = self.client.post(url, {"title": "备课", "coach_link": f"http://test.example{self.link}#goal"},
                                        HTTP_HOST="test.example")
        self.assertEqual(response.status_code, 302)
        task = TrainingTask.objects.get(schedule_slot=self.slot)
        self.assertEqual(task.coach_link, self.link + "#goal")
        self.assertEqual(read_task_note(task, self.coach), (f"{self.repo.pk}/命令行.md", "# 命令行"))
        with self.assertRaises(ValidationError):
            read_task_note(task, self.student)
        self.repo.allowed_groups.add(Group.objects.create(name="其他教师"))
        with self.assertRaises(ValidationError):
            read_task_note(task, self.coach)

    def test_other_origins_remain_ordinary_links(self):
        self.client.force_login(self.coach)
        url = reverse("training:slot_task_create", args=[self.slot.pk])
        first = "https://other.example/notes/debian/lesson/"
        response = self.client.post(url, {"title": "外部资源", "coach_link": first})
        self.assertEqual(response.status_code, 302)
        task = TrainingTask.objects.get(schedule_slot=self.slot)
        self.assertEqual(task.coach_link, first)
        self.assertIsNone(task_note_route(task.coach_link))
        for value in ("", "//other.example/notes/debian/lesson/", "/training/", "/notes/debian/a/print/"):
            with self.subTest(value=value):
                self.assertIsNone(task_note_route(value))
        for value in ("../debian/命令行", "未找到", "%252e%252e/secret", ".git/secret"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                read_task_note(TrainingTask(coach_link=f"/notes/debian/{value}/"), self.coach)

    def test_note_read_size_boundary(self):
        task = TrainingTask(coach_link=self.link)
        path = self.root / "命令行.md"
        path.write_bytes(b"a" * MAX_CONTENT_BYTES)
        self.assertEqual(len(read_task_note(task, self.coach)[1]), MAX_CONTENT_BYTES)
        with path.open("ab") as note:
            note.write(b"x")
        with self.assertRaises(ValidationError) as raised:
            read_task_note(task, self.coach)
        self.assertEqual(raised.exception.code, "note_too_large")


class TaskLinkMigrationTests(TransactionTestCase):
    def test_primary_wins_and_note_only_becomes_local_link(self):
        before = [("training", "0034_task_teaching_note"), ("notes", "0003_alter_noterepo_allowed_groups")]
        after = [("training", "0035_use_coach_link_for_teaching_notes")]
        executor = MigrationExecutor(connection)
        executor.migrate(before)
        try:
            apps = executor.loader.project_state(before).apps
            user = apps.get_model("auth", "User").objects.create(username="teaching-note-migration")
            project = apps.get_model("standards", "SkillProject").objects.create(code="NOTE", name="讲义")
            day = date(2026, 1, 1)
            cycle = apps.get_model("training", "TrainingCycle").objects.create(
                skill_project=project, code="NOTE", name="测试", start_date=day,
            )
            plan = apps.get_model("training", "TrainingPlan").objects.create(
                training_cycle=cycle, title="训练", start_date=day, end_date=day, created_by=user,
            )
            repo = apps.get_model("notes", "NoteRepo").objects.create(slug="linux", relative_path="linux", title="讲义")
            tasks = apps.get_model("training", "TrainingTask").objects
            old_link = "https://example.org/other"
            values = dict(training_plan=plan, planned_date=day, created_by=user, teaching_note=f"{repo.pk}/课堂 1.md")
            primary = tasks.create(title="主链接", coach_link=old_link, **values)
            note_only = tasks.create(title="讲义", **values)
            executor = MigrationExecutor(connection)
            executor.migrate(after)
            migrated = executor.loader.project_state(after).apps.get_model("training", "TrainingTask")
            self.assertNotIn("teaching_note", [field.name for field in migrated._meta.fields])
            self.assertEqual(migrated.objects.get(pk=primary.pk).coach_link, old_link)
            self.assertEqual(migrated.objects.get(pk=note_only.pk).coach_link, "/notes/linux/课堂%201.md/")
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
