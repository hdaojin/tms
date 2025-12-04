from django.db import models
"""避免循环导入：使用字符串引用外键模型。"""


# Create your models here.
class Module(models.Model):
    code = models.CharField("编号", max_length=50, unique=True)
    name = models.CharField("名称", max_length=100, unique=True)
    description = models.TextField("描述", blank=True)  # 可选
    
    class Meta:
        verbose_name = '模块'
        verbose_name_plural = '模块'
        ordering = ['code']
    
    def __str__(self):
        return self.name
    
class Topic(models.Model):
    module = models.ForeignKey(Module, verbose_name="所属模块", on_delete=models.CASCADE, related_name='topics')
    name = models.CharField("名称", max_length=100)
    description = models.TextField("描述", blank=True)  # 可选
    
    class Meta:
        verbose_name = '专题'
        verbose_name_plural = '专题'
        constraints = [
            models.UniqueConstraint(fields=['module', 'name'], name='unique_topic')  # 联合唯一约束, 一个模块下的专题名唯一
        ]
        ordering = ['module', 'name']
    
    def __str__(self):
        return f"{self.module.code}-{self.module.name}-{self.name}"

class Skill(models.Model):
    topic = models.ForeignKey(Topic, verbose_name="所属专题", on_delete=models.CASCADE, related_name='skills')
    name = models.CharField("技能点", max_length=100)
    description = models.TextField("描述", blank=True)  # 可选
    
    class Meta:
        verbose_name = '技能'
        verbose_name_plural = '技能'
        constraints = [
            models.UniqueConstraint(fields=['topic', 'name'], name='unique_skill')  # 联合唯一约束, 一个专题下的技能点唯一
        ]
        ordering = ['topic', 'name']

    def __str__(self):
        return f"{self.topic.module.code}-{self.topic.name}-{self.name}"

class ExamPoint(models.Model):
    competition = models.ForeignKey('competitions.Competition', verbose_name="所属竞赛", on_delete=models.PROTECT, related_name='exam_points')
    skill = models.ManyToManyField(Skill, verbose_name="技能点", related_name='exam_points')
    name = models.CharField("考点", max_length=500)  # 可选
    detail_content = models.TextField("详细内容", blank=True, null=True)  # 可选
    difficulty = models.PositiveSmallIntegerField("难度系数", default=3, help_text="1-5, 1最简单，5最难")
    score = models.DecimalField("分值", max_digits=10, decimal_places=2, default=0)  # type: ignore
    
    class Meta:
        verbose_name = '考点'
        verbose_name_plural = '考点'
        constraints = [
            models.UniqueConstraint(fields=['competition', 'name'], name='unique_exam_point')  # 联合唯一约束, 一个竞赛下的考点唯一
        ]
        ordering= ['competition', 'name']
        indexes = [
            models.Index(fields=['name', 'difficulty'], name='index_exam_point')  # 联合索引
        ]

    def __str__(self):
        return self.name