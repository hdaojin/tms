from datetime import date
import re
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from standards.models import SkillProject, SkillTreeVersion

from .forms import TrainingCycleForm, TrainingCycleTreeVersionsForm
from .models import (
    TrainingCycle, TrainingCycleMember, TrainingPlan, TrainingScheduleDay, TrainingScheduleSlot,
    TrainingTask, TrainingTaskDomain,
)
from .tests import TrainingFixtureMixin, User


class TrainingCycleDetailsTests(TrainingFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.manager = User.objects.create_superuser(username="cycle-manager", password="test")
        self.client.force_login(self.manager)

    def cycle_data(self, **overrides):
        data = {
            "skill_project": self.project.pk,
            "parent": "",
            "code": "NEW",
            "name": "新周期",
            "status": TrainingCycle.Status.PLANNING,
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
            "description": "",
        }
        data.update(overrides)
        return data

    def test_create_page_and_successful_creation_leave_snapshot_empty(self):
        response = self.client.get(reverse("training:cycle_create"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertLess(html.index('name="status"'), html.index('name="start_date"'))
        self.assertLess(html.index('name="start_date"'), html.index('name="end_date"'))
        self.assertNotIn("tree_version_", html)
        self.assertContains(response, 'name="parent"')

        response = self.client.post(reverse("training:cycle_create"), self.cycle_data())
        cycle = TrainingCycle.objects.get(code="NEW")
        self.assertRedirects(response, reverse("training:cycle_detail", args=[cycle.pk]))
        self.assertEqual(cycle.status, TrainingCycle.Status.PLANNING)
        self.assertFalse(cycle.skill_tree_version_links.exists())
        self.assertContains(self.client.get(reverse("training:cycle_list")), reverse("training:cycle_create"))

    def test_configure_clear_and_activate_cycle(self):
        cycle = self.cycle()
        edit_url = reverse("training:cycle_tree_versions", args=[cycle.pk])
        response = self.client.get(edit_url)
        self.assertIsNone(response.context["form"].fields[f"tree_version_{self.linux.pk}"].initial)
        self.assertIsNone(response.context["form"].fields[f"tree_version_{self.windows.pk}"].initial)

        response = self.client.post(edit_url, {f"tree_version_{self.linux.pk}": self.linux_tree.pk})
        self.assertRedirects(response, reverse("training:cycle_detail", args=[cycle.pk]))
        self.assertEqual(list(cycle.skill_tree_versions.all()), [self.linux_tree])
        response = self.client.get(edit_url)
        self.assertEqual(response.context["form"].fields[f"tree_version_{self.linux.pk}"].initial, self.linux_tree)
        self.assertIsNone(response.context["form"].fields[f"tree_version_{self.windows.pk}"].initial)

        self.client.post(edit_url, {})
        self.assertFalse(cycle.skill_tree_version_links.exists())
        basic_url = reverse("training:cycle_edit", args=[cycle.pk])
        data = self.cycle_data(code=cycle.code, name=cycle.name, status=TrainingCycle.Status.ACTIVE)
        response = self.client.post(basic_url, data)
        self.assertContains(response, "进入进行中前必须至少固定一个技术领域")
        cycle.refresh_from_db()
        self.assertEqual(cycle.status, TrainingCycle.Status.PLANNING)

        self.client.post(edit_url, {f"tree_version_{self.linux.pk}": self.linux_tree.pk})
        self.assertRedirects(self.client.post(basic_url, data), reverse("training:cycle_detail", args=[cycle.pk]))
        cycle.refresh_from_db()
        self.assertEqual(cycle.status, TrainingCycle.Status.ACTIVE)
        response = self.client.post(edit_url, {f"tree_version_{self.windows.pk}": self.windows_tree.pk})
        self.assertRedirects(response, reverse("training:cycle_detail", args=[cycle.pk]))
        self.assertEqual(set(cycle.skill_tree_versions.all()), {self.linux_tree, self.windows_tree})

    def test_detail_respects_member_permissions_and_has_three_sections(self):
        cycle = self.cycle()
        member_user = User.objects.create_user(username="private-member", first_name="成员")
        TrainingCycleMember.objects.create(training_cycle=cycle, user=member_user, role="coach")
        viewer = User.objects.create_user(username="cycle-viewer")
        viewer.user_permissions.add(Permission.objects.get(codename="view_trainingcycle", content_type__app_label="training"))
        self.client.force_login(viewer)
        url = reverse("training:cycle_detail", args=[cycle.pk])
        response = self.client.get(url)
        html = response.content.decode()
        self.assertLess(html.index("训练周期信息"), html.index("周期成员列表"))
        self.assertLess(html.index("周期成员列表"), html.index("领域技能树版本快照"))
        self.assertNotContains(response, "private-member")
        self.assertNotContains(response, reverse("training:cycle_members", args=[cycle.pk]))
        self.assertEqual(self.client.get(reverse("training:cycle_tree_versions", args=[cycle.pk])).status_code, 403)

        viewer.user_permissions.add(Permission.objects.get(codename="view_trainingcyclemember", content_type__app_label="training"))
        self.client.force_login(User.objects.get(pk=viewer.pk))
        response = self.client.get(url)
        self.assertContains(response, "private-member")
        self.assertContains(response, "教练")
        self.assertContains(response, reverse("training:cycle_members", args=[cycle.pk]))
        self.assertNotContains(response, "编辑成员")

    def test_detail_fields_follow_editor_order_and_remain_read_only(self):
        cycle = self.cycle(description="第一行\n第二行")
        edit = self.client.get(reverse("training:cycle_edit", args=[cycle.pk]))
        expected = [str(field.label) for field in edit.context["base_fields"]]
        expected.extend([str(edit.context["parent_field"].label), "创建时间", "修改时间"])

        viewer = User.objects.create_user(username="read-only-cycle-viewer")
        viewer.user_permissions.add(Permission.objects.get(codename="view_trainingcycle", content_type__app_label="training"))
        self.client.force_login(viewer)
        detail = self.client.get(reverse("training:cycle_detail", args=[cycle.pk]))
        html = detail.content.decode()
        fields = re.search(r"<dl\b[^>]*>(.*?)</dl>", html, re.DOTALL).group(1)
        labels = re.findall(r"<dt\b[^>]*>\s*([^<]+?)\s*</dt>", fields)
        self.assertEqual(labels, expected)
        self.assertIn("第一行\n第二行", fields)
        self.assertNotIn("<input", fields)
        self.assertNotIn("<textarea", fields)

    def test_cycle_detail_allows_inline_edit_and_saves_on_same_page(self):
        cycle = self.cycle()
        self.bind(cycle)
        member = User.objects.create_user(username="existing-cycle-member")
        TrainingCycleMember.objects.create(training_cycle=cycle, user=member, role="coach")
        url = reverse("training:cycle_detail", args=[cycle.pk])
        response = self.client.get(url)
        self.assertContains(response, '<details class="group peer" data-cycle-editor>')
        self.assertContains(response, 'class="group-open:hidden">编辑</span>')
        self.assertContains(response, "peer-open:hidden")
        self.assertContains(response, 'name="name"')
        self.assertContains(response, 'name="status"')
        self.assertContains(response, 'id="cycle-parent-context"')
        self.assertNotContains(response, reverse("training:cycle_edit", args=[cycle.pk]))

        data = self.cycle_data(code=cycle.code, name="更新后的周期", description="更新后的描述")
        response = self.client.post(f"{url}?members_page=2", data)
        self.assertRedirects(response, f"{url}?members_page=2")
        cycle.refresh_from_db()
        self.assertEqual(cycle.name, "更新后的周期")
        self.assertEqual(cycle.description, "更新后的描述")
        self.assertEqual(cycle.members.count(), 1)
        self.assertEqual(list(cycle.skill_tree_versions.all()), [self.linux_tree])
        self.assertContains(self.client.get(url), '<details class="group peer" data-cycle-editor>')

    def test_inline_edit_rejects_invalid_data_without_changing_other_sections(self):
        cycle = self.cycle()
        url = reverse("training:cycle_detail", args=[cycle.pk])
        data = self.cycle_data(code=cycle.code, name="尚未保存的名称", status=TrainingCycle.Status.ACTIVE)
        response = self.client.post(url, data)
        self.assertContains(response, "进入进行中前必须至少固定一个技术领域")
        self.assertContains(response, '<details class="group peer" data-cycle-editor open>')
        self.assertContains(response, 'value="尚未保存的名称"')
        self.assertContains(response, reverse("training:cycle_tree_versions", args=[cycle.pk]))
        self.assertContains(response, "周期成员列表")
        cycle.refresh_from_db()
        self.assertEqual(cycle.name, "C1")
        self.assertEqual(cycle.status, TrainingCycle.Status.PLANNING)

    def test_inline_status_change_updates_snapshot_edit_availability(self):
        cycle = self.cycle()
        self.bind(cycle)
        url = reverse("training:cycle_detail", args=[cycle.pk])
        data = self.cycle_data(code=cycle.code, name=cycle.name, status=TrainingCycle.Status.ACTIVE)
        self.assertRedirects(self.client.post(url, data), url)
        cycle.refresh_from_db()
        self.assertEqual(cycle.status, TrainingCycle.Status.ACTIVE)
        response = self.client.get(url)
        self.assertContains(response, reverse("training:cycle_tree_versions", args=[cycle.pk]))
        self.assertContains(response, "追加领域")

    def test_inline_status_change_rechecks_snapshot_after_validation(self):
        cycle = self.cycle()
        link = self.bind(cycle)
        url = reverse("training:cycle_detail", args=[cycle.pk])
        data = self.cycle_data(code=cycle.code, name=cycle.name, status=TrainingCycle.Status.ACTIVE)
        original_is_valid = TrainingCycleForm.is_valid

        def remove_snapshot_after_validation(form):
            valid = original_is_valid(form)
            if valid:
                link.delete()
            return valid

        with patch.object(TrainingCycleForm, "is_valid", autospec=True, side_effect=remove_snapshot_after_validation):
            response = self.client.post(url, data)
        self.assertContains(response, "进入进行中前必须至少固定一个技术领域")
        cycle.refresh_from_db()
        self.assertEqual(cycle.status, TrainingCycle.Status.PLANNING)
        self.assertFalse(cycle.skill_tree_version_links.exists())

    def test_inline_edit_requires_change_permission(self):
        cycle = self.cycle()
        viewer = User.objects.create_user(username="cycle-view-without-edit")
        viewer.user_permissions.add(Permission.objects.get(codename="view_trainingcycle", content_type__app_label="training"))
        self.client.force_login(viewer)
        url = reverse("training:cycle_detail", args=[cycle.pk])
        response = self.client.get(url)
        self.assertNotIn("cycle_form", response.context)
        self.assertNotContains(response, "data-cycle-editor")
        response = self.client.post(url, self.cycle_data(code=cycle.code, name="不应保存"))
        self.assertEqual(response.status_code, 403)
        cycle.refresh_from_db()
        self.assertEqual(cycle.name, "C1")

    def test_member_list_paginates_and_parent_choices_exclude_current_cycle(self):
        cycle = self.cycle()
        parent = self.cycle("PARENT")
        people = [User(username=f"cycle-person-{number:02}") for number in range(26)]
        User.objects.bulk_create(people)
        TrainingCycleMember.objects.bulk_create([
            TrainingCycleMember(training_cycle=cycle, user=person, role="coach") for person in people
        ])
        detail_url = reverse("training:cycle_detail", args=[cycle.pk])
        response = self.client.get(detail_url)
        self.assertContains(response, "共 26 位成员")
        self.assertContains(response, "下一页")
        self.assertEqual(len(response.context["members_page"]), 25)
        self.assertEqual(len(self.client.get(detail_url, {"members_page": 2}).context["members_page"]), 1)

        response = self.client.get(reverse("training:cycle_parent_field"), {
            "skill_project": self.project.pk, "cycle_id": cycle.pk,
        })
        self.assertContains(response, parent.name)
        self.assertNotContains(response, f'<option value="{cycle.pk}"')

    def test_basic_info_changes_cannot_orphan_existing_snapshots(self):
        cycle = self.cycle()
        self.bind(cycle)
        other_project = SkillProject.objects.create(code="OTHER", name="其他项目")
        form = TrainingCycleForm(self.cycle_data(code=cycle.code, name=cycle.name, skill_project=other_project.pk), instance=cycle)
        self.assertFalse(form.is_valid())
        self.assertIn("已有领域快照不属于所选技能项目", str(form.errors))

        parent = self.cycle("PARENT")
        self.bind(parent, self.windows, self.windows_tree)
        form = TrainingCycleForm(self.cycle_data(code=cycle.code, name=cycle.name, parent=parent.pk), instance=cycle)
        self.assertFalse(form.is_valid())
        self.assertIn("已有领域快照不属于所选父周期", str(form.errors))
        self.assertEqual(cycle.skill_tree_version_links.count(), 1)

    def test_stale_snapshot_form_cannot_change_locked_cycle(self):
        cycle = self.cycle()
        self.bind(cycle)
        form = TrainingCycleTreeVersionsForm(cycle=cycle, data={})
        self.assertTrue(form.is_valid(), form.errors)
        cycle.status = TrainingCycle.Status.ACTIVE
        cycle.save()
        with self.assertRaisesMessage(ValidationError, "不能替换或删除"):
            form.save()
        self.assertTrue(cycle.skill_tree_version_links.exists())

    def test_admin_snapshot_deletion_respects_lock_and_disables_bulk_delete(self):
        cycle = self.cycle()
        link = self.bind(cycle)
        changelist = reverse("admin:training_trainingcycleskilltreeversion_changelist")
        self.assertNotContains(self.client.get(changelist), 'value="delete_selected"')
        cycle.status = TrainingCycle.Status.ACTIVE
        cycle.save()
        delete_url = reverse("admin:training_trainingcycleskilltreeversion_delete", args=[link.pk])
        self.assertEqual(self.client.post(delete_url, {"post": "yes"}).status_code, 403)
        self.assertTrue(cycle.skill_tree_version_links.exists())

    def test_admin_can_remove_last_unused_snapshot_in_planning(self):
        cycle = self.cycle()
        link = self.bind(cycle)
        delete_url = reverse("admin:training_trainingcycleskilltreeversion_delete", args=[link.pk])
        self.assertEqual(self.client.post(delete_url, {"post": "yes"}).status_code, 302)
        self.assertFalse(cycle.skill_tree_version_links.exists())

    def test_admin_can_change_snapshot_version_without_reassigning_domain(self):
        cycle = self.cycle()
        link = self.bind(cycle)
        history = SkillTreeVersion.objects.create(technical_domain=self.linux, version="V0", name="历史版本")
        url = reverse("admin:training_trainingcycleskilltreeversion_change", args=[link.pk])
        response = self.client.get(url)
        self.assertNotContains(response, 'name="training_cycle"')
        self.assertNotContains(response, 'name="technical_domain"')
        self.assertContains(response, 'name="skill_tree_version"')
        response = self.client.post(url, {"skill_tree_version": history.pk, "_save": "保存"})
        self.assertEqual(response.status_code, 302)
        link.refresh_from_db()
        self.assertEqual(link.skill_tree_version_id, history.pk)

    def test_task_and_schedule_dependencies_prevent_clearing_snapshot(self):
        cycle = self.cycle()
        self.bind(cycle)
        plan = TrainingPlan.objects.create(
            training_cycle=cycle, title="计划", start_date=date(2026, 1, 1), end_date=date(2026, 1, 31),
            objective="训练", created_by=self.manager,
        )
        task = TrainingTask.objects.create(
            training_plan=plan, planned_date=date(2026, 1, 10), title="任务", created_by=self.manager,
        )
        link = TrainingTaskDomain.objects.create(training_task=task, technical_domain=self.linux)
        form = TrainingCycleTreeVersionsForm(cycle=cycle, data={})
        self.assertFalse(form.is_valid())
        self.assertIn("已被训练任务使用", str(form.errors))
        link.delete()

        day = TrainingScheduleDay.objects.create(training_plan=plan, date=date(2026, 1, 10))
        slot = TrainingScheduleSlot.objects.create(day=day, period="morning")
        slot.domains.add(self.linux)
        form = TrainingCycleTreeVersionsForm(cycle=cycle, data={})
        self.assertFalse(form.is_valid())
        self.assertIn("已被排班使用", str(form.errors))
        self.assertTrue(cycle.skill_tree_version_links.exists())
        slot.domains.clear()
        slot.primary_domain = self.linux
        slot.save(update_fields=["primary_domain", "updated_at"])
        form = TrainingCycleTreeVersionsForm(cycle=cycle, data={})
        self.assertFalse(form.is_valid())
        self.assertIn("已被排班使用", str(form.errors))

    def test_active_snapshot_append_after_execution_preserves_bindings(self):
        from django.utils import timezone
        from .models import TaskExecution, TrainingCycleSkillTreeVersion
        from .services import save_cycle_tree_versions
        cycle = self.cycle()
        link = self.bind(cycle)
        cycle.status = TrainingCycle.Status.ACTIVE
        cycle.save()
        plan = TrainingPlan.objects.create(training_cycle=cycle, title="原计划", objective="验证", start_date=date(2026, 1, 1), end_date=date(2026, 1, 31), created_by=self.manager)
        task = TrainingTask.objects.create(training_plan=plan, title="原任务", planned_date=date(2026, 1, 1), created_by=self.manager)
        user = User.objects.create_user(username="snapshot-executor")
        TrainingCycleMember.objects.create(training_cycle=cycle, user=user, role="competitor")
        execution = TaskExecution.objects.create(training_task=task, user=user, started_at=timezone.now())
        url = reverse("training:cycle_tree_versions", args=[cycle.pk])
        form = self.client.get(url).context["form"]
        self.assertTrue(form.fields[f"tree_version_{self.linux.pk}"].disabled)
        self.assertFalse(form.fields[f"tree_version_{self.windows.pk}"].disabled)
        response = self.client.post(url, {f"tree_version_{self.windows.pk}": self.windows_tree.pk})
        self.assertRedirects(response, reverse("training:cycle_detail", args=[cycle.pk]))
        link.refresh_from_db()
        self.assertEqual(link.skill_tree_version_id, self.linux_tree.pk)
        self.assertTrue(TrainingCycleSkillTreeVersion.objects.filter(training_cycle=cycle, technical_domain=self.windows).exists())
        self.assertTrue(TaskExecution.objects.filter(pk=execution.pk, training_task=task, started_at=execution.started_at).exists())
        with self.assertRaisesMessage(ValidationError, "不能替换或删除"):
            save_cycle_tree_versions(cycle, {self.linux.pk: self.linux_tree})
        history = SkillTreeVersion.objects.create(technical_domain=self.linux, version="append-old", name="历史")
        with self.assertRaisesMessage(ValidationError, "不能替换或删除"):
            save_cycle_tree_versions(cycle, {self.linux.pk: history, self.windows.pk: self.windows_tree})

    def test_completed_and_archived_snapshots_remain_read_only(self):
        from .models import TrainingCycleSkillTreeVersion
        from .services import save_cycle_tree_versions
        cycle = self.cycle()
        self.bind(cycle)
        for status in (TrainingCycle.Status.ACTIVE, TrainingCycle.Status.COMPLETED, TrainingCycle.Status.ARCHIVED):
            cycle.status = status
            cycle.save()
            if status == TrainingCycle.Status.ACTIVE:
                continue
            with self.assertRaisesMessage(ValidationError, "快照已经锁定"):
                save_cycle_tree_versions(cycle, {self.linux.pk: self.linux_tree, self.windows.pk: self.windows_tree})
            with self.assertRaisesMessage(ValidationError, "不能再新增"):
                TrainingCycleSkillTreeVersion.objects.create(training_cycle=cycle, technical_domain=self.windows, skill_tree_version=self.windows_tree)
            form = self.client.get(reverse("training:cycle_tree_versions", args=[cycle.pk])).context["form"]
            self.assertTrue(all(field.disabled for field in form.fields.values()))

    def test_active_child_append_still_requires_parent_domain(self):
        from .models import TrainingCycleSkillTreeVersion
        from .services import save_cycle_tree_versions
        parent = self.cycle("APPEND-PARENT")
        self.bind(parent)
        child = self.cycle("APPEND-CHILD", parent=parent)
        self.bind(child)
        child.status = TrainingCycle.Status.ACTIVE
        child.save()
        with self.assertRaisesMessage(ValidationError, "父周期"):
            save_cycle_tree_versions(child, {self.linux.pk: self.linux_tree, self.windows.pk: self.windows_tree})
        with self.assertRaisesMessage(ValidationError, "父周期"):
            TrainingCycleSkillTreeVersion.objects.create(training_cycle=child, technical_domain=self.windows, skill_tree_version=self.windows_tree)
        self.bind(parent, self.windows, self.windows_tree)
        self.assertEqual(child.skill_tree_version_links.count(), 1)
        save_cycle_tree_versions(child, {self.linux.pk: self.linux_tree, self.windows.pk: self.windows_tree})
        self.assertEqual(child.skill_tree_version_links.count(), 2)

    def test_snapshot_save_rechecks_completion_and_concurrent_append(self):
        from .services import save_cycle_tree_versions
        cycle = self.cycle()
        self.bind(cycle)
        cycle.status = TrainingCycle.Status.ACTIVE
        cycle.save()
        stale = TrainingCycleTreeVersionsForm(cycle=cycle, data={})
        self.assertTrue(stale.is_valid(), stale.errors)
        save_cycle_tree_versions(cycle, {self.linux.pk: self.linux_tree, self.windows.pk: self.windows_tree})
        with self.assertRaisesMessage(ValidationError, "不能替换或删除"):
            stale.save()
        pending = TrainingCycleTreeVersionsForm(cycle=cycle, data={})
        self.assertTrue(pending.is_valid(), pending.errors)
        cycle.status = TrainingCycle.Status.COMPLETED
        cycle.save()
        with self.assertRaisesMessage(ValidationError, "快照已经锁定"):
            pending.save()
        self.assertEqual(cycle.skill_tree_version_links.count(), 2)
