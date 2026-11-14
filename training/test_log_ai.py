import json
import socket
from datetime import date, datetime, timedelta, timezone as utc_timezone
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from pypdf import PdfReader, PdfWriter

from ai.models import AIModel
from bs4 import BeautifulSoup
from core.documents.service import generate_document_pdf, render_document_html
from core.documents.types import DocumentRenderError

from . import log_generation, process
from .log_documents import document_input, draft_document, source_digest, submit_draft
from .log_references import read_reference
from .log_sources import COACH, FIELDS, STUDENT, collect_sources, validate_body
from .log_web_references import fetch_reference_pages
from .models import TrainingLog, TrainingLogDraft, TrainingLogGeneration, TrainingLogPrompt
from .test_process_refactor import ProcessFixture

Status = TrainingLogGeneration.Status


def example_body(role):
    return {key: f"**{label}**\n\n实际记录及后续计划。" for key, label in FIELDS[role]}


class TrainingLogAITests(ProcessFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        settings = override_settings(PRIVATE_MEDIA_ROOT=self.media.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.cycle_obj.status = "active"
        self.cycle_obj.save()
        self.cycle_obj.members.filter(user__in=[self.student, self.student2, self.coach, self.other]).update(
            is_current=True
        )
        self.day = date(2026, 1, 1)
        self.task_obj = self.task(
            title="配置路由",
            requirements="验证端到端连通",
            subtask_titles=["配置地址", "核对路由表"],
            assign_all=True,
        )
        self.execution = self.task_obj.executions.get(user=self.student)
        self.student.user_permissions.add(*Permission.objects.filter(content_type__app_label="ai"))
        self.model = AIModel.objects.create(
            owner=self.student,
            provider="deepseek",
            name="已验证模型",
            base_url="https://api.deepseek.com",
            model_id="deepseek-flash",
            verified=True,
            encrypted_api_key=b"fixture",
        )
        self.day_fields = {"cycle": self.cycle_obj.pk, "training_date": self.day.isoformat()}

    def fill(self, completed="已核对路由表", problems="一处下一跳待复核"):
        return process.save_progress(
            self.execution,
            self.student,
            training_date=self.day,
            completed=completed,
            problems=problems,
            checklist=[{**item, "done": True} for item in self.task_obj.subtasks],
        )

    def draft(self):
        return TrainingLogDraft.objects.create(author=self.student, cycle=self.cycle_obj, training_date=self.day)

    def prepare(self, draft, **kwargs):
        return log_generation.prepare_generation(
            draft,
            model=self.model,
            thinking="",
            effort="",
            instructions="补充说明",
            references="https://example.com/",
            reference_text="",
            image_ids=kwargs.get("image_ids", set()),
            target_words=None,
        )

    def ready_draft(self):
        self.fill()
        draft = self.draft()
        job = self.prepare(draft)
        log_generation.confirm_generation(draft, job.pk)
        with patch("training.log_generation.generate_text", return_value=json.dumps(example_body(STUDENT))):
            self.assertTrue(log_generation.run_generation())
        log_generation.resolve_generation(draft, job.pk, apply=True, revision=draft.revision)
        draft.refresh_from_db()
        return draft

    def test_daily_page_derives_status_and_preserves_old_record(self):
        old = process.save_progress(self.execution, self.student, completed="旧填报", problems="")
        self.client.force_login(self.student)
        url = reverse("training:daily_progress") + f"?cycle={self.cycle_obj.pk}&training_date={self.day}"
        key = f"task-{self.execution.pk}"
        ids = [item["id"] for item in self.task_obj.subtasks]

        response = self.client.get(url)
        self.assertContains(response, "2026年1月1日训练完成情况")
        self.assertContains(response, "旧填报")
        invalid = self.client.post(url, {"version": response.context["version"]})
        self.assertContains(invalid, "有未完成项目时")
        self.assertFalse(self.execution.progress_records.filter(training_date=self.day).exists())

        for checked, expected in [(ids[:0], "unfinished"), (ids[:1], "partially_completed"), (ids, "completed")]:
            token = self.client.get(url).context["version"]
            response = self.client.post(url, {"version": token, f"{key}-items": checked, "problems": "待核对"})
            self.assertRedirects(
                response, f"{reverse('training:my_training')}?date={self.day}", fetch_redirect_response=False
            )
            self.execution.refresh_from_db()
            self.assertEqual(self.execution.status, expected)
            progress = self.execution.progress_records.get(training_date=self.day)
            self.assertEqual(sum(item["done"] for item in progress.checklist), len(checked))
        self.assertEqual(progress.revisions.count(), 2)
        old.refresh_from_db()
        self.assertIsNone(old.training_date)
        self.assertEqual(old.completed, "旧填报")
        with self.assertRaisesMessage(ValidationError, "子任务清单不能再修改"):
            from .scheduling import save_slot_task

            save_slot_task(self.slot, self.coach, {"subtask_titles": ["新任务"]}, task=self.task_obj)

    def test_day_issues_and_merged_checklist_are_saved_as_daily_material(self):
        second = self.task(slot=self.other_slot(), title=self.task_obj.title)
        self.client.force_login(self.student)
        url = reverse("training:daily_progress") + f"?cycle={self.cycle_obj.pk}&training_date={self.day}"
        page = self.client.get(url)
        self.assertEqual(len(page.context["rows"]), 1)
        response = self.client.post(url, {
            "version": page.context["version"],
            f"task-{self.execution.pk}-items": [self.task_obj.subtasks[0]["id"]],
            "issues-TOTAL_FORMS": "2", "issues-INITIAL_FORMS": "0",
            "issues-0-description": "地址冲突", "issues-0-domain": self.linux.pk,
            "issues-1-description": "链路不通", "issues-1-domain": self.linux.pk,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(second.executions.get(user=self.student).status, "partially_completed")
        _, materials, _ = collect_sources(self.student, self.cycle_obj, self.day)
        self.assertEqual(len([item for item in materials if item.get("任务") == self.task_obj.title]), 1)
        summary = next(item["当天训练总结"] for item in materials if "当天训练总结" in item)
        self.assertEqual([item["问题"] for item in summary["问题列表"]], ["地址冲突", "链路不通"])

    def test_daily_save_is_atomic_across_tasks(self):
        second = self.task(slot=self.other_slot(), title="第二项", assign_all=True).executions.get(user=self.student)
        process.save_progress(second, self.student, training_date=self.day, completed="", problems="旧的任务说明")
        self.client.force_login(self.student)
        url = reverse("training:daily_progress") + f"?cycle={self.cycle_obj.pk}&training_date={self.day}"
        page = self.client.get(url)
        token = page.context["version"]
        form = BeautifulSoup(page.content, "html.parser").select_one('form[enctype="multipart/form-data"]')
        self.assertEqual(len(form.select("section[id^=task-]")), 2)
        self.assertIsNotNone(form.select_one('textarea[name="issues-0-description"]'))
        self.assertNotIn("旧的任务说明", form.select_one('textarea[name="issues-0-description"]').get_text())
        self.assertIn("旧的任务说明", form.select_one(f"#task-{second.pk} details").get_text())
        self.assertEqual(len(form.select('input[type=file][name="images"]')), 1)
        self.assertNotIn("上午", [heading.get_text(strip=True) for heading in form.select("h2")])
        self.assertEqual(form.select_one("button[type=submit]").parent, form.select_one("a.btn-outline").parent)
        response = self.client.post(url, {"version": token, f"task-{second.pk}-items": "task"})
        self.assertContains(response, "有未完成项目时")
        self.assertFalse(self.execution.progress_records.exists())
        image = Path("training/static/training/school-logo.png").read_bytes()
        response = self.client.post(
            url,
            {
                "version": token,
                f"task-{second.pk}-items": "task",
                "problems": "还有任务未开始",
                "images": [SimpleUploadedFile("process.png", image)],
            },
        )
        self.assertEqual(response.status_code, 302)
        first_record = self.execution.progress_records.get()
        second_record = second.progress_records.get()
        self.assertEqual([first_record.problems, second_record.problems], ["还有任务未开始", ""])
        self.assertEqual(second_record.revisions.get().problems, "旧的任务说明")
        self.assertEqual(first_record.attachments.count() + second_record.attachments.count(), 1)
        self.assertContains(self.client.get(url), "process.png", count=1)
        _, material, missing = collect_sources(self.student, self.cycle_obj, self.day)
        self.assertFalse(missing)
        self.assertEqual(json.dumps(material, ensure_ascii=False).count("还有任务未开始"), 1)

    def test_historical_day_in_completed_cycle(self):
        self.cycle_obj.status = "completed"
        self.cycle_obj.save()
        with patch("django.utils.timezone.now", return_value=datetime(2026, 2, 1, tzinfo=utc_timezone.utc)):
            self.fill()
            self.client.force_login(self.student)
            response = self.client.post(f"{reverse('training:log_ai_start')}?history=1", self.day_fields, follow=True)
        self.assertContains(response, "当日任务与完成情况")
        self.assertContains(response, "2026-01-01")
        self.assertFalse(TrainingLogDraft.objects.exists())

    def test_role_materials_and_coverage(self):
        draft = self.draft()
        with self.assertRaisesMessage(ValidationError, "请先填写训练完成情况"):
            self.prepare(draft)
        self.fill()
        job = self.prepare(draft)
        log_generation.confirm_generation(draft, job.pk)
        with patch("training.log_generation.generate_text", return_value=json.dumps(example_body(STUDENT))):
            self.assertTrue(log_generation.run_generation())
        log_generation.resolve_generation(draft, job.pk, apply=True, revision=draft.revision)
        draft.refresh_from_db()
        self.assertEqual(draft.body, example_body(STUDENT))
        reviewed_source = source_digest(log_generation.source_for(draft)[0])
        with patch("training.log_documents.generate_document_pdf", return_value=b"%PDF-1.4\n"):
            log = submit_draft(draft, draft.revision, reviewed_source, False)
        self.assertEqual(log.author, self.student)
        source, material, missing = collect_sources(self.coach, self.cycle_obj, self.day)
        self.assertEqual(missing, [])
        self.assertEqual(source["tasks"][0]["expected"], 2)
        self.assertEqual(material[0]["已填人数"], 1)
        self.assertEqual(material[0]["执行填报"][0]["已完成"], ["配置地址", "核对路由表"])
        self.assertNotIn(self.student.first_name, json.dumps(material, ensure_ascii=False))
        self.assertEqual(collect_sources(self.other, self.cycle_obj, self.day)[0]["tasks"], [])
        self.task_obj.__class__.objects.filter(pk=self.task_obj.pk).update(requirements="")
        source, _, missing = collect_sources(self.coach, self.cycle_obj, self.day)
        self.assertFalse(missing)
        self.assertEqual(source["goal_task_ids"], [str(self.task_obj.pk)])

    def test_coach_reference_is_scoped_and_hidden_in_student_preview(self):
        self.fill()
        source, _, _ = collect_sources(self.coach, self.cycle_obj, self.day)
        source["tasks"][0]["technical_excerpt"]["训练说明"] = "教练历史技术摘录"
        log = TrainingLog.objects.create(
            author=self.coach,
            training_cycle=self.cycle_obj,
            training_date=self.day,
            online_document={
                "source": source,
                "body": {**example_body(COACH), "process": "其他选手私密内容"},
            },
        )
        draft = self.draft()
        job = self.prepare(draft)
        self.assertEqual(job.source["coach_logs"][0]["task_ids"], [self.task_obj.pk])
        self.assertIn("教练历史技术摘录", job.message)
        self.assertNotIn("其他选手私密内容", job.message)
        self.client.force_login(self.student)
        response = self.client.get(reverse("training:log_ai_draft", args=[draft.pk]))
        self.assertContains(response, "已找到 1 份相关教练正式日志")
        self.assertNotContains(response, "教练历史技术摘录")
        self.assertNotContains(response, "其他选手私密内容")

        log.online_document["body"]["process"] = "已变更的过程记录"
        log.save(update_fields=["online_document"])
        self.assertRaisesMessage(ValidationError, "素材已变化", log_generation.confirm_generation, draft, job.pk)

        log.online_document["source"]["tasks"][0]["id"] = self.task_obj.pk + 1
        log.save(update_fields=["online_document"])
        self.assertEqual(collect_sources(self.student, self.cycle_obj, self.day)[0]["coach_logs"], [])

    def test_task_attachment_content_is_authorized_and_versioned(self):
        task = self.task(
            slot=self.other_slot(),
            title="附件任务",
            assign_all=False,
            competitors=[self.student.pk],
            attachments=[SimpleUploadedFile("guide.txt", b"routing guide")],
        )
        source, materials, _ = collect_sources(self.student, self.cycle_obj, self.day)
        self.assertIn("routing guide", json.dumps(materials))
        _, other_materials, _ = collect_sources(self.student2, self.cycle_obj, self.day)
        self.assertNotIn("routing guide", json.dumps(other_materials))

        attachment = task.attachments.get()
        Path(attachment.file.path).write_bytes(b"new routing guide")
        changed, materials, _ = collect_sources(self.student, self.cycle_obj, self.day)
        self.assertNotEqual(source, changed)
        self.assertIn("new routing guide", json.dumps(materials))

    def test_coach_can_generate_without_any_student_progress(self):
        self.coach.user_permissions.add(*Permission.objects.filter(content_type__app_label="ai"))
        self.model.owner = self.coach
        self.model.save(update_fields=["owner", "updated_at"])
        draft = TrainingLogDraft.objects.create(author=self.coach, cycle=self.cycle_obj, training_date=self.day)
        self.client.force_login(self.coach)
        url = reverse("training:log_ai_draft", args=[draft.pk])

        self.assertContains(self.client.get(url), "已填 0/2 人")
        response = self.client.post(url, {"action": "prepare", "model": self.model.pk})
        self.assertEqual(response.status_code, 302)
        job = TrainingLogGeneration.objects.get(draft=draft)
        self.assertEqual(json.loads(job.message)["任务及填报"][0]["执行填报"], [])
        self.assertIn("尚无填报可供核实", job.prompt)
        log_generation.confirm_generation(draft, job.pk)
        with patch("training.log_generation.generate_text", return_value=json.dumps(example_body(COACH))):
            self.assertTrue(log_generation.run_generation())
        job.refresh_from_db()
        self.assertEqual(job.status, Status.READY)

    def test_writing_today_opens_editor_without_creating_draft_on_get(self):
        self.client.force_login(self.student)
        board = self.client.get(reverse("training:my_training"))
        self.assertContains(board, "填写训练完成情况")
        self.assertContains(board, "编写训练日志")
        self.assertContains(board, "09:00–12:00")
        self.assertContains(self.client.get(reverse("training:log_ai_start")), "请先填写训练完成情况")
        self.fill()
        response = self.client.get(reverse("training:log_ai_start"))
        self.assertContains(response, "当日任务与完成情况")
        self.assertNotContains(response, "暂无个人训练进度填报")
        self.assertContains(response, "填写训练完成情况")
        self.assertContains(response, "扩展信息")
        self.assertContains(response, "保存插图")
        self.assertNotContains(response, 'name="reference"')
        self.assertFalse(TrainingLogDraft.objects.exists())

    def test_missing_goal_links_to_task_editor_only_when_authorized(self):
        self.task_obj.__class__.objects.filter(pk=self.task_obj.pk).update(requirements="")
        self.coach.user_permissions.add(*Permission.objects.filter(content_type__app_label="ai"))
        self.model.owner = self.coach
        self.model.save(update_fields=["owner", "updated_at"])
        self.client.force_login(self.coach)
        url = reverse("training:log_ai_start")
        editor = reverse("training:task_edit", args=[self.task_obj.pk])
        response = self.client.get(url)
        self.assertContains(response, "训练目标由 AI 拟写")
        self.assertContains(response, f'href="{editor}?focus=goal#id_requirements"')
        self.assertContains(response, "预览发送内容")
        self.assertContains(response, "扩展信息")
        self.assertContains(self.client.get(f"{editor}?focus=goal"), "<details open>")
        self.coach.user_permissions.remove(
            Permission.objects.get(
                content_type__app_label="training",
                codename="change_trainingtask",
            )
        )
        self.assertNotContains(self.client.get(url), "编辑训练目标")

    def test_coach_generates_only_missing_goals_and_preserves_them_on_draft_edit(self):
        task = self.task(slot=self.other_slot(), title="配置防火墙", subtask_titles=["核对访问规则"], assign_all=True)
        self.coach.user_permissions.add(*Permission.objects.filter(content_type__app_label="ai"))
        self.model.owner = self.coach
        self.model.save(update_fields=["owner", "updated_at"])
        draft = TrainingLogDraft.objects.create(author=self.coach, cycle=self.cycle_obj, training_date=self.day)
        self.client.force_login(self.coach)
        url = reverse("training:log_ai_draft", args=[draft.pk])
        self.assertEqual(self.client.post(url, {"action": "prepare", "model": self.model.pk}).status_code, 302)
        job = TrainingLogGeneration.objects.get(draft=draft)
        self.assertEqual(job.source["goal_task_ids"], [str(task.pk)])
        self.assertIn('"任务编号": "' + str(task.pk) + '"', job.message)
        self.assertIn("suggested_goals", job.prompt)
        body = {**example_body(COACH), "task_title": "网络配置训练"}
        with self.assertRaises(ValidationError):
            validate_body(COACH, {**body, "suggested_goals": {str(self.task_obj.pk): "错误目标"}}, job.source)
        body["suggested_goals"] = {str(task.pk): "能核对防火墙访问规则"}
        log_generation.confirm_generation(draft, job.pk)
        with patch("training.log_generation.generate_text", return_value=json.dumps(body)):
            self.assertTrue(log_generation.run_generation())
        self.assertContains(self.client.get(url), "能核对防火墙访问规则")
        log_generation.resolve_generation(draft, job.pk, apply=True, revision=draft.revision)
        draft.refresh_from_db()
        fields = {key: value for key, value in body.items() if key != "suggested_goals"}
        log_generation.edit_draft(draft, draft.revision, fields | {"process": "补充过程记录"})
        preview = self.client.get(reverse("training:log_ai_preview", args=[draft.pk]))
        self.assertContains(preview, "能核对防火墙访问规则")
        self.assertNotContains(preview, "建议目标")
        self.assertContains(preview, "验证端到端连通")
        self.assertFalse(BeautifulSoup(preview.content, "html.parser").select("#log-goals strong"))
        task.refresh_from_db()
        self.assertEqual(task.requirements, "")

    def test_my_training_uploads_to_the_selected_day_and_replaces_actions_after_submission(self):
        self.client.force_login(self.student)
        today_url = reverse("training:my_training")
        with patch("django.utils.timezone.now", return_value=datetime(2026, 1, 2, tzinfo=utc_timezone.utc)):
            response = self.client.get(today_url, {"date": self.day.isoformat()})
            upload = response.context["date_groups"][0]["actions"][0]["upload"]
            self.assertContains(response, "请先填写训练完成情况")
            self.assertContains(self.client.get(upload), "请先填写训练完成情况")
            self.fill()
            self.assertIn(reverse("training:log_backfill"), upload)
            self.assertIn(f"training_date={self.day}", upload)
            form = self.client.get(upload).context["form"]
            self.assertTrue(form.fields["training_date"].disabled)
            self.assertTrue(form.fields["training_cycle"].disabled)
            posted = self.client.post(
                upload,
                {
                    "training_cycle": self.cycle_obj.pk + 1,
                    "training_date": "2026-01-02",
                    "document": SimpleUploadedFile("log.pdf", b"%PDF-1.4\n%%EOF"),
                },
            )
            log = TrainingLog.objects.get(author=self.student)
            detail = reverse("training:log_detail", args=[log.pk])
            self.assertRedirects(posted, f"{detail}?return_date={self.day}&return_plan={self.plan.pk}")
            crumbs = self.client.get(posted.url).context["breadcrumbs"]
            self.assertEqual(crumbs[-2].url, f"{today_url}?date={self.day}&plan={self.plan.pk}")
            self.assertEqual(log.training_date, self.day)
            self.assertEqual(log.training_cycle, self.cycle_obj)
            self.assertTrue(log.is_backfill)
            response = self.client.get(today_url, {"date": self.day.isoformat()})
            self.assertContains(response, "查看训练日志")
            self.assertNotContains(response, ">上传训练日志</a>")
            self.assertNotContains(response, ">编写训练日志</a>")

    def test_no_usable_model_offers_add_and_upload(self):
        self.fill()
        self.model.verified = False
        self.model.save(update_fields=["verified", "updated_at"])
        self.client.force_login(self.student)
        response = self.client.get(reverse("training:log_ai_start"))
        self.assertContains(response, reverse("ai:create"))
        self.assertContains(response, reverse("training:log_create"))
        self.assertContains(response, "当前没有可用的 AI 模型")
        self.assertNotContains(response, "预览发送内容")

    def test_save_draft_htmx_returns_editor_and_refreshes_preview_version(self):
        draft = self.ready_draft()
        self.client.force_login(self.student)
        url = reverse("training:log_ai_draft", args=[draft.pk])
        for notes in ("第一次修改", "第二次修改"):
            response = self.client.post(
                url,
                {**draft.body, "action": "edit", "revision": draft.revision, "notes": notes},
                HTTP_HX_REQUEST="true",
            )
            draft.refresh_from_db()
            self.assertContains(response, "草稿已保存")
            self.assertContains(response, f"?revision={draft.revision}")
            self.assertContains(response, "h-[48rem]")
            self.assertNotContains(response, "当日任务与完成情况")
            self.assertEqual(draft.body["notes"], notes)
        self.assertContains(self.client.get(reverse("training:log_ai_preview", args=[draft.pk])), "第二次修改")

    def test_multiple_tasks_use_summary_title_and_bounded_suggested_content(self):
        second = self.task(slot=self.other_slot(), title="验证连通", requirements="验证访问", assign_all=True)
        process.save_progress(
            second.executions.get(user=self.student),
            self.student,
            training_date=self.day,
            completed="已连通",
            problems="",
        )
        self.fill()
        source, _, missing = collect_sources(self.student, self.cycle_obj, self.day)
        self.assertFalse(missing)
        body = {**example_body(STUDENT), "task_title": "路由配置与验证", "suggested_items": ["验证端到端连通"]}
        self.assertEqual(validate_body(STUDENT, body, source), body)
        with self.assertRaisesMessage(ValidationError, "最多 20 字"):
            validate_body(STUDENT, {**body, "task_title": "题" * 21}, source)
        with self.assertRaisesMessage(ValidationError, "1 至 10 条"):
            validate_body(STUDENT, {**body, "suggested_items": ["核对"] * 11}, source)
        doc = document_input({"body": body, "source": source}, [])
        soup = BeautifulSoup(render_document_html(doc), "html.parser")
        self.assertEqual(
            doc.title,
            f"{self.cycle_obj.name}{self.project.name}精英班选手日志（{self.student.first_name}）",
        )
        rows = soup.select("#log-metadata tr")
        self.assertEqual(rows[1].td.get_text(strip=True), self.linux.name)
        self.assertEqual(rows[2].td.get_text(strip=True), "路由配置与验证")
        self.assertEqual(
            [node.get_text() for node in soup.select("#log-outline li")], ["配置地址", "核对路由表", "验证端到端连通"]
        )

    def test_uploaded_and_imported_images_require_confirmation_and_render_inline(self):
        def picture(name):
            return SimpleUploadedFile(name, Path("training/static/training", name).read_bytes())

        progress = process.save_progress(
            self.execution,
            self.student,
            training_date=self.day,
            completed="完成检查",
            problems="",
            files=[picture("school-logo.png")],
            checklist=[{**item, "done": True} for item in self.task_obj.subtasks],
        )
        draft = self.draft()
        self.client.force_login(self.student)
        url = reverse("training:log_ai_draft", args=[draft.pk])
        response = self.client.post(
            url, {"action": "prepare", "model": self.model.pk, "images": [picture("worldskills-china.png")]}
        )
        self.assertContains(response, "有尚未保存的日志插图")
        self.assertFalse(draft.images.exists())
        self.assertFalse(TrainingLogGeneration.objects.filter(draft=draft).exists())
        response = self.client.post(
            url,
            {
                "action": "image",
                "model": self.model.pk,
                "instructions": "保留本次写作要求",
                "images": [picture("worldskills-china.png")],
                "progress_images": [progress.attachments.get().pk],
            },
        )
        self.assertContains(response, "保留本次写作要求")
        self.assertEqual(draft.images.count(), 2)
        self.assertEqual(self.client.post(url, {"action": "prepare", "model": self.model.pk}).status_code, 302)
        job = TrainingLogGeneration.objects.get(draft=draft)
        inline, omitted = job.image_ids
        self.assertNotIn("school-logo", job.message)
        self.assertContains(self.client.get(url), reverse("training:log_ai_image", args=[draft.pk, inline]))
        log_generation.confirm_generation(draft, job.pk)
        self.assertContains(self.client.get(url), "等待生成")
        self.assertNotContains(self.client.get(url), "扩展信息")
        status_url = f"{url}?generation_status=1&seen_status=queued"
        self.assertEqual(self.client.get(status_url, headers={"HX-Request": "true"}).status_code, 204)
        body = example_body(STUDENT)
        body["notes"] += f"\n\n![路由截图](tms-asset:image-{inline})"

        def generate(*args):
            response = self.client.get(status_url, headers={"HX-Request": "true"})
            self.assertContains(response, "正在生成")
            self.assertContains(response, "seen_status=running")
            self.assertNotContains(response, "扩展信息")
            return json.dumps(body)

        with patch("training.log_generation.generate_text", side_effect=generate) as call:
            self.assertTrue(log_generation.run_generation())
        content = call.call_args.args[3].messages[1]["content"]
        self.assertEqual([block["type"] for block in content], ["text", "image_url", "image_url"])
        self.assertTrue(content[1]["image_url"]["url"].startswith("data:image/png;base64,"))
        response = self.client.get(status_url, headers={"HX-Request": "true"})
        self.assertContains(response, "生成完成")
        self.assertContains(response, "<strong>学习笔记</strong>", html=True)
        self.assertContains(response, reverse("training:log_ai_image", args=[draft.pk, omitted]))
        self.assertNotContains(response, "扩展信息")
        draft.refresh_from_db()
        log_generation.resolve_generation(draft, job.pk, apply=True, revision=draft.revision)
        draft.refresh_from_db()
        rendered = render_document_html(document_input(draft_document(draft), draft.images.all()))
        soup = BeautifulSoup(rendered, "html.parser")
        self.assertEqual(len(soup.select("#log-process img")), 1)
        self.assertFalse(soup.select("#log-gallery"))
        module_row = soup.select("#log-metadata tr")[1]
        self.assertEqual([node.get_text(strip=True) for node in module_row.find_all("th")], ["训练模块", "训练任务"])
        self.assertEqual(len(module_row.find_all(["th", "td"])), 4)
        with self.assertRaisesMessage(ValidationError, "每张图片只能引用一次"):
            validate_body(STUDENT, body | {"achievement": f"![截图](tms-asset:image-{inline})"}, job.source)

    def test_text_only_generation_retains_images_and_uses_text_payload(self):
        self.fill()
        draft = self.draft()
        draft.images.create(media_type="image/png", content=b"image", caption="")
        self.model.model_id = "deepseek-v4-pro"
        self.model.save(update_fields=["model_id", "updated_at"])
        self.client.force_login(self.student)
        url = reverse("training:log_ai_draft", args=[draft.pk])
        data = {"action": "prepare", "model": self.model.pk}
        self.assertContains(self.client.post(url, data), "所选模型不支持读图")
        self.assertEqual(self.client.post(url, {**data, "text_only": "on"}).status_code, 302)
        job = TrainingLogGeneration.objects.get(draft=draft)
        self.assertFalse(job.image_ids)
        log_generation.confirm_generation(draft, job.pk)
        with patch("training.log_generation.generate_text", return_value=json.dumps(example_body(STUDENT))) as call:
            self.assertTrue(log_generation.run_generation())
        self.assertIsInstance(call.call_args.args[3].messages[1]["content"], str)
        self.assertEqual(draft.images.count(), 1)

    def test_superuser_can_manage_role_prompts(self):
        url = reverse("training:log_settings")
        self.client.force_login(self.coach)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(url), "AI 写作提示词")
        data = {"action": "prompts"}
        for role in (COACH, STUDENT):
            data.update(
                {f"{role}-instructions": "按实际记录编写", f"{role}-min_words": 1000, f"{role}-max_words": 1400}
            )
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertEqual(TrainingLogPrompt.objects.count(), 2)
        self.assertIn("按实际记录编写", log_generation.system_prompt(STUDENT, None))
        self.assertContains(self.client.get(url), "系统约束")
        self.assertNotContains(self.client.get(url), "日志标题")
        self.assertIn("主体建议篇幅为 1000–1400 字", log_generation.system_prompt(STUDENT, None))
        self.assertIn("主体建议篇幅为 约 800 字", log_generation.system_prompt(STUDENT, 800))

    def test_log_heading_combines_audiences_in_task_order(self):
        from copy import copy

        from .models import TrainingPlan

        self.plan.implementation_audience = "第一梯队"
        self.plan.save(update_fields=["implementation_audience"])
        task = copy(self.task_obj)
        task.pk = None
        task.title = "第二项任务"
        second_plan = TrainingPlan.objects.get(pk=self.plan.pk)
        second_plan.pk = None
        second_plan.title = "另一计划"
        second_plan.implementation_audience = "第二梯队"
        second_plan.save()
        day = copy(self.slot.day)
        day.pk = None
        day.training_plan = second_plan
        day.save()
        slot = copy(self.slot)
        slot.pk = None
        slot.day = day
        slot.save()
        task.training_plan = second_plan
        task.schedule_slot = slot
        task.save()
        task.executions.create(user=self.student)
        source, _, _ = collect_sources(self.student, self.cycle_obj, self.day)
        self.assertEqual(
            source["header"]["heading"], f"{self.cycle_obj.name}{self.project.name}第一梯队、第二梯队",
        )

    def test_task_editor_searches_skills_and_saves_ordered_subtasks(self):
        from standards.models import Skill

        matching = Skill.objects.create(skill_project=self.project, primary_domain=self.linux, name="OSPF 配置")
        Skill.objects.create(skill_project=self.project, primary_domain=self.windows, name="OSPF 验证")
        search = reverse("training:task_skill_search", args=[self.slot.pk])
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(search, {"q": "ospf"}).status_code, 403)
        self.client.force_login(self.coach)
        self.assertEqual(
            self.client.get(search, {"q": "ospf"}).json()["results"],
            [
                {"id": matching.pk, "label": matching.name},
            ],
        )
        slot = self.other_slot()
        url = reverse("training:slot_task_create", args=[slot.pk])
        response = self.client.get(url)
        self.assertContains(response, "添加子任务")
        self.assertNotIn("priority", response.context["form"].fields)
        self.assertNotIn("estimated_minutes", response.context["form"].fields)
        self.assertEqual(
            self.client.post(
                url,
                {
                    "title": "动态子任务",
                    "subtask_titles": ["配置地址", "测试路由"],
                    "skills": [matching.pk],
                    "assign_all": "on",
                    "assignment_configured": "on",
                    "action": "publish",
                },
            ).status_code,
            302,
        )
        task = slot.tasks.get(title="动态子任务")
        self.assertEqual([item["title"] for item in task.subtasks], ["配置地址", "测试路由"])
        self.assertTrue(task.assign_all)
        self.assertEqual(task.executions.count(), 2)

    def test_early_training_is_in_material_but_has_no_module_label(self):
        from .scheduling import save_slot_task

        early = self.slot.day.slots.get(period="early")
        early.kind = "technical"
        early.primary_domain = self.linux
        early.save()
        early.domains.add(self.linux)
        early.coaches.add(self.coach)
        task = save_slot_task(early, self.coach, {"title": "早读任务", "requirements": "复习"}, publish=True)
        source, materials, _ = collect_sources(self.coach, self.cycle_obj, self.day)
        entry = next(item for item in source["tasks"] if item["id"] == task.pk)
        self.assertEqual(entry["domains"], [])
        self.assertIn("早读任务", [item["任务"] for item in materials])

    def test_generation_confirmation_worker_and_no_overwrite(self):
        draft = self.ready_draft()
        original = draft.body
        self.client.force_login(self.student)
        url = reverse("training:log_ai_draft", args=[draft.pk])
        response = self.client.post(url, {"action": "prepare", "model": self.model.pk, "instructions": "再检查一遍"})
        self.assertEqual(response.status_code, 302)
        job = TrainingLogGeneration.objects.get(draft=draft)
        review = self.client.get(url)
        self.assertContains(review, "api.deepseek.com")
        self.assertContains(review, "再检查一遍")
        self.assertEqual(job.status, Status.REVIEW)
        for _ in range(2):
            self.assertEqual(self.client.post(url, {"action": "confirm", "generation": job.pk}).status_code, 302)
        with patch("training.log_generation.generate_text", return_value="{}") as model_call:
            call_command("run_training_log_worker", once=True)
            call_command("run_training_log_worker", once=True)
        model_call.assert_called_once()
        self.assertEqual(model_call.call_args.args[3].response_mode, "json")
        job.refresh_from_db()
        draft.refresh_from_db()
        self.assertEqual(job.status, Status.FAILED)
        self.assertEqual(draft.body, original)

    def test_review_includes_reference_excerpt_and_can_be_cancelled(self):
        draft = self.ready_draft()
        self.client.force_login(self.student)
        url = reverse("training:log_ai_draft", args=[draft.pk])
        TrainingLogPrompt.objects.update_or_create(role=STUDENT, defaults={"min_words": 700, "max_words": 900})
        self.assertContains(self.client.get(url), "700–900 字")
        with patch("training.log_web_references.read_page", return_value="公开网页正文") as read:
            response = self.client.post(
                url, {"action": "prepare", "model": self.model.pk, "references": "https://example.com/"}
            )
        self.assertEqual(response.status_code, 302)
        read.assert_called_once_with("https://example.com/")
        job = TrainingLogGeneration.objects.get(draft=draft)
        self.assertContains(self.client.get(url), "公开网页正文")
        self.assertEqual(self.client.post(url, {"action": "cancel", "generation": job.pk}).status_code, 302)
        self.assertFalse(TrainingLogGeneration.objects.filter(pk=job.pk).exists())
        self.assertTrue(TrainingLogDraft.objects.get(pk=draft.pk).body)

    def test_reference_rejects_host_resolving_to_private_address(self):
        self.fill()
        addresses = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
        ]
        with (
            patch("training.log_web_references.socket.getaddrinfo", return_value=addresses),
            patch("training.log_web_references.socket.socket") as connect,
            self.assertRaisesMessage(ValidationError, "无法读取第 1 个参考链接"),
        ):
            fetch_reference_pages("https://example.com/")
        connect.assert_not_called()

    def test_expired_job_requires_explicit_retry_and_model_changes_block_calls(self):
        self.fill()
        draft = self.draft()
        job = self.prepare(draft)
        log_generation.confirm_generation(draft, job.pk)
        self.assertEqual(log_generation.claim_generation().pk, job.pk)
        TrainingLogGeneration.objects.filter(pk=job.pk).update(started_at=timezone.now() - timedelta(minutes=6))
        self.assertIsNone(log_generation.claim_generation())
        job.refresh_from_db()
        self.assertEqual(job.status, Status.FAILED)
        retry = self.prepare(draft)
        log_generation.confirm_generation(draft, retry.pk)
        AIModel.objects.filter(pk=self.model.pk).update(verified=False)
        with patch("training.log_generation.generate_text") as model_call:
            self.assertTrue(log_generation.run_generation())
        model_call.assert_not_called()
        retry.refresh_from_db()
        self.assertEqual(retry.status, Status.FAILED)

    def test_review_and_preview_are_owner_scoped(self):
        draft = self.ready_draft()
        url = reverse("training:log_ai_preview", args=[draft.pk])
        self.client.force_login(self.student2)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.student)
        response = self.client.get(url)
        self.assertContains(response, "学习笔记")
        self.assertContains(response, "配置路由")
        self.assertEqual(response.headers["X-Frame-Options"], "SAMEORIGIN")
        self.assertIn("img-src data:", response.headers["Content-Security-Policy"])
        with self.assertRaisesMessage(ValidationError, "部分插图已失效"):
            self.prepare(draft, image_ids={999})
        self.task_obj.__class__.objects.filter(pk=self.task_obj.pk).update(status="cancelled")
        response = self.client.get(reverse("training:log_ai_draft", args=[draft.pk]))
        self.assertNotContains(response, "实际记录及后续计划")
        self.assertEqual(self.client.get(url).status_code, 400)

    def test_submission_requires_fresh_review_and_retains_draft_on_pdf_failure(self):
        draft = self.ready_draft()
        source, _, _ = collect_sources(self.student, self.cycle_obj, self.day)
        reviewed = source_digest(source)
        self.fill(completed="新记录")
        with self.assertRaisesMessage(ValidationError, "素材已更新"):
            submit_draft(draft, draft.revision, reviewed, True)
        reviewed = source_digest(collect_sources(self.student, self.cycle_obj, self.day)[0])
        with self.assertRaisesMessage(ValidationError, "请确认使用"):
            submit_draft(draft, draft.revision, reviewed, False)
        with patch("training.log_documents.generate_document_pdf", side_effect=DocumentRenderError("测试失败")):
            with self.assertRaises(DocumentRenderError):
                submit_draft(draft, draft.revision, reviewed, True)
        self.assertFalse(TrainingLog.objects.exists())
        with patch("training.log_documents.generate_document_pdf", return_value=b"%PDF-1.4\n%%EOF"):
            log = submit_draft(draft, draft.revision, reviewed, True)
            with self.assertRaisesMessage(ValidationError, "已有正式日志"):
                submit_draft(draft, draft.revision, reviewed, True)
        self.assertTrue(log.document.name.startswith("logs/"))
        self.assertTrue(log.document.storage.exists(log.document.name))
        self.assertEqual(list(log.executions.values_list("pk", flat=True)), [self.execution.pk])
        self.assertEqual(log.online_document["body"], draft.body)
        self.client.force_login(self.student)
        self.assertContains(self.client.get(reverse("training:log_online", args=[log.pk])), "学习笔记")

    def test_source_change_during_pdf_conversion_cleans_archive_file(self):
        draft = self.ready_draft()
        reviewed = source_digest(collect_sources(self.student, self.cycle_obj, self.day)[0])

        def render(_document):
            self.fill(completed="渲染时更新进度")
            return b"%PDF-1.4\n%%EOF"

        with patch("training.log_documents.generate_document_pdf", side_effect=render):
            with self.assertRaisesMessage(ValidationError, "素材已变化"):
                submit_draft(draft, draft.revision, reviewed, False)
        self.assertFalse(TrainingLog.objects.exists())
        self.assertFalse(list(Path(self.media.name).rglob("*.pdf")))
        draft.refresh_from_db()
        self.assertIsNone(draft.submitted_log_id)
        self.assertTrue(draft.body)

    def test_upload_entry_keeps_file_and_removes_metadata_fields(self):
        self.client.force_login(self.student)
        for name in ("log_create", "log_backfill"):
            response = self.client.get(reverse(f"training:{name}"))
            self.assertNotContains(response, ">AI 辅助编写</a>")
            self.assertIn("document", response.context["form"].fields)
            self.assertFalse({"topic", "summary", "executions"} & response.context["form"].fields.keys())

    def test_reference_reader_accepts_code_and_rejects_blank_pdf(self):
        self.assertEqual(read_reference(SimpleUploadedFile("routing.py", b"print(42)")), "print(42)")
        output = BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.write(output)
        with self.assertRaisesMessage(ValidationError, "没有可提取的文字"):
            read_reference(SimpleUploadedFile("empty.pdf", output.getvalue()))


def sample_log(role, *, long=False, new_layout=False):
    data = {
        "source": {
            "header": {
                "role": role,
                "author": "填写人示例",
                "heading": "技能项目集训周期",
                "date": "2026-11-12",
                "teachers": "授课老师示例",
            },
            "tasks": [
                {
                    "title": "路由配置",
                    "plan": "训练计划",
                    "plan_id": 1,
                    "period": "上午",
                    "module": "网络配置",
                    "outline": ["配置路由", "核对路由表"],
                    "goal": "验证端到端连通",
                    "filled": 1,
                    "expected": 2,
                }
            ],
        },
        "body": example_body(role),
    }
    if new_layout:
        data["source"]["format"] = 2
        data["source"]["header"]["heading"] = "第49届世界技能大赛网络系统管理项目精英班"
        data["source"]["tasks"][0]["domains"] = ["Linux"]
    if long:
        primary = "process" if role == COACH else "notes"
        data["body"][primary] += (
            "\n\n"
            + "\n\n".join(f"第 {index} 项。复核网络路由与下一跳配置，验证访问结果。" for index in range(120))
            + "\n\n结束标记"
        )
        image = SimpleNamespace(
            pk=1,
            media_type="image/png",
            content=Path("training/static/training/worldskills-china.png").read_bytes(),
        )
        data["body"][primary] += "\n\n![说明图片](tms-asset:image-1)"
        return document_input(data, [image])
    return document_input(data, [])


@pytest.mark.parametrize("role, expected", [(COACH, "过程记录"), (STUDENT, "学习笔记")])
@pytest.mark.parametrize("new_layout", [False, True])
def test_training_log_html_layout(role, expected, new_layout):
    html = render_document_html(sample_log(role, new_layout=new_layout))
    assert expected in html
    assert "训练目标达成情况" in html
    assert "data:image/png;base64," in html


@pytest.mark.document_pdf_native
@pytest.mark.parametrize("role", [COACH, STUDENT])
def test_training_log_native_pdf_paginates_long_sections(role):
    from sys import platform

    if platform != "linux":
        pytest.skip("需要 Linux 文档渲染环境")
    pdf = PdfReader(BytesIO(generate_document_pdf(sample_log(role, long=True, new_layout=True))))
    assert len(pdf.pages) > 1
    text = "".join(page.extract_text() for page in pdf.pages)
    for expected in ("路由配置", "结束标记", "填写人示例"):
        assert expected in text
