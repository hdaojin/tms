from django.db import models
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from pathlib import Path

# Create your models here.

def notice_attachment_upload_to(instance, filename):
    """
    上传通知附件的路径
    """
    notice_attachment_dir = getattr(settings, 'NOTICE_ATTACHMENT_DIR', 'notices')
    # 使用当前时间构建路径，避免使用可能为None的instance.id
    return f"{notice_attachment_dir}/{timezone.now().strftime('%Y/%m/%d')}/{filename}"

class Notice(models.Model):
    """
    站内通知
    """

    title = models.CharField(max_length=200, verbose_name='标题(可选)',null=True, blank=True)
    content = models.TextField(verbose_name='通知内容')
    is_published = models.BooleanField(default=False, db_index=True, verbose_name='是否发布')
    published_by = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True, blank=True, related_name='notices_published', verbose_name='发布人')
    published_at = models.DateTimeField(null=True, blank=True, verbose_name='发布时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    target_groups = models.ManyToManyField(Group, blank=True, verbose_name='目标组', help_text='如果未选择任何组，则向所有用户发送')

    class Meta:
        ordering = ('-is_published', '-published_at', '-updated_at')
        verbose_name = '通知'
        verbose_name_plural = '通知'

    def __str__(self):
        return f"{self.title or '无标题'} - {'已发布' if self.is_published else '未发布'}"
    
    def can_user_view(self, user):
        """
        检查用户是否可以查看此通知
        """
        # 如果没有指定目标组，所有用户都可以查看
        if not self.target_groups.exists():
            return True
        
        # 检查用户是否在目标组中
        user_groups = user.groups.all()
        return self.target_groups.filter(id__in=user_groups.values_list('id', flat=True)).exists()


class NoticeAttachment(models.Model):
    """
    通知附件模型 - 支持多个附件
    """
    notice = models.ForeignKey(Notice, on_delete=models.CASCADE, related_name='attachments', verbose_name='通知')
    file = models.FileField(upload_to=notice_attachment_upload_to, verbose_name='附件文件')
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name='上传时间')
    file_size = models.BigIntegerField(null=True, blank=True, verbose_name='文件大小(字节)')

    class Meta:
        ordering = ('uploaded_at',)
        verbose_name = '通知附件'
        verbose_name_plural = '通知附件'

    def __str__(self):
        return f"{self.notice} - {Path(self.file.name).name if self.file else '未知文件'}"

    def save(self, *args, **kwargs):
        # 获取文件大小
        if self.file and not self.file_size:
            try:
                self.file_size = self.file.size
            except Exception:
                pass
        
        super().save(*args, **kwargs)

    @property
    def file_name(self):
        """
        返回文件名（不包含路径）
        """
        if self.file:
            return Path(self.file.name).name
        return '未知文件'

    @property
    def file_size_human(self):
        """
        返回人类可读的文件大小
        """
        if not self.file_size:
            return '未知'
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if self.file_size < 1024.0:
                return f"{self.file_size:.1f} {unit}"
            self.file_size /= 1024.0
        return f"{self.file_size:.1f} TB"