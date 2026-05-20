from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator

from core.uploads import COMPETITION_DOCUMENT_UPLOAD_SPEC, PrivateMediaStorage
from curriculum.models import CompetitionType, Level, ModuleAxis, Project, StandardModule

competition_storage = PrivateMediaStorage("competitions")

def competition_document_path(instance, filename):
    competition_path = instance.competition.code if instance.competition and instance.competition.code else 'unknown_competition'
    return f"competition_projects/{competition_path}/{filename}"


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
    description = models.TextField("描述", blank=True)
    
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = '具体赛事'
        verbose_name_plural = '具体赛事'
        ordering = ['-start_date', 'name']
    
    def __str__(self):
        return self.name



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
        validators=COMPETITION_DOCUMENT_UPLOAD_SPEC.validators(),
        help_text=COMPETITION_DOCUMENT_UPLOAD_SPEC.help_text(
            "上传与该赛项相关的归档文件"
        ),
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

    def _allows_legacy_project_competition_type_mismatch(self):
        if not self.competition_id or not self.project_id:
            return False

        project_links = type(self).objects.filter(project_id=self.project_id)
        return (
            project_links.filter(
                competition__competition_type_id=self.competition.competition_type_id,
            ).exists()
            and project_links.exclude(
                competition__competition_type_id=self.competition.competition_type_id,
            ).exists()
        )

    def clean(self):
        super().clean()
        if (
            self.competition_id
            and self.project_id
            and self.competition.competition_type_id != self.project.competition_type_id
            and not self._allows_legacy_project_competition_type_mismatch()
        ):
            raise ValidationError({'project': '竞赛项目必须属于当前具体赛事对应的竞赛类型。'})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

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


class CompetitionProjectMember(models.Model):
    competition_project = models.ForeignKey(
        CompetitionProject,
        on_delete=models.CASCADE,
        related_name='member_links',
        verbose_name='具体赛项',
    )
    member = models.ForeignKey(
        Member,
        on_delete=models.PROTECT,
        related_name='competition_project_links',
        verbose_name='代表队',
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('最后更新时间', auto_now=True)

    class Meta:
        verbose_name = '赛项代表队关联'
        verbose_name_plural = '赛项代表队关联'
        ordering = ['competition_project', 'member__level', 'member__name', 'pk']
        constraints = [
            models.UniqueConstraint(
                fields=['competition_project', 'member'],
                name='unique_member_per_competition_project',
            ),
        ]

    def clean(self):
        competition_project = self.competition_project if self.competition_project_id else None
        member = self.member if self.member_id else None
        validate_member_level(member, competition_project)

    def save(self, *args, **kwargs):
        competition_project = self.competition_project if self.competition_project_id else None
        member = self.member if self.member_id else None
        validate_member_level(member, competition_project)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.competition_project} / {self.member.name}'


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
        constraints = [
            models.UniqueConstraint(
                fields=['competition_project', 'person'],
                name='unique_competitor_per_competition_project',
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
        if self.pk is None and self.person_id and self.competition_project_id:
            if Competitor.objects.filter(
                competition_project_id=self.competition_project_id,
                person_id=self.person_id,
            ).exists():
                raise ValidationError({'person': '该选手已存在于当前赛项中，请勿重复新增。'})

    def save(self, *args, **kwargs):
        member = self.member if self.member_id else None
        competition_project = self.competition_project if self.competition_project_id else None
        validate_member_level(member, competition_project)
        if self._state.adding and self.person_id and self.competition_project_id:
            if Competitor.objects.filter(
                competition_project_id=self.competition_project_id,
                person_id=self.person_id,
            ).exists():
                raise ValidationError({'person': '该选手已存在于当前赛项中，请勿重复新增。'})
        super().save(*args, **kwargs)
        if member is not None and competition_project is not None:
            CompetitionProjectMember.objects.get_or_create(
                competition_project=competition_project,
                member=member,
            )

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
        if member is not None and competition_project is not None:
            CompetitionProjectMember.objects.get_or_create(
                competition_project=competition_project,
                member=member,
            )

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


