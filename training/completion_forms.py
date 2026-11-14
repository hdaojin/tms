from django import forms
from django.db.models import Q
from django.urls import reverse
from standards.models import Skill, TechnicalDomain

from core.forms import MultipleFileField
from core.utils.forms import StyledFormMixin

from .checklists import checklist_items
from .log_references import IMAGE_SPEC, image_asset
from .schedule_forms import SkillSelect


class CompletionIssueForm(StyledFormMixin, forms.Form):
    description = forms.CharField(label="问题描述", max_length=2000, widget=forms.Textarea(attrs={"rows": 3}))
    domain = forms.ModelChoiceField(
        label="训练领域", queryset=TechnicalDomain.objects.none(), empty_label="请选择训练领域",
    )
    skills = forms.ModelMultipleChoiceField(
        label="关联技能点", queryset=Skill.objects.none(), required=False, widget=SkillSelect(attrs={"compact": True}),
    )

    def __init__(self, *args, cycle, day, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["domain"].queryset = TechnicalDomain.objects.filter(skill_project=cycle.skill_project)
        skills = Skill.objects.filter(skill_project=cycle.skill_project)
        self.fields["skills"].queryset = skills
        widget = self.fields["skills"].widget
        widget.search_url = reverse("training:completion_skill_search", args=[cycle.pk, day.isoformat()])
        ids = self.data.getlist(self.add_prefix("skills")) if self.is_bound else self.initial.get("skills", [])
        widget.selected = [{"id": skill.pk, "label": skill.name} for skill in skills.filter(
            pk__in=[value for value in ids if str(value).isascii() and str(value).isdigit()],
        )]

    def clean(self):
        data = super().clean()
        domain, skills = data.get("domain"), data.get("skills")
        if domain and skills is not None and skills.exclude(
            Q(primary_domain=domain) | Q(related_domains=domain),
        ).exists():
            self.add_error("skills", "请选择与该训练领域关联的技能。")
        return data


CompletionIssues = forms.formset_factory(CompletionIssueForm, extra=1, max_num=30, validate_max=True, can_delete=True)


class TaskCompletionForm(StyledFormMixin, forms.Form):
    items = forms.MultipleChoiceField(label="已完成项目", widget=forms.CheckboxSelectMultiple, required=False)

    def __init__(self, *args, execution, record, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["items"].choices = [
            (item["id"], item["title"]) for item in checklist_items(execution.training_task)
        ]
        if record:
            self.initial["items"] = [item["id"] for item in record.checklist or [] if item["done"]]


class DailyCompletionForm(StyledFormMixin, forms.Form):
    problems = forms.CharField(
        label="未完成的部分／存在问题",
        max_length=12000,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="如有未完成项，请在这里统一说明。涉及多个任务时可注明任务名称。",
    )
    images = MultipleFileField(label="过程图片", upload_spec=IMAGE_SPEC, required=False)

    def clean_images(self):
        from core.documents.content import normalize_document_image
        from core.documents.types import DocumentError

        files = self.cleaned_data["images"]
        for file in files:
            try:
                normalize_document_image(image_asset(file), "过程图片")
            except DocumentError as exc:
                raise forms.ValidationError(str(exc)) from exc
            finally:
                file.seek(0)
        return files
