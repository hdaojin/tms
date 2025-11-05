from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from pathlib import Path

from skills.models import Module

MAX_FILE_MB = getattr(settings, 'UPLOAD_MAX_SIZE_MB', 10) # 默认10MB
ALLOWED_EXTENSIONS = ['doc', 'docx', 'pdf']

def traininglog_upload_to(instance: "TrainingLog", filename: str) -> str:
    """
    统一路径与文件名：
    training_logs/YYYY/MM/{prefix}YYYYMMDD{GROUP}LOG-{username}.ext
    """
    # 提取扩展名
    ext = Path(filename).suffix.lower()  # 保留原扩展

    # Name prefix
    prefix_part = getattr(settings, "WSCSKILL_NAME", "网络系统管理项目")
    # 日期：以 training_date 为准
    date = instance.training_date or timezone.localdate()
    date_part = f"{date:%Y年%m月%d日}"

    # 组成可读的“人造文件名”：优先使用 first_name；若为空则用用户名（支持自定义 USERNAME_FIELD）
    if instance.uploaded_by:
        first_name = (getattr(instance.uploaded_by, 'first_name', '') or '').strip()
        user_src = first_name or instance.uploaded_by.get_username()
    else:
        user_src = "unknown"
    user_part = slugify(user_src, allow_unicode=True)
    
    # 获取用户组信息，如有“教练”和“选手”，提取之中的一个，否则为空字符串
    group = ""
    if instance.uploaded_by and instance.uploaded_by.groups.exists():
        groups = instance.uploaded_by.groups.values_list('name', flat=True)
        if '教练' in groups:
            group = '教练'
        elif '选手' in groups:
            group = '选手'
        elif groups:
            group = groups[0]  # 取第一个组名

    group_part = f"{group}" if group else ""

    basename = f"{prefix_part}{date_part}{group_part}日志-{user_part}{ext}"

    # 目录：可用 settings.LOGS_DIR，否则默认 "training_logs"
    base_dir = getattr(settings, "LOGS_DIR", "training_logs")
    
    return f"{base_dir}/{date:%Y}/{date:%m}/{basename}"

def training_date_validator(date):
    """验证训练日期不能晚于今天"""
    if date and date > timezone.localdate():
        raise ValidationError("训练日期不能晚于今天。")

def file_size_validator(f):
    """验证上传的文件大小"""
    if getattr(f, 'size', 0) > MAX_FILE_MB * 1024 * 1024:
        raise ValidationError(f"上传文件大小不能超过{MAX_FILE_MB}MB。")


class TrainingLog(models.Model):
    module = models.ForeignKey(
        Module, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='training_logs', verbose_name='训练模块'
    )
    task = models.CharField("训练任务", max_length=100)  # 适当放宽
    training_date = models.DateField(
        "训练日期", default=timezone.now,
        help_text="*特别注意：请填写日志对应的实际训练日期，而非上传日期",
        validators=[training_date_validator]
    )
    file = models.FileField(
        "日志文件",
        upload_to=traininglog_upload_to,
        help_text=f"支持格式：{', '.join(ALLOWED_EXTENSIONS)}，文件大小不超过{MAX_FILE_MB}MB",
        validators=[
            FileExtensionValidator(allowed_extensions=ALLOWED_EXTENSIONS, message=f"仅支持以下格式的文件：{', '.join(ALLOWED_EXTENSIONS)}"),
            file_size_validator,
        ],
    )
    # 不再存储 filename，统一用 upload.name 展示。如果保留字段，请设 editable=False 或用 property 替代。
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
        permissions = [
            ('view_all_traininglog', '查看所有训练日志'),
            ('view_coach_traininglog', '查看教练训练日志'),
            ('view_competitor_traininglog', '查看选手训练日志'),
        ]

    def __str__(self):
        m = self.module.name if self.module else "未分配模块"
        return f"{m} - {self.task} - {self.training_date:%Y-%m-%d}"

    @property
    def filename(self) -> str:
        """供模板展示的文件名（去掉目录，仅文件名）。"""
        return Path(self.file.name).name if self.file else ''

    # @admin.display(description='文件名')
    # def display_filename(self) -> str:
    #     """供 admin 界面展示的文件名（去掉目录，仅文件名）。"""
    #     return self.filename


# —— 文件生命周期管理 ——
@receiver(post_delete, sender=TrainingLog)
def delete_traininglog_file(sender, instance, **kwargs):
    """
    删除记录后，再尝试删物理文件（post_delete 更稳）。
    """
    if instance.file and instance.file.name:
        storage = instance.file.storage
        if storage.exists(instance.file.name):
            storage.delete(instance.file.name)


@receiver(pre_save, sender=TrainingLog)
def auto_delete_old_file_on_change(sender, instance, **kwargs):
    """
    替换文件时，删除旧文件，避免孤儿文件。
    """
    if not instance.pk:
        return
    try:
        old = TrainingLog.objects.get(pk=instance.pk)
    except TrainingLog.DoesNotExist:
        return
    old_file = getattr(old, "file", None)
    new_file = getattr(instance, "file", None)
    if old_file and getattr(old_file, "name", None):
        if (not new_file) or (old_file.name != getattr(new_file, "name", None)):
            storage = old_file.storage
            if storage.exists(old_file.name):
                storage.delete(old_file.name)
