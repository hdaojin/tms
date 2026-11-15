from .models import AIModelOption, AIProviderSettings, ThinkingMode
from .providers import PROVIDERS, protocol_label, trusted_addresses

PROVIDER_LOGOS = {
    "deepseek": "icon-[simple-icons--deepseek]",
    "openai": "icon-[simple-icons--openai]",
    "anthropic": "icon-[simple-icons--anthropic]",
    "gemini": "icon-[simple-icons--googlegemini]",
    "dashscope": "icon-[simple-icons--qwen]",
    "openrouter": "icon-[simple-icons--openrouter]",
    "ollama": "icon-[simple-icons--ollama]",
}


def provider_branding(provider, settings):
    return {
        "logo_icon": PROVIDER_LOGOS.get(provider, ""),
        "logo_url": settings.logo.url if settings and settings.logo else "",
        "protocol": protocol_label(provider),
    }


def provider_catalog():
    defaults = {entry.provider: entry for entry in AIProviderSettings.objects.all()}
    catalog = {}
    for provider, adapter in PROVIDERS.items():
        settings = defaults.get(provider)
        default_url = (settings and settings.default_base_url) or adapter.default_url
        catalog[provider] = {
            "label": adapter.label,
            "default": default_url,
            "official": adapter.default_url,
            "trusted": sorted(trusted_addresses(provider, default_url)),
            "enabled": settings.enabled if settings else True,
            **provider_branding(provider, settings),
            "key_required": adapter.key_required,
            "discovery": bool(adapter.model_list_path),
            "thinking": settings.thinking if settings else ThinkingMode.DISABLED,
            "reasoning_effort": settings.reasoning_effort if settings else "",
            "models": [],
            "default_model": "",
        }

    configured_providers = set()
    for option in AIModelOption.objects.all():
        entry = catalog.get(option.provider)
        if entry:
            configured_providers.add(option.provider)
            if option.is_active:
                entry["models"].append({
                    "id": option.model_id,
                    "label": option.name,
                    "images": option.supports_images,
                    "json": option.supports_json,
                    "presets": option.parameter_presets,
                })
                if option.is_default:
                    entry["default_model"] = option.model_id

    for provider, adapter in PROVIDERS.items():
        entry = catalog[provider]
        if adapter.default_model and provider not in configured_providers:
            entry["models"].append({
                "id": adapter.default_model,
                "label": adapter.default_model,
                "images": provider == "deepseek",
                "json": provider == "deepseek",
                "builtin": True,
                "presets": {
                    "thinking": entry["thinking"],
                    "reasoning_effort": entry["reasoning_effort"] or "high",
                } if adapter.thinking else {},
            })
            entry["default_model"] = adapter.default_model
    return catalog


def matching_option(entry, base_url, model_id):
    if base_url.rstrip("/") in entry.get("trusted", ()):
        return next((option for option in entry["models"] if option["id"] == model_id), None)
    return None
