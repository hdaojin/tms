from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
"""避免循环导入：使用字符串引用外键模型。"""


class Topic(models.Model):
    module = models.ForeignKey(
        'curriculum.StandardModule',
        verbose_name="所属模块",
        on_delete=models.CASCADE,
        related_name='topics',
    )
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


class TagGroup(models.Model):
    name = models.CharField("名称", max_length=100, unique=True)
    slug = models.SlugField("标识", max_length=100, unique=True)
    description = models.TextField("描述", blank=True)
    sort_order = models.PositiveIntegerField("显示顺序", default=0, help_text="数值越小越靠前显示。")

    class Meta:
        verbose_name = '标签分组'
        verbose_name_plural = '标签分组'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class Tag(models.Model):
    group = models.ForeignKey(
        TagGroup,
        verbose_name="所属分组",
        on_delete=models.CASCADE,
        related_name='tags',
    )
    name = models.CharField("名称", max_length=100)
    slug = models.SlugField("标识", max_length=100, unique=True)
    description = models.TextField("描述", blank=True)
    sort_order = models.PositiveIntegerField("显示顺序", default=0, help_text="数值越小越靠前显示。")
    is_active = models.BooleanField("启用", default=True)

    class Meta:
        verbose_name = '标签'
        verbose_name_plural = '标签'
        constraints = [
            models.UniqueConstraint(fields=['group', 'name'], name='unique_tag_name_within_group')
        ]
        ordering = ['group', 'sort_order', 'name']

    def __str__(self):
        return f"{self.group.name} / {self.name}"


class ExamPoint(models.Model):
    competition_project = models.ForeignKey(
        'competitions.CompetitionProject',
        verbose_name="所属具体赛项",
        on_delete=models.PROTECT,
        related_name='exam_points',
    )
    skills = models.ManyToManyField(
        Skill,
        verbose_name="技能点",
        related_name='exam_points',
        through='ExamPointSkill',
    )
    tags = models.ManyToManyField(
        Tag,
        verbose_name="标签",
        related_name='exam_points',
        blank=True,
    )
    name = models.CharField("考点", max_length=500, help_text="必填；同一竞赛下名称唯一。")
    detail_content = models.TextField("详细内容", blank=True, null=True)  # 可选
    difficulty = models.PositiveSmallIntegerField(
        "难度系数",
        default=3,
        help_text="1-5，1 最简单，5 最难",
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    score = models.DecimalField("分值", max_digits=10, decimal_places=2, default=0)  # type: ignore
    
    class Meta:
        verbose_name = '考点'
        verbose_name_plural = '考点'
        constraints = [
            models.UniqueConstraint(fields=['competition_project', 'name'], name='unique_exam_point_within_project')
        ]
        ordering= ['competition_project', 'name']
        indexes = [
            models.Index(fields=['name', 'difficulty'], name='index_exam_point')  # 联合索引
        ]

    @property
    def competition(self):
        return self.competition_project.competition

    @property
    def project(self):
        return self.competition_project.project

    @property
    def skill(self):
        return self.skills

    def __str__(self):
        return self.name


class ExamPointSkill(models.Model):
    exam_point = models.ForeignKey(
        ExamPoint,
        verbose_name="考点",
        on_delete=models.CASCADE,
        related_name='exam_point_skills',
    )
    skill = models.ForeignKey(
        Skill,
        verbose_name="技能点",
        on_delete=models.CASCADE,
        related_name='exam_point_skills',
    )
    is_primary = models.BooleanField("主技能", default=False, help_text="用于标识该考点的主要能力点。")
    weight = models.DecimalField(
        "权重",
        max_digits=5,
        decimal_places=2,
        default=Decimal('1.00'),
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="用于表示该技能点在综合考点中的相对权重。",
    )
    note = models.TextField("备注", blank=True)

    class Meta:
        verbose_name = '考点技能关联'
        verbose_name_plural = '考点技能关联'
        constraints = [
            models.UniqueConstraint(fields=['exam_point', 'skill'], name='unique_exam_point_skill')
        ]
        ordering = ['exam_point', '-is_primary', 'pk']

    def __str__(self):
        return f"{self.exam_point.name} / {self.skill.name}"
