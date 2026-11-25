from datetime import timedelta

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.functional import cached_property

from ai.catalog import configurable_presets, matching_option, provider_catalog
from ai.models import AIModelPreference, ReasoningEffort, ThinkingMode
from ai.providers import ADAPTERS
from ai.services import usable_models
from core.forms import MultipleFileField
from core.utils.forms import StyledFormMixin

from .daily_progress import available_cycles, validate_training_day
from .log_references import IMAGE_SPEC
from .log_sources import FIELDS, FIELD_LIMIT, editor_body, editor_fields
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
    include_body = forms.BooleanField(
        label="将已填写的正文一并提供给 AI",
        required=False,
        help_text="勾选后，所有已填写的正文都会列入本次发送预览。确认发送后，所选模型可参考这些内容起草。",
    )
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

    @cached_property
    def parameter_catalog(self):
        return provider_catalog()

    def reasoning_settings(self, model):
        entry = self.parameter_catalog.get(model.provider, {})
        adapter = ADAPTERS.get(entry.get("provider_key"))
        if not adapter or not adapter.thinking:
            return {}
        presets = configurable_presets(matching_option(entry, model.base_url, model.model_id))
        if "thinking" not in presets:
            return {}
        return {"effort": "reasoning_effort" in presets, "default_thinking": model.thinking}

    @cached_property
    def model_reasoning_settings(self):
        models = self.fields["model"].queryset.only("provider", "base_url", "model_id", "thinking")
        return {
            str(model.pk): settings for model in models if (settings := self.reasoning_settings(model))
        }

    @cached_property
    def selected_reasoning_settings(self):
        return self.model_reasoning_settings.get(str(self["model"].value()), {})

    @property
    def show_effort(self):
        settings = self.selected_reasoning_settings
        return settings.get("effort", False) and (
            self["thinking"].value() or settings["default_thinking"]
        ) == ThinkingMode.ENABLED

    def clean(self):
        data = super().clean()
        model = data.get("model")
        thinking = self["thinking"].value()
        effort = self["effort"].value()
        if model and (thinking or effort):
            settings = self.reasoning_settings(model)
            if not settings:
                self.add_error(None, "所选模型未开放思考设置，请使用模型设置。")
            elif effort and not settings["effort"]:
                self.add_error(None, "所选模型未开放思考强度设置。")
            elif effort and (thinking or settings["default_thinking"]) != ThinkingMode.ENABLED:
                self.add_error(None, "请先开启思考模式。")
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
    section_help = {
        "goals_md": "用 - 列出可检验的训练目标，每条写清要完成的操作或达到的标准。",
        "outline_md": "用 1.、2. 按训练顺序列出任务或练习，每项写明训练内容。",
        "process": "用 ### 按步骤分段，记录实际操作、遇到的问题和验证结果。命令可用代码块。",
        "notes": "用 ### 按主题分段，记录学到的方法、关键命令和心得。",
        "achievement": "用 - 逐条对应训练目标，记录达成情况和依据，尚未核实的结果可写「待核实」。",
        "shortcomings": "用 - 逐条记录遇到的问题及影响。",
        "improvement": "用 1.、2. 列出下一步行动，并说明如何验证改进效果。",
    }

    def __init__(self, *args, role, draft, source=None, **kwargs):
        super().__init__(*args, **kwargs)
        if source is not None:
            for key, label in editor_fields(role):
                self.fields[key] = forms.CharField(
                    label=label,
                    help_text=f"支持 Markdown。{self.section_help[key]}",
                    required=False,
                    strip=False,
                    max_length=None if key in {"goals_md", "outline_md", "process"} else FIELD_LIMIT,
                    widget=forms.Textarea(attrs={
                        "rows": 8 if key in {"process", "notes"} else 4,
                        "class": "textarea w-full",
                        "data-log-section": "",
                    }),
                )
            self.initial.update(editor_body(role, draft.source or source, draft.body), revision=draft.revision)
            return
        note_mode = draft.source.get("teaching_notes")
        fields = [("goals_md", "训练目标"), ("outline_md", "训练内容"), *FIELDS[role]] if note_mode else FIELDS[role]
        for key, label in fields:
            self.fields[key] = forms.CharField(
                label=label,
                help_text=f"支持 Markdown。{self.section_help[key]}",
                required=not note_mode,
                max_length=None if note_mode and key in {"goals_md", "outline_md", "process"} else FIELD_LIMIT,
                widget=forms.Textarea(attrs={"rows": 14 if key == "process" else 4, "class": "textarea w-full"}),
            )
        if not note_mode and draft.source.get("format") == 2 and len(draft.source["tasks"]) > 1:
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
