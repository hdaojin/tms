from django.core.exceptions import ValidationError
from django.db import models


class TrainingCycle(models.Model):
    class Status(models.TextChoices):
        PLANNING = 'planning', '筹备中'
        ACTIVE = 'active', '进行中'
        COMPLETED = 'completed', '已结束'
        ARCHIVED = 'archived', '已归档'

    code = models.CharField('周期代码', max_length=50, unique=True, help_text='用于标识备赛周期的唯一代码。')
    name = models.CharField('周期名称', max_length=100)
    project = models.ForeignKey(
        'curriculum.Project',
        verbose_name='竞赛项目',
        on_delete=models.PROTECT,
        related_name='training_cycles',
    )
    module_set = models.ForeignKey(
        'curriculum.StandardModuleSet',
        verbose_name='模块标准集',
        on_delete=models.PROTECT,
        related_name='training_cycles',
    )
    start_date = models.DateField('开始日期')
    end_date = models.DateField('结束日期', null=True, blank=True)
    status = models.CharField('状态', max_length=20, choices=Status.choices, default=Status.PLANNING)
    primary_competition_project = models.ForeignKey(
        'competitions.CompetitionProject',
        verbose_name='主目标赛项',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='primary_training_cycles',
        help_text='下一届目标明确后填写；未确定时可以留空。',
    )
    reference_competition_project = models.ForeignKey(
        'competitions.CompetitionProject',
        verbose_name='参考赛项',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reference_training_cycles',
        help_text='目标未确定时，可先参考上一届或模拟赛项。',
    )
    description = models.TextField('描述', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('最后更新时间', auto_now=True)

    class Meta:
        verbose_name = '备赛周期'
        verbose_name_plural = '备赛周期'
        ordering = ['-start_date', 'name']

    def clean(self):
        super().clean()
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError({'end_date': '结束日期不能早于开始日期。'})
        if self.project_id and self.module_set_id and self.module_set.project_id != self.project_id:
            raise ValidationError({'module_set': '模块标准集必须属于当前竞赛项目。'})
        if (
            self.project_id
            and self.primary_competition_project_id
            and self.primary_competition_project.project_id != self.project_id
        ):
            raise ValidationError({'primary_competition_project': '主目标赛项必须属于当前竞赛项目。'})
        if (
            self.project_id
            and self.reference_competition_project_id
            and self.reference_competition_project.project_id != self.project_id
        ):
            raise ValidationError({'reference_competition_project': '参考赛项必须属于当前竞赛项目。'})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.name} ({self.code})'
