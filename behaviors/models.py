from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.models import AuditedModel
from core.uploads import CONDUCT_ATTACHMENT_UPLOAD_SPEC, PrivateMediaStorage
from core.utils.signals import register_file_cleanup_signals
from core.utils.validators import validate_date_not_future


class ConductNature(models.TextChoices):
    REWARD = 'REWARD', '奖励'
    PENALTY = 'PENALTY', '惩罚'


def format_conduct_score(value):
    """统一格式化分值，零分不显示正负号。"""
    if value == 0:
        return '0.00'

    result = f'{value:+.4f}'
    whole, fraction = result.split('.')
    return f'{whole}.{fraction.rstrip('0').ljust(2, '0')}'


class ConductSeverity(models.Model):
    code = models.CharField('程度代码', max_length=20, unique=True)
    name = models.CharField('程度名称', max_length=50)
    description = models.TextField('说明', blank=True)
    is_active = models.BooleanField('启用状态', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '奖惩严重程度'
        verbose_name_plural = '奖惩严重程度'
        ordering = ['code']

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.pk and not self.is_active and self.rules.filter(is_default=True).exists():
            raise ValidationError({
                'is_active': '该严重程度仍被奖惩性质用作默认项，请先调整对应系数规则。',
            })


class ConductCategory(AuditedModel):
    """奖惩分类模型（第二层：可添加修改）"""

    code = models.CharField('分类代码', max_length=64, unique=True)
    nature = models.CharField(
        '性质',
        max_length=20,
        choices=ConductNature.choices,
        help_text='行为性质：奖励、惩罚',
    )
    name = models.CharField('分类名称', max_length=50)
    description = models.TextField('说明', blank=True)
    order = models.IntegerField('排序', default=0, help_text='数字越小越靠前')
    is_active = models.BooleanField('启用状态', default=True)

    class Meta:
        verbose_name = '奖惩分类'
        verbose_name_plural = '奖惩分类'
        permissions = [
            ('change_conductcatalog', '可以维护奖惩目录（原周期授权）'),
            ('manage_global_conduct_catalog', '可以维护全局奖惩配置'),
        ]
        ordering = ['nature', 'order', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['nature', 'name'],
                name='uniq_conduct_category_nature_name',
            ),
        ]

    def __str__(self):
        return f'{self.nature_label} - {self.name}'

    @property
    def nature_label(self):
        if self.nature in ConductNature.values:
            return self.get_nature_display()
        return f'{self.nature or "空值"}（历史）'


class ConductSeverityRule(AuditedModel):
    """按性质和严重程度定义统一的计分系数。"""

    nature = models.CharField(
        '性质',
        max_length=20,
        choices=ConductNature.choices,
    )
    severity = models.ForeignKey(
        ConductSeverity,
        verbose_name='程度',
        on_delete=models.PROTECT,
        related_name='rules',
    )
    label = models.CharField('显示名称', max_length=50)
    multiplier = models.DecimalField(
        '系数',
        max_digits=4,
        decimal_places=2,
        help_text='供条例草稿选用。',
    )
    order = models.IntegerField('排序', default=0, help_text='数字越小越靠前')
    is_default = models.BooleanField('默认程度', default=False)
    is_active = models.BooleanField('启用状态', default=True)

    class Meta:
        verbose_name = '严重程度系数规则'
        verbose_name_plural = '严重程度系数规则'
        ordering = ['nature', 'order', 'severity']
        constraints = [
            models.UniqueConstraint(
                fields=['nature', 'severity'],
                name='uniq_conduct_severity_rule_nature_severity',
            ),
            models.UniqueConstraint(
                fields=['nature'],
                condition=Q(is_default=True),
                name='uniq_default_conduct_severity_rule_per_nature',
            ),
            models.CheckConstraint(
                condition=Q(is_default=False) | Q(is_active=True),
                name='conduct_default_rate_active',
            ),
            models.CheckConstraint(
                condition=Q(multiplier__gte=0),
                name='conduct_severity_rule_multiplier_nonnegative',
            ),
        ]

    def __str__(self):
        return f'{self.nature_label} - {self.label} ({self.multiplier:.2f}倍)'

    @property
    def nature_label(self):
        if self.nature in ConductNature.values:
            return self.get_nature_display()
        return f'{self.nature or "空值"}（历史）'

    @property
    def severity_label(self):
        return self.label

    def clean(self):
        if self.multiplier is not None and self.multiplier < 0:
            raise ValidationError({'multiplier': '严重程度系数不能为负数。'})
        if self.is_default and self.severity_id and not (self.is_active and self.severity.is_active):
            raise ValidationError({'severity': '默认规则必须关联已启用的严重程度。'})



def get_conduct_severity_rules(nature):
    return ConductSeverityRule.objects.filter(
        nature=nature, is_active=True, severity__is_active=True,
    ).select_related('severity').order_by('order', 'severity__code')


def get_default_conduct_severity(nature):
    return (
        get_conduct_severity_rules(nature).filter(is_default=True)
        .first()
    )


class ConductItem(AuditedModel):
    """奖惩具体事项模型（第三层：可添加修改）"""

    category = models.ForeignKey(
        ConductCategory,
        on_delete=models.PROTECT,
        related_name='items',
        verbose_name='所属分类'
    )
    code = models.CharField('事项代码', max_length=64)
    name = models.CharField('事项名称', max_length=100)
    default_score = models.DecimalField(
        '基准分',
        max_digits=6,
        decimal_places=2,
        help_text='作为新增条例事项的初始基准分。',
    )
    description = models.TextField('说明', blank=True)
    is_active = models.BooleanField('启用状态', default=True)

    class Meta:
        verbose_name = '奖惩事项'
        verbose_name_plural = '奖惩事项'
        ordering = ['category__nature', 'category__order', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['category', 'name'],
                name='uniq_conduct_item_category_name',
            ),
            models.UniqueConstraint(
                fields=['category', 'code'],
                name='uniq_conduct_item_category_code',
            ),
        ]

    def __str__(self):
        return f"{self.category.name} - {self.name} ({self.default_score:+.1f}分)"

    def clean(self):
        """验证默认分值符合事项性质。"""
        if not self.category_id or self.default_score is None:
            return

        if self.category.nature == ConductNature.REWARD and self.default_score <= 0:
            raise ValidationError({'default_score': '奖励类事项的默认分值应为正数。'})

        if self.category.nature == ConductNature.PENALTY and self.default_score >= 0:
            raise ValidationError({'default_score': '惩罚类事项的默认分值应为负数。'})


def conduct_attachment_upload_to(instance, filename):
    """
    生成奖惩记录附件上传路径
    格式: username/display_name-YYYYMMDD-ItemName-originalfilename.ext
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
    
    new_filename = f"{display_name}-{date_part}-{item_name}-{original_filename}{ext}"
    return f"{user_name}/{new_filename}"


class ConductRecord(models.Model):
    """奖惩记录模型"""

    class Status(models.TextChoices):
        PENDING = 'PENDING', '待审核'
        APPROVED = 'APPROVED', '已通过'
        REJECTED = 'REJECTED', '已驳回'
        VOID = 'VOID', '已作废'

    cycle = models.ForeignKey(
        'training.TrainingCycle', models.PROTECT, null=True, blank=True, verbose_name='训练周期',
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, models.PROTECT, related_name='conduct_records', verbose_name='学员',
    )
    item = models.ForeignKey(
        ConductItem, models.PROTECT, related_name='records', verbose_name='奖惩事项',
    )
    severity = models.ForeignKey(
        ConductSeverity, models.PROTECT, null=True, blank=True, related_name='records', verbose_name='程度',
    )
    rule = models.ForeignKey(
        'ConductPolicyRule', models.PROTECT, null=True, blank=True, verbose_name='条例分档',
    )
    source_cycle_record_id = models.PositiveBigIntegerField(null=True, unique=True, editable=False)
    submission_key = models.UUIDField(null=True, editable=False)
    quantity = models.PositiveIntegerField('计分数量', default=1)
    frozen_points = models.DecimalField('实际积分', max_digits=16, decimal_places=4, editable=False)
    frozen_nature = models.CharField('奖惩性质', max_length=20, blank=True, editable=False)
    category_label = models.CharField('记录时分类名称', max_length=100, editable=False)
    item_label = models.CharField('记录时事项名称', max_length=255, editable=False)
    severity_label = models.CharField('记录时程度或分档', max_length=255, blank=True, editable=False)
    occurred_date = models.DateField(
        '事件发生日期',
        default=timezone.localdate,
        validators=[validate_date_not_future],
        help_text='请填写实际发生日期'
    )
    reason = models.TextField('具体原因/描述')
    attachment = models.FileField(
        '附件',
        storage=PrivateMediaStorage("behaviors"),
        upload_to=conduct_attachment_upload_to,
        blank=True,
        null=True,
        help_text=CONDUCT_ATTACHMENT_UPLOAD_SPEC.help_text('上传奖惩附件'),
        validators=CONDUCT_ATTACHMENT_UPLOAD_SPEC.validators(),
    )
    status = models.CharField(
        '状态',
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
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
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, models.SET_NULL, null=True, related_name='+', verbose_name='作废人',
    )
    voided_at = models.DateTimeField('作废时间', null=True)
    void_note = models.TextField('作废原因', blank=True)

    class Meta:
        verbose_name = '奖惩记录'
        verbose_name_plural = '奖惩记录'
        ordering = ['-occurred_date', '-recorded_at', '-pk']
        permissions = [
            ('be_conduct_subject', '可作为奖惩对象'),
            ('add_conduct_record', '录入奖惩记录'),
            ('review_conduct_record', '审核奖惩记录'),
            ('view_all_conduct_records', '查看所有奖惩记录'),
        ]
        indexes = [models.Index(fields=['cycle', 'status', 'student'], name='conduct_ledger_cycle_status')]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gt=0), name='conduct_ledger_positive_quantity'),
            models.UniqueConstraint(fields=['submission_key', 'student'], name='conduct_ledger_submission_student'),
            models.CheckConstraint(
                condition=Q(cycle__isnull=True, rule__isnull=True, submission_key__isnull=True)
                | Q(cycle__isnull=False, rule__isnull=False, submission_key__isnull=False),
                name='conduct_ledger_cycle_fields',
            ),
        ]

    def __str__(self):
        return f'{self.student.display_name} · {self.item_label} · {self.occurred_date}'

    @property
    def nature_label(self):
        return ConductNature(self.frozen_nature).label if self.frozen_nature in ConductNature else self.frozen_nature

    @property
    def score_formula(self):
        if not self.rule_id or self.rule.points * self.quantity != self.frozen_points:
            return format_conduct_score(self.frozen_points)
        return (
            f'{format_conduct_score(self.rule.policy_item.base_score)} × {self.rule.multiplier:.2f}'
            f' × {self.quantity} = {format_conduct_score(self.frozen_points)}'
        )


register_file_cleanup_signals(ConductRecord, 'attachment', delete_on_commit=True)


class ConductSummary(models.Model):
    """旧汇总表保留用于升级兼容，当前汇总直接查询奖惩账本。"""
    
    student = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='conduct_summary',
        verbose_name='学生',
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
    


class ConductCycleAssignment(AuditedModel):
    cycle = models.ForeignKey('training.TrainingCycle', models.PROTECT, verbose_name='训练周期')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, models.PROTECT, verbose_name='经办人')
    can_enter = models.BooleanField('录入', default=False)
    can_review = models.BooleanField('审核', default=False)
    can_write = models.BooleanField('编写条例', default=False)
    can_publish = models.BooleanField('发布条例', default=False)

    class Meta:
        verbose_name = '周期奖惩分工'
        constraints = [
            models.UniqueConstraint(fields=['cycle', 'user'], name='unique_conduct_cycle_assignment'),
        ]


class ConductPolicy(AuditedModel):
    cycle = models.ForeignKey('training.TrainingCycle', models.PROTECT, verbose_name='训练周期')
    title = models.CharField('条例标题', max_length=200)
    issuer = models.CharField('发布单位', max_length=150)
    body = models.TextField('正文', help_text='支持 Markdown 章节、条款和表格。')
    change_note = models.TextField('变更说明', blank=True)
    effective_date = models.DateField('生效日期')
    published_at = models.DateTimeField('发布时间', null=True, editable=False)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, models.SET_NULL, null=True, editable=False,
        related_name='+', verbose_name='发布人',
    )

    class Meta:
        verbose_name = '班级管理条例版本'
        ordering = ['-effective_date', '-pk']
        permissions = [('publish_conductpolicy', '可以发布班级管理条例')]
        constraints = [
            models.UniqueConstraint(
                fields=['cycle', 'effective_date'], condition=models.Q(published_at__isnull=False),
                name='unique_published_conduct_policy_date',
            ),
        ]

    @property
    def rules(self):
        return ConductPolicyRule.objects.filter(policy_item__policy=self)

    def __str__(self):
        return self.title


class ConductPolicyItem(AuditedModel):
    policy = models.ForeignKey(ConductPolicy, models.PROTECT, related_name='policy_items', verbose_name='条例版本')
    item = models.ForeignKey(ConductItem, models.PROTECT, verbose_name='奖惩事项')
    base_score = models.DecimalField('基准分', max_digits=8, decimal_places=2)

    class Meta:
        verbose_name = '条例事项'
        verbose_name_plural = '条例事项'
        constraints = [models.UniqueConstraint(fields=['policy', 'item'], name='conduct_policy_unique_item')]

    def clean(self):
        if self.item_id and self.base_score is not None:
            nature = self.item.category.nature
            if not (
                (nature == ConductNature.REWARD and self.base_score > 0)
                or (nature == ConductNature.PENALTY and self.base_score < 0)
            ):
                raise ValidationError({'base_score': '基准分的正负必须与事项性质一致。'})

    def __str__(self):
        return f'{self.item.category.name} · {self.item.name}'


class ConductPolicyRule(AuditedModel):
    class Section(models.TextChoices):
        COMPETITION = 'competition', '竞赛奖励'
        MANAGEMENT = 'management', '日常管理'
        LEARNING = 'learning', '日常学习'

    policy_item = models.ForeignKey(ConductPolicyItem, models.PROTECT, related_name='rules', verbose_name='条例事项')
    severity = models.ForeignKey(
        ConductSeverity, models.PROTECT, null=True, blank=True, verbose_name='通用程度',
    )
    section = models.CharField('积分板块', max_length=12, choices=Section.choices)
    condition = models.CharField('程度或分档名称', max_length=255)
    multiplier = models.DecimalField('倍率', max_digits=8, decimal_places=2)
    unit = models.CharField('计分单位', max_length=30, blank=True, help_text='留空表示每次固定分值。')
    order = models.PositiveIntegerField('排序', default=0)
    item_label = models.CharField('发布时事项名称', max_length=255, editable=False)
    category_label = models.CharField('发布时分类名称', max_length=100, editable=False)

    class Meta:
        verbose_name = '条例计分分档'
        verbose_name_plural = '条例计分分档'
        ordering = ['order', 'pk']
        constraints = [models.CheckConstraint(condition=Q(multiplier__gte=0), name='conduct_policy_nonnegative_rate')]

    @property
    def points(self):
        return self.policy_item.base_score * self.multiplier

    def __str__(self):
        name = self.item_label or self.policy_item.item.name
        return f'{name} · {self.condition}（{format_conduct_score(self.points)}分）'

    def clean(self):
        if self.multiplier is not None and self.multiplier < 0:
            raise ValidationError({'multiplier': '倍率不能为负数。'})
        if (
            self.section == self.Section.COMPETITION and self.policy_item_id
            and self.multiplier is not None and self.points < 0
        ):
            raise ValidationError({'section': '竞赛奖励积分不能为负数。'})
