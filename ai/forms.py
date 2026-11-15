from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.urls import reverse

from accounts.services.users import annotate_identity_labels, get_user_full_info
from core.uploads import AI_PROVIDER_LOGO_UPLOAD_SPEC
from core.utils.forms import StyledFormMixin
from meetings.widgets import RecipientSelect

from .catalog import MAX_PROVIDER_ORDER, matching_option, provider_catalog
from .models import ReasoningEffort, ShareAudience, ThinkingMode
from .parameters import EFFORT_HELP, SAMPLING_PARAMETERS, THINKING_HELP
from .providers import ADAPTERS, PROVIDERS, adapter_protocol, provider_definition, validate_base_url, validate_model_id
from .services import share_recipients


class ThinkingForm(StyledFormMixin, forms.Form):
    thinking = forms.ChoiceField(label="思考模式", choices=ThinkingMode.choices, required=False, help_text=THINKING_HELP)
    reasoning_effort = forms.ChoiceField(
        label="思考强度", choices=ReasoningEffort.choices, required=False, initial=ReasoningEffort.HIGH,
        help_text=EFFORT_HELP,
    )


class AIModelForm(ThinkingForm):
    name = forms.CharField(label="模型名称", max_length=100, help_text="用于在 TMS 中识别这份模型配置。")
    provider = forms.ChoiceField(label="模型提供商")
    custom_provider_name = forms.CharField(
        label="自定义提供商名称", max_length=100, required=False, help_text="留空时显示为「自定义 API」。",
    )
    notes = forms.CharField(label="备注", max_length=2000, required=False, widget=forms.Textarea(attrs={"rows": 2}))
    base_url = forms.CharField(
        label="API 地址",
        max_length=300,
        required=False,
        widget=forms.URLInput(attrs={"aria-describedby": "ai-api-default"}),
    )
    model_choice = forms.ChoiceField(label="模型", required=False)
    model_id = forms.CharField(
        label="模型 ID", max_length=150, required=False,
        widget=forms.TextInput(attrs={
            "list": "ai-model-options", "autocomplete": "off", "required": True,
            "aria-describedby": "id_model_id_helptext ai-model-source",
        }),
        help_text="输入模型 ID，或从候选列表中选择。",
    )
    temperature = forms.FloatField(required=False, min_value=0, max_value=2)
    top_p = forms.FloatField(required=False, min_value=0, max_value=1)
    api_key = forms.RegexField(
        label="API Key",
        regex=r"\A[\x21-\x7e]+\Z",
        max_length=512,
        required=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        error_messages={"invalid": "API Key包含无效字符。"},
    )

    def __init__(self, *args, model=None, **kwargs):
        if model:
            kwargs["initial"] = {
                "name": model.name,
                "notes": model.notes,
                "provider": model.provider,
                "custom_provider_name": model.custom_provider_name,
                "base_url": model.base_url,
                "model_id": model.model_id,
                "thinking": model.thinking,
                "reasoning_effort": model.reasoning_effort,
                **model.request_parameters,
            }
        super().__init__(*args, **kwargs)
        for name, choices in (("thinking", ThinkingMode.choices), ("reasoning_effort", ReasoningEffort.choices)):
            self.fields[name].choices = [("", "使用接口默认值"), *choices]
        self.fields["reasoning_effort"].initial = ""
        configure_sampling_fields(self)
        self.catalog = provider_catalog()
        self.fields["provider"].choices = [
            (code, entry["label"]) for code, entry in self.catalog.items()
            if entry["enabled"] or (model and code == model.provider)
        ]
        if not model and not self.is_bound and self.fields["provider"].choices:
            self.initial["provider"] = self.fields["provider"].choices[0][0]
        self.preset_providers = [
            (code, self.catalog[code]) for code, _ in self.fields["provider"].choices if code != "custom"
        ]
        provider = self["provider"].value()
        entry = self.catalog.get(provider, {})
        self.entry = entry
        self.effective_default = model.base_url if model and model.provider == provider else entry.get("default", "")
        self.options = entry.get("models", []) if provider != "custom" else []
        self.fields["model_choice"].choices = [
            ("", ""), *((option["id"], option["label"]) for option in self.options),
        ]
        if not self.is_bound and not model:
            self.initial["base_url"] = self.effective_default
            self.initial["model_id"] = entry.get("default_model", "") if provider != "custom" else ""
        current_address = self["base_url"].value() or self.effective_default
        self.option = matching_option(entry, current_address, self["model_id"].value())
        self.presets = self.option["presets"] if self.option else {}
        self.advanced_presets = self.presets if self.option and not self.option.get("builtin") else {}
        self.sampling_fields = [
            (name, self[name], name in self.advanced_presets)
            for name in SAMPLING_PARAMETERS
        ]
        if not model:
            self.initial.update(self.presets)
        for name in (*SAMPLING_PARAMETERS, "thinking", "reasoning_effort"):
            if name not in self.advanced_presets:
                self.fields[name].widget.attrs["disabled"] = True

        self.fields["api_key"].label = "更换 API Key" if model else "API Key"
        self.fields["api_key"].help_text = (
            "提供商和 API 地址未变时，留空保留当前密钥。" if model else "密钥加密保存，之后仅显示遮罩。"
        )

    @property
    def advanced_errors(self):
        return any(self[name].errors for name in (*SAMPLING_PARAMETERS, "thinking", "reasoning_effort"))

    def clean_connection(self, data):
        provider = data.get("provider")
        if not provider or "base_url" not in data:
            return data
        submitted_url = data["base_url"]
        if provider == "custom" and not submitted_url:
            self.add_error("base_url", "请输入自定义接口的 API 地址。")
            return data
        shown_default = self.data.get("shown_default_base_url")
        if not submitted_url and shown_default and shown_default != self.effective_default:
            self.add_error("base_url", "默认 API 地址已更新，请核对当前地址后重新提交。")
            return data
        try:
            data["base_url"] = validate_base_url(provider, submitted_url or self.effective_default)
        except ValidationError as exc:
            self.add_error("base_url", exc)
        return data

    def clean(self):
        data = self.clean_connection(super().clean())
        if "base_url" not in data:
            return data
        if "model_choice" in data:
            if data["model_choice"] and data.get("model_id") and data["model_choice"] != data["model_id"]:
                self.add_error("model_id", "请清空手动输入的模型 ID，或切换为手动输入。")
            elif data["model_choice"]:
                data["model_id"] = data["model_choice"]
            elif not data.get("model_id") and not self.has_error("model_id"):
                self.add_error("model_id", "请选择模型或手动输入模型 ID。")
        if data.get("model_id"):
            try:
                validate_model_id(data["model_id"])
            except ValidationError as exc:
                self.add_error("model_id", exc)
        for name in ("thinking", "reasoning_effort"):
            if name not in self.data:
                data.pop(name, None)
        data["request_parameters"] = {
            name: data.get(name) for name in SAMPLING_PARAMETERS if name in self.data
        }
        return data


def configure_sampling_fields(form, *, preset=False):
    for name, (label, help_text, maximum) in SAMPLING_PARAMETERS.items():
        field = form.fields[name]
        field.label = f"{label}建议值" if preset else label
        field.help_text = help_text
        field.widget.attrs.update(min=0, max=maximum)


class ModelDiscoveryForm(AIModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields = {name: self.fields[name] for name in ("provider", "base_url", "api_key")}

    def clean(self):
        return self.clean_connection(self.cleaned_data)


class ProviderDefaultForm(StyledFormMixin, forms.Form):
    name = forms.CharField(label="提供商名称", max_length=100)
    display_order = forms.IntegerField(
        label="显示顺序", min_value=0, max_value=MAX_PROVIDER_ORDER, required=False,
        help_text="数字越小越靠前。相同序号按提供商名称排序。",
    )
    adapter = forms.ChoiceField(
        label="API 协议",
        choices=[("", "请选择 API 协议"), *((key, f"{adapter_protocol(key)}（{key}）") for key in ADAPTERS)],
        help_text="括号内为 LiteLLM 的 Provider Key。保存后不能更换协议。",
    )
    enabled = forms.BooleanField(label="启用提供商", required=False, initial=True)
    default_base_url = forms.CharField(label="默认 API 地址", max_length=300, required=False)
    logo = forms.ImageField(
        label="上传 Logo", required=False,
        widget=forms.FileInput(attrs=AI_PROVIDER_LOGO_UPLOAD_SPEC.widget_attrs()),
        validators=AI_PROVIDER_LOGO_UPLOAD_SPEC.validators(),
        help_text="支持 PNG 和 WebP，大小不超过 1 MB，宽高均不超过 2048 像素。建议使用透明背景的方形图片。",
    )
    remove_logo = forms.BooleanField(label="移除已上传的 Logo", required=False)

    def __init__(self, *args, provider=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.provider = provider
        self.definition = provider_definition(provider) if provider else None
        if provider:
            self.fields.pop("adapter")
        else:
            self.fields.pop("remove_logo")
        if provider in PROVIDERS:
            self.fields.pop("name")
        if provider == "custom":
            self.fields.pop("display_order")
            self.fields.pop("logo")
            self.fields.pop("remove_logo")
        if provider not in PROVIDERS:
            self.fields["default_base_url"].required = True
        if self.definition and self.definition.default_url:
            self.fields["default_base_url"].help_text = f"留空将使用 {self.definition.default_url}。"

    def clean(self):
        data = super().clean()
        adapter = self.definition or ADAPTERS.get(data.get("adapter"))
        if adapter and data.get("default_base_url"):
            try:
                data["default_base_url"] = validate_base_url(self.provider, data["default_base_url"], adapter=adapter)
            except ValidationError as exc:
                self.add_error("default_base_url", exc)
        if data.get("logo") and data.get("remove_logo"):
            self.add_error("logo", "上传新 Logo 时，请取消勾选「移除已上传的 Logo」。")
        return data

    def clean_logo(self):
        logo = self.cleaned_data["logo"]
        if logo:
            expected_extension = {"PNG": ".png", "WEBP": ".webp"}.get(logo.image.format)
            if not expected_extension or not logo.name.lower().endswith(expected_extension):
                raise ValidationError("请上传扩展名与实际格式一致的 PNG 或 WebP 图片。")
            if max(logo.image.size) > 2048:
                raise ValidationError("Logo 的宽和高均不能超过 2048 像素。")
        return logo

class ModelOptionForm(StyledFormMixin, forms.Form):
    supports_images = forms.BooleanField(label="支持图片输入", required=False)
    supports_json = forms.BooleanField(label="支持 JSON 输出模式", required=False)
    model_id = forms.CharField(label="模型 ID", max_length=150)
    name = forms.CharField(label="显示名称", max_length=100)
    is_active = forms.BooleanField(label="在模型选项中显示", initial=True, required=False)
    is_default = forms.BooleanField(
        label="设为默认模型", required=False, help_text="新建此提供商的模型配置时将优先选中这一项。"
    )
    show_temperature = forms.BooleanField(label="向用户展示采样温度", required=False)
    temperature = forms.FloatField(required=False, min_value=0, max_value=2)
    show_top_p = forms.BooleanField(label="向用户展示核采样范围", required=False)
    top_p = forms.FloatField(required=False, min_value=0, max_value=1)
    show_thinking = forms.BooleanField(label="支持设置思考模式", required=False)
    thinking = forms.ChoiceField(
        label="建议的思考模式", choices=[("", "未指定"), *ThinkingMode.choices],
        required=False, help_text=THINKING_HELP,
    )
    show_reasoning_effort = forms.BooleanField(label="支持设置思考强度", required=False)
    reasoning_effort = forms.ChoiceField(
        label="建议的思考强度", choices=[("", "未指定"), *ReasoningEffort.choices],
        required=False, help_text=EFFORT_HELP,
    )

    def __init__(self, *args, provider, option=None, **kwargs):
        if option:
            kwargs["initial"] = {
                "model_id": option.model_id,
                "name": option.name,
                "is_active": option.is_active,
                "is_default": option.is_default,
                "supports_images": option.supports_images,
                "supports_json": option.supports_json,
                **option.parameter_presets,
                **{f"show_{name}": True for name in option.parameter_presets},
            }
        super().__init__(*args, **kwargs)
        configure_sampling_fields(self, preset=True)
        if not provider_definition(provider).thinking:
            for name in ("thinking", "reasoning_effort"):
                self.fields.pop(name)
                self.fields.pop(f"show_{name}")

    def clean_model_id(self):
        return validate_model_id(self.cleaned_data["model_id"])

    def clean(self):
        data = super().clean()
        if data.get("is_default") and not data.get("is_active"):
            self.add_error("is_default", "请先勾选「在模型选项中显示」，再设为默认模型。")
        if data.get("show_reasoning_effort") and not data.get("show_thinking"):
            self.add_error("show_reasoning_effort", "请同时启用思考模式设置。")
        data["parameter_presets"] = {
            name: data.get(name) for name in (*SAMPLING_PARAMETERS, "thinking", "reasoning_effort")
            if data.get(f"show_{name}")
        }
        return data


class ShareRecipientSelect(RecipientSelect):
    model_id = None

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"].update(
            search_url=reverse("ai:share_recipients", args=[self.model_id]),
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
