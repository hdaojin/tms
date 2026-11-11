import json
from io import BytesIO
from unittest.mock import Mock
from urllib.error import HTTPError

import pytest
from cryptography.fernet import Fernet
from django.contrib.auth.models import Permission
from django.urls import reverse

from . import services
from .models import AIModel, AIModelOption, AIModelPreference, AIProviderSettings
from .providers import PROVIDERS, DeepSeekProvider, ProviderError, RejectRedirects

pytestmark = pytest.mark.django_db

API_KEY = "fake-test-key-39xy"
GATEWAY = "https://gateway.example.test/llm/v1"
MODEL_DATA = {
    "name": "测试模型",
    "provider": "deepseek",
    "base_url": "",
    "model_id": "deepseek-flash",
    "api_key": API_KEY,
}


@pytest.fixture(autouse=True)
def ai_settings(settings):
    settings.AI_MODEL_ENCRYPTION_KEY = Fernet.generate_key()


@pytest.fixture
def users(django_user_model):
    def create(name, *permissions):
        user = django_user_model.objects.create_user(name)
        user.user_permissions.set(
            Permission.objects.filter(content_type__app_label="ai_models", codename__in=permissions)
        )
        return user

    return {
        "owner": create("owner", "view_aimodel", "manage_own_aimodel"),
        "consumer": create("consumer", "view_aimodel", "use_shared_aimodel"),
        "other": create("other", "view_aimodel", "manage_own_aimodel"),
        "unassigned": create("unassigned"),
        "admin": django_user_model.objects.create_superuser("admin"),
    }


@pytest.fixture
def upstream(monkeypatch):
    adapter = Mock(spec=DeepSeekProvider)
    adapter.label = "DeepSeek"
    adapter.default_url = "https://api.deepseek.com"
    adapter.default_model = "deepseek-flash"
    adapter.test_payload.side_effect = DeepSeekProvider().test_payload
    adapter.test.return_value = "连接成功。"
    monkeypatch.setitem(PROVIDERS, "deepseek", adapter)
    return adapter


def url(name, model=None):
    return reverse(f"ai_models:{name}", args=[model.pk] if model else [])


def test_save_masks_secret_and_never_calls_provider(client, users, settings, upstream):
    client.force_login(users["owner"])
    response = client.post(url("create"), MODEL_DATA, follow=True)
    model = AIModel.objects.get()
    assert response.status_code == 200
    assert response.redirect_chain == [(url("detail", model), 302)]
    assert "fak••••39xy" in response.content.decode()
    assert API_KEY not in response.content.decode()
    assert API_KEY not in client.get(url("edit", model)).content.decode()
    assert bytes(model.encrypted_api_key) != API_KEY.encode()
    assert Fernet(settings.AI_MODEL_ENCRYPTION_KEY).decrypt(bytes(model.encrypted_api_key)) == API_KEY.encode()
    assert not model.is_shared
    assert not model.verified
    upstream.test.assert_not_called()


@pytest.mark.parametrize(
    "value",
    [
        "file:///etc/passwd",
        "https:///chat",
        "https://api.deepseek.com@host.example.test",
        "https://api.deepseek.com?key=other",
        "http://127.0.0.1:99999",
    ],
)
def test_rejects_invalid_base_urls(client, users, value):
    client.force_login(users["owner"])
    response = client.post(url("create"), {**MODEL_DATA, "base_url": value})
    assert "完整的 HTTP 或 HTTPS API 基址" in response.content.decode()
    assert API_KEY not in response.content.decode()
    assert not AIModel.objects.exists()


def test_without_deployment_key_save_fails_without_echoing_secret(client, users, settings):
    settings.AI_MODEL_ENCRYPTION_KEY = ""
    client.force_login(users["owner"])
    response = client.post(url("create"), MODEL_DATA)
    assert "未正确配置 AI 模型加密密钥" in response.content.decode()
    assert API_KEY not in response.content.decode()
    assert not AIModel.objects.exists()


def test_manual_test_requires_post_and_is_rate_limited(client, users, upstream):
    model = services.save_model(users["owner"], MODEL_DATA)
    client.force_login(users["owner"])
    assert client.get(url("test", model)).status_code == 405
    upstream.test.assert_not_called()
    response = client.post(url("test", model), follow=True)
    model.refresh_from_db()
    assert model.verified
    assert model.tested_at is not None
    assert model.test_duration_ms >= 0
    assert "测试成功" in response.content.decode()
    assert "固定短句" in response.content.decode()
    response = client.post(url("test", model), follow=True)
    assert "刚刚发起过测试" in response.content.decode()
    upstream.test.assert_called_once_with("https://api.deepseek.com", model.test_request, API_KEY)
    assert model.test_reply == "连接成功。"


def test_failure_is_recorded_without_verifying(client, users, upstream):
    model = services.save_model(users["owner"], MODEL_DATA)
    upstream.test.side_effect = ProviderError("API 账号余额不足。")
    client.force_login(users["owner"])
    response = client.post(url("test", model), follow=True)
    assert "API 账号余额不足" in response.content.decode()
    model.refresh_from_db()
    assert model.test_error == "API 账号余额不足。"
    assert model.tested_at and not model.verified


def test_changed_configuration_discards_in_flight_result(users, upstream):
    owner = users["owner"]
    model = services.save_model(owner, MODEL_DATA)

    def change_configuration(*args):
        services.save_model(owner, {**MODEL_DATA, "model_id": "custom-model", "api_key": ""}, model.pk)
        return "已过期的回复"

    upstream.test.side_effect = change_configuration
    with pytest.raises(services.ValidationError, match="测试期间配置已变更"):
        services.test_model(owner, model.pk)
    model.refresh_from_db()
    assert model.model_id == "custom-model"
    assert not model.verified and model.tested_at is None


def test_sharing_requires_current_test_and_changes_invalidate_it(client, users, upstream):
    owner = users["owner"]
    model = services.save_model(owner, MODEL_DATA)
    client.force_login(owner)
    response = client.post(url("share", model), {"is_shared": "on"}, follow=True)
    assert "请先手动测试当前配置" in response.content.decode()
    client.post(url("test", model))
    assert client.post(url("share", model), {"is_shared": "on"}).status_code == 302
    client.post(url("edit", model), {**MODEL_DATA, "name": "重命名", "api_key": ""})
    model.refresh_from_db()
    assert model.is_shared and model.verified and model.name == "重命名"
    response = client.post(url("edit", model), {**MODEL_DATA, "base_url": GATEWAY, "api_key": ""})
    assert "更换提供商、API 地址时，请输入 API 密钥" in response.content.decode()
    client.post(url("edit", model), {**MODEL_DATA, "base_url": GATEWAY, "api_key": "new-test-key"})
    model.refresh_from_db()
    assert model.base_url == GATEWAY
    assert not model.is_shared and not model.verified and model.tested_at is None
    upstream.test.assert_called_once()


@pytest.mark.parametrize("role", ["other", "consumer", "admin"])
def test_foreign_model_cannot_be_read_or_modified(client, users, upstream, role):
    model = services.save_model(users["owner"], MODEL_DATA)
    client.force_login(users[role])
    listing = client.get(url("list")).content.decode()
    assert model.name not in listing
    for action in ["detail", "edit", "delete"]:
        assert client.get(url(action, model)).status_code in {403, 404}
    for action in ["edit", "test", "share", "delete", "default", "delist"]:
        assert client.post(url(action, model), MODEL_DATA).status_code in {403, 404}
    assert AIModel.objects.filter(pk=model.pk).exists()
    upstream.test.assert_not_called()


def test_unassigned_user_has_no_access(client, users):
    client.force_login(users["unassigned"])
    assert client.get(url("list")).status_code == 403
    assert client.get(url("moderation")).status_code == 403


def test_public_default_moderation_and_restore(client, users, upstream):
    owner = users["owner"]
    model = services.save_model(owner, {**MODEL_DATA, "base_url": GATEWAY})
    services.test_model(owner, model.pk)
    services.set_shared(owner, model.pk, True)

    client.force_login(users["consumer"])
    response = client.get(url("list"))
    assert model.name in response.content.decode()
    assert GATEWAY not in response.content.decode()
    assert "••••39xy" not in response.content.decode()
    assert client.post(url("default", model)).status_code == 302
    assert AIModelPreference.objects.get(user=users["consumer"]).model_id == model.pk
    assert client.post(url("test", model)).status_code == 403
    assert client.post(url("delist", model)).status_code == 403

    client.force_login(users["admin"])
    response = client.get(url("moderation"))
    assert model.name in response.content.decode()
    assert GATEWAY not in response.content.decode()
    assert "••••39xy" not in response.content.decode()
    assert client.post(url("delist", model)).status_code == 302
    with pytest.raises(services.ValidationError, match="管理员已下架"):
        services.set_shared(owner, model.pk, True)
    assert client.post(url("restore", model)).status_code == 302
    model.refresh_from_db()
    assert not model.is_shared and not model.is_delisted

    client.force_login(users["consumer"])
    response = client.get(url("list"))
    assert model.name not in response.content.decode()
    assert "原默认模型已不可用" in response.content.decode()
    assert client.post(url("default", model)).status_code == 404


def test_stale_default_after_account_deactivation_and_deletion(client, users, upstream):
    owner, consumer = users["owner"], users["consumer"]
    model = services.save_model(owner, MODEL_DATA)
    services.test_model(owner, model.pk)
    services.set_shared(owner, model.pk, True)
    services.set_default_model(consumer, model.pk)
    client.force_login(consumer)

    owner.is_active = False
    owner.save(update_fields=["is_active"])
    assert "原默认模型已不可用" in client.get(url("list")).content.decode()
    assert client.post(url("default", model)).status_code == 404

    owner.is_active = True
    owner.save(update_fields=["is_active"])
    client.force_login(owner)
    assert client.post(url("delete", model)).status_code == 302
    assert AIModelPreference.objects.get(user=consumer).model is None
    client.force_login(consumer)
    assert "原默认模型已不可用" in client.get(url("list")).content.decode()


@pytest.mark.parametrize("address", ["http://127.0.0.1:8001/v1", "http://10.0.0.8/v1", GATEWAY])
def test_custom_address_can_be_tested_and_shared(client, users, upstream, address):
    owner = users["owner"]
    client.force_login(owner)
    assert client.post(url("create"), {**MODEL_DATA, "base_url": address}).status_code == 302
    model = AIModel.objects.get()
    services.test_model(owner, model.pk)
    services.set_shared(owner, model.pk, True)
    assert services.usable_models(users["consumer"]).filter(pk=model.pk).exists()
    upstream.test.assert_called_once_with(
        address, DeepSeekProvider().test_payload("deepseek-flash", "disabled", ""), API_KEY
    )


def test_deepseek_sends_only_a_bounded_fixed_test(monkeypatch):
    opener = Mock()
    opener.open.return_value = BytesIO(b'{"choices":[{"message":{"content":"ok"}}]}')
    monkeypatch.setattr("ai_models.providers.build_opener", lambda *handlers: opener)
    adapter = DeepSeekProvider()
    assert adapter.test(GATEWAY, adapter.test_payload("custom-id", "disabled", ""), API_KEY) == "ok"
    request = opener.open.call_args.args[0]
    assert request.full_url == f"{GATEWAY}/chat/completions"
    assert request.method == "POST"
    assert request.get_header("Authorization") == f"Bearer {API_KEY}"
    assert opener.open.call_args.kwargs["timeout"] == 10
    assert json.loads(request.data) == {
        "model": "custom-id",
        "messages": [{"role": "user", "content": "请回复：连接成功。"}],
        "max_tokens": 16,
        "thinking": {"type": "disabled"},
        "stream": False,
    }
    assert RejectRedirects().redirect_request(None, None, 307, "", {}, "https://unapproved.example") is None


@pytest.mark.parametrize(
    ("code", "message"), [(307, "意外状态"), (401, "认证失败"), (402, "余额不足"), (429, "请求频率")]
)
def test_provider_discards_upstream_error_body(monkeypatch, code, message):
    opener = Mock()
    opener.open.side_effect = HTTPError(GATEWAY, code, "", {}, BytesIO(API_KEY.encode()))
    monkeypatch.setattr("ai_models.providers.build_opener", lambda *handlers: opener)
    with pytest.raises(ProviderError, match=message) as caught:
        adapter = DeepSeekProvider()
        adapter.test(GATEWAY, adapter.test_payload("model", "disabled", ""), API_KEY)
    assert API_KEY not in str(caught.value)


def test_provider_catalog_management_is_superuser_only(client, users):
    client.force_login(users["owner"])
    provider_url = reverse("ai_models:provider", args=["deepseek"])
    create_url = reverse("ai_models:option_create", args=["deepseek"])
    assert client.get(url("providers")).status_code == 403
    assert client.post(provider_url, {"default_base_url": GATEWAY}).status_code == 403
    assert client.post(create_url, {"base_url": GATEWAY, "model_id": "other"}).status_code == 403
    assert not AIProviderSettings.objects.exists()
    assert not AIModelOption.objects.exists()


def test_provider_default_only_applies_to_new_models(client, users):
    owner = users["owner"]
    original = services.save_model(owner, MODEL_DATA)
    provider_url = reverse("ai_models:provider", args=["deepseek"])
    client.force_login(users["admin"])
    listing = client.get(url("providers"))
    assert listing.status_code == 200
    assert f'href="{provider_url}"' in listing.content.decode()
    assert "保存默认设置" not in listing.content.decode()
    assert client.get(provider_url).status_code == 200
    assert client.post(provider_url, {"default_base_url": "file:///etc/passwd"}).status_code == 200
    assert not AIProviderSettings.objects.exists()
    saved = client.post(
        provider_url, {"default_base_url": GATEWAY, "thinking": "enabled", "reasoning_effort": "max"}, follow=True
    )
    assert saved.redirect_chain == [(provider_url, 302)]
    assert saved.status_code == 200

    client.force_login(owner)
    assert f"留空将使用 {GATEWAY}" in client.get(url("create")).content.decode()
    edit_response = client.get(url("edit", original))
    assert "留空将使用 https://api.deepseek.com" in edit_response.content.decode()
    assert client.post(url("edit", original), {**MODEL_DATA, "api_key": ""}).status_code == 302
    original.refresh_from_db()
    assert original.base_url == "https://api.deepseek.com"
    assert original.thinking == "disabled"

    stale = client.post(url("create"), {**MODEL_DATA, "shown_default_base_url": "https://api.deepseek.com"})
    assert "默认 API 地址已更新" in stale.content.decode()
    assert API_KEY not in stale.content.decode()
    assert AIModel.objects.count() == 1
    assert client.post(url("create"), {**MODEL_DATA, "shown_default_base_url": GATEWAY}).status_code == 302
    new_model = AIModel.objects.exclude(pk=original.pk).get()
    assert (new_model.base_url, new_model.thinking, new_model.reasoning_effort) == (GATEWAY, "enabled", "max")


def test_catalog_is_provider_wide_and_manual_entry_remains_available(client, users):
    provider_url = reverse("ai_models:provider", args=["deepseek"])
    create_url = reverse("ai_models:option_create", args=["deepseek"])
    data = {"model_id": "gateway-model", "name": "网关模型", "is_active": "on", "is_default": "on"}
    client.force_login(users["admin"])
    assert client.post(provider_url, {"default_base_url": GATEWAY}).status_code == 302
    assert 'name="base_url"' not in client.get(create_url).content.decode()
    assert client.post(create_url, data).status_code == 302
    option = AIModelOption.objects.get()
    duplicate = client.post(create_url, data)
    assert "此提供商已有相同的模型 ID 在显示" in duplicate.content.decode()

    client.force_login(users["owner"])
    response = client.get(url("create"))
    assert '<option value="gateway-model" selected>网关模型</option>' in response.content.decode()
    selection = {**MODEL_DATA, "model_id": "", "model_choice": "gateway-model"}
    assert client.post(url("create"), {**selection, "base_url": "https://api.deepseek.com"}).status_code == 302
    saved_model = AIModel.objects.get()
    assert (saved_model.base_url, saved_model.model_id) == ("https://api.deepseek.com", "gateway-model")

    client.force_login(users["admin"])
    edit_url = reverse("ai_models:option_edit", args=["deepseek", option.pk])
    assert 'name="base_url"' not in client.get(edit_url).content.decode()
    assert client.post(edit_url, {"name": "隐藏模型", "model_id": "different"}).status_code == 302
    option.refresh_from_db()
    assert not option.is_active
    assert option.model_id == "different"

    client.force_login(users["owner"])
    assert 'value="gateway-model"' not in client.get(url("create")).content.decode()
    saved_model.refresh_from_db()
    assert saved_model.model_id == "gateway-model"
    assert client.post(url("create"), {**MODEL_DATA, "model_id": "gateway-model"}).status_code == 302


def test_empty_default_falls_back_to_official_address(client, users):
    AIProviderSettings.objects.create(provider="deepseek", default_base_url="")
    client.force_login(users["owner"])
    response = client.get(url("create"))
    assert "留空将使用 https://api.deepseek.com" in response.content.decode()
    assert GATEWAY not in response.content.decode()


def test_mask_updates_on_successful_manual_test_and_short_keys_show_only_mask(client, users, upstream):
    owner = users["owner"]
    model = services.save_model(owner, MODEL_DATA)
    AIModel.objects.filter(pk=model.pk).update(api_key_preview="••••39xy")
    client.force_login(owner)
    assert "fak••••39xy" not in client.get(url("detail", model)).content.decode()
    upstream.test.assert_not_called()
    assert client.post(url("test", model)).status_code == 302
    model.refresh_from_db()
    assert model.api_key_preview == "fak••••39xy"
    model = services.save_model(owner, {**MODEL_DATA, "api_key": "short-key"}, model.pk)
    assert model.api_key_preview == "••••"


def test_fallback_model_can_be_replaced_from_provider_page(client, users):
    provider_url = reverse("ai_models:provider", args=["deepseek"])
    fallback_url = reverse("ai_models:option_fallback", args=["deepseek"])
    client.force_login(users["admin"])
    assert f'href="{fallback_url}"' in client.get(provider_url).content.decode()
    assert 'value="deepseek-flash"' in client.get(fallback_url).content.decode()
    assert (
        client.post(
            fallback_url,
            {"model_id": "local", "name": "本地模型", "is_active": "on", "is_default": "on"},
            follow=True,
        ).status_code
        == 200
    )
    assert AIModelOption.objects.get(is_default=True).model_id == "local"
    assert "deepseek-flash" not in client.get(provider_url).content.decode()


def test_thinking_override_and_transcript_render_as_plain_text(client, users, upstream):
    owner = users["owner"]
    AIProviderSettings.objects.create(provider="deepseek", thinking="enabled", reasoning_effort="low")
    client.force_login(owner)
    assert (
        client.post(url("create"), {**MODEL_DATA, "thinking": "enabled", "reasoning_effort": "max"}).status_code == 302
    )
    model = AIModel.objects.get()
    assert (model.thinking, model.reasoning_effort) == ("enabled", "max")
    upstream.test.return_value = f"<script>reply</script> {API_KEY}"
    response = client.post(url("test", model), follow=True)
    model.refresh_from_db()
    assert model.test_request["thinking"] == {"type": "enabled"}
    assert model.test_request["reasoning_effort"] == "max"
    assert model.test_request["max_tokens"] == 2048
    assert model.test_reply == "<script>reply</script> [已隐藏]"
    page = response.content.decode()
    assert "发送内容" in page
    assert "请回复：连接成功。" in page
    assert "模型回复" in page
    assert "&lt;script&gt;reply&lt;/script&gt; [已隐藏]" in page
    assert API_KEY not in page

    services.set_shared(owner, model.pk, True)
    assert (
        client.post(
            url("edit", model), {**MODEL_DATA, "api_key": "", "thinking": "disabled", "reasoning_effort": "max"}
        ).status_code
        == 302
    )
    model.refresh_from_db()
    assert (model.thinking, model.reasoning_effort) == ("disabled", "")
    assert not model.is_shared and not model.verified
    assert not model.test_request and not model.test_reply


def test_provider_default_switches_atomically_and_appears_in_summary(client, users):
    client.force_login(users["admin"])
    create_url = reverse("ai_models:option_create", args=["deepseek"])
    first = {"model_id": "alpha", "name": "甲模型", "is_active": "on", "is_default": "on"}
    second = {**first, "model_id": "beta", "name": "乙模型"}
    assert client.post(create_url, first).status_code == 302
    assert client.post(create_url, second).status_code == 302
    rejected = client.post(create_url, {**first, "is_active": ""})
    assert "再设为默认模型" in rejected.content.decode()
    assert AIModelOption.objects.get(is_default=True).model_id == "beta"

    overview = client.get(url("providers")).content.decode()
    assert "默认 API 地址" in overview
    assert "https://api.deepseek.com" in overview
    assert "默认模型" in overview
    assert "beta" in overview
    assert "2 个" in overview

    client.force_login(users["owner"])
    create_page = client.get(url("create")).content.decode()
    assert '<option value="beta" selected>乙模型</option>' in create_page
    assert '<option value="alpha">甲模型</option>' in create_page
