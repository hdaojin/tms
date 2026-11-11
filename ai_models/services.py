from datetime import timedelta
from time import monotonic
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from .models import AIModel, AIModelOption, AIModelPreference, AIProviderSettings, ReasoningEffort, ThinkingMode
from .providers import PROVIDERS, ProviderError, validate_base_url

VIEW = "ai_models.view_aimodel"
MANAGE_OWN = "ai_models.manage_own_aimodel"
USE_SHARED = "ai_models.use_shared_aimodel"
TEST_INTERVAL = timedelta(seconds=30)


def can_manage(user):
    return user.is_active and user.has_perms((VIEW, MANAGE_OWN))


def can_use_shared(user):
    return user.is_active and user.has_perms((VIEW, USE_SHARED))


def can_moderate(user):
    return user.is_active and user.is_superuser


@transaction.atomic
def save_model_option(user, provider, data, pk=None):
    if not can_moderate(user):
        raise PermissionDenied
    if provider not in PROVIDERS:
        raise Http404
    AIProviderSettings.objects.select_for_update().get_or_create(provider=provider)
    options = AIModelOption.objects.filter(provider=provider)
    option = AIModelOption(provider=provider) if pk is None else get_object_or_404(options, pk=pk)
    siblings = options.exclude(pk=pk)
    if data["is_active"] and siblings.filter(is_active=True, model_id=data["model_id"]).exists():
        raise ValidationError("此提供商已有相同的模型 ID 在显示。")
    if data["is_default"]:
        if not data["is_active"]:
            raise ValidationError("请先勾选「在模型选项中显示」，再设为默认模型。")
        siblings.filter(is_default=True).update(is_default=False, updated_at=timezone.now())
    for field in ("model_id", "name", "is_active", "is_default"):
        setattr(option, field, data[field])
    option.save()


def own_models(user):
    if not can_manage(user):
        raise PermissionDenied
    return AIModel.objects.filter(owner=user)


def configured_models():
    return AIModel.objects.filter(provider__in=PROVIDERS)


def shared_models():
    return configured_models().filter(is_shared=True, owner__is_active=True)


def usable_models(user):
    """当前用户可选用的模型范围，业务调用时须重新检查。"""
    scope = Q(pk__in=[])
    if can_manage(user):
        scope |= Q(owner=user)
    if can_use_shared(user):
        scope |= Q(pk__in=shared_models().values("pk"))
    return configured_models().filter(scope, verified=True)


@sensitive_variables()
def cipher():
    try:
        return Fernet(settings.AI_MODEL_ENCRYPTION_KEY)
    except (TypeError, ValueError):
        raise ValidationError("系统尚未正确配置 AI 模型加密密钥，请联系管理员。") from None


@sensitive_variables("api_key")
def key_preview(api_key):
    return f"{api_key[:3]}••••{api_key[-4:]}" if len(api_key) >= 12 else "••••"


def normalize_thinking(thinking, effort):
    thinking = thinking or ThinkingMode.DISABLED
    if thinking not in ThinkingMode.values or (effort and effort not in ReasoningEffort.values):
        raise ValidationError("请选择有效的思考模式和思考强度。")
    return thinking, (effort or ReasoningEffort.HIGH) if thinking == ThinkingMode.ENABLED else ""


@sensitive_variables()
@transaction.atomic
def save_model(user, data, pk=None):
    queryset = own_models(user)
    model = AIModel(owner=user) if pk is None else get_object_or_404(queryset.select_for_update(), pk=pk)
    api_key = data["api_key"]
    provider = data["provider"]
    base_url = validate_base_url(provider, data["base_url"])
    thinking, effort = normalize_thinking(
        data.get("thinking", model.thinking), data.get("reasoning_effort", model.reasoning_effort)
    )
    destination_changed = (model.provider, model.base_url) != (provider, base_url)
    if (pk is None or destination_changed) and not api_key:
        raise ValidationError({"api_key": "新增模型或更换提供商、API 地址时，请输入 API 密钥。"})
    if api_key:
        model.encrypted_api_key = cipher().encrypt(api_key.encode())
        model.api_key_preview = key_preview(api_key)
    parameters_changed = (model.model_id, model.thinking, model.reasoning_effort) != (
        data["model_id"],
        thinking,
        effort,
    )
    if destination_changed or parameters_changed or api_key:
        model.revision = uuid4()
        model.verified = False
        model.is_shared = False
        model.tested_at = None
        model.test_error = ""
        model.test_duration_ms = None
        model.test_request = {}
        model.test_reply = ""
    model.name = data["name"]
    model.provider = provider
    model.base_url = base_url
    model.model_id = data["model_id"]
    model.thinking = thinking
    model.reasoning_effort = effort
    model.save()
    return model


@transaction.atomic
def set_shared(user, pk, shared):
    model = get_object_or_404(own_models(user).select_for_update(), pk=pk)
    if shared:
        if model.is_delisted:
            raise ValidationError("管理员已下架此模型，请联系管理员解除下架。")
        if not model.verified:
            raise ValidationError("请先手动测试当前配置，测试成功后即可共享。")
        validate_base_url(model.provider, model.base_url)
    model.is_shared = shared
    model.save(update_fields=["is_shared", "updated_at"])


@transaction.atomic
def delete_model(user, pk):
    model = get_object_or_404(own_models(user).select_for_update(), pk=pk)
    model.delete()


def moderated_models(user):
    if not can_moderate(user):
        raise PermissionDenied
    return AIModel.objects.filter(Q(is_shared=True) | Q(is_delisted=True))


def moderate_model(user, pk, delisted):
    queryset = moderated_models(user).filter(pk=pk)
    queryset = queryset.filter(is_shared=True) if delisted else queryset.filter(is_delisted=True)
    if not queryset.update(is_shared=False, is_delisted=delisted, updated_at=timezone.now()):
        raise Http404


@transaction.atomic
def set_default_model(user, pk):
    model = get_object_or_404(usable_models(user).select_for_update(), pk=pk)
    validate_base_url(model.provider, model.base_url)
    AIModelPreference.objects.update_or_create(user=user, defaults={"model": model})


@sensitive_variables()
def test_model(user, pk):
    queryset = own_models(user)
    model = get_object_or_404(queryset, pk=pk)
    base_url = validate_base_url(model.provider, model.base_url)
    started_at = timezone.now()
    current_config = queryset.filter(pk=pk, revision=model.revision)
    claimed = current_config.filter(
        Q(test_started_at__isnull=True) | Q(test_started_at__lte=started_at - TEST_INTERVAL)
    ).update(test_started_at=started_at, updated_at=started_at)
    if not claimed:
        raise ValidationError("配置已更新或刚刚发起过测试，请刷新页面后稍候再试。")

    error = ""
    payload = {}
    reply = ""
    timer = monotonic()
    try:
        api_key = cipher().decrypt(bytes(model.encrypted_api_key)).decode()
        adapter = PROVIDERS[model.provider]
        payload = adapter.test_payload(model.model_id, model.thinking, model.reasoning_effort)
        reply = adapter.test(base_url, payload, api_key).replace(api_key, "[已隐藏]")[:4096]
    except (InvalidToken, UnicodeError):
        error = "无法读取 API 密钥，请检查系统加密配置或重新保存密钥。"
    except ValidationError as exc:
        error = exc.messages[0]
    except ProviderError as exc:
        error = str(exc)

    finished_at = timezone.now()
    updates = {
        "tested_at": finished_at,
        "test_error": error,
        "test_duration_ms": round((monotonic() - timer) * 1000),
        "test_request": payload,
        "test_reply": reply,
        "updated_at": finished_at,
    }
    if not error:
        updates["verified"] = True
        updates["api_key_preview"] = key_preview(api_key)
    if not current_config.filter(test_started_at=started_at).update(**updates):
        raise ValidationError("测试期间配置已变更，请使用当前配置重新测试。")
    return error
