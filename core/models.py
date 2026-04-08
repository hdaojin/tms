from django.conf import settings
from django.core.cache import cache
from django.db import models


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
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = '站点配置'
        verbose_name_plural = '站点配置'

    def __str__(self):
        return self.site_name or "站点配置"
    
    @classmethod
    def get_solo(cls):
        """获取唯一的站点配置实例，若不存在则创建一个默认实例。"""
        cache_key = "site_config_solo"
        obj = cache.get(cache_key)
        if obj:
            return obj

        obj, _created = cls.objects.get_or_create(id=1, defaults={
            "site_name": "my site",
            "site_short_name": "MySite",
            "site_description": "This is my site description.",
            "site_keywords": "site, mysite, example",
            "site_author": "webmaster",
        })
        cache.set(cache_key, obj, timeout=settings.CACHE_TIMEOUT)
        return obj

    