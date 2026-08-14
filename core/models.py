from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import models


class UploadedDocumentModel(models.Model):
    """通用文档上传字段与文件名展示。"""

    file_field_name = 'file'

    uploaded_at = models.DateTimeField('上传时间', auto_now_add=True)

    class Meta:
        abstract = True

    @property
    def filename(self) -> str:
        file_obj = getattr(self, self.file_field_name, None)
        return Path(file_obj.name).name if file_obj else ''


class AuditedModel(models.Model):
    """通用创建/更新审计字段。"""

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name='创建人',
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name='更新人',
    )
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        abstract = True

class SiteConfig(models.Model):
    """站点配置模型，存储全局站点设置，如名称、描述等。"""

    site_name = models.CharField("站点名称", max_length=100)
    site_short_name = models.CharField("站点简称", max_length=50, blank=True,
                                       help_text="用于简短显示，如浏览器标签页标题")
    site_description = models.TextField("站点描述", blank=True)
    site_keywords = models.CharField("站点关键词", max_length=255, blank=True,
                                     help_text="用于SEO的关键词，用逗号分隔")
    site_author = models.CharField("站点作者", max_length=100, blank=True)
    site_author_link = models.URLField("站点作者网址链接", blank=True,
                                       help_text="如: https://example.com/about")
    site_domain = models.CharField("站点域名", max_length=100, blank=True,
                                   help_text="如: www.example.com")
    site_copyright = models.CharField("站点版权信息", max_length=255, blank=True,
                                      help_text="如: TMS 版权所有")
    site_ism_beian = models.CharField("公安联网备案号", max_length=50, blank=True,
                                        help_text="如: 粤公网安备440200001234")
    site_ism_beian_link = models.URLField("公安联网备案链接", blank=True,
                                          help_text="如: https://beian.mps.gov.cn/#/query/webSearch?code=440200001234")
    site_icp_beian = models.CharField("ICP备案号", max_length=50, blank=True,
                                      help_text="如: 粤ICP备12345678号-1")
    site_icp_beian_link = models.URLField("ICP备案链接", blank=True,
                                          help_text="如: https://beian.miit.gov.cn/")
    default_registration_group = models.ForeignKey(
        Group,
        verbose_name="新用户默认用户组",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="新注册用户自动加入此组；留空时不授予任何默认业务权限。",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = '站点配置'
        verbose_name_plural = '站点配置'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(pk=1),
                name="core_siteconfig_singleton_pk",
            ),
        ]

    def __str__(self):
        return self.site_name or "站点配置"

    def clean(self):
        super().clean()
        if self.pk not in (None, 1):
            raise ValidationError("站点配置只能存在固定主键为 1 的单例记录。")

    def save(self, *args, **kwargs):
        if self._state.adding and type(self).objects.filter(pk=1).exists():
            raise ValidationError("站点配置只能存在一条记录。")
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete("site_config_solo")

    def delete(self, *args, **kwargs):
        result = super().delete(*args, **kwargs)
        cache.delete("site_config_solo")
        return result
    
    @classmethod
    def get_solo(cls):
        """获取唯一的站点配置实例，若不存在则创建一个默认实例。"""
        cache_key = "site_config_solo"
        obj = cache.get(cache_key)
        if obj is not None:
            return obj

        obj, _created = cls.objects.get_or_create(id=1, defaults={
            "site_name": "Training management system",
            "site_short_name": "TMS",
            "site_description": "A training management system for skill competitions.",
            "site_keywords": "training, management, skills, competitions",
            "site_author": "hdaojin",
            "site_copyright": "TMS 版权所有",
        })
        cache.set(cache_key, obj, timeout=settings.CACHE_TIMEOUT)
        return obj

