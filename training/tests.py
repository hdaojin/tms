from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from standards.models import Skill, SkillProject, SkillTreeVersion, TechnicalDomain, TechnicalDomainMembership

from .forms import TrainingCycleForm, TrainingTaskForm
from .models import (
    TaskExecution,
    TrainingCycle,
    TrainingCycleMember,
    TrainingCycleSkillTreeVersion,
    TrainingLog,
    TrainingLogExecution,
    TrainingPlan,
    TrainingTask,
    TrainingTaskCoach,
    TrainingTaskDomain,
    TrainingTaskSkill,
)
from .selectors import manageable_training_tasks_for
from .services import publish_training_task


User = get_user_model()


class TrainingFixtureMixin:
    def setUp(self):
        super().setUp()
        self.project = SkillProject.objects.create(code="NS", name="网络系统管理", is_default=True)
        self.linux = TechnicalDomain.objects.create(skill_project=self.project, code="LINUX", name="Linux")
        self.windows = TechnicalDomain.objects.create(skill_project=self.project, code="WIN", name="Windows")
        self.linux_tree = SkillTreeVersion.objects.create(
            technical_domain=self.linux,
            version="V1",
            name="Linux V1",
            is_current=True,
        )
        self.windows_tree = SkillTreeVersion.objects.create(
            technical_domain=self.windows,
            version="V1",
            name="Windows V1",
            is_current=True,
        )

    def cycle(self, code="C1", **kwargs):
        values = {
            "skill_project": self.project,
            "code": code,
            "name": code,
            "start_date": date(2026, 1, 1),
            "end_date": date(2026, 1, 31),
        }
        values.update(kwargs)
        return TrainingCycle.objects.create(**values)

    def bind(self, cycle, domain=None, tree=None):
        return TrainingCycleSkillTreeVersion.objects.create(
            training_cycle=cycle,
            technical_domain=domain or self.linux,
            skill_tree_version=tree or self.linux_tree,
        )


class TrainingCycleVersionBindingTests(TrainingFixtureMixin, TestCase):
    def test_cycle_can_bind_one_version_per_domain(self):
        cycle = self.cycle()
        self.bind(cycle)
        self.bind(cycle, self.windows, self.windows_tree)
        self.assertEqual(cycle.skill_tree_versions.count(), 2)
        with self.assertRaises(IntegrityError), transaction.atomic():
            TrainingCycleSkillTreeVersion.objects.create(
                training_cycle=cycle,
                technical_domain=self.linux,
                skill_tree_version=self.linux_tree,
            )

    def test_binding_requires_matching_project_domain_and_version(self):
        cycle = self.cycle()
        with self.assertRaisesMessage(ValidationError, "必须属于所选技术领域"):
            self.bind(cycle, self.linux, self.windows_tree)

        other_project = SkillProject.objects.create(code="OTHER", name="其他项目")
        other_domain = TechnicalDomain.objects.create(
            skill_project=other_project,
            code="OTHER",
            name="其他领域",
        )
        other_tree = SkillTreeVersion.objects.create(
            technical_domain=other_domain,
            version="V1",
            name="其他 V1",
        )
        with self.assertRaisesMessage(ValidationError, "训练周期对应的技能项目"):
            self.bind(cycle, other_domain, other_tree)

    def test_child_domains_are_parent_subset_but_versions_may_differ(self):
        parent = self.cycle("PARENT")
        self.bind(parent)
        history = SkillTreeVersion.objects.create(
            technical_domain=self.linux,
            version="V0",
            name="Linux V0",
        )
        child = self.cycle(
            "CHILD",
            parent=parent,
            start_date=date(2026, 1, 5),
            end_date=date(2026, 1, 20),
        )
        self.bind(child, self.linux, history)
        self.assertEqual(child.skill_tree_version_links.get().skill_tree_version, history)
        with self.assertRaisesMessage(ValidationError, "父周期已经包含"):
            self.bind(child, self.windows, self.windows_tree)

    def test_status_must_advance_sequentially(self):
        cycle = self.cycle()
        self.bind(cycle)
        cycle.status = TrainingCycle.Status.COMPLETED
        with self.assertRaisesMessage(ValidationError, "依次推进"):
            cycle.save()
        cycle.status = TrainingCycle.Status.ACTIVE
        cycle.save()
        cycle.status = TrainingCycle.Status.PLANNING
        with self.assertRaisesMessage(ValidationError, "依次推进"):
            cycle.save()

    def test_cycle_cannot_start_without_a_domain_version_snapshot(self):
        cycle = self.cycle()
        cycle.status = TrainingCycle.Status.ACTIVE
        with self.assertRaisesMessage(ValidationError, "至少固定一个技术领域"):
            cycle.save()

    def test_form_defaults_currents_and_requires_at_least_one(self):
        form = TrainingCycleForm(
            data={
                "skill_project": self.project.pk,
                "parent": "",
                "code": "FORM",
                "name": "表单周期",
                "start_date": "2026-02-01",
                "end_date": "2026-02-28",
                "status": TrainingCycle.Status.PLANNING,
                "description": "",
                f"tree_version_{self.linux.pk}": self.linux_tree.pk,
                f"tree_version_{self.windows.pk}": self.windows_tree.pk,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        cycle = form.save()
        self.assertEqual(cycle.skill_tree_version_links.count(), 2)

        empty = TrainingCycleForm(
            data={
                "skill_project": self.project.pk,
                "parent": "",
                "code": "EMPTY",
                "name": "空周期",
                "start_date": "2026-03-01",
                "end_date": "2026-03-31",
                "status": TrainingCycle.Status.PLANNING,
                "description": "",
                f"tree_version_{self.linux.pk}": "",
                f"tree_version_{self.windows.pk}": "",
            }
        )
        self.assertFalse(empty.is_valid())
        self.assertIn("至少固定一个技术领域", str(empty.non_field_errors()))

    def test_form_requires_new_cycle_to_start_in_planning(self):
        form = TrainingCycleForm(
            data={
                "skill_project": self.project.pk,
                "parent": "",
                "code": "ACTIVE",
                "name": "进行中周期",
                "start_date": "2026-04-01",
                "end_date": "2026-04-30",
                "status": TrainingCycle.Status.ACTIVE,
                "description": "",
                f"tree_version_{self.linux.pk}": self.linux_tree.pk,
                f"tree_version_{self.windows.pk}": "",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("必须先保存为筹备中", str(form.errors["status"]))

    def test_form_parent_choices_prefill_but_saved_child_is_independent(self):
        parent = self.cycle("PARENT")
        self.bind(parent)
        form = TrainingCycleForm(
            initial={"skill_project": self.project.pk, "parent": parent.pk}
        )
        field_name = f"tree_version_{self.linux.pk}"
        self.assertIn(field_name, form.fields)
        self.assertEqual(form.fields[field_name].initial, self.linux_tree)
        self.assertNotIn(f"tree_version_{self.windows.pk}", form.fields)

    def test_started_execution_locks_cycle_bindings(self):
        cycle = self.cycle()
        self.bind(cycle)
        plan = TrainingPlan.objects.create(
            training_cycle=cycle,
            title="计划",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            objective="训练",
            created_by=User.objects.create_user(username="creator-lock"),
        )
        task = TrainingTask.objects.create(
            training_plan=plan,
            planned_date=date(2026, 1, 10),
            title="任务",
            requirements="验证",
            created_by=plan.created_by,
        )
        started_user = User.objects.create_user(username="started-user")
        TrainingCycleMember.objects.create(
            training_cycle=cycle,
            user=started_user,
            role=TrainingCycleMember.Role.COMPETITOR,
        )
        TaskExecution.objects.create(
            training_task=task,
            user=started_user,
            status=TaskExecution.Status.IN_PROGRESS,
        )
        self.assertTrue(cycle.skill_tree_bindings_locked)
        form = TrainingCycleForm(instance=cycle)
        self.assertTrue(form.fields[f"tree_version_{self.linux.pk}"].disabled)

    def test_locked_binding_cannot_be_changed_or_deleted_outside_form(self):
        cycle = self.cycle()
        link = self.bind(cycle)
        history = SkillTreeVersion.objects.create(
            technical_domain=self.linux,
            version="V0",
            name="Linux V0",
        )
        cycle.status = TrainingCycle.Status.ACTIVE
        cycle.save()

        link.skill_tree_version = history
        with self.assertRaisesMessage(ValidationError, "快照已经锁定"):
            link.save()
        with self.assertRaisesMessage(ValidationError, "快照已经锁定"):
            TrainingCycleSkillTreeVersion.objects.create(
                training_cycle=cycle,
                technical_domain=self.windows,
                skill_tree_version=self.windows_tree,
            )
        with self.assertRaisesMessage(ValidationError, "快照已经锁定"):
            TrainingCycleSkillTreeVersion.objects.get(pk=link.pk).delete()

    def test_parent_cannot_remove_domain_used_by_child_cycle(self):
        parent = self.cycle("PARENT")
        self.bind(parent)
        self.bind(parent, self.windows, self.windows_tree)
        child = self.cycle(
            "CHILD",
            parent=parent,
            start_date=date(2026, 1, 5),
            end_date=date(2026, 1, 20),
        )
        self.bind(child)

        form = TrainingCycleForm(
            data={
                "skill_project": self.project.pk,
                "parent": "",
                "code": parent.code,
                "name": parent.name,
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
                "status": TrainingCycle.Status.PLANNING,
                "description": "",
                f"tree_version_{self.linux.pk}": "",
                f"tree_version_{self.windows.pk}": self.windows_tree.pk,
            },
            instance=parent,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("已被阶段周期使用", str(form.non_field_errors()))

    def test_cycle_form_fragment_requires_permission(self):
        user = User.objects.create_user(username="cycle-form-user")
        user.user_permissions.add(
            Permission.objects.get(content_type__app_label="training", codename="add_trainingcycle")
        )
        self.client.force_login(user)
        response = self.client.get(
            reverse("training:cycle_version_fields"),
            {"skill_project": self.project.pk},
            HTTP_HX_REQUEST="true",
        )
        self.assertContains(response, f"tree_version_{self.linux.pk}")
        self.assertContains(response, "Linux V1")


class TrainingWorkflowTests(TrainingFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.skill = Skill.objects.create(
            skill_project=self.project,
            primary_domain=self.linux,
            name="Linux",
        )
        self.cycle = self.cycle()
        self.bind(self.cycle)
        self.creator = User.objects.create_user(username="creator")
        self.coach = User.objects.create_user(username="coach")
        self.competitor = User.objects.create_user(username="student")
        self.other_competitor = User.objects.create_user(username="other")
        TrainingCycleMember.objects.create(
            training_cycle=self.cycle,
            user=self.coach,
            role=TrainingCycleMember.Role.COACH,
        )
        TrainingCycleMember.objects.create(
            training_cycle=self.cycle,
            user=self.competitor,
            role=TrainingCycleMember.Role.COMPETITOR,
        )
        TrainingCycleMember.objects.create(
            training_cycle=self.cycle,
            user=self.other_competitor,
            role=TrainingCycleMember.Role.COMPETITOR,
        )
        self.plan = TrainingPlan.objects.create(
            training_cycle=self.cycle,
            title="一月计划",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            objective="训练",
            created_by=self.creator,
        )
        self.task = TrainingTask.objects.create(
            training_plan=self.plan,
            planned_date=date(2026, 1, 10),
            title="部署服务",
            requirements="完成验证",
            created_by=self.creator,
        )
        TrainingTaskDomain.objects.create(
            training_task=self.task,
            technical_domain=self.linux,
            role=TrainingTaskDomain.Role.PRIMARY,
        )
        TrainingTaskSkill.objects.create(
            training_task=self.task,
            skill=self.skill,
            role=TrainingTaskSkill.Role.PRIMARY,
        )
        TrainingTaskCoach.objects.create(
            training_task=self.task,
            user=self.coach,
            role=TrainingTaskCoach.Role.PRIMARY,
        )

    def test_task_domain_must_be_bound_by_cycle(self):
        with self.assertRaisesMessage(ValidationError, "周期已固定"):
            TrainingTaskDomain.objects.create(
                training_task=self.task,
                technical_domain=self.windows,
            )

    def test_task_form_only_offers_cycle_bound_domains(self):
        form = TrainingTaskForm(instance=self.task)
        self.assertEqual(list(form.fields["domains"].queryset), [self.linux])

    def test_publish_assigns_only_explicit_competitors(self):
        publish_training_task(self.task, [self.competitor.pk], user=self.creator)
        self.assertTrue(TaskExecution.objects.filter(training_task=self.task, user=self.competitor).exists())
        self.assertFalse(TaskExecution.objects.filter(training_task=self.task, user=self.other_competitor).exists())

    def test_started_execution_locks_task_core_fields(self):
        execution = TaskExecution.objects.create(
            training_task=self.task,
            user=self.competitor,
            status=TaskExecution.Status.IN_PROGRESS,
        )
        self.task.title = "改写核心内容"
        with self.assertRaises(ValidationError):
            self.task.save()
        self.assertIsNotNone(execution.started_at)

    def test_training_log_execution_accepts_planned_date_and_rejects_unrelated_date(self):
        execution = TaskExecution.objects.create(training_task=self.task, user=self.competitor)
        valid = TrainingLog.objects.create(
            training_cycle=self.cycle,
            author=self.competitor,
            training_date=date(2026, 1, 10),
            topic="日志",
        )
        TrainingLogExecution.objects.create(training_log=valid, task_execution=execution)
        invalid = TrainingLog.objects.create(
            training_cycle=self.cycle,
            author=self.competitor,
            training_date=date(2026, 1, 11),
            topic="次日日志",
        )
        with self.assertRaises(ValidationError):
            TrainingLogExecution.objects.create(training_log=invalid, task_execution=execution)

    def test_cross_domain_task_requires_cycle_binding_and_explicit_coach(self):
        self.bind(self.cycle, self.windows, self.windows_tree)
        change = Permission.objects.get(content_type__app_label="training", codename="change_trainingtask")
        self.coach.user_permissions.add(change)
        TechnicalDomainMembership.objects.create(
            technical_domain=self.linux,
            user=self.coach,
            role=TechnicalDomainMembership.Role.COACH,
        )
        TrainingTaskDomain.objects.create(training_task=self.task, technical_domain=self.windows)
        self.task.coach_links.all().delete()
        self.assertFalse(manageable_training_tasks_for(self.coach).filter(pk=self.task.pk).exists())
        TrainingTaskCoach.objects.create(training_task=self.task, user=self.coach)
        self.assertTrue(manageable_training_tasks_for(self.coach).filter(pk=self.task.pk).exists())
