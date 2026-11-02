from django import forms
from django.contrib.auth import get_user_model
from django.urls import reverse

from core.utils.forms import StyledFormMixin
from core.forms import MultipleFileField
from core.uploads import TRAINING_ATTACHMENT_UPLOAD_SPEC
from meetings.widgets import RecipientSelect
from standards.models import Skill, TechnicalDomain

from .models import TrainingTask, TrainingScheduleSlot
from accounts.services.users import get_user_full_info


class TrainingRecipientSelect(RecipientSelect):
    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["search_url"] = self.search_url
        context["widget"]["candidate_help"] = "仅可搜索本训练周期的选手。"
        return context


def cycle_coaches(plan):
    return get_user_model().objects.filter(
        training_cycle_memberships__training_cycle=plan.training_cycle, training_cycle_memberships__role="coach"
    )


class DayScheduleForm(StyledFormMixin, forms.Form):
    object_id = forms.IntegerField(widget=forms.HiddenInput)
    revision = forms.IntegerField(widget=forms.HiddenInput)
    date = forms.DateField(
        label="日期", input_formats=["%Y-%m-%d"], widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})
    )
    duty_all = forms.BooleanField(label="全体值班", required=False)
    duty_coaches = forms.ModelMultipleChoiceField(
        label="值班教练", queryset=get_user_model().objects.none(), required=False
    )
    note = forms.CharField(label="备注", required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, plan, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["duty_coaches"].queryset = cycle_coaches(plan)
        self.fields["date"].disabled = True
        self.fields["duty_coaches"].label_from_instance = get_user_full_info

    def clean(self):
        data = super().clean()
        if data.get("duty_all") and data.get("duty_coaches"):
            self.add_error("duty_coaches", "全体值班与具体值班名单不能同时选择。")
        return data


class SlotScheduleForm(StyledFormMixin, forms.Form):
    object_id = forms.IntegerField(widget=forms.HiddenInput)
    revision = forms.IntegerField(widget=forms.HiddenInput)
    period = forms.ChoiceField(label="时段", choices=TrainingScheduleSlot.Period.choices, disabled=True)
    domain_choice = forms.ChoiceField(label="领域")
    coaches_all = forms.BooleanField(label="全体负责", required=False)
    coaches = forms.ModelMultipleChoiceField(label="负责教练", queryset=get_user_model().objects.none(), required=False)

    def __init__(self, *args, plan, **kwargs):
        super().__init__(*args, **kwargs)
        self.domain_queryset = TechnicalDomain.objects.filter(pk__in=plan.training_cycle.skill_tree_version_links.values("technical_domain_id"))
        self.fields["domain_choice"].choices = [("", "请选择领域"), *[(str(obj.pk), obj.name) for obj in self.domain_queryset], ("other", "其他"), ("rest", "休息"), ("unused", "不安排")]
        self.fields["coaches"].queryset = cycle_coaches(plan)
        self.fields["coaches"].label_from_instance = get_user_full_info
        kind = self.initial.get("kind", "pending")
        self.initial["domain_choice"] = str(self.initial["primary_domain"]) if self.initial.get("primary_domain") else {"general": "other", "rest": "rest", "unused": "unused"}.get(kind, "")
        selected = self.data.get(self.add_prefix("domain_choice"), "") if self.is_bound else self.initial["domain_choice"]
        all_selected = self.data.get(self.add_prefix("coaches_all")) if self.is_bound else self.initial.get("coaches_all")
        self.fields["coaches"].required = selected not in {"rest", "unused"} and not all_selected

    def clean(self):
        data = super().clean()
        domain = data.get("domain_choice", "")
        data["kind"] = {"other": "general", "rest": "rest", "unused": "unused"}.get(domain, "technical")
        data["domains"] = self.domain_queryset.filter(pk=domain) if domain.isdecimal() else self.domain_queryset.none()
        data["primary_domain"] = data["domains"].first()
        if data.get("coaches_all") and data.get("coaches"):
            self.add_error("coaches", "全体与具体教练名单不能同时选择。")
        if domain not in {"rest", "unused"} and not data.get("coaches_all") and not data.get("coaches"):
            self.add_error("coaches", "请选择负责教练或全体负责。")
        return data


class SlotTaskForm(StyledFormMixin, forms.ModelForm):
    attachments = MultipleFileField(label="教练任务附件", required=False, upload_spec=TRAINING_ATTACHMENT_UPLOAD_SPEC)
    reason = forms.CharField(label="调整原因和实际执行情况", required=False)
    assignment_configured = forms.BooleanField(required=False, initial=True, widget=forms.HiddenInput)
    skills = forms.ModelMultipleChoiceField(label="关联技能", queryset=Skill.objects.none(), required=False)
    competitors = forms.ModelMultipleChoiceField(
        label="指定选手", queryset=get_user_model().objects.none(), required=False, widget=TrainingRecipientSelect
    )

    class Meta:
        model = TrainingTask
        fields = ["title", "description", "requirements", "estimated_minutes", "priority", "order", "assign_all"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3}), "requirements": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, slot, **kwargs):
        super().__init__(*args, **kwargs)
        self.slot = slot
        if not self.instance.pk or self.instance.status == "draft":
            self.fields.pop("reason")
        self.fields["priority"].required = False
        self.fields["order"].required = False
        plan = slot.day.training_plan
        self.fields["skills"].queryset = Skill.objects.filter(skill_project=plan.training_cycle.skill_project)
        self.fields["competitors"].queryset = get_user_model().objects.filter(
            training_plan_participations__training_plan=plan,
            training_plan_participations__is_active=True,
        )
        if self.instance.pk:
            from django.db.models import Q
            self.fields["competitors"].queryset = get_user_model().objects.filter(Q(pk__in=self.fields["competitors"].queryset.values("pk")) | Q(pk__in=self.instance.executions.values("user_id"))).distinct()
        widget = self.fields["competitors"].widget
        widget.search_url = reverse("training:task_competitor_search", args=[slot.pk])
        if self.instance.pk:
            self.initial["skills"] = list(self.instance.skill_links.values_list("skill_id", flat=True))
            self.initial["competitors"] = list(self.instance.selected_competitors.values_list("pk", flat=True))
        ids = self.data.getlist("competitors") if self.is_bound else self.initial.get("competitors", [])
        from accounts.services.users import get_user_display_name

        widget.selected = [
            {"id": user.pk, "label": get_user_display_name(user)}
            for user in self.fields["competitors"].queryset.filter(
                pk__in=[value for value in ids if str(value).isdigit()]
            )
        ]

    def _post_clean(self):
        # 日期/计划由事务服务固定，避免 ModelForm 把尚未挂接的新任务作为完整实体校验。
        from django.forms.models import construct_instance

        self.instance = construct_instance(self, self.instance, self._meta.fields, self._meta.exclude)

    def clean(self):
        cleaned = super().clean()
        cleaned["priority"] = cleaned.get("priority") or TrainingTask.Priority.NORMAL
        cleaned["order"] = cleaned.get("order") or 0
        if not cleaned.get("assignment_configured"):
            cleaned["assign_all"] = True
        return cleaned


class SkillCorrectionForm(StyledFormMixin, forms.Form):
    reason = forms.CharField(label="过期修改原因和实际执行情况", required=False)
    skills = forms.ModelMultipleChoiceField(label="关联技能", queryset=Skill.objects.none(), required=False)

    def __init__(self, *args, task, **kwargs):
        super().__init__(*args, **kwargs)
        if task.status == "draft":
            self.fields.pop("reason")
        self.fields["skills"].queryset = Skill.objects.filter(skill_project=task.skill_project)
        self.initial["skills"] = list(task.skill_links.values_list("skill_id", flat=True))
