from dataclasses import dataclass
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


PROVIDERS = {
    "deepseek": Provider("DeepSeek", "deepseek", "https://api.deepseek.com", "deepseek-flash", thinking=True, model_list_path="/models"),
    "openai": Provider("OpenAI", "openai", "https://api.openai.com/v1", openai_client=True, model_list_path="/models"),
    "anthropic": Provider("Anthropic", "anthropic", "https://api.anthropic.com"),
    "gemini": Provider("Gemini", "gemini", "https://generativelanguage.googleapis.com/v1beta"),
    "dashscope": Provider("阿里云百炼 / 通义千问", "openai", "https://dashscope.aliyuncs.com/compatible-mode/v1", openai_client=True, model_list_path="/models"),
    "openrouter": Provider("OpenRouter", "openrouter", "https://openrouter.ai/api/v1", model_list_path="/models"),
    "ollama": Provider("Ollama（自托管）", "ollama_chat", key_required=False, model_list_path="/api/tags"),
    "custom": Provider("自定义（OpenAI 兼容）", "openai", openai_client=True, model_list_path="/models"),
}


def supports_thinking(model):
    provider = PROVIDERS.get(model.provider)
    return bool(provider and provider.thinking)


def supports_images(model):
    # An ID alone does not establish that a gateway implements image input.
    provider = PROVIDERS.get(model.provider)
    if provider is None:
        return False
    return (
        model.provider == "deepseek" and model.base_url == provider.default_url and model.model_id == provider.default_model
    ) or capability(model, "supports_images")


def capability(model, field):
    from .models import AIModelOption, AIProviderSettings

    provider = PROVIDERS[model.provider]
    trusted_url = AIProviderSettings.objects.filter(provider=model.provider).values_list("default_base_url", flat=True).first()
    return model.base_url in {provider.default_url, trusted_url} and AIModelOption.objects.filter(
        provider=model.provider, model_id=model.model_id, is_active=True, **{field: True}
    ).exists()


def validate_model_id(value):
    if not value or any(char.isspace() or ord(char) < 32 for char in value) or any(
        char in value for char in ("?", "#", "\\", "%")
    ) or any(part in {"", ".", ".."} for part in value.split("/")):
        raise ValidationError("请输入有效的模型 ID。")
    return value


def validate_base_url(provider: str, value: str) -> str:
    adapter = PROVIDERS.get(provider)
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
