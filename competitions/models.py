from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class Level(models.TextChoices):
    INTERNATIONAL = 'international', '国际级'
    NATIONAL = 'national', '国家级'
    PROVINCIAL = 'provincial', '省级'
    MUNICIPAL = 'municipal', '市级'
    DISTRICT = 'district', '区级'
    SCHOOL = 'school', '校级'
    CLASS = 'class', '班级'
    OTHER = 'other', '其他'


class Competition(models.Model):
    code = models.CharField("竞赛代码", max_length=50, unique=True, help_text="用于标识竞赛的唯一代码，如WSC或WorldSkills")
    name = models.CharField("竞赛名称", max_length=100, unique=True)
    level = models.CharField("级别", choices=Level.choices, default=Level.INTERNATIONAL, max_length=20, help_text="竞赛的级别")
    weight = models.DecimalField(
        "权重",
        max_digits=2,
        decimal_places=1,
        default=7.0,    # type: ignore
        help_text="用于统计该竞赛所涉考点的重要性，数值越大表示该竞赛所涉考点越重要，取值范围0.0-7.0，原则上与竞赛级别对应。",
        validators=[MinValueValidator(0.0), MaxValueValidator(7.0)]
    )
    description = models.TextField("描述", blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = '竞赛'
        verbose_name_plural = '竞赛'
        ordering = ['level', 'name']

    def __str__(self):
        return self.name


class Project(models.Model):
    competition = models.ForeignKey(
        Competition,
        verbose_name="所属竞赛",
        on_delete=models.CASCADE,
        related_name='projects',
    )
    code = models.CharField("竞赛项目代码", max_length=50, unique=True,help_text="用于标识竞赛项目的唯一代码，如ITNSA")
    name = models.CharField("竞赛项目名称", max_length=100, unique=True)
    description = models.TextField("描述", blank=True)  # 可选
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = '竞赛项目'
        verbose_name_plural = '竞赛项目'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Module(models.Model):
    project = models.ForeignKey(
        Project,
        verbose_name="所属竞赛项目",
        on_delete=models.CASCADE,
        related_name='modules',
    )
    code = models.CharField("编号", max_length=50, unique=True)
    name = models.CharField("名称", max_length=100, unique=True)
    description = models.TextField("描述", blank=True)  # 可选
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)
    
    class Meta:
        verbose_name = '模块'
        verbose_name_plural = '模块'
        ordering = ['code']
    
    def __str__(self):
        return self.name
    


# class Competition(models.Model):
#     class Level(models.TextChoices):
#         INTERNATIONAL = 'international', '国际级'
#         NATIONAL = 'national', '国家级'
#         PROVINCIAL = 'provincial', '省级'
#         MUNICIPAL = 'municipal', '市级'
#         DISTRICT = 'district', '区级'
#         SCHOOL = 'school', '校级'
#         CLASS = 'class', '班级'
#         OTHER = 'other', '其他'

#     name = models.CharField("名称", max_length=100, unique=True)
#     level = models.CharField("级别", choices=Level, default=Level.INTERNATIONAL, max_length=20, help_text="比赛的级别")
#     weight = models.DecimalField(
#         "权重",
#         max_digits=2,
#         decimal_places=1,
#         default=Decimal('7.0'),
#         help_text="用于统计该比赛所涉考点的重要性，数值越大表示该比赛所涉考点越重要，取值范围0.0-7.0，原则上与比赛级别对应。",
#         validators=[MinValueValidator(Decimal('0.0')), MaxValueValidator(Decimal('7.0'))]
#     )
#     start_date = models.DateField("开始日期", help_text="比赛开始日期", null=True)
#     end_date = models.DateField("结束日期", help_text="比赛结束日期", null=True)
#     location = models.CharField("地点", max_length=100, help_text="比赛举办城市", null=True)
#     organizer = models.CharField("主办单位", max_length=200, help_text="比赛的主办单位", null=True)
#     description = models.TextField("描述", blank=True,  help_text="比赛的详细描述")  
#     is_team_event = models.BooleanField("团体赛", default=False, help_text="是否为团体赛")
#     created_at = models.DateTimeField("创建时间", auto_now_add=True)
#     updated_at = models.DateTimeField("最后更新时间", auto_now=True)

#     class Meta:
#         verbose_name = '竞赛'
#         verbose_name_plural = '竞赛'  # 复数形式的名称
#         ordering = ('-start_date', 'name', 'level')  # 开始日期降序，名称升序，其次按级别字符串排序

#     @property
#     def get_level_name(self):
#         return self.Level(self.level).label
    
#     def __str__(self):
#         return f"{self.name}({self.get_level_name})"
    
# class Examination(models.Model):
#     name = models.CharField("名称", max_length=100, unique=True)
#     start_date = models.DateField("开始日期", help_text="考核开始日期", null=True)
#     end_date = models.DateField("结束日期", help_text="考核结束日期", null=True)
#     location = models.CharField("地点", max_length=100, help_text="考核地点", blank=True, null=True)
#     organizer = models.CharField("组织单位", max_length=200, help_text="考核的组织单位", blank=True, null=True)
#     description = models.TextField("描述", blank=True,  help_text="考核的详细描述")
#     is_team_event = models.BooleanField("团体考核", default=False, help_text="是否为团体考核")
#     created_at = models.DateTimeField("创建时间", auto_now_add=True)
#     updated_at = models.DateTimeField("最后更新时间", auto_now=True)

#     class Meta:
#         verbose_name = '考核'
#         verbose_name_plural = '考核'  # 复数形式的名称
#         ordering = ('-start_date', 'name')  # 开始日期降序，名称升序

#     def __str__(self):
#         return f"{self.name}"
    

# class ExamScore(models.Model):
#     examination = models.ForeignKey(Examination, on_delete=models.CASCADE, related_name='scores', verbose_name='考核')
#     module = models.ForeignKey('skills.Module', on_delete=models.PROTECT, related_name='exam_scores', verbose_name='模块')
#     user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='exam_scores', verbose_name='姓名')
#     score = models.DecimalField("分值", max_digits=4, 
#                                 decimal_places=2, 
#                                 default=0,  # type: ignore
#                                 validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('25.00'))],
#                                 help_text="该模块成绩的分值，取值范围0.00-25.00",
#                                 )
#     remarks = models.TextField("备注", blank=True, null=True, help_text="对该成绩的备注说明")
#     created_at = models.DateTimeField("创建时间", auto_now_add=True)
#     updated_at = models.DateTimeField("最后更新时间", auto_now=True)

#     class Meta:
#         verbose_name = '考核成绩'
#         verbose_name_plural = '考核成绩'  # 复数形式的名称
#         ordering = ('-examination__start_date', 'user__username', 'module__code')  # 考核开始日期降序，姓名升序，模块代码升序
#         constraints = [
#             models.UniqueConstraint(fields=['examination', 'module', 'user'], name='unique_exam_score')
#         ]

#     def __str__(self):
#         return f"{self.examination.name} - {self.user.username} - {self.module.code} : {self.score}"
    
# class ExamResult(models.Model):
#     examination = models.ForeignKey(Examination, on_delete=models.CASCADE, related_name='results', verbose_name='考核')
#     user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='exam_results', verbose_name='姓名')
#     total_score = models.DecimalField("总分", max_digits=5, decimal_places=2)
#     average_score = models.DecimalField("平均分", max_digits=5, decimal_places=2)
#     remarks = models.TextField("备注", blank=True, null=True, help_text="对该考核结果的备注说明")
#     created_at = models.DateTimeField("创建时间", auto_now_add=True)
#     updated_at = models.DateTimeField("最后更新时间", auto_now=True)
# """