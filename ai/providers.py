from dataclasses import dataclass, replace
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError


class ProviderError(Exception):
    """可以安全显示给用户的上游错误。"""


@dataclass(frozen=True)
class Provider:
    label: str
    route: str
    default_url: str = ""
    default_model: str = ""
    key_required: bool = True
    openai_client: bool = False
    thinking: bool = False
    model_list_path: str = ""


ADAPTERS = {
    "deepseek": Provider("", "deepseek", thinking=True, model_list_path="/models"),
    "openai": Provider("", "openai", openai_client=True, model_list_path="/models"),
    "anthropic": Provider("", "anthropic"),
    "gemini": Provider("", "gemini"),
    "openrouter": Provider("", "openrouter", model_list_path="/models"),
    "ollama_chat": Provider("", "ollama_chat", key_required=False, model_list_path="/api/tags"),
}


def builtin_provider(route, label, url="", model=""):
    return replace(ADAPTERS[route], label=label, default_url=url, default_model=model)


PROVIDERS = {
    "deepseek": builtin_provider("deepseek", "DeepSeek", "https://api.deepseek.com", "deepseek-flash"),
    "openai": builtin_provider("openai", "OpenAI", "https://api.openai.com/v1"),
    "anthropic": builtin_provider("anthropic", "Anthropic", "https://api.anthropic.com"),
    "gemini": builtin_provider("gemini", "Gemini", "https://generativelanguage.googleapis.com/v1beta"),
    "dashscope": builtin_provider("openai", "阿里云百炼 / 通义千问", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    "openrouter": builtin_provider("openrouter", "OpenRouter", "https://openrouter.ai/api/v1"),
    "ollama": builtin_provider("ollama_chat", "Ollama（自托管）"),
    "custom": builtin_provider("openai", "自定义（OpenAI 兼容）"),
}

PROTOCOL_LABELS = {
    "anthropic": "Anthropic Messages",
    "gemini": "Gemini API",
    "ollama_chat": "Ollama API",
}


def provider_definition(provider, settings=None):
    if provider in PROVIDERS:
        return PROVIDERS[provider]
    if settings is None:
        from .models import AIProviderSettings

        settings = AIProviderSettings.objects.filter(provider=provider).first()
    if settings and (adapter := ADAPTERS.get(settings.adapter)):
        return replace(adapter, label=settings.name)
    return None


def provider_names():
    from .models import AIProviderSettings

    names = {code: adapter.label for code, adapter in PROVIDERS.items()}
    registered = AIProviderSettings.objects.filter(adapter__in=ADAPTERS).order_by("name", "provider")
    for code, name in registered.values_list("provider", "name"):
        names.setdefault(code, name)
    return names


def provider_display_name(code, custom_name, names):
    if code == "custom":
        return custom_name or "自定义 API"
    return names.get(code, code)


def adapter_protocol(route):
    return PROTOCOL_LABELS.get(route, "OpenAI 兼容")


def protocol_label(provider):
    adapter = provider_definition(provider)
    return adapter_protocol(adapter.route) if adapter else "未知协议"


def supports_thinking(model):
    return supports_reasoning_parameter(model, "thinking")


BUILTIN_MODEL_PRESETS = {"thinking": "disabled", "reasoning_effort": "high"}


def supports_reasoning_parameter(model, parameter, *, adapter=None):
    from .catalog import matching_option, provider_catalog

    adapter = adapter or provider_definition(model.provider)
    if not adapter or not adapter.thinking:
        return False
    # Continue honoring explicitly saved settings on existing connections.
    if getattr(model, "thinking", "") == "enabled" and (
        parameter == "thinking" or getattr(model, "reasoning_effort", "")
    ):
        return True
    option = matching_option(provider_catalog(model.provider).get(model.provider, {}), model.base_url, model.model_id)
    return bool(option and parameter in option["presets"])


def supports_images(model):
    return capability(model, "supports_images")


def capability(model, field):
    from .catalog import matching_option, provider_catalog

    entry = provider_catalog(model.provider).get(model.provider, {})
    option = matching_option(entry, model.base_url, model.model_id)
    return bool(option and option[{"supports_images": "images", "supports_json": "json"}[field]])


def trusted_addresses(adapter, default_url):
    return {url.rstrip("/") for url in (adapter.default_url, default_url) if url}


def validate_model_id(value):
    if not value or any(char.isspace() or ord(char) < 32 for char in value) or any(
        char in value for char in ("?", "#", "\\", "%")
    ) or any(part in {"", ".", ".."} for part in value.split("/")):
        raise ValidationError("请输入有效的模型 ID。")
    return value


def validate_base_url(provider: str, value: str, *, adapter=None) -> str:
    adapter = adapter or provider_definition(provider)
    if adapter is None:
        raise ValidationError("请选择已支持的模型提供商。")
    if provider == "custom" and not value:
        raise ValidationError("请输入自定义接口的 API 地址。")
    value = value.rstrip("/") if value else adapter.default_url
    try:
        parts = urlsplit(value)
        valid = (
            parts.scheme in {"http", "https"}
            and parts.hostname
            and parts.username is None
            and parts.password is None
            and "@" not in parts.netloc
            and not any(char.isspace() or ord(char) < 32 for char in value)
            and not any(char in value for char in "?#\\")
            and (parts.port is None or 1 <= parts.port <= 65535)
        )
    except ValueError:
        valid = False
    if not valid:
        raise ValidationError("请输入完整的 HTTP 或 HTTPS API 基址，地址应省略用户名、密码、查询参数和片段。")
    return value
