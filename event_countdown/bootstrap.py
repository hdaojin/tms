from django.core.exceptions import ValidationError

from .models import CountdownEventType


COUNTDOWN_EVENT_TYPE_DEFAULTS = (
    ('worldskills', '世界技能大赛', 10),
    ('national', '全国技能大赛', 20),
    ('provincial', '省级技能大赛', 30),
    ('municipal', '市级技能大赛', 40),
    ('school', '校内比赛', 50),
    ('training', '集训活动', 60),
    ('exam', '考核测评', 70),
    ('meeting', '会议活动', 80),
    ('other', '其他活动', 90),
)


def bootstrap_defaults():
    created_count = 0
    existing_count = 0
    for code, name, order in COUNTDOWN_EVENT_TYPE_DEFAULTS:
        if CountdownEventType.objects.filter(name=name).exclude(code=code).exists():
            raise ValidationError(f'倒计时事件类型“{name}”已被其他代码占用，请先人工修正稳定代码。')
        _event_type, created = CountdownEventType.objects.get_or_create(
            code=code,
            defaults={'name': name, 'order': order},
        )
        created_count += int(created)
        existing_count += int(not created)
    return {'created': created_count, 'existing': existing_count}
