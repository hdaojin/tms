from django import forms
from django.contrib.auth import get_user_model
from django.urls import reverse

from core.utils.forms import StyledFormMixin
from core.forms import MultipleFileField
from core.uploads import TRAINING_ATTACHMENT_UPLOAD_SPEC
from meetings.widgets import RecipientSelect
from standards.models import Skill, TechnicalDomain

from . import scheduling
from .models import TrainingTask, TrainingScheduleSlot
from accounts.services.users import annotate_identity_labels, get_user_full_info


class TrainingRecipientSelect(RecipientSelect):
    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["search_url"] = self.search_url
        context["widget"]["candidate_help"] = "仅可搜索本训练周期的选手。"
        return context


class SkillSelect(TrainingRecipientSelect):
    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"].update(candidate_help="仅显示本项目及当前技术领域内的技能。", candidate_label="技能",
                                 candidate_placeholder="输入技能名称，不区分大小写")
        return context


class SubtaskInputs(forms.Widget):
    template_name = "training/subtask_inputs.html"

    class Media:
        js = ("js/training-checklist-editor.js",)

    def value_from_datadict(self, data, files, name):
        return data.getlist(name) if hasattr(data, "getlist") else data.get(name, [])

    def format_value(self, value):
        return value or []


def slot_skills(slot):
    from django.db.models import Q

    skills = Skill.objects.filter(skill_project=slot.day.training_plan.training_cycle.skill_project)
    domains = list(slot.domains.values_list("pk", flat=True))
    if domains:
        skills = skills.filter(Q(primary_domain_id__in=domains) | Q(related_domains__in=domains)).distinct()
    return skills


def plan_coaches(plan):
    return plan.responsible_coaches.all()


class DayScheduleForm(StyledFormMixin, forms.Form):
    object_id = forms.IntegerField(widget=forms.HiddenInput)
    revision = forms.IntegerField(widget=forms.HiddenInput)
    date = forms.DateField(
        label="日期", input_formats=["%Y-%m-%d"], widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})
    )
    duty_all = forms.BooleanField(label="全体值班", required=False)
    duty_coaches = forms.ModelMultipleChoiceField(
        label="值班人员", queryset=get_user_model().objects.none(), required=False
    )
    note = forms.CharField(label="备注", required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, plan, **kwargs):
        super().__init__(*args, **kwargs)
        from .plan_members import ordered_duty
        self.fields["duty_coaches"].queryset = annotate_identity_labels(ordered_duty(plan))
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
        self.fields["domain_choice"].choices = [("", "请选择领域"), *[(str(obj.pk), obj.name) for obj in self.domain_queryset], *scheduling.SPECIAL_DOMAIN_CHOICES]
        self.fields["coaches"].queryset = annotate_identity_labels(plan_coaches(plan))
        self.fields["coaches"].label_from_instance = get_user_full_info
        kind = self.initial.get("kind", "pending")
        self.initial["domain_choice"] = str(self.initial["primary_domain"]) if self.initial.get("primary_domain") else scheduling.SPECIAL_DOMAIN_BY_KIND.get(kind, "")
        selected = self.data.get(self.add_prefix("domain_choice"), "") if self.is_bound else self.initial["domain_choice"]
        all_selected = self.data.get(self.add_prefix("coaches_all")) if self.is_bound else self.initial.get("coaches_all")
        self.fields["coaches"].required = selected not in {"rest", "unused"} and not all_selected

    def clean(self):
        data = super().clean()
        domain = data.get("domain_choice", "")
        data["kind"] = scheduling.SPECIAL_DOMAIN_KINDS.get(domain, "technical")
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
    subtask_titles = forms.Field(label="子任务", widget=SubtaskInputs, required=False)
    skills = forms.ModelMultipleChoiceField(label="关联技能", queryset=Skill.objects.none(), required=False, widget=SkillSelect)
    competitors = forms.ModelMultipleChoiceField(
        label="指定选手", queryset=get_user_model().objects.none(), required=False, widget=TrainingRecipientSelect
    )
    field_order = [
        "title", "requirements", "overview", "subtask_titles", "attachments", "skills",
        "order", "assign_all", "competitors", "reason",
    ]

    class Meta:
        model = TrainingTask
        fields = ["title", "requirements", "overview", "order", "assign_all"]
        widgets = {
            "requirements": forms.Textarea(attrs={"rows": 3}),
            "overview": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, slot, **kwargs):
        super().__init__(*args, **kwargs)
        self.slot = slot
        if not self.instance.pk or self.instance.status == "draft":
            self.fields.pop("reason")
        self.fields["order"].required = False
        plan = slot.day.training_plan
        self.fields["skills"].queryset = slot_skills(slot)
        self.fields["skills"].widget.search_url = reverse("training:task_skill_search", args=[slot.pk])
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
            self.initial["subtask_titles"] = [item["title"] for item in self.instance.subtasks]
            self.fields["subtask_titles"].disabled = self.instance.executions.filter(
                progress_records__checklist__isnull=False,
            ).exists()
        skill_ids = self.data.getlist("skills") if self.is_bound else self.initial.get("skills", [])
        self.fields["skills"].widget.selected = [
            {"id": skill.pk, "label": skill.name} for skill in self.fields["skills"].queryset.filter(
                pk__in=[value for value in skill_ids if str(value).isdigit()],
            )
        ]
        ids = self.data.getlist("competitors") if self.is_bound else self.initial.get("competitors", [])
        widget.selected = [
            {"id": user.pk, "label": get_user_full_info(user)}
            for user in annotate_identity_labels(self.fields["competitors"].queryset).filter(
                pk__in=[value for value in ids if str(value).isdigit()]
            )
        ]

    def _post_clean(self):
        # 日期/计划由事务服务固定，避免 ModelForm 把尚未挂接的新任务作为完整实体校验。
        from django.forms.models import construct_instance

        self.instance = construct_instance(self, self.instance, self._meta.fields, self._meta.exclude)

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("assignment_configured"):
            cleaned["assign_all"] = self.instance.assign_all
        if cleaned.get("competitors") is not None and not cleaned.get("assign_all"):
            from accounts.services.users import require_distinguishable_users
            from django.contrib.auth import get_user_model

            previous = set(self.instance.selected_competitors.values_list("pk", flat=True)) if self.instance.pk else set()
            selected = set(cleaned["competitors"].values_list("pk", flat=True)) - previous
            plan = self.slot.day.training_plan
            scope = get_user_model().objects.filter(pk__in=plan.participants.filter(is_active=True).values("user_id"))
            try:
                require_distinguishable_users(scope, selected)
            except forms.ValidationError as exc:
                self.add_error("competitors", exc)
        cleaned["order"] = cleaned.get("order") or 0
        return cleaned

    def clean_subtask_titles(self):
        titles = [value.strip() for value in self.cleaned_data["subtask_titles"] or [] if value.strip()]
        if len(titles) > 100 or any(len(title) > 240 for title in titles):
            raise forms.ValidationError("每项子任务最多 240 字，最多填写 100 项。")
        return titles


class SkillCorrectionForm(StyledFormMixin, forms.Form):
    reason = forms.CharField(label="过期修改原因和实际执行情况", required=False)
    skills = forms.ModelMultipleChoiceField(label="关联技能", queryset=Skill.objects.none(), required=False)

    def __init__(self, *args, task, **kwargs):
        super().__init__(*args, **kwargs)
        if task.status == "draft":
            self.fields.pop("reason")
        self.fields["skills"].queryset = Skill.objects.filter(skill_project=task.skill_project)
        self.initial["skills"] = list(task.skill_links.values_list("skill_id", flat=True))
