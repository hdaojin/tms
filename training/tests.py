from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase

from standards.models import Skill, SkillProject, SkillTreeVersion, TechnicalDomain, TechnicalDomainMembership
from .models import (
    TaskExecution,
    TrainingCycle,
    TrainingCycleMember,
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


class TrainingWorkflowTests(TestCase):
    def setUp(self):
        self.project = SkillProject.objects.create(code="NS", name="网络系统管理")
        self.linux = TechnicalDomain.objects.create(skill_project=self.project, code="LINUX", name="Linux")
        self.windows = TechnicalDomain.objects.create(skill_project=self.project, code="WIN", name="Windows")
        self.skill = Skill.objects.create(
            skill_project=self.project, primary_domain=self.linux, name="Linux"
        )
        tree = SkillTreeVersion.objects.create(skill_project=self.project, version="V1", name="V1")
        self.cycle = TrainingCycle.objects.create(
            skill_project=self.project,
            skill_tree_version=tree,
            code="C1",
            name="周期",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )
        self.creator = User.objects.create_user(username="creator")
        self.coach = User.objects.create_user(username="coach")
        self.competitor = User.objects.create_user(username="student")
        self.other_competitor = User.objects.create_user(username="other")
        TrainingCycleMember.objects.create(
            training_cycle=self.cycle, user=self.coach, role=TrainingCycleMember.Role.COACH
        )
        TrainingCycleMember.objects.create(
            training_cycle=self.cycle, user=self.competitor, role=TrainingCycleMember.Role.COMPETITOR
        )
        TrainingCycleMember.objects.create(
            training_cycle=self.cycle, user=self.other_competitor, role=TrainingCycleMember.Role.COMPETITOR
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
            training_task=self.task, technical_domain=self.linux, role=TrainingTaskDomain.Role.PRIMARY
        )
        TrainingTaskSkill.objects.create(training_task=self.task, skill=self.skill, role=TrainingTaskSkill.Role.PRIMARY)
        TrainingTaskCoach.objects.create(training_task=self.task, user=self.coach, role=TrainingTaskCoach.Role.PRIMARY)

    def test_publish_assigns_only_explicit_competitors(self):
        publish_training_task(self.task, [self.competitor.pk], user=self.creator)
        self.assertTrue(TaskExecution.objects.filter(training_task=self.task, user=self.competitor).exists())
        self.assertFalse(TaskExecution.objects.filter(training_task=self.task, user=self.other_competitor).exists())

    def test_started_execution_locks_task_core_fields(self):
        execution = TaskExecution.objects.create(
            training_task=self.task, user=self.competitor, status=TaskExecution.Status.IN_PROGRESS
        )
        self.task.title = "改写核心内容"
        with self.assertRaises(ValidationError):
            self.task.save()
        self.assertIsNotNone(execution.started_at)

    def test_training_log_execution_accepts_planned_date_and_rejects_unrelated_date(self):
        execution = TaskExecution.objects.create(training_task=self.task, user=self.competitor)
        valid = TrainingLog.objects.create(
            training_cycle=self.cycle, author=self.competitor, training_date=date(2026, 1, 10), topic="日志"
        )
        TrainingLogExecution.objects.create(training_log=valid, task_execution=execution)
        invalid = TrainingLog.objects.create(
            training_cycle=self.cycle, author=self.competitor, training_date=date(2026, 1, 11), topic="次日日志"
        )
        with self.assertRaises(ValidationError):
            TrainingLogExecution.objects.create(training_log=invalid, task_execution=execution)

    def test_cross_domain_task_requires_explicit_coach_for_management(self):
        change = Permission.objects.get(content_type__app_label="training", codename="change_trainingtask")
        self.coach.user_permissions.add(change)
        TechnicalDomainMembership.objects.create(
            technical_domain=self.linux, user=self.coach, role=TechnicalDomainMembership.Role.COACH
        )
        TrainingTaskDomain.objects.create(training_task=self.task, technical_domain=self.windows)
        self.task.coach_links.all().delete()
        self.assertFalse(manageable_training_tasks_for(self.coach).filter(pk=self.task.pk).exists())
        TrainingTaskCoach.objects.create(training_task=self.task, user=self.coach)
        self.assertTrue(manageable_training_tasks_for(self.coach).filter(pk=self.task.pk).exists())
