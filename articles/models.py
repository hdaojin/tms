from django.db import models
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils.text import slugify

# Create your models here.
# 分类系统
class Category(models.Model):
    name = models.CharField("分类名称", max_length=100, unique=True)
    slug = models.SlugField("URL别名", max_length=250, unique=True, blank=True)

    class Meta:
        verbose_name = "分类"
        verbose_name_plural = "分类"

    def __str__(self):
        return self.name
    
# 标签系统
class Tag(models.Model):
    name = models.CharField("标签名称", max_length=100, unique=True)

    class Meta:
        verbose_name = "标签"
        verbose_name_plural = "标签"

    def __str__(self):
        return self.name

# 文章管理
class Article(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'DR', '草稿'
        PUBLISHED = 'PB', '已发布'
        ARCHIVED = 'AR', '已归档'

    status = models.CharField("状态", max_length=2, choices=Status.choices, default=Status.DRAFT)
    title = models.CharField("标题", max_length=200)
    slug = models.SlugField("URL别名", max_length=250, unique_for_date="publish_date", blank=True)
    author = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name="articles", verbose_name="作者")
    content = models.TextField("内容")
    publish_date = models.DateTimeField("发布时间", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)
    is_deleted = models.BooleanField("已删除", default=False)
    view_count = models.PositiveIntegerField("浏览数", default=0)
    category = models.ManyToManyField(Category, related_name="articles", verbose_name="分类")
    tags = models.ManyToManyField(Tag, related_name="articles", verbose_name="标签")

    class Meta:
        ordering = ["-publish_date"]
        verbose_name = "文章"
        verbose_name_plural = "文章"
        indexes = [
            models.Index(fields=["publish_date"], name="articles_publish_date_idx"),
            models.Index(fields=["status"], name="articles_status_idx"),
        ]

    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse("articles:detail", kwargs={"slug": self.slug})
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)


