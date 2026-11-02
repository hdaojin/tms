from __future__ import annotations

from datetime import timedelta

from django import forms
from django.utils import timezone
from django.utils.html import format_html
from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.urls import reverse

from core.uploads import TRAINING_LOG_UPLOAD_SPEC
from core.utils.forms import StyledFormMixin
from standards.forms import DefaultSkillProjectFormMixin
from standards.models import Skill, SkillProject, SkillTreeVersion, TechnicalDomain

from .models import (
    TaskExecution,
    TrainingCycle,
    TrainingCycleMember,
    TrainingLog,
    TrainingLogTemplate,
    TrainingPlan,
    TrainingTask,
    TrainingTaskCoach,
    TrainingTaskDomain,
    TrainingTaskSkill,
)
from .services import (
    publish_training_task, save_cycle_tree_versions, save_training_log, validate_cycle_tree_versions, validate_new_log,
)
from .log_files import DUPLICATE_LOG_MESSAGE, build_log_filename
from .plan_people import PlanStaffSelect, eligible_staff


User = get_user_model()


class TrainingLogTemplateForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = TrainingLogTemplate
        fields = ["name", "training_cycle", "file", "description", "order", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["file"].widget.attrs.update(TRAINING_LOG_UPLOAD_SPEC.widget_attrs())
        self.fields["file"].help_text = TRAINING_LOG_UPLOAD_SPEC.help_text("上传日志模板")
        # 替换是可选操作，不允许清空必需文件。
        self.fields["file"].widget = forms.FileInput(attrs=self.fields["file"].widget.attrs)

    def _get_validation_exclusions(self):
        exclusions = super()._get_validation_exclusions()
        if self.instance.pk and not self.files.get("file"):
            exclusions.add("file")
        return exclusions


class TrainingLogStatisticsForm(StyledFormMixin, forms.Form):
    cycle = forms.ModelChoiceField(label="训练周期", queryset=TrainingCycle.objects.none())
    year = forms.IntegerField(label="年份", min_value=1, max_value=9999)
    month = forms.TypedChoiceField(label="月份", coerce=int, choices=[(i, f"{i}月") for i in range(1, 13)])
    role = forms.ChoiceField(label="成员身份", required=False,
                             choices=[("", "全部"), *TrainingCycleMember.Role.choices])

    def __init__(self, *args, user, **kwargs):
        from .selectors import training_log_statistics_cycles_for

        super().__init__(*args, **kwargs)
        self.fields["cycle"].queryset = training_log_statistics_cycles_for(user)


class CycleMemberAddForm(StyledFormMixin, forms.Form):
    users = forms.ModelMultipleChoiceField(label="用户", queryset=User.objects.filter(is_active=True))
    role = forms.ChoiceField(label="周期身份", choices=TrainingCycleMember.Role.choices)
    is_current = forms.BooleanField(label="设为当前周期", required=False,
                                   help_text="将替换所选用户原来的当前周期。")


class CycleMemberEditForm(StyledFormMixin, forms.Form):
    role = forms.ChoiceField(label="周期身份", choices=TrainingCycleMember.Role.choices)
    is_current = forms.BooleanField(label="设为当前周期", required=False,
                                   help_text="勾选将替换该用户原来的当前周期；取消则清除本周期的当前标记。")


class TrainingCycleForm(DefaultSkillProjectFormMixin, StyledFormMixin, forms.ModelForm):
    class Meta:
        model = TrainingCycle
        fields = [
            "skill_project",
            "parent",
            "code",
            "name",
            "status",
            "start_date",
            "end_date",
            "description",
        ]
        widgets = {
            "start_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "end_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
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
        context_url = reverse("training:cycle_parent_field")
        if self.instance.pk:
            context_url += f"?cycle_id={self.instance.pk}"
        self.fields["skill_project"].widget.attrs.update(
            {
                "hx-get": context_url,
                "hx-target": "#cycle-parent-context",
                "hx-trigger": "change",
                "hx-include": "closest form",
            }
        )

    def clean(self):
        cleaned = super().clean()
        if not self.instance.pk and cleaned.get("status") != TrainingCycle.Status.PLANNING:
            self.add_error("status", "新建周期必须先保存为筹备中，再按顺序推进状态。")
        return cleaned

    @transaction.atomic
    def save(self, commit=True):
        cycle = super().save(commit=False)
        if not commit:
            return cycle
        if cycle.pk:
            TrainingCycle.objects.select_for_update().get(pk=cycle.pk)
        cycle.save()
        self.save_m2m()
        return cycle


class TrainingCycleTreeVersionsForm(StyledFormMixin, forms.Form):
    def __init__(self, *args, cycle, **kwargs):
        super().__init__(*args, **kwargs)
        self.cycle = cycle
        existing_links = {
            link.technical_domain_id: link
            for link in cycle.skill_tree_version_links.select_related("technical_domain", "skill_tree_version")
        }
        if cycle.parent_id:
            domains = TechnicalDomain.objects.filter(
                pk__in=cycle.parent.skill_tree_version_links.values("technical_domain_id")
            )
        else:
            domains = TechnicalDomain.objects.filter(
                models.Q(skill_project=cycle.skill_project, is_active=True) | models.Q(pk__in=existing_links)
            )
        self.version_fields = []
        locked = cycle.skill_tree_bindings_locked
        for domain in domains.order_by("order", "code", "pk"):
            field_name = f"tree_version_{domain.pk}"
            field = forms.ModelChoiceField(
                label=f"{domain.name}技能树版本",
                queryset=SkillTreeVersion.objects.filter(technical_domain=domain).select_related(
                    "technical_domain"
                ).order_by("-is_current", "-created_at", "-pk"),
                required=False,
                empty_label="不纳入当前周期",
                disabled=locked and (domain.pk in existing_links or not cycle.can_add_skill_tree_bindings),
            )
            if domain.pk in existing_links:
                field.initial = existing_links[domain.pk].skill_tree_version
            field.widget.attrs["class"] = "select w-full"
            self.fields[field_name] = field
            self.version_fields.append((field_name, domain))

    def clean(self):
        cleaned = super().clean()
        if self.errors:
            return cleaned
        selected = {
            domain.pk: cleaned.get(field_name)
            for field_name, domain in self.version_fields
            if cleaned.get(field_name) is not None
        }
        validate_cycle_tree_versions(self.cycle, selected)
        cleaned["selected_tree_versions"] = selected
        return cleaned

    def save(self):
        return save_cycle_tree_versions(self.cycle, self.cleaned_data["selected_tree_versions"])


class TrainingPlanForm(StyledFormMixin, forms.ModelForm):
    reason = forms.CharField(label="时段时间调整原因", required=False, widget=forms.Textarea(attrs={"rows": 2}))
    class Meta:
        model = TrainingPlan
        fields = ["training_cycle", "title", "start_date", "end_date", *TrainingPlan.TIME_FIELDS, "objective", "schedulers", "approvers"]
        widgets = {
            "start_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "end_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "objective": forms.Textarea(attrs={"rows": 4}),
            "schedulers": PlanStaffSelect(),
            "approvers": PlanStaffSelect(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["training_cycle"].empty_label = "请选择训练周期"
        unknown_periods = set()
        if self.instance.pk:
            from .models import TrainingScheduleSlot
            unknown_periods = set(TrainingScheduleSlot.objects.filter(
                day__training_plan=self.instance, is_configured=True, ends_at__isnull=True
            ).values_list("period", flat=True))
        for name in TrainingPlan.TIME_FIELDS:
            self.fields[name].required = name.startswith(("morning_", "afternoon_"))
            self.fields[name].widget = forms.TimeInput(format="%H:%M", attrs={"type": "time", "class": "input w-full"})
            if self.instance.pk and getattr(self.instance, name) is None and name.rsplit("_", 1)[0] in unknown_periods:
                self.fields[name].help_text = "历史时间缺失或不一致，请核对后填写；普通保存不改变已结束快照。"
        if not self.instance.pk:
            self.fields.pop("reason")
            from .models import TrainingPeriodConfig
            for config in TrainingPeriodConfig.objects.all():
                self.initial.setdefault(f"{config.period}_start", config.start_time)
                self.initial.setdefault(f"{config.period}_end", config.end_time)
        else:
            for name in ("training_cycle", "start_date", "end_date"):
                self.fields[name].help_text = "首次保存后固定；需要改变请另建计划。"
            for name in ("start_date", "end_date"):
                self.fields[name].widget.attrs["readonly"] = True
        from accounts.services.users import get_user_full_info
        for name in ("schedulers", "approvers"):
            field = self.fields[name]
            field.widget.plan_id = self.instance.pk
            ids = [str(pk) for pk in (self[name].value() or []) if str(pk).isdecimal()]
            eligible_ids = set(eligible_staff(name).filter(pk__in=ids).values_list("pk", flat=True))
            field.widget.selected = [
                {"id": person.pk, "label": get_user_full_info(person),
                 "unavailable": person.pk not in eligible_ids}
                for person in field.queryset.filter(pk__in=ids).order_by("last_name", "first_name", "username", "pk")
            ]

    def clean(self):
        cleaned = super().clean()
        if self.instance.pk:
            previous = TrainingPlan.objects.get(pk=self.instance.pk)
            if {"training_cycle", "start_date", "end_date"}.intersection(self.changed_data):
                raise forms.ValidationError("计划创建后不能修改周期和日期范围，请另建计划。")
            if set(TrainingPlan.TIME_FIELDS).intersection(self.changed_data) and previous.schedule_published_at and not cleaned.get("reason", "").strip():
                self.add_error("reason", "已发布排班的时间调整须填写原因并提交审批。")
        for name in ("schedulers", "approvers"):
            previous_ids = set(getattr(self.instance, name).values_list("pk", flat=True)) if self.instance.pk else set()
            selected_ids = {person.pk for person in cleaned.get(name, ())}
            new_ids = selected_ids - previous_ids
            eligible_ids = set(eligible_staff(name).filter(pk__in=new_ids).values_list("pk", flat=True))
            if new_ids - eligible_ids:
                self.add_error(name, "新指定的人员必须账号有效且具有对应权限。")
        return cleaned


class TrainingTaskForm(StyledFormMixin, forms.ModelForm):
    domains = forms.ModelMultipleChoiceField(
        label="技术领域", queryset=TechnicalDomain.objects.none(), widget=forms.CheckboxSelectMultiple
    )
    primary_domain = forms.ModelChoiceField(
        label="主要技术领域", queryset=TechnicalDomain.objects.none(), required=False
    )
    skills = forms.ModelMultipleChoiceField(
        label="技能", queryset=Skill.objects.none(), widget=forms.CheckboxSelectMultiple, required=False
    )
    primary_skill = forms.ModelChoiceField(label="主要技能", queryset=Skill.objects.none(), required=False)
    coaches = forms.ModelMultipleChoiceField(
        label="负责教练", queryset=User.objects.none(), widget=forms.CheckboxSelectMultiple
    )
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
            "planned_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
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
        if cleaned.get("status") == TrainingTask.Status.PUBLISHED:
            if not domains:
                self.add_error("domains", "发布任务前必须至少选择一个技术领域。")
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
            )
        if task.status == TrainingTask.Status.PUBLISHED:
            publish_training_task(
                task, self.cleaned_data["competitors"].values_list("pk", flat=True), user=self.request_user
            )
        return task


class TaskExecutionForm(StyledFormMixin, forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.training_task_id and self.instance.training_task.schedule_slot_id:
            from .process import STATES
            self.fields["status"].choices = STATES

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
            "training_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "summary": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, **kwargs):
        self.author = kwargs.pop("author", None)
        self.backfill = kwargs.pop("backfill", False)
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.author = self.instance.author
        elif self.author:
            self.instance.author = self.author
            default_cycle = (
                TrainingCycle.objects.filter(members__user=self.author, members__is_current=True,
                                             status=TrainingCycle.Status.ACTIVE).first()
            )
            if not self.backfill:
                self.current_cycle = default_cycle
                self.initial["training_cycle"] = default_cycle.pk if default_cycle else None
                self.fields["training_cycle"].disabled = True
                self.fields["training_cycle"].widget = forms.HiddenInput()
                self.fields["training_cycle"].label = "当前周期"
                self.fields["training_cycle"].queryset = TrainingCycle.objects.filter(
                    pk=default_cycle.pk if default_cycle else None
                )
                self.fields["training_cycle"].empty_label = "未设置有效的当前周期，请联系管理员"
                self.fields["training_cycle"].help_text = "当前周期由管理员设置；其他周期的日志请使用历史补交入口。"
            else:
                self.fields["training_cycle"].queryset = TrainingCycle.objects.filter(
                    members__user=self.author,
                    status__in=[TrainingCycle.Status.ACTIVE, TrainingCycle.Status.COMPLETED],
                )
        if self.instance.pk:
            self.fields["training_cycle"].disabled = True
            self.fields["training_cycle"].widget = forms.HiddenInput()
            self.current_cycle = self.instance.training_cycle
        if not self.instance.pk and not self.backfill:
            self.initial["training_date"] = timezone.localdate()
            self.fields["training_date"].disabled = True
            self.fields["training_date"].help_text = format_html(
                '只能提交当天训练日志；历史日志请使用<a class="link link-primary" href="{}">补交入口</a>。',
                reverse("training:log_backfill"),
            )
        elif not self.instance.pk:
            self.initial["training_date"] = timezone.localdate() - timedelta(days=1)
        self.fields["document"].widget.attrs.update(TRAINING_LOG_UPLOAD_SPEC.widget_attrs())
        latest_date = timezone.localdate() - timedelta(days=1) if self.backfill and not self.instance.pk else timezone.localdate()
        self.fields["training_date"].widget.attrs["max"] = latest_date.isoformat()
        self.fields["document"].help_text = TRAINING_LOG_UPLOAD_SPEC.help_text("上传日志文件")
        self.fields["document"].required = not self.instance.pk
        if self.instance.pk and self.instance.document:
            # 不把已有文件再次交给 FileField 校验，避免读取旧文件或触发替换。
            self.fields.pop("document")
            for field in ("training_cycle", "training_date"):
                self.fields[field].disabled = True
                self.fields[field].help_text = "已有日志文件，如需修改请先删除日志后重新上传。"
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
        if not self.instance.pk and not self.backfill and not cycle:
            self.add_error(None, "未设置有效的当前周期，请联系管理员。")
        if cycle and training_date and self.author:
            if not self.instance.pk:
                try:
                    validate_new_log(TrainingLog(training_cycle=cycle, author=self.author, training_date=training_date),
                                     backfill=self.backfill)
                except forms.ValidationError as exc:
                    self.add_error(None, exc)
            others = TrainingLog.objects.filter(training_cycle=cycle).exclude(pk=self.instance.pk)
            if others.filter(author=self.author, training_date=training_date).exists():
                self.add_error(None, DUPLICATE_LOG_MESSAGE)
            document = cleaned.get("document")
            if document and not getattr(document, "_committed", False):
                candidate = TrainingLog(training_cycle=cycle, author=self.author, training_date=training_date)
                try:
                    filename = build_log_filename(candidate, document.name)
                except forms.ValidationError as exc:
                    self.add_error("document", exc)
                else:
                    if others.filter(
                        models.Q(canonical_filename=filename) | models.Q(document__endswith="/" + filename)
                        | models.Q(document__endswith="\\" + filename)
                    ).exists():
                        self.add_error("document", DUPLICATE_LOG_MESSAGE)
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
            save_training_log(log, self.cleaned_data.get("executions"), backfill=self.backfill)
        return log
