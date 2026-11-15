from .models import AIModelOption, AIProviderSettings
from .providers import BUILTIN_MODEL_PRESETS, PROVIDERS, adapter_protocol, provider_definition, trusted_addresses

PRESET_PROVIDER_ORDER = {
    "deepseek": 10,
    "xiaomi_mimo": 20,
    "dashscope": 30,
    "doubao": 40,
    "zhipu": 50,
    "minimax": 60,
    "kimi": 70,
    "openai": 80,
    "anthropic": 90,
    "gemini": 100,
    "openrouter": 110,
    "ollama": 120,
}
OTHER_PROVIDER_ORDER = 130
MAX_PROVIDER_ORDER = 2147483647


def provider_display_order(provider, settings):
    if provider == "custom":
        return None
    if settings and settings.display_order is not None:
        return settings.display_order
    return PRESET_PROVIDER_ORDER.get(provider, OTHER_PROVIDER_ORDER)

PROVIDER_LOGOS = {
    "deepseek": "icon-[simple-icons--deepseek]",
    "openai": "icon-[simple-icons--openai]",
    "anthropic": "icon-[simple-icons--anthropic]",
    "gemini": "icon-[simple-icons--googlegemini]",
    "dashscope": "icon-[simple-icons--qwen]",
    "openrouter": "icon-[simple-icons--openrouter]",
    "ollama": "icon-[simple-icons--ollama]",
    "zhipu": "icon-[thesvg--zhipu]",
    "xiaomi_mimo": "icon-[thesvg--xiaomi-mimo]",
    "doubao": "icon-[thesvg--doubao]",
    "kimi": "icon-[simple-icons--kimi]",
    "minimax": "icon-[simple-icons--minimax]",
    "custom": "icon-[tabler--plug]",
}


def provider_logo(provider, settings):
    return {
        "logo_icon": PROVIDER_LOGOS.get(provider, ""),
        "logo_url": settings.logo.url if settings and settings.logo else "",
    }


def provider_logos(codes):
    settings = {
        row.provider: row for row in AIProviderSettings.objects.filter(provider__in=codes).only("provider", "logo")
    }
    return {code: provider_logo(code, settings.get(code)) for code in codes}


def provider_branding(provider, settings, adapter):
    return {**provider_logo(provider, settings), "protocol": adapter_protocol(adapter.route)}


def provider_catalog(code=None):
    settings_rows = AIProviderSettings.objects.order_by("name", "provider")
    options = AIModelOption.objects.all()
    if code is not None:
        settings_rows = settings_rows.filter(provider=code)
        options = options.filter(provider=code)
    defaults = {entry.provider: entry for entry in settings_rows}
    entries = {key: definition for key, definition in PROVIDERS.items() if code is None or key == code}
    for provider, settings in defaults.items():
        if provider not in entries and (adapter := provider_definition(provider, settings)):
            entries[provider] = adapter
    catalog = {}
    for provider, adapter in entries.items():
        settings = defaults.get(provider)
        default_url = (settings and settings.default_base_url) or adapter.default_url
        catalog[provider] = {
            "label": adapter.label,
            "display_order": provider_display_order(provider, settings),
            "default": default_url,
            "official": adapter.default_url,
            "trusted": sorted(trusted_addresses(adapter, default_url)),
            "enabled": settings.enabled if settings else True,
            **provider_branding(provider, settings, adapter),
            "provider_key": adapter.route,
            "key_required": adapter.key_required,
            "discovery": bool(adapter.model_list_path),
            "models": [],
            "default_model": "",
        }

    configured_providers = set()
    for option in options:
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
                    entry["default_model_label"] = option.name

    for provider, adapter in entries.items():
        entry = catalog[provider]
        if adapter.default_model and provider not in configured_providers:
            entry["models"].append({
                "id": adapter.default_model,
                "label": adapter.default_model,
                "images": provider == "deepseek",
                "json": provider == "deepseek",
                "builtin": True,
                "presets": BUILTIN_MODEL_PRESETS if adapter.thinking else {},
            })
            entry["default_model"] = adapter.default_model
            entry["default_model_label"] = adapter.default_model
    return dict(sorted(catalog.items(), key=provider_sort_key))


def provider_sort_key(item):
    code, entry = item
    return code == "custom", entry["display_order"] or 0, entry["label"], code


def next_provider_display_order():
    highest = max(
        (entry["display_order"] for entry in provider_catalog().values() if entry["display_order"] is not None),
        default=0,
    )
    return min(highest + 10, MAX_PROVIDER_ORDER)


def matching_option(entry, base_url, model_id):
    if base_url.rstrip("/") in entry.get("trusted", ()):
        return next((option for option in entry["models"] if option["id"] == model_id), None)
    return None
