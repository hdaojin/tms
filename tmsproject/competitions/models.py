from django.db import models
from django.contrib.auth import get_user_model

# Create your models here.

# 比赛管理

# Create your models here.

class Competition(models.Model):
    class Level(models.TextChoices):
        INTERNATIONAL = '0IN', '国际级'
        NATIONAL = '1NA', '国家级'
        PROVINCIAL = '2PR', '省级'
        MUNICIPAL = '3MU', '市级'
        OTHER = '4OT', '其他'

    name = models.CharField("名称", max_length=100, unique=True)
    level = models.CharField("级别", max_length=3, choices=Level.choices, default=Level.OTHER)
    weight = models.FloatField("权重", default=1.0, help_text="比赛的权重，用于计算考点的重要性")
    
    class Meta:
        verbose_name = '竞赛'
        verbose_name_plural = '竞赛'  # 复数形式的名称
        ordering = ('-level', 'name')  # 按级别降序，名称升序排序
    
    def __str__(self):
        return self.name


class CompetitionDetail(models.Model):
    competition = models.OneToOneField(Competition, on_delete=models.CASCADE, related_name='detail', verbose_name='竞赛')
    start_date = models.DateField("开始日期", help_text="比赛开始日期", blank=True, null=True)
    end_date = models.DateField("结束日期", help_text="比赛结束日期", blank=True, null=True)
    location = models.CharField("地点", max_length=100, help_text="比赛举办城市", blank=True, null=True)
    description = models.TextField("描述", blank=True, null=True, help_text="比赛的详细描述")  

    class Meta:
        verbose_name = '竞赛详情'
        verbose_name_plural = '竞赛详情'

    def __str__(self):
        return f"{self.competition.name}的详细信息"


class CompetitionTeam(models.Model):
    name = models.CharField("参赛队名称", max_length=100, help_text="参赛队名称", unique=True)
    competitions = models.ManyToManyField(Competition, through='CompetitionTeamRelation', related_name='all_teams', verbose_name='参加的竞赛')
    
    class Meta:
        verbose_name = '参赛队'
        verbose_name_plural = '参赛队'
        ordering = ('name',)

    def __str__(self):
        return f"{self.name}"

class CompetitionTeamRelation(models.Model):
    competition = models.ForeignKey(Competition, on_delete=models.CASCADE, related_name='teams', verbose_name='竞赛')
    team = models.ForeignKey(CompetitionTeam, on_delete=models.CASCADE, related_name='competition_relations', verbose_name='参赛队')
    
    class Meta:
        verbose_name = '竞赛-参赛队关系'
        verbose_name_plural = '竞赛-参赛队关系'
        constraints = [
            models.UniqueConstraint(fields=['competition', 'team'], name='unique_competition_team')
        ]

    def __str__(self):
        return f"{self.competition.name} - {self.team.name}"


class CompetionResult(models.Model):
    competition = models.OneToOneField(Competition, on_delete=models.CASCADE, related_name='result', verbose_name='竞赛', null=True, blank=True)
    gold = models.ForeignKey(CompetitionTeam, on_delete=models.SET_NULL, null=True, blank=True, related_name='+', verbose_name="获得金牌的参赛队", help_text="获得金牌的参赛队")
    silver = models.ForeignKey(CompetitionTeam, on_delete=models.SET_NULL, null=True, blank=True, related_name='+', verbose_name="获得银牌的参赛队", help_text="获得银牌的参赛队")
    bronze = models.ForeignKey(CompetitionTeam, on_delete=models.SET_NULL, null=True, blank=True, related_name='+', verbose_name="获得铜牌的参赛队", help_text="获得铜牌的参赛队")
    our_competitor = models.ForeignKey(get_user_model(), verbose_name="我们的参赛选手", on_delete=models.CASCADE, related_name="competitions", help_text="我们的参赛选手", null=True, blank=True)
    our_result = models.CharField("我们的选手成绩", max_length=100, blank=True, help_text='我们选手的成绩, 填写"金牌" "银牌" "铜牌" "优胜奖" "未获奖"，或名次，如"第一名"，或具体成绩，如"78.5分"')

    class Meta:
        verbose_name = '比赛结果'
        verbose_name_plural = '比赛结果'

    def __str__(self):
        return f"{self.competition.name}的比赛结果"

