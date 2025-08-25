from django.db import models

# Create your models here.

class Page(models.Model):
    # 页面模板选项
    TEMPLATE_CHOICES = (
        ('default', '默认'),
        ('no_sidebar', '无侧边栏'),
        ('no_header_sidebar', '无头部、无侧边栏'),
        ('no_header_sidebar_footer', '无头部、无侧边栏、无底部'),
        # 可根据需要添加更多模板
    )
    title = models.CharField(max_length=255, verbose_name="标题")
    slug = models.SlugField(max_length=255, unique=True, verbose_name="别名", help_text="用于URL的唯一标识符, 例如：about。'首页'必须为'index'")
    content = models.TextField(verbose_name="内容")
    template = models.CharField(
        max_length=50,
        choices=TEMPLATE_CHOICES,
        default='default',
        verbose_name='页面模板',
        help_text="选择页面的布局模板, 例如：是否显示侧边栏、头部和底部等。'首页'必须选择'无头部、无侧边栏、无底部'"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "页面"
        verbose_name_plural = "页面管理"

    def __str__(self):
        return self.title

