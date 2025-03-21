from django.db import models

# Create your models here.

from competitions.models import Competition

class Module(models.Model):
    code = models.CharField("编号", max_length=50, unique=True)
    name = models.CharField("名称", max_length=100)
    description = models.TextField("描述", blank=True)  # 可选
    
    class Meta:
        verbose_name = '模块'
        verbose_name_plural = '模块'
    
    def __str__(self):
        return self.name
    
class Topic(models.Model):
    name = models.CharField("名称", max_length=100)
    description = models.TextField("描述", blank=True)  # 可选
    module = models.ForeignKey(Module, verbose_name="所属模块", on_delete=models.CASCADE)
    
    class Meta:
        verbose_name = '专题'
        verbose_name_plural = '专题'
    
    def __str__(self):
        return self.name

class Skill(models.Model):
    name = models.CharField("技能点", max_length=100)
    description = models.TextField("描述", blank=True)  # 可选
    topic = models.ForeignKey(Topic, verbose_name="所属专题", on_delete=models.CASCADE)
    
    class Meta:
        verbose_name = '技能'
        verbose_name_plural = '技能'

    def __str__(self):
        return self.name

class ExamPoint(models.Model):
    skill = models.ForeignKey(Skill, verbose_name="技能点", on_delete=models.CASCADE)
    name = models.CharField("考点", max_length=500)  # 可选
    detail_content = models.TextField("详细内容", blank=True, null=True)  # 可选
    score = models.DecimalField("分值", max_digits=10, decimal_places=2, default=0)
    
    class Meta:
        verbose_name = '考点'
        verbose_name_plural = '考点'

    def __str__(self):
        return self.name