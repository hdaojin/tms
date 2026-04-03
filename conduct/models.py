from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError
from django.db.models import Count, Q, Sum
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from pathlib import Path
from functools import partial
from decimal import Decimal

from core.constants import (
    GROUP_COMPETITOR,
    CONDUCT_ALLOWED_EXTENSIONS,
    CONDUCT_UPLOAD_MAX_SIZE_MB,
    CONDUCT_UPLOAD_DIR,
    CONDUCT_NATURE_REWARD,
    CONDUCT_NATURE_PENALTY,
    CONDUCT_NATURE_WARNING,
    CONDUCT_NATURE_CHOICES,
)
from core.utils.validators import validate_file_size, validate_date_not_future
from core.utils.signals import register_file_cleanup_signals


class ConductCategory(models.Model):
    """奖惩分类模型（第二层：可添加修改）"""
    
    nature = models.CharField(
        '性质',
        max_length=20,
        choices=CONDUCT_NATURE_CHOICES,
        help_text='行为性质：奖励、惩罚或警告'
    )
    name = models.CharField('分类名称', max_length=50)
    description = models.TextField('说明', blank=True)
    order = models.IntegerField('排序', default=0, help_text='数字越小越靠前')
    is_active = models.BooleanField('启用状态', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '奖惩分类'
        verbose_name_plural = '奖惩分类'
        ordering = ['nature', 'order', 'name']
        unique_together = [['nature', 'name']]

    def __str__(self):
        return f"{self.get_nature_display()} - {self.name}"


class ConductItem(models.Model):
    """奖惩具体事项模型（第三层：可添加修改）"""
    
    category = models.ForeignKey(
        ConductCategory,
        on_delete=models.PROTECT,
        related_name='items',
        verbose_name='所属分类'
    )
    name = models.CharField('事项名称', max_length=100)
    score = models.DecimalField(
        '分值',
        max_digits=6,
        decimal_places=2,
        help_text='奖励为正数，惩罚为负数，警告为0'
    )
    description = models.TextField('说明', blank=True)
    is_active = models.BooleanField('启用状态', default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_conduct_items',
        verbose_name='创建人'
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '奖惩事项'
        verbose_name_plural = '奖惩事项'
        ordering = ['category__nature', 'category__order', '-score', 'name']
        unique_together = [['category', 'name']]

    def __str__(self):
        return f"{self.category.name} - {self.name} ({self.score:+.1f}分)"
    
    def clean(self):
        """验证分值符合性质"""
        if self.category:
            nature = self.category.nature
            # 奖励应为正分
            if nature == CONDUCT_NATURE_REWARD and self.score <= 0:
                raise ValidationError({'score': '奖励类事项的分值应为正数'})
            # 惩罚应为负分
            elif nature == CONDUCT_NATURE_PENALTY and self.score >= 0:
                raise ValidationError({'score': '惩罚类事项的分值应为负数'})
            # 警告应为0分
            elif nature == CONDUCT_NATURE_WARNING and self.score != 0:
                raise ValidationError({'score': '警告类事项的分值应为0'})


def conduct_attachment_upload_to(instance, filename):
    """
    生成奖惩记录附件上传路径
    格式: CONDUCT_UPLOAD_DIR/username/display_name-YYYYMMDD-ItemName-originalfilename.ext
    其中 CONDUCT_UPLOAD_DIR 定义于 core.constants
    """
    student = instance.student
    user_name = student.username if student else 'unknown'
    display_name = getattr(student, 'display_name', user_name) or user_name
    date_part = timezone.now().strftime('%Y%m%d')
    
    # 获取item名称，处理可能的None情况
    item_name = 'unknown'
    if hasattr(instance, 'item') and instance.item:
        item_name = instance.item.name
    
    original_filename = Path(filename).stem
    ext = Path(filename).suffix
    
    # 使用 CONDUCT_UPLOAD_DIR 的基础名称（conduct）作为相对路径基础
    base_dir = CONDUCT_UPLOAD_DIR.name if isinstance(CONDUCT_UPLOAD_DIR, Path) else 'conduct'
    new_filename = f"{display_name}-{date_part}-{item_name}-{original_filename}{ext}"
    return f"{base_dir}/{user_name}/{new_filename}"


class ConductRecord(models.Model):
    """奖惩记录模型"""

    STATUS_PENDING = 'PENDING'
    STATUS_APPROVED = 'APPROVED'
    STATUS_REJECTED = 'REJECTED'
    
    STATUS_CHOICES = [
        (STATUS_PENDING, '待审核'),
        (STATUS_APPROVED, '已通过'),
        (STATUS_REJECTED, '已驳回'),
    ]
    
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='conduct_records',
        verbose_name='学生',
        limit_choices_to={'groups__name': GROUP_COMPETITOR}
    )
    item = models.ForeignKey(
        ConductItem,
        on_delete=models.PROTECT,
        related_name='records',
        verbose_name='奖惩事项',
        limit_choices_to={'is_active': True}
    )
    occurred_date = models.DateField(
        '事件发生日期',
        default=timezone.localdate,
        validators=[validate_date_not_future],
        help_text='请填写实际发生日期'
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
        default=STATUS_PENDING
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
        return f"{self.student.display_name} - {self.item.name} - {self.occurred_date}"

    def clean(self):
        """验证学生范围与审核状态流。"""
        errors = {}

        if self.student and not self.student.groups.filter(name=GROUP_COMPETITOR).exists():
            errors['student'] = '只能为选手组用户录入奖惩记录。'

        if self.status == self.STATUS_PENDING:
            if self.review_note.strip():
                errors['review_note'] = '待审核记录不能填写审核意见。'
            if self.reviewed_by or self.reviewed_at:
                errors['status'] = '待审核记录不能包含审核信息。'

        if self.status == self.STATUS_REJECTED and not self.review_note.strip():
            errors['review_note'] = '驳回时必须填写审核意见。'

        if self.pk:
            original_status = type(self).objects.filter(pk=self.pk).values_list('status', flat=True).first()
            if (
                original_status
                and original_status != self.status
                and original_status != self.STATUS_PENDING
            ):
                errors['status'] = '已审核记录不允许再次变更状态。'

        if errors:
            raise ValidationError(errors)
    
    @property
    def filename(self):
        """返回去掉路径的文件名"""
        return Path(self.attachment.name).name if self.attachment else ''
    
    @property
    def score(self):
        """返回当前奖惩事项分值。历史记录始终跟随事项当前分值。"""
        return self.item.score if self.item else 0


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
        default=Decimal('0')
    )
    reward_count = models.PositiveIntegerField('奖励次数', default=0)
    penalty_count = models.PositiveIntegerField('惩罚次数', default=0)
    last_updated = models.DateTimeField('最后更新时间', auto_now=True)

    class Meta:
        verbose_name = '奖惩汇总'
        verbose_name_plural = '奖惩汇总'
        ordering = ['-total_score']

    def __str__(self):
        return f"{self.student.display_name} - 总分: {self.total_score:+.1f}"
    
    def update_summary(self):
        """更新汇总信息（仅统计已通过的记录）"""
        approved_records = self.student.conduct_records.filter(status=ConductRecord.STATUS_APPROVED)
        stats = approved_records.aggregate(
            total_score=Sum('item__score'),
            reward_count=Count(
                'pk',
                filter=Q(item__category__nature=CONDUCT_NATURE_REWARD),
            ),
            penalty_count=Count(
                'pk',
                filter=Q(item__category__nature=CONDUCT_NATURE_PENALTY),
            ),
        )

        self.total_score = stats['total_score'] or Decimal('0')
        self.reward_count = stats['reward_count'] or 0
        self.penalty_count = stats['penalty_count'] or 0
        
        self.save()


def refresh_conduct_summary(student_id):
    """重算单个学生的奖惩汇总。"""
    summary, _ = ConductSummary.objects.get_or_create(student_id=student_id)
    summary.update_summary()


def refresh_conduct_summaries(student_ids):
    """批量重算多个学生的奖惩汇总。"""
    for student_id in set(student_ids):
        if student_id is not None:
            refresh_conduct_summary(student_id)


# 注册文件清理信号
register_file_cleanup_signals(ConductRecord, 'attachment')


# 自动更新汇总表的信号处理
@receiver(post_save, sender=ConductRecord)
def update_conduct_summary_on_save(sender, instance, **kwargs):
    """当记录状态变为已通过或已驳回时，更新汇总表"""
    if instance.status in [ConductRecord.STATUS_APPROVED, ConductRecord.STATUS_REJECTED]:
        refresh_conduct_summary(instance.student_id)


@receiver(post_delete, sender=ConductRecord)
def update_conduct_summary_on_delete(sender, instance, **kwargs):
    """当记录被删除时，更新汇总表"""
    try:
        summary = ConductSummary.objects.get(student_id=instance.student_id)
        summary.update_summary()
    except ConductSummary.DoesNotExist:
        pass


@receiver(post_save, sender=ConductItem)
def update_conduct_summary_on_item_save(sender, instance, **kwargs):
    """事项分值或分类变化后，重算受影响学生汇总。"""
    student_ids = ConductRecord.objects.filter(
        item=instance,
        status=ConductRecord.STATUS_APPROVED,
    ).values_list('student_id', flat=True).distinct()
    refresh_conduct_summaries(student_ids)


@receiver(post_save, sender=ConductCategory)
def update_conduct_summary_on_category_save(sender, instance, **kwargs):
    """分类性质变化后，重算受影响学生汇总。"""
    student_ids = ConductRecord.objects.filter(
        item__category=instance,
        status=ConductRecord.STATUS_APPROVED,
    ).values_list('student_id', flat=True).distinct()
    refresh_conduct_summaries(student_ids)
