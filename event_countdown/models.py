from django.db import models

from .themes import DEFAULT_THEME_KEY, THEME_CHOICES


class CountdownEvent(models.Model):
    class EventType(models.TextChoices):
        WORLDSKILLS = 'worldskills', '世界技能大赛'
        NATIONAL = 'national', '全国技能大赛'
        PROVINCIAL = 'provincial', '省级技能大赛'
        MUNICIPAL = 'municipal', '市级技能大赛'
        SCHOOL = 'school', '校内比赛'
        TRAINING = 'training', '集训活动'
        EXAM = 'exam', '考核测评'
        MEETING = 'meeting', '会议活动'
        OTHER = 'other', '其他活动'

    name = models.CharField('事件名称', max_length=120)
    slug = models.SlugField('访问标识', max_length=120, unique=True, blank=True, null=True)
    subtitle = models.CharField('副标题', max_length=200, blank=True)
    event_type = models.CharField(
        '事件类型',
        max_length=20,
        choices=EventType.choices,
        default=EventType.OTHER,
    )
    project_name = models.CharField('项目名称', max_length=120, blank=True)
    project_english_name = models.CharField('项目英文名称', max_length=160, blank=True)
    target_at = models.DateTimeField('目标时间')
    location = models.CharField('地点', max_length=120, blank=True, default='')
    theme = models.CharField('主题风格', max_length=50, choices=THEME_CHOICES, default=DEFAULT_THEME_KEY, blank=True)
    description = models.TextField('说明文字', blank=True)
    countdown_prefix = models.CharField(
        '倒计时前缀',
        max_length=50,
        default='距离开始还有',
        blank=True,
        help_text='显示在倒计时数字上方或附近的提示文字，例如：距离开幕还有、距离比赛开始还有。',
    )
    finished_message = models.CharField(
        '结束提示语',
        max_length=100,
        default='活动已经开始',
        blank=True,
        help_text='当倒计时目标时间已到或已过时显示的提示文字。',
    )
    is_active = models.BooleanField('启用', default=True)
    display_order = models.PositiveIntegerField('显示排序', default=10)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '倒计时事件'
        verbose_name_plural = '倒计时事件'
        ordering = ['display_order', 'target_at']

    def __str__(self):
        return self.name
