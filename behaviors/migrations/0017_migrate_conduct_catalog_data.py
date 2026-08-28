from django.db import migrations


SEVERITY_NAMES = {
    'MINOR': '轻微',
    'MODERATE': '一般',
    'SEVERE': '严重',
    'CRITICAL': '特别严重',
}

RULE_LABELS = {
    ('REWARD', 'MINOR'): '鼓励',
    ('REWARD', 'MODERATE'): '表扬',
    ('REWARD', 'SEVERE'): '嘉奖',
    ('REWARD', 'CRITICAL'): '特别嘉奖',
    ('PENALTY', 'MINOR'): '轻微',
    ('PENALTY', 'MODERATE'): '一般',
    ('PENALTY', 'SEVERE'): '严重',
    ('PENALTY', 'CRITICAL'): '特别严重',
}

CATEGORY_CODES = {
    ('PENALTY', '考勤'): 'attendance',
    ('REWARD', '竞赛获奖'): 'competition_award',
}

ITEM_CODES = {
    ('attendance', '迟到'): 'late',
    ('attendance', '早退'): 'early_leave',
    ('attendance', '旷课'): 'absence',
    ('competition_award', '市级'): 'municipal',
    ('competition_award', '省级'): 'provincial',
    ('competition_award', '国家级'): 'national',
    ('competition_award', '世界级'): 'world',
}


def _severity_for_code(ConductSeverity, database, cache, raw_value):
    code = raw_value if raw_value is not None else ''
    if code not in cache:
        name = SEVERITY_NAMES.get(code, code or '历史空值')
        severity, _created = ConductSeverity.objects.using(database).get_or_create(
            code=code,
            defaults={
                'name': name,
                'description': '' if code in SEVERITY_NAMES else '从历史奖惩严重程度保留。',
                'is_active': code in SEVERITY_NAMES,
            },
        )
        cache[code] = severity
    return cache[code]


def forwards(apps, schema_editor):
    ConductCategory = apps.get_model('behaviors', 'ConductCategory')
    ConductItem = apps.get_model('behaviors', 'ConductItem')
    ConductRecord = apps.get_model('behaviors', 'ConductRecord')
    ConductSeverity = apps.get_model('behaviors', 'ConductSeverity')
    ConductSeverityRule = apps.get_model('behaviors', 'ConductSeverityRule')
    database = schema_editor.connection.alias
    severity_cache = {}

    for code in SEVERITY_NAMES:
        _severity_for_code(ConductSeverity, database, severity_cache, code)

    rule_values = ConductSeverityRule.objects.using(database).values_list('severity', flat=True).distinct()
    record_values = ConductRecord.objects.using(database).values_list('severity', flat=True).distinct()
    for raw_value in set(rule_values) | set(record_values):
        _severity_for_code(ConductSeverity, database, severity_cache, raw_value)

    for rule in ConductSeverityRule.objects.using(database).iterator():
        severity = _severity_for_code(
            ConductSeverity,
            database,
            severity_cache,
            rule.severity,
        )
        rule.severity_config_id = severity.pk
        rule.label = RULE_LABELS.get((rule.nature, severity.code), severity.name)
        rule.is_default = rule.nature in {'REWARD', 'PENALTY'} and severity.code == 'MODERATE'
        rule.save(update_fields=['severity_config', 'label', 'is_default'])

    for record in ConductRecord.objects.using(database).iterator():
        severity = _severity_for_code(
            ConductSeverity,
            database,
            severity_cache,
            record.severity,
        )
        record.severity_config_id = severity.pk
        record.save(update_fields=['severity_config'])

    categories_by_id = {}
    for category in ConductCategory.objects.using(database).order_by('pk').iterator():
        category.code = CATEGORY_CODES.get(
            (category.nature, category.name),
            f'legacy-category-{category.pk}',
        )
        category.save(update_fields=['code'])
        categories_by_id[category.pk] = category.code

    for item in ConductItem.objects.using(database).order_by('pk').iterator():
        category_code = categories_by_id[item.category_id]
        item.code = ITEM_CODES.get(
            (category_code, item.name),
            f'legacy-item-{item.pk}',
        )
        item.save(update_fields=['code'])

    if ConductSeverityRule.objects.using(database).filter(severity_config__isnull=True).exists():
        raise RuntimeError('奖惩严重程度规则数据迁移未能映射全部历史记录。')
    if ConductRecord.objects.using(database).filter(severity_config__isnull=True).exists():
        raise RuntimeError('奖惩记录严重程度数据迁移未能映射全部历史记录。')
    if ConductCategory.objects.using(database).filter(code__isnull=True).exists():
        raise RuntimeError('奖惩分类代码数据迁移未能映射全部历史记录。')
    if ConductItem.objects.using(database).filter(code__isnull=True).exists():
        raise RuntimeError('奖惩事项代码数据迁移未能映射全部历史记录。')


def backwards(apps, schema_editor):
    ConductRecord = apps.get_model('behaviors', 'ConductRecord')
    ConductSeverityRule = apps.get_model('behaviors', 'ConductSeverityRule')
    database = schema_editor.connection.alias

    for rule in ConductSeverityRule.objects.using(database).select_related('severity_config').iterator():
        rule.severity = rule.severity_config.code
        rule.save(update_fields=['severity'])
    for record in ConductRecord.objects.using(database).select_related('severity_config').iterator():
        record.severity = record.severity_config.code
        record.save(update_fields=['severity'])


class Migration(migrations.Migration):
    dependencies = [('behaviors', '0016_create_conduct_catalog_fields')]
    operations = [migrations.RunPython(forwards, backwards)]
