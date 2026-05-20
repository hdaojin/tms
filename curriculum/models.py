from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


DEFAULT_MODULE_SET_CODE = 'default'
DEFAULT_MODULE_SET_NAME = '默认标准模块集'


class Level(models.TextChoices):
    INTERNATIONAL = 'international', '世界级'
    NATIONAL = 'national', '国家级'
    PROVINCIAL = 'provincial', '省级'
    MUNICIPAL = 'municipal', '市级'
    DISTRICT = 'district', '区级'
    SCHOOL = 'school', '校级'
    CLASS = 'class', '班级'
    OTHER = 'other', '其他'


class StandardModuleSetQuerySet(models.QuerySet):
    def current(self):
        return self.filter(is_current=True)


class StandardModuleQuerySet(models.QuerySet):
    def current(self):
        return self.filter(module_set__is_current=True)


class CompetitionType(models.Model):
    """竞赛类型。"""

    code = models.CharField("赛事代码", max_length=50, unique=True, help_text="用于标识竞赛的唯一代码，如WSC或WorldSkills")
    name = models.CharField("赛事名称", max_length=100, unique=True)
    level = models.CharField("级别", choices=Level.choices, default=Level.INTERNATIONAL, max_length=20, help_text="竞赛的级别")
    weight = models.DecimalField(
        "权重",
        max_digits=2,
        decimal_places=1,
        default=Decimal("7.0"),
        help_text="用于统计该竞赛所涉考点的重要性，数值越大表示该竞赛所涉考点越重要，取值范围0.0-7.0，原则上与竞赛级别对应。",
        validators=[
            MinValueValidator(Decimal("0.0")),
            MaxValueValidator(Decimal("7.0")),
        ],
    )
    description = models.TextField("描述", blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = '竞赛类型'
        verbose_name_plural = '竞赛类型'
        ordering = ['level', 'name']

    def __str__(self):
        return self.name


class Project(models.Model):
    """竞赛项目标准库。"""

    competition_type = models.ForeignKey(
        CompetitionType,
        verbose_name="所属竞赛类型",
        on_delete=models.PROTECT,
        related_name='projects',
    )
    code = models.CharField("项目代码", max_length=50, help_text="同一竞赛类型下唯一，如ITNSA")
    name = models.CharField("项目名称", max_length=100)
    description = models.TextField("描述", blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = '竞赛项目'
        verbose_name_plural = '竞赛项目'
        ordering = ['competition_type', 'name', 'code']
        constraints = [
            models.UniqueConstraint(fields=['competition_type', 'code'], name='unique_project_code_within_competition_type'),
        ]

    def __str__(self):
        return f"{self.competition_type.name} / {self.name} ({self.code})"

    @property
    def standard_module_sets(self):
        return self.module_sets

    @property
    def standard_modules(self):
        return self.modules

    @property
    def current_standard_module_set(self):
        return self.module_sets.current().order_by('sort_order', 'pk').first()

    def get_or_create_default_standard_module_set(self):
        current_standard_module_set = self.current_standard_module_set
        if current_standard_module_set is not None:
            return current_standard_module_set

        module_set, created = self.module_sets.get_or_create(
            code=DEFAULT_MODULE_SET_CODE,
            defaults={
                'name': DEFAULT_MODULE_SET_NAME,
                'description': '系统自动创建的默认标准模块集。',
                'sort_order': 0,
                'is_current': True,
            },
        )
        if not created and not module_set.is_current:
            self.module_sets.filter(is_current=True).exclude(pk=module_set.pk).update(is_current=False)
            module_set.is_current = True
            module_set.save(update_fields=['is_current', 'updated_at'])
        return module_set

    def get_current_standard_modules_queryset(self):
        current_standard_module_set = self.current_standard_module_set
        if current_standard_module_set is None:
            return self.modules.none()
        return current_standard_module_set.modules.all()


class StandardModuleSet(models.Model):
    project = models.ForeignKey(
        Project,
        verbose_name="所属竞赛项目",
        on_delete=models.CASCADE,
        related_name='module_sets',
    )
    code = models.CharField("模块集代码", max_length=50, help_text="同一项目下唯一，用于标识某一版标准模块集。")
    name = models.CharField("模块集名称", max_length=100, help_text="例如：2025 版标准模块、2026 版标准模块。")
    description = models.TextField("描述", blank=True)
    sort_order = models.PositiveIntegerField("显示顺序", default=0, help_text="数值越小越靠前显示。")
    is_current = models.BooleanField("当前启用", default=False, help_text="同一项目同一时刻只允许一套当前启用的标准模块集。")
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    objects = StandardModuleSetQuerySet.as_manager()

    class Meta:
        verbose_name = '标准模块集'
        verbose_name_plural = '标准模块集'
        ordering = ['project', '-is_current', 'sort_order', 'name']
        constraints = [
            models.UniqueConstraint(fields=['project', 'code'], name='unique_module_set_code_within_project'),
            models.UniqueConstraint(
                fields=['project'],
                condition=models.Q(is_current=True),
                name='unique_current_module_set_per_project',
            ),
        ]

    def save(self, *args, **kwargs):
        if self.is_current and self.project_id:
            type(self).objects.filter(project_id=self.project_id, is_current=True).exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)

    def __str__(self):
        suffix = '（当前）' if self.is_current else ''
        return f"{self.project.name} / {self.name}{suffix}"


class ModuleAxis(models.Model):
    project = models.ForeignKey(
        Project,
        verbose_name='所属竞赛项目',
        on_delete=models.CASCADE,
        related_name='module_axes',
    )
    code = models.CharField('主线代码', max_length=50, help_text='同一项目下唯一，用于标识能力主线。')
    name = models.CharField('主线名称', max_length=100)
    description = models.TextField('描述', blank=True)
    sort_order = models.PositiveIntegerField('显示顺序', default=0, help_text='数值越小越靠前显示。')
    is_active = models.BooleanField('启用', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('最后更新时间', auto_now=True)

    class Meta:
        verbose_name = '模块主线'
        verbose_name_plural = '模块主线'
        ordering = ['project', 'sort_order', 'code', 'name']
        constraints = [
            models.UniqueConstraint(fields=['project', 'code'], name='unique_module_axis_code_within_project'),
        ]

    def __str__(self):
        return f"{self.project.name} / {self.code} - {self.name}"


class StandardModule(models.Model):
    """标准模块（隶属于标准项目 Project）。"""

    project = models.ForeignKey(
        Project,
        verbose_name="所属竞赛项目",
        on_delete=models.CASCADE,
        related_name='modules',
    )
    module_set = models.ForeignKey(
        StandardModuleSet,
        verbose_name="所属标准模块集",
        on_delete=models.PROTECT,
        related_name='modules',
    )
    code = models.CharField("编号", max_length=50)
    name = models.CharField("名称", max_length=100)
    description = models.TextField("描述", blank=True)
    default_counts_towards_ranking = models.BooleanField(
        "默认计入排名分",
        default=True,
        help_text="新建考核模块时默认继承此设置。",
    )
    sort_order = models.PositiveIntegerField("显示顺序", default=0, help_text="数值越小越靠前显示。")
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    objects = StandardModuleQuerySet.as_manager()

    class Meta:
        verbose_name = '标准模块'
        verbose_name_plural = '标准模块'
        ordering = ['project', 'module_set__sort_order', 'sort_order', 'code', 'name']
        unique_together = ['module_set', 'code']

    def clean(self):
        if self.module_set_id and self.project_id and self.module_set.project_id != self.project_id:
            raise ValidationError({'module_set': '所选标准模块集不属于当前竞赛项目。'})

    def save(self, *args, **kwargs):
        if not self.module_set_id and self.project_id:
            self.module_set = self.project.get_or_create_default_standard_module_set()
        if self.module_set_id and self.project_id and self.module_set.project_id != self.project_id:
            raise ValidationError({'module_set': '所选标准模块集不属于当前竞赛项目。'})
        super().save(*args, **kwargs)

    @property
    def is_current(self):
        return self.module_set.is_current

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def standard_module_set(self):
        return self.module_set

    @property
    def primary_axis(self):
        primary_mapping = self.axis_mappings.filter(is_primary=True).select_related('module_axis').first()
        if primary_mapping is not None:
            return primary_mapping.module_axis
        first_mapping = self.axis_mappings.select_related('module_axis').first()
        return first_mapping.module_axis if first_mapping is not None else None


class StandardModuleAxisMap(models.Model):
    module = models.ForeignKey(
        StandardModule,
        on_delete=models.CASCADE,
        related_name='axis_mappings',
        verbose_name='标准模块',
    )
    module_axis = models.ForeignKey(
        ModuleAxis,
        on_delete=models.PROTECT,
        related_name='standard_module_mappings',
        verbose_name='模块主线',
    )
    is_primary = models.BooleanField('主映射', default=False, help_text='用于标识该标准模块当前主要归属的模块主线。')
    weight = models.DecimalField(
        '权重',
        max_digits=5,
        decimal_places=2,
        default=Decimal('1.00'),
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='用于表示该标准模块映射到该模块主线时的相对权重。',
    )
    note = models.TextField('备注', blank=True)

    class Meta:
        verbose_name = '标准模块主线映射'
        verbose_name_plural = '标准模块主线映射'
        unique_together = ['module', 'module_axis']
        ordering = ['module', '-is_primary', 'module_axis__sort_order', 'module_axis__code', 'pk']
        constraints = [
            models.UniqueConstraint(
                fields=['module'],
                condition=models.Q(is_primary=True),
                name='unique_primary_axis_mapping_per_standard_module',
            ),
        ]

    def clean(self):
        if self.module_id and self.module_axis_id and self.module.project_id != self.module_axis.project_id:
            raise ValidationError({'module_axis': '模块主线必须属于当前标准模块对应的竞赛项目。'})
        if self.is_primary and self.module_id:
            existing_primary = type(self).objects.filter(module_id=self.module_id, is_primary=True).exclude(pk=self.pk)
            if existing_primary.exists():
                raise ValidationError({'is_primary': '同一标准模块只能设置一个主映射。'})

    def save(self, *args, **kwargs):
        if self.module_id and self.module_axis_id and self.module.project_id != self.module_axis.project_id:
            raise ValidationError({'module_axis': '模块主线必须属于当前标准模块对应的竞赛项目。'})
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.module} -> {self.module_axis}"
