from datetime import timedelta

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from ai.dispatcher import supports_thinking
from ai.models import AIModelPreference, ReasoningEffort, ThinkingMode
from ai.services import usable_models
from core.forms import MultipleFileField
from core.utils.forms import StyledFormMixin

from .daily_progress import available_cycles, validate_training_day
from .log_references import IMAGE_SPEC
from .log_sources import FIELDS, FIELD_LIMIT
from .log_web_references import MAX_LINKS
from .models import TrainingLogPrompt


class TrainingDayForm(StyledFormMixin, forms.Form):
    training_date = forms.DateField(label="训练日期", widget=forms.DateInput(attrs={"type": "date"}))
    cycle = forms.ModelChoiceField(label="训练周期", queryset=None)

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        today = timezone.localdate()
        field = self.fields["training_date"]
        field.widget.attrs["max"] = today.isoformat()
        if not self.is_bound:
            self.initial["training_date"] = today
        try:
            day = field.to_python(self.data.get(self.add_prefix("training_date"))) or today
        except ValidationError:
            day = today
        self.fields["cycle"].queryset = available_cycles(user, today - timedelta(days=1))
        eligible = available_cycles(user, day)
        if not self.is_bound and eligible.count() == 1:
            self.initial["cycle"] = eligible.first().pk

    def clean(self):
        data = super().clean()
        cycle, day = data.get("cycle"), data.get("training_date")
        if cycle and day and not self.errors:
            validate_training_day(self.user, cycle, day)
        return data


class LogGenerationForm(StyledFormMixin, forms.Form):
    model = forms.ModelChoiceField(label="AI 模型", queryset=None, empty_label="请选择已验证的模型")
    thinking = forms.ChoiceField(
        label="思考模式", choices=[("", "使用模型设置"), *ThinkingMode.choices], required=False
    )
    effort = forms.ChoiceField(
        label="思考强度", choices=[("", "使用模型设置"), *ReasoningEffort.choices], required=False
    )
    instructions = forms.CharField(label="补充说明和写作要求", max_length=6000, required=False, widget=forms.Textarea)
    target_words = forms.IntegerField(label="主体内容建议字数", min_value=100, max_value=4000, required=False)
    text_only = forms.BooleanField(label="本次仅生成正文", required=False, help_text="已保存的插图会留在草稿中。")
    references = forms.CharField(
        label="参考链接",
        max_length=2500,
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text=f"每行填写一个可直接访问的公开网页链接，最多 {MAX_LINKS} 个。预览时会读取正文，供 AI 写作参考。",
    )

    def __init__(self, *args, draft, role, **kwargs):
        super().__init__(*args, **kwargs)
        models = usable_models(draft.author)
        self.fields["model"].queryset = models
        self.fields["model"].label_from_instance = lambda model: model.name
        setting = TrainingLogPrompt.for_role(role)
        self.fields["target_words"].help_text = (
            f"留空时，系统建议主体内容为 {setting.min_words}–{setting.max_words} 字。"
        )
        self.initial.setdefault("references", draft.references)
        if "model" not in self.initial:
            self.initial["model"] = (
                AIModelPreference.objects.filter(user=draft.author, model__in=models)
                .values_list("model_id", flat=True)
                .first()
            )

    def clean_references(self):
        url = forms.URLField(assume_scheme="https")
        links = []
        for line in self.cleaned_data["references"].splitlines():
            value = line.strip()
            if value:
                if not value.lower().startswith(("https://", "http://")):
                    raise ValidationError("参考链接须以 http:// 或 https:// 开头。")
                links.append(url.clean(value))
        links = list(dict.fromkeys(links))
        if len(links) > MAX_LINKS:
            raise ValidationError(f"最多填写 {MAX_LINKS} 个参考链接。")
        return "\n".join(links)

    def clean(self):
        data = super().clean()
        model = data.get("model")
        if model and not supports_thinking(model) and (data.get("thinking") or data.get("effort")):
            self.add_error("thinking", "所选模型未开放思考设置，请使用模型默认值。")
        elif data.get("effort") and model and (data.get("thinking") or model.thinking) != ThinkingMode.ENABLED:
            self.add_error("effort", "请先开启思考模式。")
        return data


class LogImageForm(StyledFormMixin, forms.Form):
    images = MultipleFileField(
        label="日志插图",
        upload_spec=IMAGE_SPEC,
        required=False,
        help_text="可上传或从训练完成情况带入。选好图片后请点击「保存插图」。",
    )
    progress_images = forms.ModelMultipleChoiceField(
        label="带入训练过程图片",
        required=False,
        queryset=None,
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, available, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["progress_images"].queryset = available
        self.fields["progress_images"].label_from_instance = lambda item: item.original_filename


class DraftBodyForm(StyledFormMixin, forms.Form):
    revision = forms.IntegerField(widget=forms.HiddenInput, min_value=0)

    def __init__(self, *args, role, draft, **kwargs):
        super().__init__(*args, **kwargs)
        for key, label in FIELDS[role]:
            self.fields[key] = forms.CharField(
                label=label,
                max_length=FIELD_LIMIT,
                widget=forms.Textarea(attrs={"rows": 14 if key == "process" else 4, "class": "textarea w-full"}),
            )
        if draft.source.get("format") == 2 and len(draft.source["tasks"]) > 1:
            self.fields["task_title"] = forms.CharField(
                label="训练任务概括标题",
                max_length=20,
                widget=forms.TextInput(attrs={"class": "input w-full"}),
            )
            self.order_fields(["revision", "task_title"])
        self.initial.update(draft.body, revision=draft.revision)


class LogPromptForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = TrainingLogPrompt
        fields = ("instructions", "min_words", "max_words")
        labels = {
            "instructions": "写作提示词",
            "min_words": "主体内容最少字数",
            "max_words": "主体内容最多字数",
        }


class LogActionForm(forms.Form):
    revision = forms.IntegerField(min_value=0, required=False)
    generation = forms.IntegerField(min_value=1, required=False)
    source_digest = forms.CharField(max_length=64, required=False)
    accept_changes = forms.BooleanField(required=False)
