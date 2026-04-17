from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.utils.text import slugify
from pathlib import Path
from functools import partial

from core.constants import GROUP_COACH, GROUP_COMPETITOR, TRAININGLOG_UPLOAD_DIR, TRAININGLOG_ALLOWED_EXTENSIONS, TRAININGLOG_UPLOAD_MAX_SIZE_MB
from core.utils.validators import validate_file_size, validate_date_not_future
from core.utils.signals import register_file_cleanup_signals

"""避免循环导入：使用字符串引用外键模型。"""


def traininglog_upload_to(instance: "TrainingLog", filename: str) -> str:
    """
    统一路径与文件名：
    training_logs/YYYY/MM/{prefix}YYYYMMDD{GROUP}LOG-{username}.ext
    """
    ext = Path(filename).suffix.lower()

    prefix_part = getattr(settings, "WSCSKILL_NAME", "网络系统管理项目")
    date = instance.training_date or timezone.localdate()
    date_part = f"{date:%Y年%m月%d日}"

    if instance.uploaded_by:
        user_src = instance.uploaded_by.display_name
    else:
        user_src = "unknown"
    user_part = slugify(user_src, allow_unicode=True)
    
    # 获取用户组信息
    group = ""
    if instance.uploaded_by and instance.uploaded_by.groups.exists():
        groups = instance.uploaded_by.groups.values_list('name', flat=True)
        if GROUP_COACH in groups:
            group = GROUP_COACH
        elif GROUP_COMPETITOR in groups:
            group = GROUP_COMPETITOR
        elif groups:
            group = groups[0]

    group_part = f"{group}" if group else ""
    basename = f"{prefix_part}{date_part}{group_part}日志-{user_part}{ext}"
    base_dir = TRAININGLOG_UPLOAD_DIR
    
    return f"{base_dir}/{date:%Y}/{date:%m}/{basename}"


class TrainingLog(models.Model):
    module = models.ForeignKey(
        'competitions.Module', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='training_logs', verbose_name='训练模块'
    )
    task = models.CharField("训练任务", max_length=100)
    training_date = models.DateField(
        "训练日期", default=timezone.now,
        help_text="*特别注意：请填写日志对应的实际训练日期，而非上传日期",
        validators=[validate_date_not_future]
    )
    file = models.FileField(
        "日志文件",
        upload_to=traininglog_upload_to,
        help_text=f"支持格式：{', '.join(TRAININGLOG_ALLOWED_EXTENSIONS)}，文件大小不超过 {TRAININGLOG_UPLOAD_MAX_SIZE_MB}MB",
        validators=[
            FileExtensionValidator(
                allowed_extensions=TRAININGLOG_ALLOWED_EXTENSIONS,
                message=f"仅支持以下格式的文件：{', '.join(TRAININGLOG_ALLOWED_EXTENSIONS)}"
            ),
            partial(validate_file_size, max_size_mb=TRAININGLOG_UPLOAD_MAX_SIZE_MB),
        ],
    )
    uploaded_by = models.ForeignKey(
        get_user_model(), on_delete=models.PROTECT,
        related_name='training_logs', verbose_name='上传者',
        blank=True, null=True
    )
    uploaded_at = models.DateTimeField("上传时间", auto_now_add=True)

    class Meta:
        verbose_name = '训练日志'
        verbose_name_plural = '训练日志'
        ordering = ('-training_date', '-uploaded_at')
        unique_together = [('uploaded_by', 'training_date')]
        permissions = [
            ('view_all_traininglog', '查看所有训练日志'),
            ('view_coach_traininglog', '查看教练训练日志'),
            ('view_competitor_traininglog', '查看选手训练日志'),
        ]

    def clean(self):
        super().clean()
        if not self.uploaded_by_id or not self.training_date:
            return

        duplicate_qs = type(self).objects.filter(
            uploaded_by_id=self.uploaded_by_id,
            training_date=self.training_date,
        )
        if self.pk:
            duplicate_qs = duplicate_qs.exclude(pk=self.pk)

        if duplicate_qs.exists():
            raise ValidationError({
                'training_date': '同一训练日期只能上传一条训练日志。如需更正，请先删除原日志后再重新上传。'
            })

    def __str__(self):
        m = self.module.name if self.module else "未分配模块"
        return f"{m} - {self.task} - {self.training_date:%Y-%m-%d}"

    @property
    def filename(self) -> str:
        """供模板展示的文件名（去掉目录，仅文件名）。"""
        return Path(self.file.name).name if self.file else ''


# 注册文件清理信号
register_file_cleanup_signals(TrainingLog, file_field="file")
