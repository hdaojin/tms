from django.db import models
from django.contrib.auth import get_user_model

# Create your models here.

# 比赛管理

# Create your models here.

class Competition(models.Model):
    class Level(models.TextChoices):
        INTERNATIONAL = 'IN', '国际级'
        NATIONAL = 'NA', '国家级'
        PROVINCIAL = 'PR', '省级'
        MUNICIPAL = 'MU', '市级'
        OTHER = 'OT', '其他'

    name = models.CharField("名称", max_length=100, unique=True)
    start_date = models.DateField("开始日期", help_text="比赛开始日期")
    end_date = models.DateField("结束日期", help_text="比赛结束日期")
    location = models.CharField("地点", max_length=100, help_text="比赛举办城市")
    gold = models.CharField("金牌获得者", max_length=100, blank=True, help_text="获得金牌的国家或地区")
    silver = models.CharField("银牌获得者", max_length=100, blank=True, help_text="获得银牌的国家或地区")
    bronze = models.CharField("铜牌获得者", max_length=100, blank=True, help_text="获得铜牌的国家或地区")
    our_competitor = models.ForeignKey(get_user_model(), verbose_name="我们的参赛选手", on_delete=models.CASCADE, related_name="competitions", help_text="我们的参赛选手")
    our_result = models.CharField("我们的选手成绩", max_length=100, blank=True, help_text='我们选手的成绩, 填写" "金牌" "银牌" "铜牌" "优胜奖" "未获奖"，或名次，如"第一名"，或具体成绩，如"78.5分"')
    description = models.TextField("描述", blank=True)  # 改为可选
    
    class Meta:
        verbose_name = '竞赛'
        verbose_name_plural = '竞赛'  # 复数形式的名称
    
    def __str__(self):
        return self.name