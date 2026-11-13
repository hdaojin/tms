from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.urls import reverse

from accounts.services.users import annotate_identity_labels, get_user_full_info
from core.utils.forms import StyledFormMixin
from meetings.widgets import RecipientSelect

from .catalog import provider_catalog
from .models import ReasoningEffort, ShareAudience, ThinkingMode
from .providers import PROVIDERS, validate_base_url
from .services import normalize_thinking, share_recipients


class ThinkingForm(StyledFormMixin, forms.Form):
    thinking = forms.ChoiceField(label="思考模式", choices=ThinkingMode.choices, required=False)
    reasoning_effort = forms.ChoiceField(
        label="思考强度", choices=ReasoningEffort.choices, required=False, initial=ReasoningEffort.HIGH
    )

    def clean(self):
        data = super().clean()
        if "thinking" in data and "reasoning_effort" in data:
            thinking = data["thinking"] or self.initial.get("thinking")
            effort = data["reasoning_effort"]
            if not data["thinking"] and not effort:
                effort = self.initial.get("reasoning_effort")
            data["thinking"], data["reasoning_effort"] = normalize_thinking(thinking, effort)
        return data


class AIModelForm(ThinkingForm):
    field_order = (
        "name",
        "provider",
        "base_url",
        "model_choice",
        "model_id",
        "api_key",
        "thinking",
        "reasoning_effort",
    )
    name = forms.CharField(label="显示名称", max_length=100)
    provider = forms.ChoiceField(label="模型提供商", choices=[(code, item.label) for code, item in PROVIDERS.items()])
    base_url = forms.CharField(
        label="API 地址",
        max_length=300,
        required=False,
        widget=forms.TextInput(attrs={"aria-describedby": "ai-api-default"}),
    )
    model_choice = forms.ChoiceField(label="模型", required=False)
    model_id = forms.CharField(label="手动输入模型 ID", max_length=150, required=False)
    api_key = forms.RegexField(
        label="API 密钥",
        regex=r"\A[\x21-\x7e]+\Z",
        max_length=512,
        required=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        error_messages={"invalid": "API 密钥包含无效字符。"},
    )

    def __init__(self, *args, model=None, **kwargs):
        if model:
            kwargs["initial"] = {
                "name": model.name,
                "provider": model.provider,
                "base_url": model.base_url,
                "model_id": model.model_id,
                "thinking": model.thinking,
                "reasoning_effort": model.reasoning_effort or ReasoningEffort.HIGH,
            }
        else:
            kwargs["initial"] = {"provider": next(iter(PROVIDERS))}
        super().__init__(*args, **kwargs)
        self.catalog = provider_catalog()
        if model and model.provider in self.catalog:
            self.catalog[model.provider]["default"] = model.base_url
        provider = self["provider"].value()
        entry = self.catalog.get(provider, {})
        if not model:
            self.initial.update(
                thinking=entry.get("thinking", ThinkingMode.DISABLED),
                reasoning_effort=entry.get("reasoning_effort") or ReasoningEffort.HIGH,
            )
        self.effective_default = entry.get("default", "")
        options = entry.get("models", [])
        self.fields["model_choice"].choices = [
            ("", "手动输入模型 ID"),
            *((option["id"], option["label"]) for option in options),
        ]
        if not self.is_bound:
            existing_model_id = model.model_id if model else entry.get("default_model", "")
            if any(option["id"] == existing_model_id for option in options):
                self.initial["model_choice"] = existing_model_id
                self.initial["model_id"] = ""
        self.fields["api_key"].help_text = (
            f"当前密钥：{model.api_key_preview}。留空保留，填写新密钥即可替换。" if model else "保存后仅显示遮罩预览。"
        )

    def clean(self):
        data = super().clean()
        provider = data.get("provider")
        if not provider or "base_url" not in data:
            return data
        submitted_url = data["base_url"]
        shown_default = self.data.get("shown_default_base_url")
        if not submitted_url and shown_default and shown_default != self.effective_default:
            self.add_error("base_url", "默认 API 地址已更新，请核对当前地址后重新提交。")
            return data
        try:
            data["base_url"] = validate_base_url(provider, submitted_url or self.effective_default)
        except ValidationError as exc:
            self.add_error("base_url", exc)
        if "model_choice" in data:
            if data["model_choice"]:
                data["model_id"] = data["model_choice"]
            elif not data.get("model_id") and not self.has_error("model_id"):
                self.add_error("model_id", "请选择模型或手动输入模型 ID。")
        return data


class ProviderDefaultForm(ThinkingForm):
    field_order = ("default_base_url", "thinking", "reasoning_effort")
    default_base_url = forms.CharField(label="默认 API 地址", max_length=300, required=False)

    def __init__(self, *args, provider, **kwargs):
        super().__init__(*args, **kwargs)
        self.provider = provider
        self.fields["default_base_url"].help_text = f"留空将使用 {PROVIDERS[provider].default_url}。"

    def clean_default_base_url(self):
        value = self.cleaned_data["default_base_url"]
        return validate_base_url(self.provider, value) if value else ""


class ModelOptionForm(StyledFormMixin, forms.Form):
    model_id = forms.CharField(label="模型 ID", max_length=150)
    name = forms.CharField(label="显示名称", max_length=100)
    is_active = forms.BooleanField(label="在模型选项中显示", initial=True, required=False)
    is_default = forms.BooleanField(
        label="设为默认模型", required=False, help_text="新建此提供商的模型配置时将优先选中这一项。"
    )

    def __init__(self, *args, option=None, **kwargs):
        if option:
            kwargs["initial"] = {
                "model_id": option.model_id,
                "name": option.name,
                "is_active": option.is_active,
                "is_default": option.is_default,
            }
        super().__init__(*args, **kwargs)

    def clean(self):
        data = super().clean()
        if data.get("is_default") and not data.get("is_active"):
            self.add_error("is_default", "请先勾选「在模型选项中显示」，再设为默认模型。")
        return data


class ShareRecipientSelect(RecipientSelect):
    model_id = None

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"].update(
            search_url=reverse("ai_models:share_recipients", args=[self.model_id]),
            candidate_help="可选择有效账号。接收者使用模型时仍需共享模型使用权限。",
        )
        return context


class ShareModelForm(StyledFormMixin, forms.Form):
    mode = forms.ChoiceField(
        label="共享范围",
        choices=[("private", "私有"), *ShareAudience.choices],
        help_text="共享调用的内容会发送到配置的 API 地址，费用由该 API 账号承担。",
    )
    groups = forms.ModelMultipleChoiceField(
        label="指定角色",
        queryset=Group.objects.order_by("name", "pk"),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "checkbox checkbox-primary"}),
    )
    users = forms.ModelMultipleChoiceField(
        label="指定用户",
        queryset=get_user_model().objects.none(),
        required=False,
        widget=ShareRecipientSelect,
    )

    def __init__(self, *args, model, **kwargs):
        existing = list(model.shared_users.values_list("pk", flat=True))
        super().__init__(
            *args,
            initial={"mode": model.sharing_mode, "groups": model.shared_groups.all(), "users": existing},
            **kwargs,
        )
        field = self.fields["users"]
        field.queryset = get_user_model().objects.filter(Q(is_active=True) | Q(pk__in=existing))
        field.widget.model_id = model.pk
        if self.is_bound and self["mode"].value() != ShareAudience.SELECTED:
            self.fields["groups"].disabled = True
            field.disabled = True
        selected_ids = [pk for pk in (self["users"].value() or []) if str(pk).isdecimal()]
        field.widget.selected = []
        if selected_ids:
            selected = annotate_identity_labels(share_recipients()).filter(pk__in=selected_ids)
            labels = {person.pk: get_user_full_info(person) for person in selected}
            field.widget.selected = [
                {
                    "id": person.pk,
                    "label": labels.get(person.pk, get_user_full_info(person))
                    + ("" if person.is_active else "（账号已停用）"),
                }
                for person in field.queryset.filter(pk__in=selected_ids).order_by("last_name", "first_name", "pk")
            ]
