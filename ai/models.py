from uuid import uuid4

from django.conf import settings
from django.db import models
from django.db.models import Q

from core.models import TimestampedModel
from core.uploads import ai_provider_logo_path
from core.utils.signals import register_file_cleanup_signals

from .providers import PROVIDERS, protocol_label


class ThinkingMode(models.TextChoices):
    DISABLED = "disabled", "关闭"
    ENABLED = "enabled", "开启"


class ReasoningEffort(models.TextChoices):
    LOW = "low", "低"
    HIGH = "high", "高"
    MAX = "max", "最高"


class ShareAudience(models.TextChoices):
    ALL = "all", "共享给所有有使用权限的用户"
    SELECTED = "selected", "共享给指定用户或角色"


class AIModel(TimestampedModel):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="所有者")
    name = models.CharField("显示名称", max_length=100)
    notes = models.TextField("备注", blank=True, max_length=2000)
    provider = models.CharField("模型提供商", max_length=32)
    custom_provider_name = models.CharField("自定义提供商名称", max_length=100, blank=True)
    base_url = models.URLField("API 地址", max_length=300)
    model_id = models.CharField("模型 ID", max_length=150)
    thinking = models.CharField("思考模式", max_length=8, choices=ThinkingMode, default=ThinkingMode.DISABLED, blank=True)
    reasoning_effort = models.CharField("思考强度", max_length=4, choices=ReasoningEffort, blank=True)
    request_parameters = models.JSONField("高级请求参数", default=dict, blank=True)
    encrypted_api_key = models.BinaryField("加密 API 密钥", editable=False)
    api_key_preview = models.CharField("API 密钥预览", max_length=11, editable=False)
    revision = models.UUIDField(default=uuid4, editable=False)
    is_shared = models.BooleanField("开启共享", default=False)
    share_audience = models.CharField("共享范围", max_length=8, choices=ShareAudience, default=ShareAudience.ALL)
    shared_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL, verbose_name="指定用户", blank=True, related_name="+"
    )
    shared_groups = models.ManyToManyField("auth.Group", verbose_name="指定角色", blank=True, related_name="+")
    is_delisted = models.BooleanField("管理员已下架", default=False)
    verified = models.BooleanField("当前配置已验证", default=False)
    test_started_at = models.DateTimeField("最近发起测试时间", null=True)
    tested_at = models.DateTimeField("最近完成测试时间", null=True)
    test_error = models.CharField("最近测试失败原因", max_length=150, blank=True)
    test_duration_ms = models.PositiveIntegerField("最近测试耗时（毫秒）", null=True)
    test_request = models.JSONField("最近测试请求", default=dict, blank=True)
    test_reply = models.TextField("最近测试回复", blank=True)

    class Meta:
        verbose_name = "AI 模型"
        verbose_name_plural = "AI 模型"
        ordering = ["name", "pk"]
        default_permissions = ("view",)
        permissions = [
            ("manage_own_aimodel", "管理自己的 AI 模型"),
            ("use_shared_aimodel", "使用共享 AI 模型"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(is_shared=False) | Q(verified=True, is_delisted=False),
                name="ai_model_shared_requires_verified",
            ),
        ]

    @property
    def sharing_mode(self):
        return self.share_audience if self.is_shared else "private"

    @property
    def provider_label(self):
        if self.provider == "custom":
            return self.custom_provider_name or "自定义 API"
        provider = PROVIDERS.get(self.provider)
        return provider.label if provider else self.provider

    @property
    def protocol_label(self):
        return protocol_label(self.provider)


class AIModelPreference(TimestampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="用户")
    model = models.ForeignKey(AIModel, on_delete=models.SET_NULL, null=True, verbose_name="默认 AI 模型")

    class Meta:
        verbose_name = "默认 AI 模型设置"
        verbose_name_plural = "默认 AI 模型设置"
        default_permissions = ()


class AIProviderSettings(TimestampedModel):
    enabled = models.BooleanField("启用提供商", default=True)
    provider = models.CharField("模型提供商", max_length=32, unique=True)
    default_base_url = models.URLField("默认 API 地址", max_length=300, blank=True)
    logo = models.ImageField("提供商 Logo", upload_to=ai_provider_logo_path, blank=True)
    thinking = models.CharField("默认思考模式", max_length=8, choices=ThinkingMode, default=ThinkingMode.DISABLED)
    reasoning_effort = models.CharField("默认思考强度", max_length=4, choices=ReasoningEffort, blank=True)

    class Meta:
        verbose_name = "AI 提供商配置"
        verbose_name_plural = "AI 提供商配置"
        default_permissions = ()


register_file_cleanup_signals(AIProviderSettings, file_field="logo", delete_on_commit=True)


class AIModelOption(TimestampedModel):
    parameter_presets = models.JSONField("高级请求参数预设", default=dict, blank=True)
    supports_images = models.BooleanField("支持图片输入", default=False)
    supports_json = models.BooleanField("支持 JSON 输出模式", default=False)
    provider = models.CharField("模型提供商", max_length=32)
    base_url = models.URLField("旧目录 API 地址", max_length=300, blank=True, editable=False)
    model_id = models.CharField("模型 ID", max_length=150)
    name = models.CharField("显示名称", max_length=100)
    is_active = models.BooleanField("在模型选项中显示", default=True)
    is_default = models.BooleanField("设为提供商默认模型", default=False)

    class Meta:
        verbose_name = "AI 模型选项"
        verbose_name_plural = "AI 模型选项"
        default_permissions = ()
        ordering = ("name", "model_id")
        constraints = [
            models.UniqueConstraint(
                fields=("provider", "model_id"), condition=Q(is_active=True), name="ai_option_unique_active_model"
            ),
            models.UniqueConstraint(fields=("provider",), condition=Q(is_default=True), name="ai_option_one_default"),
            models.CheckConstraint(
                condition=Q(is_default=False) | Q(is_active=True), name="ai_option_default_requires_active"
            ),
        ]
