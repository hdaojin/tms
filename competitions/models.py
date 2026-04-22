from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator, FileExtensionValidator

from core.utils.validators import validate_file_size
from core.constants import COMPETITION_UPLOAD_DIR, COMPETITION_ALLOWED_EXTENSIONS, DEFAULT_UPLOAD_MAX_SIZE_MB
from functools import partial

competition_storage = FileSystemStorage(location=str(COMPETITION_UPLOAD_DIR))

DEFAULT_MODULE_SET_CODE = 'default'
DEFAULT_MODULE_SET_NAME = '默认标准模块集'


class StandardModuleSetQuerySet(models.QuerySet):
    def current(self):
        return self.filter(is_current=True)


class StandardModuleQuerySet(models.QuerySet):
    def current(self):
        return self.filter(module_set__is_current=True)

def competition_document_path(instance, filename):
    competition_path = instance.competition.code if instance.competition and instance.competition.code else 'unknown_competition'
    return f"competition_projects/{competition_path}/{filename}"

class Level(models.TextChoices):
    INTERNATIONAL = 'international', '国际级'
    NATIONAL = 'national', '国家级'
    PROVINCIAL = 'provincial', '省级'
    MUNICIPAL = 'municipal', '市级'
    DISTRICT = 'district', '区级'
    SCHOOL = 'school', '校级'
    CLASS = 'class', '班级'
    OTHER = 'other', '其他'


class MemberScope(models.TextChoices):
    INTERNATIONAL = Level.INTERNATIONAL, '国家或地区'
    NATIONAL = Level.NATIONAL, '省级代表队'
    PROVINCIAL = Level.PROVINCIAL, '地市代表队'
    MUNICIPAL = Level.MUNICIPAL, '区县代表队'
    DISTRICT = Level.DISTRICT, '学校代表队'
    SCHOOL = Level.SCHOOL, '班级代表队'
    CLASS = Level.CLASS, '班级小组'
    OTHER = Level.OTHER, '其他'


def get_member_scope_label(level):
    if level in MemberScope.values:
        return MemberScope(level).label
    return MemberScope.OTHER.label


def validate_member_level(member, competition_project):
    if member is None or competition_project is None:
        return

    required_level = competition_project.required_member_level
    if required_level is None:
        return
    if member.level != required_level:
        raise ValidationError(
            {
                'member': (
                    f'当前赛事级别只能选择“{competition_project.required_member_level_label}”代表队，'
                    f'当前选择的是“{member.get_level_display()}”。'
                )
            }
        )


class CompetitionType(models.Model):
    """赛事类型（原有 Competition 重命名）"""
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


class Competition(models.Model):
    """具体赛事 (Event, 新增)"""
    competition_type = models.ForeignKey(
        CompetitionType,
        verbose_name="所属赛事类型",
        on_delete=models.CASCADE,
        related_name='competitions'
    )
    name = models.CharField("赛事名称", max_length=100, help_text="具体赛事名称，如：第47届世界技能大赛")
    code = models.CharField("赛事编号", max_length=50, unique=True, help_text="具体赛事唯一编号，如：47WSC2024")
    start_date = models.DateField("开始日期", null=True, blank=True)
    end_date = models.DateField("结束日期", null=True, blank=True)
    location = models.CharField("举办地点", max_length=100, blank=True)
    
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = '具体赛事'
        verbose_name_plural = '具体赛事'
        ordering = ['-start_date', 'name']
    
    def __str__(self):
        return self.name



class Project(models.Model):
    """标准项目库 (Skill)"""
    code = models.CharField("项目代码", max_length=50, unique=True, help_text="用于标识竞赛项目的唯一代码，如ITNSA")
    name = models.CharField("项目名称", max_length=100)
    description = models.TextField("描述", blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = '竞赛项目'
        verbose_name_plural = '竞赛项目'
        ordering = ['name', 'code']
    
    def __str__(self):
        return f"{self.name} ({self.code})"

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


class CompetitionProject(models.Model):
    """具体赛项 (Event-Project 关联)"""
    competition = models.ForeignKey(
        Competition,
        verbose_name="所属赛事",
        on_delete=models.PROTECT,
        related_name='competition_projects'
    )
    project = models.ForeignKey(
        Project,
        verbose_name="竞赛项目",
        on_delete=models.PROTECT,
        related_name='competition_projects'
    )
    document = models.FileField(
        "赛项文件",
        storage=competition_storage,
        upload_to=competition_document_path,
        blank=True,
        validators=[
            FileExtensionValidator(allowed_extensions=COMPETITION_ALLOWED_EXTENSIONS, message=f"仅支持以下格式的文件：{', '.join(COMPETITION_ALLOWED_EXTENSIONS)}"),
            partial(validate_file_size, max_size_mb=DEFAULT_UPLOAD_MAX_SIZE_MB),
        ],
        help_text=f"上传与该赛项相关的归档文件，支持格式：{', '.join(COMPETITION_ALLOWED_EXTENSIONS)}，文件大小不超过 {DEFAULT_UPLOAD_MAX_SIZE_MB}MB"
    )
    description = models.TextField("本届赛项描述", blank=True) 

    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)
    # 可在此处覆盖具体的规则或属性

    class Meta:
        verbose_name = '具体赛事项目'
        verbose_name_plural = '具体赛事项目'
        unique_together = ['competition', 'project']
        ordering = ['competition', 'project']

    def __str__(self):
        return f"{self.competition.name} - {self.project.name}"

    @property
    def required_member_level(self):
        if not self.competition_id:
            return None
        return self.competition.competition_type.level

    @property
    def required_member_level_label(self):
        required_level = self.required_member_level
        if required_level is None:
            return None
        return get_member_scope_label(required_level)


class StandardModule(models.Model):
    """标准模块（隶属于标准项目 Project）"""
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
    code = models.CharField("编号", max_length=50) # 不再全表unique，因为不同项目可能有相同编号的模块
    name = models.CharField("名称", max_length=100)
    description = models.TextField("描述", blank=True)
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


class CompetitionModule(models.Model):
    """具体赛项模块 (Event-Module 关联)"""
    competition_project = models.ForeignKey(
        CompetitionProject,
        verbose_name="所属具体赛项",
        on_delete=models.PROTECT,
        related_name='competition_modules'
    )
    code = models.CharField("本届模块编号", max_length=50, help_text="按该届官方模块原始编号填写。")
    name = models.CharField("本届模块名称", max_length=100, help_text="按该届官方模块原始名称填写。")
    description = models.TextField("本届模块描述", blank=True)
    sort_order = models.PositiveIntegerField("显示顺序", default=0, help_text="数值越小越靠前显示。")
    
    class Meta:
        verbose_name = '具体赛项模块'
        verbose_name_plural = '具体赛项模块'
        unique_together = ['competition_project', 'code']
        ordering = ['competition_project', 'sort_order', 'code', 'pk']

    @property
    def project(self):
        return self.competition_project.project

    @property
    def primary_standard_module(self):
        primary_mapping = self.module_mappings.filter(is_primary=True).select_related('module').first()
        if primary_mapping is not None:
            return primary_mapping.module
        first_mapping = self.module_mappings.select_related('module').first()
        return first_mapping.module if first_mapping is not None else None

    @property
    def primary_axis(self):
        primary_mapping = self.axis_mappings.filter(is_primary=True).select_related('module_axis').first()
        if primary_mapping is not None:
            return primary_mapping.module_axis
        first_mapping = self.axis_mappings.select_related('module_axis').first()
        if first_mapping is not None:
            return first_mapping.module_axis
        primary_standard_module = self.primary_standard_module
        if primary_standard_module is None:
            return None
        return primary_standard_module.primary_axis

    def __str__(self):
        return f"{self.competition_project} - {self.code} - {self.name}"


class CompetitionModuleStandardModuleMap(models.Model):
    competition_module = models.ForeignKey(
        CompetitionModule,
        on_delete=models.CASCADE,
        related_name='module_mappings',
        verbose_name='具体赛项模块',
    )
    module = models.ForeignKey(
        StandardModule,
        on_delete=models.PROTECT,
        related_name='competition_module_mappings',
        verbose_name='标准模块',
    )
    is_primary = models.BooleanField('主映射', default=False, help_text='用于标识该官方模块当前主要对应的标准模块。')
    weight = models.DecimalField(
        '权重',
        max_digits=5,
        decimal_places=2,
        default=Decimal('1.00'),
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='用于表示该官方模块映射到该标准模块时的相对权重。',
    )
    note = models.TextField('备注', blank=True)

    class Meta:
        verbose_name = '官方模块标准映射'
        verbose_name_plural = '官方模块标准映射'
        unique_together = ['competition_module', 'module']
        ordering = ['competition_module', '-is_primary', 'module__sort_order', 'module__code', 'pk']
        constraints = [
            models.UniqueConstraint(
                fields=['competition_module'],
                condition=models.Q(is_primary=True),
                name='unique_primary_mapping_per_competition_module',
            ),
        ]

    def clean(self):
        if self.competition_module_id and self.module_id and self.competition_module.competition_project.project_id != self.module.project_id:
            raise ValidationError({'module': '标准模块必须属于当前具体赛项对应的竞赛项目。'})
        if self.is_primary and self.competition_module_id:
            existing_primary = type(self).objects.filter(
                competition_module_id=self.competition_module_id,
                is_primary=True,
            ).exclude(pk=self.pk)
            if existing_primary.exists():
                raise ValidationError({'is_primary': '同一官方模块只能设置一个主映射。'})

    def save(self, *args, **kwargs):
        if self.competition_module_id and self.module_id and self.competition_module.competition_project.project_id != self.module.project_id:
            raise ValidationError({'module': '标准模块必须属于当前具体赛项对应的竞赛项目。'})
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.competition_module} -> {self.module}"


class CompetitionModuleAxisMap(models.Model):
    competition_module = models.ForeignKey(
        CompetitionModule,
        on_delete=models.CASCADE,
        related_name='axis_mappings',
        verbose_name='具体赛项模块',
    )
    module_axis = models.ForeignKey(
        ModuleAxis,
        on_delete=models.PROTECT,
        related_name='competition_module_mappings',
        verbose_name='模块主线',
    )
    is_primary = models.BooleanField('主映射', default=False, help_text='用于标识该官方模块当前主要归属的模块主线。')
    weight = models.DecimalField(
        '权重',
        max_digits=5,
        decimal_places=2,
        default=Decimal('1.00'),
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='用于表示该官方模块映射到该模块主线时的相对权重。',
    )
    note = models.TextField('备注', blank=True)

    class Meta:
        verbose_name = '官方模块主线映射'
        verbose_name_plural = '官方模块主线映射'
        unique_together = ['competition_module', 'module_axis']
        ordering = ['competition_module', '-is_primary', 'module_axis__sort_order', 'module_axis__code', 'pk']
        constraints = [
            models.UniqueConstraint(
                fields=['competition_module'],
                condition=models.Q(is_primary=True),
                name='unique_primary_axis_mapping_per_competition_module',
            ),
        ]

    def clean(self):
        if (
            self.competition_module_id
            and self.module_axis_id
            and self.competition_module.competition_project.project_id != self.module_axis.project_id
        ):
            raise ValidationError({'module_axis': '模块主线必须属于当前具体赛项对应的竞赛项目。'})
        if self.is_primary and self.competition_module_id:
            existing_primary = type(self).objects.filter(
                competition_module_id=self.competition_module_id,
                is_primary=True,
            ).exclude(pk=self.pk)
            if existing_primary.exists():
                raise ValidationError({'is_primary': '同一官方模块只能设置一个主主线映射。'})

    def save(self, *args, **kwargs):
        if (
            self.competition_module_id
            and self.module_axis_id
            and self.competition_module.competition_project.project_id != self.module_axis.project_id
        ):
            raise ValidationError({'module_axis': '模块主线必须属于当前具体赛项对应的竞赛项目。'})
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.competition_module} -> {self.module_axis}"


class Member(models.Model):
    """成员/代表队 (如 China, Korea, Indonesia)"""
    name = models.CharField("名称", max_length=100)
    code = models.CharField("代码", max_length=20, unique=True, help_text="ISO代码或缩写")
    level = models.CharField(
        "代表队层级",
        max_length=20,
        choices=MemberScope.choices,
        help_text='用于匹配赛事级别；国际级赛事应选择“国家或地区”，国家级赛事应选择“省级代表队”，以此类推。',
    )
    flag = models.ImageField("旗帜", upload_to='flags/', blank=True, null=True)

    class Meta:
        verbose_name = '参赛代表队'
        verbose_name_plural = '参赛代表队'
        ordering = ['level', 'name']

    def __str__(self):
        return self.name


class CompetitorUser(User):
    class Meta:
        proxy = True
        verbose_name = '关联用户'
        verbose_name_plural = '关联用户'
        app_label = 'competitions'
    
    def __str__(self):
        if self.first_name:
            return f"{self.first_name} ({self.username})"
        return self.username


class Competitor(models.Model):
    """参赛选手 (关联到具体赛项)"""
    person = models.ForeignKey(
        'CompetitionPerson',
        on_delete=models.PROTECT,
        verbose_name="选手人员",
        related_name="competitor_assignments",
    )
    competition_project = models.ForeignKey(
        CompetitionProject,
        on_delete=models.PROTECT,
        verbose_name="参赛项目",
        related_name="competitors",
    )
    gender = models.CharField("性别", max_length=1, choices=[('M', '男'), ('F', '女')], blank=True, null=True)
    member = models.ForeignKey(
        Member, 
        on_delete=models.PROTECT, 
        verbose_name="代表队",
        related_name="competitors"
    )
    
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = '参赛选手'
        verbose_name_plural = '参赛选手'
        ordering = ['competition_project', 'person__name', 'pk']

    @property
    def name(self):
        return self.person.name

    @property
    def user(self):
        return self.person.user

    @property
    def organization(self):
        return self.person.organization

    def clean(self):
        member = self.member if self.member_id else None
        competition_project = self.competition_project if self.competition_project_id else None
        validate_member_level(member, competition_project)

    def save(self, *args, **kwargs):
        member = self.member if self.member_id else None
        competition_project = self.competition_project if self.competition_project_id else None
        validate_member_level(member, competition_project)
        super().save(*args, **kwargs)

    def __str__(self):
        if self.person.user:
            return f"{self.person.name} (User: {self.person.user.username})"
        return self.person.name


class CompetitionPerson(models.Model):
    """可在不同赛事中复用的竞赛人员主档。"""
    user = models.ForeignKey(
        CompetitorUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="关联用户",
        related_name="competition_people",
        help_text="如果是校内人员，可关联用户账号；外部人员可留空。",
    )
    name = models.CharField("姓名", max_length=100)
    organization = models.CharField("所属单位", max_length=100, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = '竞赛人员'
        verbose_name_plural = '竞赛人员'
        ordering = ['name', 'organization', 'pk']

    def __str__(self):
        if self.organization:
            return f"{self.name} - {self.organization}"
        return self.name


class Expert(models.Model):
    """专家 (关联到具体赛项)"""
    person = models.ForeignKey(
        CompetitionPerson,
        on_delete=models.PROTECT,
        verbose_name="专家人员",
        related_name="expert_assignments",
    )
    competition_project = models.ForeignKey(
        CompetitionProject,
        on_delete=models.PROTECT,
        verbose_name="所属赛项",
        related_name="experts"
    )
    member = models.ForeignKey(
        Member, 
        on_delete=models.PROTECT, 
        verbose_name="代表队",
        related_name="experts"
    )
    
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = '参赛专家(裁判)'
        verbose_name_plural = '参赛专家(裁判)'
        ordering = ['competition_project', 'person__name', 'pk']
        constraints = [
            models.UniqueConstraint(
                fields=['competition_project', 'person'],
                name='unique_expert_per_competition_project',
            ),
        ]

    @property
    def name(self):
        return self.person.name

    @property
    def user(self):
        return self.person.user

    @property
    def organization(self):
        return self.person.organization

    def clean(self):
        member = self.member if self.member_id else None
        competition_project = self.competition_project if self.competition_project_id else None
        validate_member_level(member, competition_project)

    def save(self, *args, **kwargs):
        member = self.member if self.member_id else None
        competition_project = self.competition_project if self.competition_project_id else None
        validate_member_level(member, competition_project)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.person.name} - {self.member.name if self.member else ''}"


class SkillPosition(models.Model):
    """技能岗位人员 (如场地经理、翻译等, 关联到具体赛项)"""
    person = models.ForeignKey(
        CompetitionPerson,
        on_delete=models.PROTECT,
        verbose_name="岗位人员",
        related_name="skill_position_assignments",
    )
    competition_project = models.ForeignKey(
        CompetitionProject,
        on_delete=models.PROTECT,
        verbose_name="所属赛项",
        related_name="skill_positions"
    )
    position_name = models.CharField("岗位名称", max_length=100, help_text="如：技能竞赛经理(Skill Competition Manager)、首席专家(Chief Expert)、场地经理(Workshop Manager)")
    remarks = models.TextField("备注", blank=True)

    
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = '具体赛事技能岗位人员'
        verbose_name_plural = '具体赛事技能岗位人员'
        ordering = ['competition_project', 'position_name', 'person__name', 'pk']
        constraints = [
            models.UniqueConstraint(
                fields=['competition_project', 'person', 'position_name'],
                name='unique_skill_position_per_person_in_competition_project',
            ),
        ]

    @property
    def name(self):
        return self.person.name

    @property
    def user(self):
        return self.person.user

    @property
    def organization(self):
        return self.person.organization

    def __str__(self):
        return f"{self.person.name} - {self.position_name}"


class CompetitionResult(models.Model):
    """竞赛总成绩"""
    class Medal(models.TextChoices):
        GOLD = 'gold', '金牌'
        SILVER = 'silver', '银牌'
        BRONZE = 'bronze', '铜牌'
        FIRST_PRIZE = 'first', '一等奖'
        SECOND_PRIZE = 'second', '二等奖'
        THIRD_PRIZE = 'third', '三等奖'
        EXCELLENCE = 'excellence', '优胜奖'
        NONE = 'none', '无'

    # Result 现在只需关联 Competitor (因为 Competitor 已经绑定了 CompetitionProject)
    competitor = models.ForeignKey(
        Competitor, 
        on_delete=models.PROTECT, 
        verbose_name="选手",
        related_name="results"
    )
    
    score_100 = models.DecimalField("百分制成绩", max_digits=5, decimal_places=2, null=True, blank=True)
    score_700 = models.DecimalField("700分制成绩", max_digits=6, decimal_places=2, null=True, blank=True)
    
    rank = models.PositiveIntegerField("排名", null=True, blank=True)
    medal = models.CharField("奖项", max_length=20, choices=Medal.choices, default=Medal.NONE)

    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = '具体赛事总成绩'
        verbose_name_plural = '具体赛事总成绩'
        ordering = ['competitor__competition_project', 'rank', '-score_700']
        constraints = [
            models.UniqueConstraint(fields=['competitor'], name='unique_competition_result_per_competitor'),
        ]
        
    def __str__(self):
        return f"{self.competitor} (Rank: {self.rank})"


