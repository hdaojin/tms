from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver
from django.core.validators import FileExtensionValidator
from pathlib import Path

from functools import partial

from core.constants import (
    NOTICE_ALLOWED_EXTENSIONS,
    NOTICE_UPLOAD_DIR,
    NOTICE_UPLOAD_MAX_SIZE_MB,
)
from core.utils.validators import validate_file_size

# Create your models here.
# 站内通知模型
class Notice(models.Model):
    """
    站内通知的模型
    """

    title = models.CharField(max_length=200, verbose_name='标题(可选)', blank=True)
    content = models.TextField(verbose_name='通知内容')
    published_by = models.ForeignKey(get_user_model(), on_delete=models.PROTECT, null=True, blank=True, related_name='notices_published', verbose_name='发布人')
    published_at = models.DateTimeField(null=True, blank=True, verbose_name='发布时间')
    target_groups = models.ManyToManyField(Group, blank=True, verbose_name='目标组', help_text='如果未选择任何组，则向所有用户发送')

    class Meta:
        ordering = ('-published_at', '-id')
        verbose_name = '通知'
        verbose_name_plural = '通知'

    def __str__(self):
        return f"{self.title or '无标题'}"
    
    def can_user_view(self, user):
        """
        检查用户是否可以查看此通知
        """
    # 发布者本人始终可见
        if user and getattr(user, 'is_authenticated', False) and getattr(self.published_by, 'id', None) == getattr(user, 'id', None):
            return True

        # 如果没有指定目标组，所有用户都可以查看
        if not self.target_groups.exists():
            return True

        # 未登录或无分组信息的用户不允许查看限定分组的通知
        if not user or not getattr(user, 'is_authenticated', False) or not hasattr(user, 'groups'):
            return False

        # 检查用户是否在目标组中
        return self.target_groups.filter(
            id__in=user.groups.values_list('id', flat=True)
        ).exists()



def notice_attachment_upload_to(instance, original_name: str) -> str:
    """上传通知相关附件的路径。
    符合 Django FileField upload_to 回调签名 (instance, filename)。"""
    notice_attachment_dir = NOTICE_UPLOAD_DIR
    # 使用当前时间构建路径，避免使用可能为 None 的 instance.id
    return f"{notice_attachment_dir}/{timezone.now().strftime('%Y/%m/%d')}/{original_name}"

class NoticeAttachment(models.Model):
    """
    通知附件模型 - 支持多个附件
    """
    notice = models.ForeignKey(Notice, on_delete=models.CASCADE, related_name='attachments', verbose_name='通知')
    file = models.FileField(
        upload_to=notice_attachment_upload_to,
        verbose_name='附件文件',
        help_text="支持多个文件上传",
        validators=[
            FileExtensionValidator(
                allowed_extensions=NOTICE_ALLOWED_EXTENSIONS,
                message=f"仅支持以下格式的文件：{', '.join(NOTICE_ALLOWED_EXTENSIONS)}"
            ),
            partial(validate_file_size, max_size_mb=NOTICE_UPLOAD_MAX_SIZE_MB),
        ],
    )   # type: ignore[arg-type]
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name='上传时间')
    file_size = models.BigIntegerField(null=True, blank=True, verbose_name='文件大小(字节)')

    class Meta:
        ordering = ('uploaded_at',)
        verbose_name = '附件'
        verbose_name_plural = '附件'

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

    def _get_effective_size(self) -> int | None:
        """优先返回数据库中的文件大小；若无，则尝试从存储读取。"""
        if self.file_size:
            return int(self.file_size)
        try:
            if self.file:
                # FieldFile.size 会调用存储后端获取大小（可能触发 I/O 或网络请求）
                return int(self.file.size)
        except Exception:
            pass
        return None

    @property
    def file_size_human(self):
        """返回人类可读的文件大小；若无法获取则返回“未知”。"""
        eff = self._get_effective_size()
        if eff is None:
            return '未知'

        size = float(eff)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"


# 删除信号处理器
@receiver(post_delete, sender=NoticeAttachment)
def delete_attachment_file(sender, instance, **kwargs):
    """
    删除附件时，同时删除对应的文件
    """
    if instance.file and instance.file.name:
        try:
            storage = instance.file.storage
            if storage.exists(instance.file.name):
                storage.delete(instance.file.name)
        except Exception:
            # 如果文件删除失败，记录错误但不阻止删除
            pass


@receiver(post_delete, sender=Notice)
def delete_notice_attachments(sender, instance, **kwargs):
    """
    删除通知时，同时删除所有相关的附件文件
    """
    # 删除所有相关的附件文件
    for attachment in instance.attachments.all():
        if attachment.file:
            try:
                # 删除物理文件
                if attachment.file.storage.exists(attachment.file.name):
                    attachment.file.storage.delete(attachment.file.name)
            except Exception:
                # 如果文件删除失败，记录错误但不阻止删除
                pass


@receiver(pre_save, sender=NoticeAttachment)
def auto_delete_old_attachment_on_change(sender, instance, **kwargs):
    """
    更新附件时，若文件被替换，则删除旧文件，避免孤儿文件
    """
    if not instance.pk:
        return
    try:
        old_instance = NoticeAttachment.objects.get(pk=instance.pk)
    except NoticeAttachment.DoesNotExist:
        return
    
    old_file = getattr(old_instance, 'file', None)
    new_file = getattr(instance, 'file', None)

    if old_file and getattr(old_file, 'name', None):
        if (not new_file) or (old_file.name != getattr(new_file, 'name', None)):
            try:
                storage = old_file.storage
                if storage.exists(old_file.name):
                    storage.delete(old_file.name)
            except Exception:
                # 如果文件删除失败，记录错误但不阻止保存
                pass
