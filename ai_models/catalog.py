from .models import AIModelOption, AIProviderSettings, ThinkingMode
from .providers import PROVIDERS


def provider_catalog():
    defaults = {entry.provider: entry for entry in AIProviderSettings.objects.all()}
    catalog = {}
    for provider, adapter in PROVIDERS.items():
        settings = defaults.get(provider)
        default_url = (settings and settings.default_base_url) or adapter.default_url
        catalog[provider] = {
            "default": default_url,
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
                entry["models"].append({"id": option.model_id, "label": option.name})
                if option.is_default:
                    entry["default_model"] = option.model_id

    for provider, adapter in PROVIDERS.items():
        entry = catalog[provider]
        if provider not in configured_providers:
            entry["models"].append({"id": adapter.default_model, "label": adapter.default_model})
            entry["default_model"] = adapter.default_model
    return catalog
