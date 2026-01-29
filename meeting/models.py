from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.conf import settings
from django.contrib.auth import get_user_model
from pathlib import Path

from core.utils.validators import FileSizeValidator, DateNotFutureValidator, validate_pdf_file
from core.utils.signals import register_file_cleanup_signals


def meeting_file_upload_to(instance, original_name: str) -> str:
    """生成存储路径: <MEETING_UPLOAD_DIR>/<YYYY>/<YYYY.MM.DD>-<title><ext>"""
    ext = Path(original_name).suffix.lower() or '.pdf'
    date_part = instance.date or timezone.localdate()
    safe_title = slugify(instance.title or 'untitled', allow_unicode=True)
    basename = f"{date_part:%Y.%m.%d}-{safe_title}{ext}"
    base_dir = getattr(settings, 'MEETING_UPLOAD_DIR', 'meetings')
    return f"{base_dir}/{date_part:%Y}/{basename}"


def meeting_file_validator(file):
    """验证会议记录文件（PDF 格式和大小）"""
    validate_pdf_file(file)
    FileSizeValidator()(file)


class Meeting(models.Model):
    title = models.CharField(max_length=200, verbose_name="会议名称")
    date = models.DateField(
        verbose_name="会议日期",
        default=timezone.localdate,
        help_text="特别注意：请填写会议的实际日期, 而非上传日期",
        validators=[DateNotFutureValidator("会议日期")]
    )
    file = models.FileField(
        "会议记录文件",
        upload_to=meeting_file_upload_to,
        help_text="支持 PDF 格式, 文件大小不超过 100MB",
        validators=[meeting_file_validator]
    )
    uploaded_by = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        related_name='meetings',
        verbose_name='上传者',
        null=True,
        blank=True
    )
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


# 注册文件清理信号
register_file_cleanup_signals(Meeting, file_field="file")
    