import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("has_options", [False, True])
def test_migrates_legacy_defaults_only_when_used_by_builtin_model(has_options):
    before = ("ai", "0008_provider_logo")
    after = ("ai", "0009_provider_catalog")
    executor = MigrationExecutor(connection)
    executor.migrate([before])
    try:
        apps = executor.loader.project_state([before]).apps
        providers = apps.get_model("ai", "AIProviderSettings")
        options = apps.get_model("ai", "AIModelOption")
        providers.objects.create(provider="deepseek", thinking="enabled", reasoning_effort="max")
        if has_options:
            options.objects.create(
                provider="deepseek", model_id="different-model", name="目录模型", is_default=True,
                parameter_presets={"thinking": "disabled"},
            )

        executor = MigrationExecutor(connection)
        executor.migrate([after])
        apps = executor.loader.project_state([after]).apps
        options = apps.get_model("ai", "AIModelOption")
        option = options.objects.get(provider="deepseek")
        assert option.is_default
        if has_options:
            assert option.model_id == "different-model"
            assert option.parameter_presets == {"thinking": "disabled"}
        else:
            assert option.model_id == "deepseek-flash"
            assert option.parameter_presets == {"thinking": "enabled", "reasoning_effort": "max"}
            assert option.supports_images and option.supports_json
    finally:
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
