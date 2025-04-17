from django.db import models

# Create your models here.

class Page(models.Model):
    title = models.CharField(max_length=255, verbose_name="标题")
    slug = models.SlugField(max_length=255, unique=True, verbose_name="别名")
    is_homepage = models.BooleanField(default=False, verbose_name="是否首页")
    content = models.TextField(verbose_name="内容")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "页面"
        verbose_name_plural = "页面管理"

    def __str__(self):
        return self.title
    
