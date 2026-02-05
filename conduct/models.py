from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from pathlib import Path
from functools import partial

from core.constants import (
    GROUP_COMPETITOR,
    CONDUCT_ALLOWED_EXTENSIONS,
    CONDUCT_UPLOAD_MAX_SIZE_MB,
    CONDUCT_UPLOAD_DIR,
)
from core.utils.validators import validate_file_size, validate_date_not_future
from core.utils.signals import register_file_cleanup_signals


def conduct_attachment_upload_to(instance, filename):
    """
    生成奖惩记录附件上传路径
    格式: CONDUCT_UPLOAD_DIR/username/first_name-YYYYMMDD-ConductType-originalfilename.ext
    其中 CONDUCT_UPLOAD_DIR 定义于 core.constants
    """
    student = instance.student
    user_name = student.username if student else 'unknown'
    first_name = getattr(student, 'first_name', '') or user_name
    date_part = timezone.now().strftime('%Y%m%d')
    
    # 获取record_type名称，处理可能的None情况
    conduct_type_name = 'unknown'
    if hasattr(instance, 'record_type') and instance.record_type:
        conduct_type_name = instance.record_type.name
    
    original_filename = Path(filename).stem
    ext = Path(filename).suffix
    
    # 使用 CONDUCT_UPLOAD_DIR 的基础名称（conduct）作为相对路径基础
    base_dir = CONDUCT_UPLOAD_DIR.name if isinstance(CONDUCT_UPLOAD_DIR, Path) else 'conduct'
    new_filename = f"{first_name}-{date_part}-{conduct_type_name}-{original_filename}{ext}"
    return f"{base_dir}/{user_name}/{new_filename}"


class ConductType(models.Model):
    """奖惩类型模型"""
    
    CATEGORY_CHOICES = [
        ('REWARD', '奖励'),
        ('PENALTY', '惩罚'),
    ]
    
    name = models.CharField('类型名称', max_length=100, unique=True)
    category = models.CharField('分类', max_length=10, choices=CATEGORY_CHOICES)
    score = models.DecimalField(
        '对应分值',
        max_digits=6,
        decimal_places=2,
        help_text='正数为奖励分，负数为惩罚分'
    )
    description = models.TextField('说明', blank=True)
    is_active = models.BooleanField('启用状态', default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_conduct_types',
        verbose_name='创建人'
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '奖惩类型'
        verbose_name_plural = '奖惩类型'
        ordering = ['category', '-score', 'name']
        permissions = [
            ('manage_conduct_types', '管理奖惩类型'),
        ]

    def get_category_display(self):
        """返回分类的中文显示名称"""
        return dict(self.CATEGORY_CHOICES).get(self.category, self.category)

    def __str__(self):
        return f"{self.get_category_display()} - {self.name} ({self.score:+.1f}分)"
    
    def clean(self):
        """验证分值符合类别"""
        if self.category == 'REWARD' and self.score < 0:
            raise ValidationError({'score': '奖励分值应为正数'})
        if self.category == 'PENALTY' and self.score > 0:
            raise ValidationError({'score': '惩罚分值应为负数'})


class ConductRecord(models.Model):
    """奖惩记录模型"""
    
    STATUS_CHOICES = [
        ('PENDING', '待审核'),
        ('APPROVED', '已通过'),
        ('REJECTED', '已驳回'),
    ]
    
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='conduct_records',
        verbose_name='学生',
        limit_choices_to={'groups__name': GROUP_COMPETITOR}
    )
    record_type = models.ForeignKey(
        ConductType,
        on_delete=models.PROTECT,
        related_name='records',
        verbose_name='奖惩类型',
        limit_choices_to={'is_active': True}
    )
    occurred_date = models.DateField(
        '事件发生日期',
        default=timezone.localdate,
        validators=[validate_date_not_future],
        help_text='请填写实际发生日期'
    )
    score = models.DecimalField(
        '实际得分',
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='默认使用选中类型的分值，可微调'
    )
    reason = models.TextField('具体原因/描述')
    attachment = models.FileField(
        '附件',
        upload_to=conduct_attachment_upload_to,
        blank=True,
        null=True,
        help_text=f'支持PDF、图片等格式，文件大小不超过 {CONDUCT_UPLOAD_MAX_SIZE_MB}MB',
        validators=[
            FileExtensionValidator(
                allowed_extensions=CONDUCT_ALLOWED_EXTENSIONS,
                message=f'仅支持以下文件格式: {", ".join(CONDUCT_ALLOWED_EXTENSIONS)}'
            ),
            partial(validate_file_size, max_size_mb=CONDUCT_UPLOAD_MAX_SIZE_MB),
        ]
    )
    status = models.CharField(
        '状态',
        max_length=10,
        choices=STATUS_CHOICES,
        default='PENDING'
    )
    
    # 记录信息
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recorded_conducts',
        verbose_name='记录人'
    )
    recorded_at = models.DateTimeField('记录时间', auto_now_add=True)
    
    # 审核信息
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_conducts',
        verbose_name='审核人'
    )
    reviewed_at = models.DateTimeField('审核时间', null=True, blank=True)
    review_note = models.TextField('审核意见', blank=True)

    class Meta:
        verbose_name = '奖惩记录'
        verbose_name_plural = '奖惩记录'
        ordering = ['-occurred_date', '-recorded_at']
        permissions = [
            ('add_conduct_record', '录入奖惩记录'),
            ('review_conduct_record', '审核奖惩记录'),
            ('view_all_conduct_records', '查看所有奖惩记录'),
        ]

    def __str__(self):
        student_name = getattr(self.student, 'first_name', None) or self.student.username
        return f"{student_name} - {self.record_type.name} - {self.occurred_date}"
    
    @property
    def filename(self):
        """返回去掉路径的文件名"""
        return Path(self.attachment.name).name if self.attachment else ''
    
    def save(self, *args, **kwargs):
        # 如果未设置score，使用类型默认分值
        if self.score is None:
            self.score = self.record_type.score
        super().save(*args, **kwargs)


class ConductSummary(models.Model):
    """学生奖惩汇总模型"""
    
    student = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='conduct_summary',
        verbose_name='学生',
        limit_choices_to={'groups__name': GROUP_COMPETITOR}
    )
    total_score = models.DecimalField(
        '总分',
        max_digits=8,
        decimal_places=2,
        default=0
    )
    reward_count = models.PositiveIntegerField('奖励次数', default=0)
    penalty_count = models.PositiveIntegerField('惩罚次数', default=0)
    last_updated = models.DateTimeField('最后更新时间', auto_now=True)

    class Meta:
        verbose_name = '奖惩汇总'
        verbose_name_plural = '奖惩汇总'
        ordering = ['-total_score']

    def __str__(self):
        student_name = getattr(self.student, 'first_name', None) or self.student.username
        return f"{student_name} - 总分: {self.total_score:+.1f}"
    
    def update_summary(self):
        """更新汇总信息（仅统计已通过的记录）"""
        approved_records = self.student.conduct_records.filter(status='APPROVED')
        
        self.total_score = sum(
            record.score for record in approved_records
        ) or 0
        
        self.reward_count = approved_records.filter(
            record_type__category='REWARD'
        ).count()
        
        self.penalty_count = approved_records.filter(
            record_type__category='PENALTY'
        ).count()
        
        self.save()


# 注册文件清理信号
register_file_cleanup_signals(ConductRecord, 'attachment')


# 自动更新汇总表的信号处理
@receiver(post_save, sender=ConductRecord)
def update_conduct_summary_on_save(sender, instance, **kwargs):
    """当记录状态变为已通过或已驳回时，更新汇总表"""
    if instance.status in ['APPROVED', 'REJECTED']:
        summary, created = ConductSummary.objects.get_or_create(
            student=instance.student
        )
        summary.update_summary()


@receiver(post_delete, sender=ConductRecord)
def update_conduct_summary_on_delete(sender, instance, **kwargs):
    """当记录被删除时，更新汇总表"""
    try:
        summary = ConductSummary.objects.get(student=instance.student)
        summary.update_summary()
    except ConductSummary.DoesNotExist:
        pass
