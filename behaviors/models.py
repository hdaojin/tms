from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from pathlib import Path
from decimal import Decimal

from core.constants import (
    GROUP_COMPETITOR,
    BEHAVIORS_UPLOAD_DIR,
    CONDUCT_NATURE_REWARD,
    CONDUCT_NATURE_PENALTY,
    CONDUCT_NATURE_CHOICES,
    CONDUCT_SEVERITY_CHOICES,
    CONDUCT_SEVERITY_MODERATE,
    CONDUCT_SEVERITY_NAMES,
    CONDUCT_REWARD_SEVERITY_NAMES,
    CONDUCT_PENALTY_SEVERITY_NAMES,
)
from core.models import AuditedModel
from core.uploads import CONDUCT_ATTACHMENT_UPLOAD_SPEC
from core.utils.validators import validate_date_not_future
from core.utils.signals import register_file_cleanup_signals


def format_conduct_score(value):
    """统一格式化分值，零分不显示正负号。"""
    if value == 0:
        return '0.00'

    return f'{value:+.2f}'


def get_conduct_severity_name(nature, severity):
    """按事项性质返回对应的严重程度文案。"""
    if nature == CONDUCT_NATURE_REWARD:
        return CONDUCT_REWARD_SEVERITY_NAMES.get(severity, CONDUCT_SEVERITY_NAMES.get(severity, severity))

    if nature == CONDUCT_NATURE_PENALTY:
        return CONDUCT_PENALTY_SEVERITY_NAMES.get(severity, CONDUCT_SEVERITY_NAMES.get(severity, severity))

    return CONDUCT_SEVERITY_NAMES.get(severity, severity)


def get_conduct_severity_choices(nature=None):
    """按事项性质返回对应的程度选项。"""
    return [
        (code, get_conduct_severity_name(nature, code))
        for code, _label in CONDUCT_SEVERITY_CHOICES
    ]


def get_conduct_severity_choices_with_multiplier(nature):
    """按事项性质返回程度选项，同时显示系数。"""
    rules = dict(
        ConductSeverityRule.objects.filter(nature=nature)
        .values_list('severity', 'multiplier')
    )
    choices = []
    for code, _label in CONDUCT_SEVERITY_CHOICES:
        name = get_conduct_severity_name(nature, code)
        multiplier = rules.get(code)
        if multiplier is not None:
            label = f"{name}（×{multiplier:.2f}）"
        else:
            label = name
        choices.append((code, label))
    return choices


class ConductCategory(AuditedModel):
    """奖惩分类模型（第二层：可添加修改）"""
    
    nature = models.CharField(
        '性质',
        max_length=20,
        choices=CONDUCT_NATURE_CHOICES,
        help_text='行为性质：奖励、惩罚'
    )
    name = models.CharField('分类名称', max_length=50)
    description = models.TextField('说明', blank=True)
    order = models.IntegerField('排序', default=0, help_text='数字越小越靠前')
    is_active = models.BooleanField('启用状态', default=True)

    class Meta:
        verbose_name = '奖惩分类'
        verbose_name_plural = '奖惩分类'
        ordering = ['nature', 'order', 'name']
        unique_together = [['nature', 'name']]

    def __str__(self):
        return f"{self.get_nature_display()} - {self.name}"


class ConductSeverityRule(AuditedModel):
    """按性质和严重程度定义统一的计分系数。"""

    nature = models.CharField(
        '性质',
        max_length=20,
        choices=CONDUCT_NATURE_CHOICES,
    )
    severity = models.CharField(
        '程度',
        max_length=20,
        choices=CONDUCT_SEVERITY_CHOICES,
    )
    multiplier = models.DecimalField(
        '系数',
        max_digits=4,
        decimal_places=2,
        help_text='当前分值 = 事项默认分值 × 严重程度系数。',
    )
    order = models.IntegerField('排序', default=0, help_text='数字越小越靠前')

    class Meta:
        verbose_name = '严重程度系数规则'
        verbose_name_plural = '严重程度系数规则'
        ordering = ['nature', 'order', 'severity']
        unique_together = [['nature', 'severity']]

    def __str__(self):
        return f"{self.get_nature_display()} - {self.severity_label} ({self.multiplier:.2f}倍)"

    @property
    def severity_label(self):
        """返回按性质映射后的严重程度文案。"""
        return get_conduct_severity_name(self.nature, self.severity)

    def clean(self):
        """严重程度系数不能为负数。"""
        if self.multiplier < 0:
            raise ValidationError({'multiplier': '严重程度系数不能为负数。'})

    @classmethod
    def get_multiplier(cls, nature, severity):
        if not nature or not severity:
            return None

        return cls.objects.filter(
            nature=nature,
            severity=severity,
        ).values_list('multiplier', flat=True).first()


class ConductItem(AuditedModel):
    """奖惩具体事项模型（第三层：可添加修改）"""
    
    category = models.ForeignKey(
        ConductCategory,
        on_delete=models.PROTECT,
        related_name='items',
        verbose_name='所属分类'
    )
    name = models.CharField('事项名称', max_length=100)
    default_score = models.DecimalField(
        '默认分值',
        max_digits=6,
        decimal_places=2,
        help_text='一般情形下的基础分值。当前分值 = 默认分值 × 严重程度系数。',
    )
    description = models.TextField('说明', blank=True)
    is_active = models.BooleanField('启用状态', default=True)

    class Meta:
        verbose_name = '奖惩事项'
        verbose_name_plural = '奖惩事项'
        ordering = ['category__nature', 'category__order', 'name']
        unique_together = [['category', 'name']]

    def __str__(self):
        return f"{self.category.name} - {self.name} ({self.default_score:+.1f}分)"

    def clean(self):
        """验证默认分值符合事项性质。"""
        if not self.category_id:
            return

        if self.category.nature == CONDUCT_NATURE_REWARD and self.default_score <= 0:
            raise ValidationError({'default_score': '奖励类事项的默认分值应为正数。'})

        if self.category.nature == CONDUCT_NATURE_PENALTY and self.default_score >= 0:
            raise ValidationError({'default_score': '惩罚类事项的默认分值应为负数。'})


def conduct_attachment_upload_to(instance, filename):
    """
    生成奖惩记录附件上传路径
    格式: BEHAVIORS_UPLOAD_DIR/username/display_name-YYYYMMDD-ItemName-originalfilename.ext
    其中 BEHAVIORS_UPLOAD_DIR 定义于 core.constants
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
    
    # 使用 behaviors 作为相对路径基础目录
    base_dir = BEHAVIORS_UPLOAD_DIR.name if isinstance(BEHAVIORS_UPLOAD_DIR, Path) else 'behaviors'
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
    severity = models.CharField(
        '严重程度',
        max_length=20,
        choices=CONDUCT_SEVERITY_CHOICES,
        default=CONDUCT_SEVERITY_MODERATE,
        help_text='当前分值 = 事项默认分值 × 严重程度系数',
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
        help_text=CONDUCT_ATTACHMENT_UPLOAD_SPEC.help_text('上传奖惩附件'),
        validators=CONDUCT_ATTACHMENT_UPLOAD_SPEC.validators(),
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
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_conduct_records',
        verbose_name='更新人'
    )
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    
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
        return f"{self.student.display_name} - {self.item.name} - {self.severity_label} - {self.occurred_date}"

    @property
    def severity_label(self):
        """返回按事项性质映射后的严重程度文案。"""
        if not self.severity:
            return ''

        nature = self.item.category.nature if self.item_id else None
        return get_conduct_severity_name(nature, self.severity)

    def clean(self):
        """验证学生范围与审核状态流。"""
        errors = {}

        if self.student and not self.student.groups.filter(name=GROUP_COMPETITOR).exists():
            errors['student'] = '只能为选手组用户录入奖惩记录。'

        if self.item and self.severity:
            has_rule = ConductSeverityRule.objects.filter(
                nature=self.item.category.nature,
                severity=self.severity,
            ).exists()
            if not has_rule:
                errors['severity'] = '当前事项性质下未配置该严重程度的系数规则。'

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

    def get_multiplier(self, rule_map=None):
        """根据事项性质和严重程度解析当前系数。"""
        if not self.item_id:
            return Decimal('0')

        if not self.severity:
            return Decimal('1')

        nature = self.item.category.nature
        if rule_map is not None:
            return rule_map.get((nature, self.severity), Decimal('0'))

        multiplier = ConductSeverityRule.get_multiplier(nature, self.severity)
        return multiplier if multiplier is not None else Decimal('0')

    def get_score(self, rule_map=None):
        """根据默认分值和严重程度系数计算当前分值。"""
        if not self.item_id:
            return Decimal('0')

        base_score = self.item.default_score
        if not self.severity:
            return base_score

        score = base_score * self.get_multiplier(rule_map=rule_map)
        return Decimal('0') if score == 0 else score

    @property
    def score_formula(self):
        """返回用于展示的计分公式。"""
        if not self.item_id:
            return ''

        base_score = self.item.default_score
        if not self.severity:
            return format_conduct_score(base_score)

        multiplier = self.get_multiplier()
        return f'{format_conduct_score(base_score)} x {multiplier:.2f} = {format_conduct_score(self.score)}'
    
    @property
    def score(self):
        """返回当前默认分值和严重程度系数对应的分值。"""
        return self.get_score()


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
        approved_records = self.student.conduct_records.filter(
            status=ConductRecord.STATUS_APPROVED,
        ).select_related('item__category')
        rule_map = {
            (rule.nature, rule.severity): rule.multiplier
            for rule in ConductSeverityRule.objects.all()
        }

        total_score = Decimal('0')
        reward_count = 0
        penalty_count = 0

        for record in approved_records:
            total_score += record.get_score(rule_map=rule_map)
            if record.item.category.nature == CONDUCT_NATURE_REWARD:
                reward_count += 1
            elif record.item.category.nature == CONDUCT_NATURE_PENALTY:
                penalty_count += 1

        self.total_score = total_score
        self.reward_count = reward_count
        self.penalty_count = penalty_count

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
    """事项或所属分类变化后，重算受影响学生汇总。"""
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


@receiver(post_save, sender=ConductSeverityRule)
def update_conduct_summary_on_rule_save(sender, instance, **kwargs):
    """分值规则变化后，重算受影响学生汇总。"""
    student_ids = ConductRecord.objects.filter(
        item__category__nature=instance.nature,
        severity=instance.severity,
        status=ConductRecord.STATUS_APPROVED,
    ).values_list('student_id', flat=True).distinct()
    refresh_conduct_summaries(student_ids)


@receiver(post_delete, sender=ConductSeverityRule)
def update_conduct_summary_on_rule_delete(sender, instance, **kwargs):
    """分值规则删除后，重算受影响学生汇总。"""
    student_ids = ConductRecord.objects.filter(
        item__category__nature=instance.nature,
        severity=instance.severity,
        status=ConductRecord.STATUS_APPROVED,
    ).values_list('student_id', flat=True).distinct()
    refresh_conduct_summaries(student_ids)
