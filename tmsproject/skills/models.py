from django.db import models

# Create your models here.

from competitions.models import Competition

class Module(models.Model):
    code = models.CharField("编号", max_length=50, unique=True)
    name = models.CharField("名称", max_length=100)
    description = models.TextField("描述", blank=True)  # 改为可选
    
    class Meta:
        verbose_name = '模块'
        verbose_name_plural = '模块'
    
    def __str__(self):
        return self.name

class Skill(models.Model):
    skill_point = models.CharField("技能点", max_length=100)
    exam_point = models.CharField("考点", max_length=500, blank=True)  # 改为可选
    detail_content = models.TextField("详细内容", blank=True)  # 改为可选
    competition = models.ForeignKey(Competition, verbose_name="所属竞赛", on_delete=models.CASCADE)
    module = models.ForeignKey(Module, verbose_name="所属模块", on_delete=models.CASCADE)
    score = models.DecimalField("分值", max_digits=10, decimal_places=2)
    
    class Meta:
        verbose_name = '技能'
        verbose_name_plural = '技能'

    def __str__(self):
        return self.skill_point