from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model

from core.uploads import GLOSSARY_WORKBOOK_UPLOAD_SPEC
from core.utils.forms import StyledFormMixin
from standards.forms import DefaultSkillProjectFormMixin
from standards.models import SkillProject

from .models import GlossaryEntry, GlossaryEntryProposal, ProfessionalGlossary, StudySession
from .normalization import english_comparison_key, normalize_display_text


def _aliases_to_lines(value) -> str:
    return "\n".join(value or [])


def _lines_to_aliases(value: str) -> list[str]:
    return [line for line in (normalize_display_text(part) for part in (value or "").splitlines()) if line]


class AliasFieldsMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = getattr(self, "instance", None)
        if instance and instance.pk:
            self.fields["english_aliases_text"].initial = _aliases_to_lines(instance.english_aliases)
            self.fields["chinese_aliases_text"].initial = _aliases_to_lines(instance.chinese_aliases)

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.english_aliases = _lines_to_aliases(self.cleaned_data.get("english_aliases_text", ""))
        instance.chinese_aliases = _lines_to_aliases(self.cleaned_data.get("chinese_aliases_text", ""))
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class ProfessionalGlossaryForm(DefaultSkillProjectFormMixin, StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ProfessionalGlossary
        fields = ["skill_project", "name", "description", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}


class GlossaryEntryForm(AliasFieldsMixin, StyledFormMixin, forms.ModelForm):
    english_aliases_text = forms.CharField(
        label="英文答案别名",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="每行一个；Acronym 无需重复填写。",
    )
    chinese_aliases_text = forms.CharField(
        label="中文答案别名",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="每行一个；系统会自动处理与英文或 Acronym 完全对应的末尾括注。",
    )

    class Meta:
        model = GlossaryEntry
        fields = [
            "glossary",
            "english_term",
            "acronym",
            "chinese_translation",
            "english_aliases_text",
            "chinese_aliases_text",
            "is_active",
        ]
        widgets = {"chinese_translation": forms.Textarea(attrs={"rows": 3})}

    def clean(self):
        cleaned = super().clean()
        glossary = cleaned.get("glossary")
        key = english_comparison_key(cleaned.get("english_term"))
        if not glossary or not key:
            return cleaned
        duplicates = GlossaryEntry.objects.filter(glossary=glossary, english_key=key)
        if self.instance.pk:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            self.add_error("english_term", "该专业词库中已存在相同英文词条。")
        return cleaned


class GlossaryEntryProposalForm(AliasFieldsMixin, StyledFormMixin, forms.ModelForm):
    english_aliases_text = forms.CharField(
        label="英文答案别名",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="每行一个；Acronym 无需重复填写。",
    )
    chinese_aliases_text = forms.CharField(
        label="中文答案别名",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="每行一个；系统会自动处理与英文或 Acronym 完全对应的末尾括注。",
    )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["glossary"].queryset = ProfessionalGlossary.objects.filter(is_active=True).select_related(
            "skill_project"
        )

    class Meta:
        model = GlossaryEntryProposal
        fields = [
            "glossary",
            "english_term",
            "acronym",
            "chinese_translation",
            "english_aliases_text",
            "chinese_aliases_text",
        ]
        widgets = {"chinese_translation": forms.Textarea(attrs={"rows": 3})}

    def clean(self):
        cleaned = super().clean()
        glossary = cleaned.get("glossary")
        key = english_comparison_key(cleaned.get("english_term"))
        if not glossary or not key:
            return cleaned
        if GlossaryEntry.objects.filter(glossary=glossary, english_key=key).exists():
            self.add_error("english_term", "该专业词库中已存在相同英文词条。")
        pending = GlossaryEntryProposal.objects.filter(
            glossary=glossary,
            english_key=key,
            status=GlossaryEntryProposal.Status.PENDING,
        )
        if self.instance.pk:
            pending = pending.exclude(pk=self.instance.pk)
        if pending.exists():
            self.add_error("english_term", "该专业词库中已有相同英文的待审核提案。")
        return cleaned


class GlossaryImportForm(StyledFormMixin, forms.Form):
    glossary = forms.ModelChoiceField(
        label="专业词库",
        queryset=ProfessionalGlossary.objects.none(),
    )
    file = forms.FileField(
        label="Smartcat XLSX",
        validators=GLOSSARY_WORKBOOK_UPLOAD_SPEC.validators(),
        widget=forms.ClearableFileInput(attrs=GLOSSARY_WORKBOOK_UPLOAD_SPEC.widget_attrs(type="file")),
        help_text=GLOSSARY_WORKBOOK_UPLOAD_SPEC.help_text("上传 Smartcat 工作簿"),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["glossary"].queryset = ProfessionalGlossary.objects.select_related("skill_project")

    def clean_file(self):
        file_obj = self.cleaned_data["file"]
        GLOSSARY_WORKBOOK_UPLOAD_SPEC.validate_file(file_obj)
        return file_obj


class GlossaryImportConfirmForm(StyledFormMixin, forms.Form):
    overwrite_all = forms.BooleanField(label="覆盖全部库内重复项", required=False)

    def __init__(self, *args, payload: dict, **kwargs):
        self.payload = payload
        super().__init__(*args, **kwargs)
        for index, group in enumerate(payload.get("groups", [])):
            options = group.get("options") or []
            if len(options) > 1:
                self.fields[f"choice_{index}"] = forms.ChoiceField(
                    label=f"{options[0]['english_term']}：选择保留行",
                    choices=[
                        (
                            str(option_index),
                            f"第 {option['row_number']} 行：{option['chinese_translation']}",
                        )
                        for option_index, option in enumerate(options)
                    ],
                    widget=forms.RadioSelect,
                )
            if group.get("existing"):
                self.fields[f"overwrite_{index}"] = forms.BooleanField(
                    label=f"覆盖 {group['existing']['english_term']}",
                    required=False,
                )

    def decisions(self) -> dict:
        choices: dict[str, int] = {}
        overwrite: list[str] = []
        for index, _group in enumerate(self.payload.get("groups", [])):
            choice_name = f"choice_{index}"
            if choice_name in self.fields:
                choices[str(index)] = int(self.cleaned_data[choice_name])
            if self.cleaned_data.get(f"overwrite_{index}"):
                overwrite.append(str(index))
        return {
            "overwrite_all": self.cleaned_data.get("overwrite_all", False),
            "overwrite": overwrite,
            "choices": choices,
        }


class ProposalRejectForm(StyledFormMixin, forms.Form):
    review_note = forms.CharField(label="驳回原因", widget=forms.Textarea(attrs={"rows": 4}))


class StudyStartForm(StyledFormMixin, forms.Form):
    glossary = forms.ModelChoiceField(label="专业词库", queryset=ProfessionalGlossary.objects.none())
    mode = forms.ChoiceField(label="学习模式", choices=StudySession.Mode.choices)
    target_count = forms.ChoiceField(
        label="题量",
        choices=[("10", "10 题"), ("20", "20 题"), ("50", "50 题"), ("", "不限量")],
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["glossary"].queryset = (
            ProfessionalGlossary.objects.filter(is_active=True, entries__is_active=True)
            .select_related("skill_project")
            .distinct()
        )

    def clean_target_count(self):
        value = self.cleaned_data.get("target_count")
        return int(value) if value else None


class StudyAnswerForm(StyledFormMixin, forms.Form):
    answer = forms.CharField(
        label="你的答案",
        max_length=2000,
        widget=forms.TextInput(
            attrs={
                "autocomplete": "off",
                "autocapitalize": "none",
                "spellcheck": "false",
                "placeholder": "输入对应的专业词条或释义",
            }
        ),
    )


class StatisticsFilterForm(StyledFormMixin, forms.Form):
    user = forms.ModelChoiceField(label="学习者", queryset=get_user_model().objects.none(), required=False)
    skill_project = forms.ModelChoiceField(label="技能项目", queryset=SkillProject.objects.none(), required=False)
    glossary = forms.ModelChoiceField(label="专业词库", queryset=ProfessionalGlossary.objects.none(), required=False)
    date_from = forms.DateField(label="开始日期", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(label="结束日期", required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, include_user=True, **kwargs):
        super().__init__(*args, **kwargs)
        if not include_user:
            self.fields.pop("user")
        else:
            self.fields["user"].queryset = get_user_model().objects.filter(is_active=True).order_by("username")
        self.fields["skill_project"].queryset = SkillProject.objects.filter(is_active=True)
        self.fields["glossary"].queryset = ProfessionalGlossary.objects.select_related("skill_project")
