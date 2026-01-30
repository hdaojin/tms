from decimal import Decimal

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator, FileExtensionValidator

from core.utils.validators import FileSizeValidator
from core.constants import COMPETITION_UPLOAD_DIR, COMPETITION_ALLOWED_EXTENSIONS

competition_storage = FileSystemStorage(location=str(COMPETITION_UPLOAD_DIR))

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
    code = models.CharField("赛事编号", max_length=50, unique=True, help_text="具体赛事唯一编号，如：WSC2024")
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
    competition_type = models.ForeignKey(
        CompetitionType,
        verbose_name="所属赛事类型",
        on_delete=models.CASCADE,
        related_name='projects',
    )
    code = models.CharField("项目代码", max_length=50, unique=True, help_text="用于标识竞赛项目的唯一代码，如ITNSA")
    name = models.CharField("项目名称", max_length=100, unique=True)
    description = models.TextField("描述", blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = '竞赛项目'
        verbose_name_plural = '竞赛项目'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.competition_type})"


class CompetitionProject(models.Model):
    """具体赛项 (Event-Project 关联)"""
    competition = models.ForeignKey(
        Competition,
        verbose_name="所属赛事",
        on_delete=models.CASCADE,
        related_name='competition_projects'
    )
    project = models.ForeignKey(
        Project,
        verbose_name="竞赛项目",
        on_delete=models.CASCADE,
        related_name='competition_projects'
    )
    document = models.FileField(
        "赛项文件",
        storage=competition_storage,
        upload_to=competition_document_path,
        blank=True,
        validators=[
            FileExtensionValidator(allowed_extensions=COMPETITION_ALLOWED_EXTENSIONS, message=f"仅支持以下格式的文件：{', '.join(COMPETITION_ALLOWED_EXTENSIONS)}"),
            FileSizeValidator(),
        ],
        help_text=f"上传与该赛项相关的归档文件，支持格式：{', '.join(COMPETITION_ALLOWED_EXTENSIONS)}，文件大小不超过{settings.UPLOAD_MAX_SIZE_MB}MB"
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


class Module(models.Model):
    """项目模块 (隶属于标准项目 Project)"""
    project = models.ForeignKey(
        Project,
        verbose_name="所属竞赛项目",
        on_delete=models.CASCADE,
        related_name='modules',
    )
    code = models.CharField("编号", max_length=50) # 不再全表unique，因为不同项目可能有相同编号的模块
    name = models.CharField("名称", max_length=100)
    description = models.TextField("描述", blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)
    
    class Meta:
        verbose_name = '竞赛模块'
        verbose_name_plural = '竞赛模块'
        ordering = ['project', 'code']
        unique_together = ['project', 'code']
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class CompetitionModule(models.Model):
    """具体赛项模块 (Event-Module 关联)"""
    competition_project = models.ForeignKey(
        CompetitionProject,
        verbose_name="所属具体赛项",
        on_delete=models.CASCADE,
        related_name='competition_modules'
    )
    module = models.ForeignKey(
        Module,
        verbose_name="竞赛模块",
        on_delete=models.CASCADE,
        related_name='competition_modules'
    )
    # 可在此处覆盖具体的名称或描述
    name = models.CharField("本届模块名称", max_length=100, blank=True, help_text="如不填则使用标准模块名称")
    
    class Meta:
        verbose_name = '具体赛项模块'
        verbose_name_plural = '具体赛项模块'
        unique_together = ['competition_project', 'module']
        ordering = ['competition_project', 'module__code']

    def __str__(self):
        return f"{self.competition_project} - {self.name or f'{self.module.code} - {self.module.name}'}"


class Member(models.Model):
    """成员/代表队 (如 China, Korea, Indonesia)"""
    name = models.CharField("名称", max_length=100)
    code = models.CharField("代码", max_length=20, unique=True, help_text="ISO代码或缩写")
    flag = models.ImageField("旗帜", upload_to='flags/', blank=True, null=True)

    class Meta:
        verbose_name = '参赛代表队'
        verbose_name_plural = '参赛代表队'
        ordering = ['name']

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
    user = models.ForeignKey(
        CompetitorUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="关联用户",
        related_name="competitor_profiles",
        help_text="如果是校内选手，请关联用户账号；如果是外部选手，留空即可。"
    )
    competition_project = models.ForeignKey(
        CompetitionProject,
        on_delete=models.CASCADE,
        verbose_name="参赛项目",
        related_name="competitors",
        null=True # 允许为空以便迁移
    )
    name = models.CharField("姓名", max_length=100, help_text="选手姓名")
    gender = models.CharField("性别", max_length=1, choices=[('M', '男'), ('F', '女')], blank=True, null=True)
    organization = models.CharField("所属单位", max_length=100, blank=True, help_text="具体所属学校或单位，区别于代表队")
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
        ordering = ['competition_project', 'name']

    def __str__(self):
        if self.user:
            return f"{self.name} (User: {self.user.username})"
        return self.name


class Expert(models.Model):
    """专家 (关联到具体赛项)"""
    user = models.ForeignKey(
        CompetitorUser, # 复用之前定义的代理用户
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="关联用户",
        related_name="expert_profiles"
    )
    competition_project = models.ForeignKey(
        CompetitionProject,
        on_delete=models.CASCADE,
        verbose_name="所属赛项",
        related_name="experts"
    )
    name = models.CharField("姓名", max_length=100)
    member = models.ForeignKey(
        Member, 
        on_delete=models.PROTECT, 
        verbose_name="代表队",
        related_name="experts"
    )
    organization = models.CharField("所属单位", max_length=100, blank=True)
    
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = '参赛专家(裁判)'
        verbose_name_plural = '参赛专家(裁判)'
        ordering = ['competition_project', 'name']

    def __str__(self):
        return f"{self.name} - {self.member.name if self.member else ''}"


class SkillPosition(models.Model):
    """技能岗位人员 (如场地经理、翻译等, 关联到具体赛项)"""
    user = models.ForeignKey(
        CompetitorUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="关联用户",
        related_name="skill_positions"
    )
    competition_project = models.ForeignKey(
        CompetitionProject,
        on_delete=models.CASCADE,
        verbose_name="所属赛项",
        related_name="skill_positions"
    )
    name = models.CharField("姓名", max_length=100)
    position_name = models.CharField("岗位名称", max_length=100, help_text="如：技能竞赛经理(Skill Competition Manager)、首席专家(Chief Expert)、场地经理(Workshop Manager)")
    organization = models.CharField("所属单位", max_length=100, blank=True)
    remarks = models.TextField("备注", blank=True)

    
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = '具体赛事技能岗位人员'
        verbose_name_plural = '具体赛事技能岗位人员'
        ordering = ['competition_project', 'position_name', 'name']

    def __str__(self):
        return f"{self.name} - {self.position_name}"


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
        on_delete=models.CASCADE, 
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
        
    def __str__(self):
        return f"{self.competitor} (Rank: {self.rank})"


class ModuleResult(models.Model):
    """模块成绩"""
    competition_result = models.ForeignKey(
        CompetitionResult,
        on_delete=models.CASCADE,
        verbose_name="所属总成绩",
        related_name='module_results'
    )
    competition_module = models.ForeignKey(
        CompetitionModule,
        on_delete=models.CASCADE,
        verbose_name="具体模块"
    )
    score = models.DecimalField("模块得分", max_digits=5, decimal_places=2, help_text="通常为百分制或其他原始分")
    
    class Meta:
        verbose_name = '模块成绩'
        verbose_name_plural = '模块成绩'
        ordering = ['competition_module']
        unique_together = ['competition_result', 'competition_module'] 

    def __str__(self):
        return f"{self.competition_module}: {self.score}"


