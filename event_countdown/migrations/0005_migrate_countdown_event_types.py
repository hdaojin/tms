from django.db import migrations


EVENT_TYPE_DEFAULTS = (
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


def forwards(apps, schema_editor):
    CountdownEvent = apps.get_model('event_countdown', 'CountdownEvent')
    CountdownEventType = apps.get_model('event_countdown', 'CountdownEventType')
    database = schema_editor.connection.alias
    types_by_code = {}

    for code, name, order in EVENT_TYPE_DEFAULTS:
        obj, _created = CountdownEventType.objects.using(database).get_or_create(
            code=code,
            defaults={'name': name, 'order': order, 'is_active': True},
        )
        types_by_code[code] = obj

    values = CountdownEvent.objects.using(database).values_list('event_type', flat=True).distinct()
    for raw_value in values:
        code = raw_value or ''
        event_type = types_by_code.get(code)
        if event_type is None:
            event_type, _created = CountdownEventType.objects.using(database).get_or_create(
                code=code,
                defaults={
                    'name': code or '历史空值',
                    'description': '从历史倒计时事件类型保留。',
                    'order': 9000,
                    'is_active': False,
                },
            )
            types_by_code[code] = event_type
        CountdownEvent.objects.using(database).filter(event_type=raw_value).update(
            event_type_config_id=event_type.pk
        )

    if CountdownEvent.objects.using(database).filter(event_type_config__isnull=True).exists():
        raise RuntimeError('倒计时事件类型数据迁移未能映射全部历史记录。')


def backwards(apps, schema_editor):
    CountdownEvent = apps.get_model('event_countdown', 'CountdownEvent')
    database = schema_editor.connection.alias
    for event in CountdownEvent.objects.using(database).select_related('event_type_config').iterator():
        event.event_type = event.event_type_config.code
        event.save(update_fields=['event_type'])


class Migration(migrations.Migration):
    dependencies = [('event_countdown', '0004_create_countdown_event_type')]
    operations = [migrations.RunPython(forwards, backwards)]
