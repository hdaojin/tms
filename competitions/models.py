from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
"""避免循环导入：使用字符串引用外键模型。"""



class Competition(models.Model):
    class Level(models.TextChoices):
        INTERNATIONAL = 'international', '国际级'
        NATIONAL = 'national', '国家级'
        PROVINCIAL = 'provincial', '省级'
        MUNICIPAL = 'municipal', '市级'
        DISTRICT = 'district', '区级'
        SCHOOL = 'school', '校级'
        CLASS = 'class', '班级'
        OTHER = 'other', '其他'

    name = models.CharField("名称", max_length=100, unique=True)
    level = models.CharField("级别", choices=Level, default=Level.INTERNATIONAL, max_length=20, help_text="比赛的级别")
    weight = models.DecimalField(
        "权重",
        max_digits=2,
        decimal_places=1,
        default=Decimal('7.0'),
        help_text="用于统计该比赛所涉考点的重要性，数值越大表示该比赛所涉考点越重要，取值范围0.0-7.0，原则上与比赛级别对应。",
        validators=[MinValueValidator(Decimal('0.0')), MaxValueValidator(Decimal('7.0'))]
    )
    start_date = models.DateField("开始日期", help_text="比赛开始日期", null=True)
    end_date = models.DateField("结束日期", help_text="比赛结束日期", null=True)
    location = models.CharField("地点", max_length=100, help_text="比赛举办城市", null=True)
    organizer = models.CharField("主办单位", max_length=200, help_text="比赛的主办单位", null=True)
    description = models.TextField("描述", blank=True,  help_text="比赛的详细描述")  
    is_team_event = models.BooleanField("团体赛", default=False, help_text="是否为团体赛")
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = '竞赛'
        verbose_name_plural = '竞赛'  # 复数形式的名称
        ordering = ('-start_date', 'name', 'level')  # 开始日期降序，名称升序，其次按级别字符串排序

    @property
    def get_level_name(self):
        return self.Level(self.level).label
    
    def __str__(self):
        return f"{self.name}({self.get_level_name})"
    
class Examination(models.Model):
    name = models.CharField("名称", max_length=100, unique=True)
    start_date = models.DateField("开始日期", help_text="考核开始日期", null=True)
    end_date = models.DateField("结束日期", help_text="考核结束日期", null=True)
    location = models.CharField("地点", max_length=100, help_text="考核地点", blank=True, null=True)
    organizer = models.CharField("组织单位", max_length=200, help_text="考核的组织单位", blank=True, null=True)
    description = models.TextField("描述", blank=True,  help_text="考核的详细描述")
    is_team_event = models.BooleanField("团体考核", default=False, help_text="是否为团体考核")
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = '考核'
        verbose_name_plural = '考核'  # 复数形式的名称
        ordering = ('-start_date', 'name')  # 开始日期降序，名称升序

    def __str__(self):
        return f"{self.name}"
    

class ExamScore(models.Model):
    examination = models.ForeignKey(Examination, on_delete=models.CASCADE, related_name='scores', verbose_name='考核')
    model = models.ForeignKey('skills.Module', on_delete=models.PROTECT, related_name='exam_scores', verbose_name='模块')
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='exam_scores', verbose_name='姓名')
    score = models.DecimalField("分值", max_digits=4, 
                                decimal_places=2, 
                                default=0,  # type: ignore
                                validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('25.00'))],
                                help_text="该模块成绩的分值，取值范围0.00-25.00",
                                )
    remarks = models.TextField("备注", blank=True, null=True, help_text="对该成绩的备注说明")
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = '考核成绩'
        verbose_name_plural = '考核成绩'  # 复数形式的名称
        ordering = ('-examination__start_date', 'user__username', 'model__code')  # 考核开始日期降序，姓名升序，模块代码升序
        constraints = [
            models.UniqueConstraint(fields=['examination', 'model', 'user'], name='unique_exam_score')
        ]

    def __str__(self):
        return f"{self.examination.name} - {self.user.username} - {self.model.code} : {self.score}"
    

    
    

# class CompetitionDetail(models.Model):
#     competition = models.OneToOneField(Competition, on_delete=models.CASCADE, related_name='detail', verbose_name='竞赛')

#     class Meta:
#         verbose_name = '竞赛详情'
#         verbose_name_plural = '竞赛详情'

#     def __str__(self):
#         return f"{self.competition.name}的详细信息"


# class CompetitionTeam(models.Model):
#     name = models.CharField("参赛队名称", max_length=100, help_text="参赛队名称", unique=True)
#     competitions = models.ManyToManyField(Competition, through='CompetitionTeamRelation', related_name='all_teams', verbose_name='参加的竞赛')
    
#     class Meta:
#         verbose_name = '参赛队'
#         verbose_name_plural = '参赛队'
#         ordering = ('name',)

#     def __str__(self):
#         return f"{self.name}"

# class CompetitionTeamRelation(models.Model):
#     competition = models.ForeignKey(Competition, on_delete=models.CASCADE, related_name='teams', verbose_name='竞赛')
#     team = models.ForeignKey(CompetitionTeam, on_delete=models.CASCADE, related_name='competition_relations', verbose_name='参赛队')
    
#     class Meta:
#         verbose_name = '竞赛-参赛队关系'
#         verbose_name_plural = '竞赛-参赛队关系'
#         constraints = [
#             models.UniqueConstraint(fields=['competition', 'team'], name='unique_competition_team')
#         ]

#     def __str__(self):
#         return f"{self.competition.name} - {self.team.name}"


# class CompetionResult(models.Model):
#     competition = models.OneToOneField(Competition, on_delete=models.CASCADE, related_name='result', verbose_name='竞赛',  blank=True)
#     gold = models.ForeignKey(CompetitionTeam, on_delete=models.PROTECT,  blank=True, related_name='+', verbose_name="获得金牌的参赛队", help_text="获得金牌的参赛队")
#     silver = models.ForeignKey(CompetitionTeam, on_delete=models.PROTECT,  blank=True, related_name='+', verbose_name="获得银牌的参赛队", help_text="获得银牌的参赛队")
#     bronze = models.ForeignKey(CompetitionTeam, on_delete=models.PROTECT,  blank=True, related_name='+', verbose_name="获得铜牌的参赛队", help_text="获得铜牌的参赛队")
#     our_competitor = models.ForeignKey(get_user_model(), verbose_name="我们的参赛选手", on_delete=models.PROTECT, related_name="competitions", help_text="我们的参赛选手",  blank=True)
#     our_result = models.CharField("我们的选手成绩", max_length=100, blank=True, help_text='我们选手的成绩, 填写"金牌" "银牌" "铜牌" "优胜奖" "未获奖"，或名次，如"第一名"，或具体成绩，如"78.5分"')

#     class Meta:
#         verbose_name = '比赛结果'
#         verbose_name_plural = '比赛结果'

#     def __str__(self):
#         return f"{self.competition.name}的比赛结果"

