from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models.signals import post_delete , pre_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from pathlib import Path

# Create your models here.


def meeting_file_upload_to(instance, original_name: str) -> str:
    """生成存储路径: <MEETING_FILE_DIR>/<YYYY>/<YYYY.MM.DD>-<title><ext>"""
    ext = Path(original_name).suffix.lower() or '.pdf'
    date_part = instance.date or timezone.localdate()
    # 简单清理标题中的不安全字符
    # 这里之前错误使用 getattr(instance.title,'title',...) 得到的是内置方法对象，导致文件名包含 'built-in-method-title...'
    safe_title = slugify(instance.title or 'untitled', allow_unicode=True)
    basename = f"{date_part:%Y.%m.%d}-{safe_title}{ext}"
    base_dir = getattr(settings, 'MEETING_FILE_DIR', 'meetings')
    return f"{base_dir}/{date_part:%Y}/{basename}"


def file_validator(file):
    """验证上传的文件是否符合要求"""
    name_lower = file.name.lower()
    if not name_lower.endswith('.pdf'):
        raise ValidationError("上传文件格式必须为.pdf。")
    MAX_FILE_MB = getattr(settings, 'UPLOAD_MAX_SIZE_MB', 10) # 默认10MB
    if getattr(file, 'size', 0) > MAX_FILE_MB * 1024 * 1024:
        raise ValidationError(f"上传文件大小不能超过{MAX_FILE_MB}MB。")
    

def date_validator(date):
    """验证日期不能晚于今天"""
    if date and date > timezone.localdate():
        raise ValidationError("会议日期不能是未来的日期。")


class Meeting(models.Model):
    title = models.CharField(max_length=200, verbose_name="会议名称")
    date = models.DateField(verbose_name="会议日期", default=timezone.localdate, help_text="特别注意：请填写会议的实际日期, 而非上传日期", validators=[date_validator])
    file = models.FileField("会议记录文件", upload_to=meeting_file_upload_to, help_text="支持pdf格式, 文件大小不超过10MB", validators=[file_validator])
    uploaded_by = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, related_name='meetings', verbose_name='上传者', null=True, blank=True)
    uploaded_at = models.DateTimeField("上传时间", auto_now_add=True)

    class Meta:
        verbose_name = '会议记录'
        verbose_name_plural = '会议记录'
        ordering = ('-date',)
    
    def __str__(self):
        return f"{self.title} - {self.date}"
    
    @property
    def date_chinese(self):
        """返回中文格式的日期，如：2024年1月1日"""
        return self.date.strftime('%Y年%m月%d日')
    
    @property
    def filename(self):
        """返回去掉路径的文件名，供模板显示使用"""
        return Path(self.file.name).name if self.file else ''


# 删除信号处理器
@receiver(post_delete, sender=Meeting)
def delete_meeting_file(sender, instance, **kwargs):
    """删除 Meeting 实例时，同时删除关联的文件"""
    if instance.file and instance.file.name:
        storage = instance.file.storage
        if storage.exists(instance.file.name):
            storage.delete(instance.file.name)


@receiver(pre_save, sender=Meeting)
def auto_delete_old_file_on_change(sender, instance, **kwargs):
    """更新 Meeting 实例时，若文件被替换，则删除旧文件"""
    if not instance.pk:
        return
    try:
        old_instance = Meeting.objects.get(pk=instance.pk)
    except Meeting.DoesNotExist:
        return
    
    old_file = getattr(old_instance, 'file', None)
    new_file = getattr(instance, 'file', None)

    if old_file and getattr(old_file, 'name', None):
        if (not new_file) or (old_file.name != getattr(new_file, 'name', None)):
            storage = old_file.storage
            if storage.exists(old_file.name):
                storage.delete(old_file.name)
    