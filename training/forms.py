from __future__ import annotations

from django import forms
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.urls import reverse

from core.uploads import TRAINING_ATTACHMENT_UPLOAD_SPEC, TRAINING_LOG_UPLOAD_SPEC
from core.utils.forms import StyledFormMixin
from standards.forms import DefaultSkillProjectFormMixin
from standards.models import Skill, SkillProject, SkillTreeVersion, TechnicalDomain

from .models import (
    TaskExecution,
    TrainingCycle,
    TrainingCycleSkillTreeVersion,
    TrainingCycleMember,
    TrainingLog,
    TrainingPlan,
    TrainingTask,
    TrainingTaskCoach,
    TrainingTaskDomain,
    TrainingTaskSkill,
)
from .services import publish_training_task


User = get_user_model()


class TrainingCycleForm(DefaultSkillProjectFormMixin, StyledFormMixin, forms.ModelForm):
    class Meta:
        model = TrainingCycle
        fields = [
            "skill_project",
            "parent",
            "code",
            "name",
            "start_date",
            "end_date",
            "status",
            "description",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        project = None
        if self.is_bound and self.data.get("skill_project"):
            project = SkillProject.objects.filter(pk=self.data.get("skill_project")).first()
        if project is None and self.instance.pk:
            project = self.instance.skill_project
        if project is None:
            project = self.initial.get("skill_project")
            if project and not getattr(project, "pk", None):
                project = SkillProject.objects.filter(pk=project).first()
        if getattr(project, "pk", None):
            self.fields["parent"].queryset = TrainingCycle.objects.filter(skill_project=project).exclude(
                pk=self.instance.pk or None
            )
        else:
            self.fields["parent"].queryset = TrainingCycle.objects.none()
        parent = None
        parent_id = self.data.get("parent") if self.is_bound else self.initial.get("parent")
        if parent_id:
            parent_id = getattr(parent_id, "pk", parent_id)
            parent = TrainingCycle.objects.filter(pk=parent_id, skill_project=project).first()
        elif self.instance.parent_id:
            parent = self.instance.parent

        context_url = reverse("training:cycle_version_fields")
        self.fields["skill_project"].widget.attrs.update(
            {
                "hx-get": context_url,
                "hx-target": "#cycle-version-context",
                "hx-trigger": "change",
                "hx-include": "closest form",
                "data-cycle-version-context-trigger": "true",
            }
        )
        self.fields["parent"].widget.attrs.update(
            {
                "hx-get": context_url,
                "hx-target": "#cycle-version-context",
                "hx-trigger": "change",
                "hx-include": "closest form",
                "data-cycle-version-context-trigger": "true",
            }
        )

        existing_links = {
            link.technical_domain_id: link
            for link in (
                self.instance.skill_tree_version_links.select_related(
                    "technical_domain", "skill_tree_version"
                ).all()
                if self.instance.pk
                else ()
            )
        }
        if parent is not None:
            domains = TechnicalDomain.objects.filter(
                pk__in=parent.skill_tree_version_links.values("technical_domain_id")
            )
        elif project is not None:
            domains = TechnicalDomain.objects.filter(skill_project=project, is_active=True)
            if existing_links:
                domains = TechnicalDomain.objects.filter(
                    models.Q(skill_project=project, is_active=True) | models.Q(pk__in=existing_links)
                )
        else:
            domains = TechnicalDomain.objects.none()
        self.version_fields = []
        for domain in domains.order_by("order", "code", "pk"):
            field_name = f"tree_version_{domain.pk}"
            versions = SkillTreeVersion.objects.filter(technical_domain=domain).order_by(
                "-is_current", "-created_at", "-pk"
            )
            current_version = versions.filter(is_current=True).first()
            if current_version is not None:
                empty_label = "不纳入当前周期"
            elif versions.exists():
                empty_label = "尚无当前技能树（可选择历史版本）"
            else:
                empty_label = "尚无技能树版本"
            field = forms.ModelChoiceField(
                label=f"{domain.name}技能树版本",
                queryset=versions,
                required=False,
                empty_label=empty_label,
            )
            if field_name in self.initial:
                field.initial = self.initial[field_name]
            elif domain.pk in existing_links:
                field.initial = existing_links[domain.pk].skill_tree_version
            elif parent is not None:
                parent_link = parent.skill_tree_version_links.filter(technical_domain=domain).first()
                if parent_link:
                    field.initial = parent_link.skill_tree_version
            else:
                field.initial = current_version
            if self.instance.pk and self.instance.skill_tree_bindings_locked:
                field.disabled = True
            field.widget.attrs["data-cycle-version-field"] = "true"
            self.fields[field_name] = field
            self.version_fields.append((field_name, domain))

    def clean(self):
        cleaned = super().clean()
        if not self.instance.pk and cleaned.get("status") != TrainingCycle.Status.PLANNING:
            self.add_error("status", "新建周期必须先保存为筹备中，再按顺序推进状态。")
        selected = {
            domain.pk: cleaned.get(field_name)
            for field_name, domain in self.version_fields
            if cleaned.get(field_name) is not None
        }
        if not selected:
            raise forms.ValidationError("训练周期必须至少固定一个技术领域的技能树版本。")
        if self.instance.pk:
            existing = dict(
                self.instance.skill_tree_version_links.values_list(
                    "technical_domain_id", "skill_tree_version_id"
                )
            )
            selected_ids = {domain_id: tree.pk for domain_id, tree in selected.items()}
            if self.instance.skill_tree_bindings_locked and selected_ids != existing:
                raise forms.ValidationError("训练周期的技能树版本快照已经锁定，不能再修改。")
            removed_domain_ids = set(existing) - set(selected_ids)
            used_domain = TrainingTaskDomain.objects.filter(
                training_task__training_plan__training_cycle=self.instance,
                technical_domain_id__in=removed_domain_ids,
            ).select_related("technical_domain").first()
            if used_domain:
                raise forms.ValidationError(
                    f"技术领域“{used_domain.technical_domain.name}”已被训练任务使用，不能从周期中移除。"
                )
            child_link = TrainingCycleSkillTreeVersion.objects.filter(
                training_cycle__parent=self.instance,
                technical_domain_id__in=removed_domain_ids,
            ).select_related("technical_domain").first()
            if child_link:
                raise forms.ValidationError(
                    f"技术领域“{child_link.technical_domain.name}”已被阶段周期使用，不能从父周期中移除。"
                )
        cleaned["selected_tree_versions"] = selected
        return cleaned

    @transaction.atomic
    def save(self, commit=True):
        cycle = super().save(commit=False)
        if not commit:
            return cycle
        target_status = cycle.status
        was_planning = not cycle.pk or TrainingCycle.objects.filter(
            pk=cycle.pk, status=TrainingCycle.Status.PLANNING
        ).exists()
        if was_planning and target_status != TrainingCycle.Status.PLANNING:
            cycle.status = TrainingCycle.Status.PLANNING
        cycle.save()
        if not cycle.skill_tree_bindings_locked:
            selected = self.cleaned_data["selected_tree_versions"]
            for domain_id, tree in selected.items():
                TrainingCycleSkillTreeVersion.objects.update_or_create(
                    training_cycle=cycle,
                    technical_domain_id=domain_id,
                    defaults={"skill_tree_version": tree},
                )
            for link in cycle.skill_tree_version_links.exclude(technical_domain_id__in=selected):
                link.delete()
        if cycle.status != target_status:
            cycle.status = target_status
            cycle.save(update_fields=["status", "updated_at"])
        return cycle


class TrainingPlanForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = TrainingPlan
        fields = ["training_cycle", "title", "start_date", "end_date", "objective", "status", "source_file"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "objective": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["source_file"].widget.attrs.update(TRAINING_ATTACHMENT_UPLOAD_SPEC.widget_attrs())


class TrainingTaskForm(StyledFormMixin, forms.ModelForm):
    domains = forms.ModelMultipleChoiceField(
        label="技术领域", queryset=TechnicalDomain.objects.none(), widget=forms.CheckboxSelectMultiple
    )
    primary_domain = forms.ModelChoiceField(
        label="主要技术领域", queryset=TechnicalDomain.objects.none(), required=False
    )
    skills = forms.ModelMultipleChoiceField(
        label="技能", queryset=Skill.objects.none(), widget=forms.CheckboxSelectMultiple
    )
    primary_skill = forms.ModelChoiceField(label="主要技能", queryset=Skill.objects.none())
    coaches = forms.ModelMultipleChoiceField(
        label="负责教练", queryset=User.objects.none(), widget=forms.CheckboxSelectMultiple
    )
    primary_coach = forms.ModelChoiceField(label="主教练", queryset=User.objects.none(), required=False)
    competitors = forms.ModelMultipleChoiceField(
        label="分配选手", queryset=User.objects.none(), widget=forms.CheckboxSelectMultiple, required=False
    )

    class Meta:
        model = TrainingTask
        fields = [
            "training_plan",
            "planned_date",
            "title",
            "description",
            "requirements",
            "estimated_minutes",
            "priority",
            "status",
            "order",
        ]
        widgets = {
            "planned_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 3}),
            "requirements": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        plan = (
            self.instance.training_plan
            if self.instance.pk
            else self.initial.get("training_plan")
        )
        if plan and not getattr(plan, "pk", None):
            plan = (
                TrainingPlan.objects.filter(pk=plan)
                .select_related("training_cycle__skill_project")
                .first()
            )
        if self.is_bound and self.data.get("training_plan"):
            plan = (
                TrainingPlan.objects.filter(pk=self.data.get("training_plan"))
                .select_related("training_cycle__skill_project")
                .first()
            )
        if plan:
            project = plan.training_cycle.skill_project
            bound_domain_ids = plan.training_cycle.skill_tree_version_links.values("technical_domain_id")
            domain_queryset = TechnicalDomain.objects.filter(pk__in=bound_domain_ids, is_active=True)
            if self.instance.pk:
                domain_queryset = TechnicalDomain.objects.filter(
                    models.Q(pk__in=bound_domain_ids, is_active=True)
                    | models.Q(pk__in=self.instance.domain_links.values("technical_domain_id"))
                )
            self.fields["domains"].queryset = domain_queryset.order_by("order", "code", "pk")
            self.fields["primary_domain"].queryset = self.fields["domains"].queryset
            self.fields["skills"].queryset = Skill.objects.filter(skill_project=project, is_active=True)
            self.fields["primary_skill"].queryset = self.fields["skills"].queryset
            coaches = User.objects.filter(
                training_cycle_memberships__training_cycle=plan.training_cycle,
                training_cycle_memberships__role=TrainingCycleMember.Role.COACH,
            ).distinct()
            competitors = User.objects.filter(
                training_cycle_memberships__training_cycle=plan.training_cycle,
                training_cycle_memberships__role=TrainingCycleMember.Role.COMPETITOR,
            ).distinct()
            self.fields["coaches"].queryset = coaches
            self.fields["primary_coach"].queryset = coaches
            self.fields["competitors"].queryset = competitors
        if self.instance.pk:
            self.fields["domains"].initial = self.instance.domain_links.values_list("technical_domain_id", flat=True)
            self.fields["primary_domain"].initial = (
                self.instance.domain_links.filter(role=TrainingTaskDomain.Role.PRIMARY)
                .values_list("technical_domain_id", flat=True)
                .first()
            )
            self.fields["skills"].initial = self.instance.skill_links.values_list("skill_id", flat=True)
            self.fields["primary_skill"].initial = (
                self.instance.skill_links.filter(role=TrainingTaskSkill.Role.PRIMARY)
                .values_list("skill_id", flat=True)
                .first()
            )
            self.fields["coaches"].initial = self.instance.coach_links.values_list("user_id", flat=True)
            self.fields["primary_coach"].initial = (
                self.instance.coach_links.filter(role=TrainingTaskCoach.Role.PRIMARY)
                .values_list("user_id", flat=True)
                .first()
            )
            self.fields["competitors"].initial = self.instance.executions.values_list("user_id", flat=True)

    def clean(self):
        cleaned = super().clean()
        domains = set(cleaned.get("domains") or [])
        skills = set(cleaned.get("skills") or [])
        coaches = set(cleaned.get("coaches") or [])
        if cleaned.get("primary_domain") and cleaned["primary_domain"] not in domains:
            self.add_error("primary_domain", "主要技术领域必须包含在技术领域中。")
        if cleaned.get("primary_skill") and cleaned["primary_skill"] not in skills:
            self.add_error("primary_skill", "主要技能必须包含在技能中。")
        if cleaned.get("primary_coach") and cleaned["primary_coach"] not in coaches:
            self.add_error("primary_coach", "主教练必须包含在负责教练中。")
        if cleaned.get("status") == TrainingTask.Status.PUBLISHED:
            if not domains:
                self.add_error("domains", "发布任务前必须至少选择一个技术领域。")
            if not cleaned.get("primary_skill"):
                self.add_error("primary_skill", "发布任务前必须选择主要技能。")
            if not coaches:
                self.add_error("coaches", "发布任务前必须至少选择一位教练。")
        if self.instance.pk and self.instance.is_locked and self.has_changed():
            protected = {
                "training_plan",
                "planned_date",
                "title",
                "description",
                "requirements",
                "estimated_minutes",
                "domains",
                "primary_domain",
                "skills",
                "primary_skill",
            }
            if protected.intersection(self.changed_data):
                raise forms.ValidationError("已有选手开始执行后，不能修改任务核心内容、领域和技能。")
        return cleaned

    @transaction.atomic
    def save(self, commit=True):
        task = super().save(commit=commit)
        if not commit:
            return task
        domains = list(self.cleaned_data["domains"])
        primary_domain = self.cleaned_data.get("primary_domain")
        skills = list(self.cleaned_data["skills"])
        primary_skill = self.cleaned_data["primary_skill"]
        coaches = list(self.cleaned_data["coaches"])
        primary_coach = self.cleaned_data.get("primary_coach")
        if not task.is_locked:
            task.domain_links.all().delete()
            for domain in domains:
                TrainingTaskDomain.objects.create(
                    training_task=task,
                    technical_domain=domain,
                    role=TrainingTaskDomain.Role.PRIMARY
                    if domain == primary_domain
                    else TrainingTaskDomain.Role.RELATED,
                )
            task.skill_links.all().delete()
            for order, skill in enumerate(skills):
                TrainingTaskSkill.objects.create(
                    training_task=task,
                    skill=skill,
                    role=TrainingTaskSkill.Role.PRIMARY if skill == primary_skill else TrainingTaskSkill.Role.RELATED,
                    order=order,
                )
        task.coach_links.all().delete()
        for coach in coaches:
            TrainingTaskCoach.objects.create(
                training_task=task,
                user=coach,
                role=TrainingTaskCoach.Role.PRIMARY if coach == primary_coach else TrainingTaskCoach.Role.COLLABORATOR,
            )
        if task.status == TrainingTask.Status.PUBLISHED:
            publish_training_task(
                task, self.cleaned_data["competitors"].values_list("pk", flat=True), user=self.request_user
            )
        return task


class TaskExecutionForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = TaskExecution
        fields = [
            "status",
            "actual_minutes",
            "completion_note",
            "problems",
            "problem_resolved",
            "solution",
            "reflection",
        ]
        widgets = {
            name: forms.Textarea(attrs={"rows": 3})
            for name in ["completion_note", "problems", "solution", "reflection"]
        }


class CoachFeedbackForm(StyledFormMixin, forms.Form):
    coach_feedback = forms.CharField(label="教练反馈", widget=forms.Textarea(attrs={"rows": 5}))


class TrainingLogForm(StyledFormMixin, forms.ModelForm):
    executions = forms.ModelMultipleChoiceField(
        label="关联任务执行", queryset=TaskExecution.objects.none(), required=False, widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = TrainingLog
        fields = ["training_cycle", "training_date", "topic", "summary", "document"]
        widgets = {
            "training_date": forms.DateInput(attrs={"type": "date"}),
            "summary": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, **kwargs):
        self.author = kwargs.pop("author", None)
        super().__init__(*args, **kwargs)
        self.fields["document"].widget.attrs.update(TRAINING_LOG_UPLOAD_SPEC.widget_attrs())
        if self.author:
            self.fields["executions"].queryset = TaskExecution.objects.filter(user=self.author).select_related(
                "training_task"
            )
        if self.instance.pk:
            self.fields["executions"].initial = self.instance.executions.all()

    def clean(self):
        cleaned = super().clean()
        cycle = cleaned.get("training_cycle")
        training_date = cleaned.get("training_date")
        for execution in cleaned.get("executions") or []:
            if self.author and execution.user_id != self.author.pk:
                self.add_error("executions", "训练日志只能关联作者本人的任务执行。")
                break
            if cycle and execution.training_task.training_plan.training_cycle_id != cycle.pk:
                self.add_error("executions", "任务执行必须属于训练日志对应周期。")
                break
            planned = execution.training_task.planned_date
            started = timezone.localtime(execution.started_at).date() if execution.started_at else None
            completed = timezone.localtime(execution.completed_at).date() if execution.completed_at else None
            actual_end = completed or training_date
            if training_date and planned != training_date and not (started and started <= training_date <= actual_end):
                self.add_error("executions", "任务计划日期或实际执行日期必须与训练日志日期合理对应。")
                break
        return cleaned

    def save(self, commit=True):
        log = super().save(commit=False)
        if self.author and not log.author_id:
            log.author = self.author
        if commit:
            log.save()
            log.executions.set(self.cleaned_data.get("executions"))
        return log
