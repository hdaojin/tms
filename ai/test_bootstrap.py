import pytest

from core.bootstrap_engine import apply_bootstrap_plan, build_bootstrap_plan

from .catalog import provider_catalog
from .models import AIModelOption, AIProviderSettings


@pytest.mark.django_db
def test_bootstrap_makes_presets_available_and_preserves_admin_choices():
    AIProviderSettings.objects.create(
        provider="dashscope", enabled=False, default_base_url="https://qwen.example.com/v1"
    )
    AIModelOption.objects.create(provider="dashscope", model_id="qwen3.8-max", name="管理员的 Qwen", is_default=True)

    plan = build_bootstrap_plan()
    assert not plan.has_errors
    assert not AIProviderSettings.objects.filter(provider="zhipu").exists()
    apply_bootstrap_plan(plan)

    expected_models = {
        "dashscope": {"qwen3.8-flash", "qwen3.8-max"},
        "zhipu": {"glm-5.3"},
        "xiaomi_mimo": {"mimo-v2.6-flash", "mimo-v2.6-pro", "mimo-v2.6-pro-ultraspeed"},
        "doubao": {"doubao-seed-2-1-lite-260915", "doubao-seed-2-1-pro-260915"},
        "kimi": {"kimi-k3.1-pro"},
        "minimax": {"MiniMax-M3.1-Flash", "MiniMax-M3"},
    }
    catalog = provider_catalog()
    for provider, model_ids in expected_models.items():
        entry = catalog[provider]
        assert entry["provider_key"] == "openai"
        assert {option["id"] for option in entry["models"]} == model_ids
        if provider != "dashscope":
            assert entry["enabled"]
            assert entry["default_model"] == ""

    qwen = catalog["dashscope"]
    assert not qwen["enabled"]
    assert qwen["default"] == "https://qwen.example.com/v1"
    assert qwen["default_model_label"] == "管理员的 Qwen"

    AIProviderSettings.objects.filter(provider="kimi").update(name="内部 Kimi", enabled=False)
    subsequent_plan = build_bootstrap_plan()
    assert not subsequent_plan.has_errors
    assert not subsequent_plan.has_changes
    assert provider_catalog("kimi")["kimi"]["label"] == "内部 Kimi"
