from io import BytesIO
from unittest.mock import Mock

import httpx
import pytest
from cryptography.fernet import Fernet
from django.contrib.auth.models import Group, Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from . import services
from .models import AIModel, AIModelOption, AIModelPreference, AIProviderSettings, ShareAudience
from .providers import ProviderError, supports_images, supports_thinking

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
            Permission.objects.filter(content_type__app_label="ai", codename__in=permissions)
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
    adapter = Mock()
    adapter.test.return_value = "连接成功。"
    monkeypatch.setattr(services, "invoke", adapter.test)
    return adapter


def url(name, model=None):
    return reverse(f"ai:{name}", args=[model.pk] if model else [])


def test_provider_logo_upload_replacement_and_reset(client, users, settings, tmp_path, django_capture_on_commit_callbacks):
    settings.MEDIA_ROOT = tmp_path
    provider_url = reverse("ai:provider", args=["deepseek"])

    def logo(extension, image_format):
        buffer = BytesIO()
        Image.new("RGBA", (32, 32), "blue").save(buffer, format=image_format)
        return SimpleUploadedFile(f"logo.{extension}", buffer.getvalue())

    client.force_login(users["owner"])
    assert client.post(provider_url, {"logo": logo("png", "PNG")}).status_code == 403
    create_page = client.get(url("create")).content.decode()
    assert "icon-[simple-icons--deepseek]" in create_page
    assert "OpenAI 兼容" in create_page

    client.force_login(users["admin"])
    assert client.post(provider_url, {"logo": logo("webp", "PNG")}).status_code == 200
    assert not AIProviderSettings.objects.exists()
    assert client.post(provider_url, {"logo": logo("png", "PNG")}).status_code == 302
    provider = AIProviderSettings.objects.get(provider="deepseek")
    original = provider.logo.name
    assert provider.logo.storage.exists(original)
    client.force_login(users["owner"])
    assert provider.logo.url in client.get(url("create")).content.decode()
    client.force_login(users["admin"])

    with django_capture_on_commit_callbacks(execute=True):
        assert client.post(provider_url, {"logo": logo("webp", "WEBP")}).status_code == 302
    provider.refresh_from_db()
    assert provider.logo.name.endswith(".webp")
    assert not provider.logo.storage.exists(original)

    replacement = provider.logo.name
    assert client.post(provider_url, {}).status_code == 302
    provider.refresh_from_db()
    assert provider.logo.name == replacement
    with django_capture_on_commit_callbacks(execute=True):
        assert client.post(provider_url, {"remove_logo": "on"}).status_code == 302
    provider.refresh_from_db()
    assert not provider.logo and not provider.logo.storage.exists(replacement)
    client.force_login(users["owner"])
    assert "icon-[simple-icons--deepseek]" in client.get(url("create")).content.decode()


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
    assert upstream.test.call_args.args[0].base_url == "https://api.deepseek.com"
    assert upstream.test.call_args.args[2] == API_KEY
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
    response = client.post(url("share", model), {"mode": "all"}, follow=True)
    assert "请先手动测试当前配置" in response.content.decode()
    client.post(url("test", model))
    assert client.post(url("share", model), {"mode": "all"}).status_code == 302
    client.post(url("edit", model), {**MODEL_DATA, "name": "重命名", "api_key": ""})
    model.refresh_from_db()
    assert model.is_shared and model.verified and model.name == "重命名"
    response = client.post(url("edit", model), {**MODEL_DATA, "base_url": GATEWAY, "api_key": ""})
    assert "更换提供商、API 地址时，请输入 API Key" in response.content.decode()
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


def test_targeted_sharing_requires_permission_and_live_membership(client, users, upstream):
    owner, consumer, pending, admin = (users[key] for key in ("owner", "consumer", "unassigned", "admin"))
    pending.first_name = "待授权用户"
    pending.save(update_fields=["first_name"])
    role = Group.objects.create(name="模型试用组")
    consumer.groups.add(role)
    model = services.save_model(owner, MODEL_DATA)
    services.test_model(owner, model.pk)

    client.force_login(owner)
    response = client.post(url("share", model), {"mode": "selected"})
    assert "请至少选择一个指定用户或角色" in response.content.decode()
    assert not AIModel.objects.get(pk=model.pk).is_shared
    assert client.post(
        url("share", model), {"mode": "selected", "users": [pending.pk], "groups": [role.pk]}
    ).status_code == 302
    assert not services.usable_models(pending).exists()
    assert not services.usable_models(admin).exists()

    client.force_login(consumer)
    listing = client.get(url("list")).content.decode()
    assert model.name in listing
    assert role.name not in listing
    assert client.post(url("default", model)).status_code == 302
    consumer.groups.remove(role)
    assert "原默认模型已不可用" in client.get(url("list")).content.decode()
    assert client.post(url("default", model)).status_code == 404
    with pytest.raises(services.ValidationError, match="已不可用"):
        services.generate_text(consumer, model.pk, model.revision, {})
    upstream.generate.assert_not_called()

    pending.user_permissions.set(consumer.user_permissions.all())
    client.force_login(pending)
    assert model.name in client.get(url("list")).content.decode()
    role.delete()
    assert model.name in client.get(url("list")).content.decode()
    client.force_login(admin)
    assert model.name in client.get(url("moderation")).content.decode()
    assert client.get(url("detail", model)).status_code == 404
    pending.delete()
    model.refresh_from_db()
    assert model.is_shared and model.share_audience == ShareAudience.SELECTED
    assert not services.shared_models(consumer).exists()


def test_sharing_scope_switches_and_pauses_preserve_recipients(client, users, upstream):
    owner, consumer, admin = users["owner"], users["consumer"], users["admin"]
    consumer.first_name = "指定接收者"
    consumer.save(update_fields=["first_name"])
    model = services.save_model(owner, MODEL_DATA)
    services.test_model(owner, model.pk)
    role = Group.objects.create(name="空角色")
    selection = {"mode": "selected", "users": [consumer.pk], "groups": [role.pk]}
    client.force_login(owner)
    assert client.post(url("share", model), selection).status_code == 302
    for mode in ("all", "private"):
        assert client.post(url("share", model), {"mode": mode}).status_code == 302
        assert list(model.shared_users.all()) == [consumer]
        assert list(model.shared_groups.all()) == [role]
    assert not services.usable_models(consumer).exists()
    assert client.post(url("share", model), selection).status_code == 302
    services.moderate_model(admin, model.pk, True)
    services.moderate_model(admin, model.pk, False)
    assert not services.usable_models(consumer).exists()
    assert client.post(url("share", model), selection).status_code == 302
    services.save_model(owner, {**MODEL_DATA, "api_key": "", "model_id": "changed"}, model.pk)
    model.refresh_from_db()
    assert not model.is_shared and model.share_audience == ShareAudience.SELECTED
    assert list(model.shared_users.all()) == [consumer]
    assert list(model.shared_groups.all()) == [role]


def test_share_recipient_search_and_save_check_identity(client, users, upstream, django_user_model):
    owner = users["owner"]
    person = django_user_model.objects.create_user("hidden-login", last_name="张", first_name="三")
    django_user_model.objects.create_user("duplicate-login", last_name="张", first_name="三")
    model = services.save_model(owner, MODEL_DATA)
    services.test_model(owner, model.pk)
    client.force_login(users["other"])
    assert client.get(url("share_recipients", model), {"q": "zs"}).status_code == 404
    client.force_login(owner)
    response = client.get(url("share_recipients", model), {"q": "zs"})
    assert {"id": person.pk, "label": "张三", "invalid": True} in response.json()["results"]
    assert "hidden-login" not in response.content.decode()
    response = client.post(url("share", model), {"mode": "selected", "users": [person.pk]})
    assert "同名人员的区分备注未填写或重复" in response.content.decode()
    assert not model.shared_users.exists()


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
    assert upstream.test.call_args.args[0].base_url == address

def test_provider_catalog_management_is_superuser_only(client, users):
    client.force_login(users["owner"])
    provider_url = reverse("ai:provider", args=["deepseek"])
    create_url = reverse("ai:option_create", args=["deepseek"])
    assert client.get(url("providers")).status_code == 403
    assert client.get(url("provider_create")).status_code == 403
    assert client.post(url("provider_create"), {}).status_code == 403
    assert client.post(provider_url, {"default_base_url": GATEWAY}).status_code == 403
    assert client.post(create_url, {"base_url": GATEWAY, "model_id": "other"}).status_code == 403
    assert not AIProviderSettings.objects.exists()
    assert not AIModelOption.objects.exists()


def test_provider_display_order_is_shared_by_admin_list_and_model_picker(client, users):
    AIProviderSettings.objects.create(
        provider="xiaomi_mimo", name="小米 MiMo", adapter="openai", default_base_url=GATEWAY,
    )
    client.force_login(users["admin"])
    table = client.get(url("providers")).context["table"]
    assert [row.record["code"] for row in table.rows][:3] == ["deepseek", "xiaomi_mimo", "dashscope"]
    detail = reverse("ai:provider", args=["dashscope"])
    assert client.post(detail, {"display_order": "0", "enabled": "on"}).status_code == 302
    table = client.get(url("providers")).context["table"]
    assert [row.record["code"] for row in table.rows][:3] == ["dashscope", "deepseek", "xiaomi_mimo"]

    client.force_login(users["owner"])
    form = client.get(url("create")).context["form"]
    assert [code for code, _entry in form.preset_providers][:3] == ["dashscope", "deepseek", "xiaomi_mimo"]
    assert "custom" not in dict(form.preset_providers)


def test_registered_provider_can_be_configured_discovered_and_used(client, users, monkeypatch):
    client.force_login(users["admin"])
    data = {"name": "校内模型网关", "adapter": "openai", "default_base_url": GATEWAY, "enabled": "on"}
    assert client.post(url("provider_create"), {**data, "adapter": "unknown"}).status_code == 200
    assert not AIProviderSettings.objects.exists()
    created = client.post(url("provider_create"), data)
    registered = AIProviderSettings.objects.get()
    provider = registered.provider
    detail = reverse("ai:provider", args=[provider])
    assert created.url == detail
    headers = [column.header for column in client.get(url("providers")).context["table"].columns]
    assert headers == ["显示顺序", "提供商", "Provider Key", "API 协议", "默认 API 地址", "默认模型", "可选模型（数量）", "状态"]
    assert registered.display_order > 120
    assert 'name="thinking"' not in client.get(detail).content.decode()
    assert client.post(detail, {**data, "adapter": "gemini"}).status_code == 302
    registered.refresh_from_db()
    assert registered.adapter == "openai"

    option_create = reverse("ai:option_create", args=[provider])
    assert client.post(option_create, {
        "name": "网关视觉模型", "model_id": "vendor/vision", "supports_images": "on",
        "is_active": "on", "is_default": "on",
    }).status_code == 302
    option = AIModelOption.objects.get()
    option_edit = reverse("ai:option_edit", args=[provider, option.pk])
    assert "openai/vendor/vision" in client.get(option_edit).content.decode()

    def send(transport, request):
        assert request.headers["authorization"] == f"Bearer {API_KEY}"
        if request.method == "GET":
            assert str(request.url) == f"{GATEWAY}/models"
            return httpx.Response(200, json={"data": [{"id": "vendor/vision"}]})
        assert str(request.url) == f"{GATEWAY}/chat/completions"
        assert b'"model":"vendor/vision"' in request.content
        return httpx.Response(200, json={
            "id": "test", "model": "vendor/vision", "object": "chat.completion", "created": 0,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "连接成功"}, "finish_reason": "stop"}],
        })

    monkeypatch.setattr("ai.llm.transport.ProviderTransport.handle_request", send)
    owner = users["owner"]
    client.force_login(owner)
    discover = client.post(url("discover"), {**MODEL_DATA, "provider": provider})
    assert discover.status_code == 200
    assert "vendor/vision" in discover.content.decode()
    assert client.post(url("create"), {**MODEL_DATA, "provider": provider, "model_id": option.model_id}).status_code == 302
    model = AIModel.objects.get()
    assert model.base_url == GATEWAY
    assert supports_images(model)
    assert not supports_thinking(model)
    services.test_model(owner, model.pk)
    assert services.usable_models(owner).filter(pk=model.pk).exists()
    listing = client.get(url("list"), {"provider": provider, "q": "校内模型网关"}).content.decode()
    assert model.name in listing and "校内模型网关" in listing

    client.force_login(users["admin"])
    assert client.post(detail, {**data, "enabled_present": "1", "enabled": ""}).status_code == 302
    assert not services.usable_models(owner).filter(pk=model.pk).exists()
    assert client.post(detail, data).status_code == 302
    assert services.usable_models(owner).filter(pk=model.pk).exists()


def test_reasoning_presets_do_not_apply_to_other_models_or_addresses(users):
    owner = users["owner"]
    flash = services.save_model(owner, MODEL_DATA)
    other = services.save_model(owner, {**MODEL_DATA, "model_id": "another-model"})
    alternate = services.save_model(owner, {**MODEL_DATA, "base_url": GATEWAY})
    assert supports_thinking(flash)
    assert not supports_thinking(other)
    assert not supports_thinking(alternate)


def test_provider_default_only_applies_to_new_models(client, users):
    owner = users["owner"]
    original = services.save_model(owner, MODEL_DATA)
    provider_url = reverse("ai:provider", args=["deepseek"])
    client.force_login(users["admin"])
    listing = client.get(url("providers"))
    assert listing.status_code == 200
    assert f'href="{provider_url}"' in listing.content.decode()
    assert "保存默认设置" not in listing.content.decode()
    assert client.get(provider_url).status_code == 200
    assert client.post(provider_url, {"default_base_url": "file:///etc/passwd"}).status_code == 200
    assert not AIProviderSettings.objects.exists()
    saved = client.post(
        provider_url, {"default_base_url": GATEWAY}, follow=True
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
    assert (new_model.base_url, new_model.thinking, new_model.reasoning_effort) == (GATEWAY, "disabled", "")


def test_catalog_is_provider_wide_and_manual_entry_remains_available(client, users):
    provider_url = reverse("ai:provider", args=["deepseek"])
    create_url = reverse("ai:option_create", args=["deepseek"])
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
    assert '<option value="gateway-model">网关模型 · 系统预设</option>' in response.content.decode()
    assert response.context["form"]["model_id"].value() == "gateway-model"
    selection = {**MODEL_DATA, "model_id": "gateway-model"}
    assert client.post(url("create"), {**selection, "base_url": "https://api.deepseek.com"}).status_code == 302
    saved_model = AIModel.objects.get()
    assert (saved_model.base_url, saved_model.model_id) == ("https://api.deepseek.com", "gateway-model")

    client.force_login(users["admin"])
    edit_url = reverse("ai:option_edit", args=["deepseek", option.pk])
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
    provider_url = reverse("ai:provider", args=["deepseek"])
    fallback_url = reverse("ai:option_fallback", args=["deepseek"])
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
    AIModelOption.objects.create(
        provider="deepseek", model_id="deepseek-flash", name="Flash",
        parameter_presets={"thinking": "enabled", "reasoning_effort": "low"},
    )
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
    create_url = reverse("ai:option_create", args=["deepseek"])
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
    create_page = client.get(url("create"))
    assert create_page.context["form"]["model_id"].value() == "beta"
    assert '<option value="alpha">甲模型 · 系统预设</option>' in create_page.content.decode()


def test_model_list_filters_and_test_fragment(client, users, upstream):
    owner = users["owner"]
    model = services.save_model(owner, MODEL_DATA)
    services.save_model(owner, {**MODEL_DATA, "name": "另一模型"})
    client.force_login(owner)
    listing = client.get(url("list"), {"q": model.name, "scope": "own", "verified": "no"}).content.decode()
    assert model.name in listing
    assert "另一模型" not in listing
    assert 'class="table w-full"' in listing
    assert 'name="scope"' in listing
    assert 'value="own" selected' in listing

    partial = client.get(url("list"), {"q": model.name, "scope": "own", "verified": "no"},
                         headers={"HX-Request": "true"}).content.decode()
    assert model.name in partial
    assert "另一模型" not in partial
    assert 'class="table w-full"' in partial
    assert 'name="scope"' not in partial

    response = client.post(url("test", model), headers={"HX-Request": "true"})
    assert response.status_code == 200
    content = response.content.decode()
    assert 'id="ai-test-result"' in content
    assert "连接已验证" in content
    assert 'hx-swap-oob="true"' in content
    assert "设为个人默认模型" in content
    assert "共享设置" in content
    assert '<fieldset class="space-y-3" disabled' not in content


def test_discovery_uses_form_connection_without_saving(client, users, monkeypatch):
    monkeypatch.setattr("ai.views.cache", Mock(add=Mock(return_value=True)))
    client.force_login(users["owner"])
    fetch = Mock(return_value=["vendor/model"])
    monkeypatch.setattr("ai.views.fetch_model_ids", fetch)
    data = {"provider": "custom", "base_url": GATEWAY, "api_key": API_KEY}
    response = client.post(url("discover"), data)
    assert response.json() == {"models": ["vendor/model"]}
    fetch.assert_called_once_with("custom", GATEWAY, API_KEY)
    assert not AIModel.objects.exists()


def test_discovery_reuses_saved_key_only_on_same_owned_endpoint(client, users, monkeypatch):
    monkeypatch.setattr("ai.views.cache", Mock(add=Mock(return_value=True)))
    model = services.save_model(users["owner"], {**MODEL_DATA, "provider": "custom", "base_url": GATEWAY})
    fetch = Mock(return_value=[])
    monkeypatch.setattr("ai.views.fetch_model_ids", fetch)
    data = {"provider": "custom", "base_url": GATEWAY}
    client.force_login(users["other"])
    assert client.post(url("discover_saved", model), data).status_code == 404
    client.force_login(users["owner"])
    assert client.post(url("discover_saved", model), {**data, "base_url": "https://other.example/v1"}).status_code == 400
    fetch.assert_not_called()
    assert client.post(url("discover_saved", model), data).status_code == 200
    fetch.assert_called_once_with("custom", GATEWAY, API_KEY)


def test_model_parameter_preset_defaults_and_saved_config_are_independent(client, users, upstream, monkeypatch):
    support = Mock(return_value={"temperature", "top_p"})
    monkeypatch.setattr("ai.services.supported_sampling_parameters", support)
    client.force_login(users["admin"])
    preset = {
        "name": "推荐模型", "model_id": "gpt-test", "is_active": "on", "is_default": "on",
        "show_temperature": "on", "temperature": "0.4", "show_top_p": "on", "top_p": "0.9",
    }
    assert client.post(reverse("ai:option_create", args=["openai"]), preset).status_code == 302
    support.assert_called_once_with("openai", "gpt-test")
    option = AIModelOption.objects.get()
    assert option.parameter_presets == {"temperature": 0.4, "top_p": 0.9}

    client.force_login(users["owner"])
    data = {
        **MODEL_DATA, "provider": "openai", "base_url": "https://api.openai.com/v1", "model_id": "gpt-test",
        "notes": "用于训练日志", "temperature": "0", "top_p": "",
    }
    assert client.post(url("create"), data).status_code == 302
    upstream.test.assert_not_called()
    model = AIModel.objects.get()
    assert model.request_parameters == {"temperature": 0}
    assert model.notes == "用于训练日志"
    assert client.post(url("test", model)).status_code == 302
    model.refresh_from_db()
    assert model.test_request["temperature"] == 0
    assert "top_p" not in model.test_request
    services.set_shared(users["owner"], model.pk, True)
    revision = model.revision

    option.parameter_presets = {"temperature": 0.7, "top_p": 0.6}
    option.save()
    edit = client.get(url("edit", model))
    assert edit.context["form"]["temperature"].value() == 0
    assert edit.context["form"]["top_p"].value() is None
    assert "回答通常越稳定" in edit.content.decode()
    assert API_KEY not in edit.content.decode()

    edit_data = {**data, "api_key": ""}
    assert client.post(url("edit", model), edit_data).status_code == 302
    model.refresh_from_db()
    assert model.revision == revision and model.is_shared
    assert client.post(url("edit", model), {**edit_data, "temperature": ""}).status_code == 302
    model.refresh_from_db()
    assert model.request_parameters == {}
    assert not model.verified and not model.is_shared and model.revision != revision


def test_request_parameter_presets_require_a_trusted_address_and_allowed_fields(client, users, monkeypatch):
    monkeypatch.setattr("ai.services.supported_sampling_parameters", Mock(return_value={"temperature"}))
    client.force_login(users["admin"])
    create = reverse("ai:option_create", args=["deepseek"])
    preset = {
        "name": "推荐模型", "model_id": "preset", "is_active": "on",
        "show_temperature": "on", "temperature": "0.4",
    }
    rejected = client.post(create, {**preset, "show_top_p": "on"})
    assert "当前调用适配器未声明支持以下参数" in rejected.content.decode()
    assert client.post(create, preset).status_code == 302

    client.force_login(users["owner"])
    data = {**MODEL_DATA, "model_id": "preset", "temperature": "0.4"}
    untrusted = client.post(url("create"), {**data, "base_url": GATEWAY})
    assert "当前模型和 API 地址没有配置此参数预设" in untrusted.content.decode()
    assert client.post(url("create"), {**data, "temperature": "3"}).status_code == 200
    assert not AIModel.objects.exists()
    assert client.post(url("create"), data).status_code == 302


def test_custom_provider_name_and_manual_id_have_independent_identity(client, users):
    client.force_login(users["owner"])
    data = {
        **MODEL_DATA, "provider": "custom", "base_url": GATEWAY, "model_id": "vendor/new-model",
        "custom_provider_name": "内部网关",
    }
    response = client.post(url("create"), data, follow=True)
    model = AIModel.objects.get()
    assert (model.provider, model.provider_label, model.model_id) == ("custom", "内部网关", "vendor/new-model")
    assert model.protocol_label == "OpenAI 兼容"
    assert "内部网关" in response.content.decode()
    assert model.name in client.get(url("list"), {"q": "内部网关"}).content.decode()


def test_thinking_preset_can_be_cleared_to_use_the_interface_default(client, users, upstream):
    AIModelOption.objects.create(
        provider="deepseek", model_id="deepseek-flash", name="测试预设", is_default=True,
        parameter_presets={"thinking": "enabled", "reasoning_effort": "max"},
    )
    client.force_login(users["owner"])
    form = client.get(url("create")).context["form"]
    assert form["thinking"].value() == "enabled"
    assert form["reasoning_effort"].value() == "max"
    assert client.post(url("create"), {**MODEL_DATA, "thinking": "", "reasoning_effort": ""}).status_code == 302
    model = AIModel.objects.get()
    assert (model.thinking, model.reasoning_effort) == ("", "")
    assert client.post(url("test", model)).status_code == 302
    model.refresh_from_db()
    assert "thinking" not in model.test_request
    assert "reasoning_effort" not in model.test_request
    upstream.test.assert_called_once()


def test_candidate_verification_matches_endpoint_and_only_returns_requested_ids(client, users):
    other = users["other"]
    verified = services.save_model(other, MODEL_DATA)
    gateway_model = services.save_model(other, {**MODEL_DATA, "base_url": GATEWAY, "model_id": "gateway-only"})
    unrequested = services.save_model(other, {**MODEL_DATA, "model_id": "private-unrequested"})
    AIModel.objects.filter(pk__in=[verified.pk, gateway_model.pk, unrequested.pk]).update(verified=True)
    services.save_model(other, {**MODEL_DATA, "model_id": "pending"})

    endpoint = url("candidate_verification")
    data = {
        "provider": "deepseek", "base_url": "https://api.deepseek.com/",
        "model_ids": [verified.model_id, gateway_model.model_id, "pending"],
    }
    client.force_login(users["owner"])
    assert client.post(endpoint, data).json() == {"models": [verified.model_id]}
    assert client.post(endpoint, {**data, "provider": "custom"}).json() == {"models": []}
    client.force_login(users["consumer"])
    assert client.post(endpoint, data).status_code == 403
