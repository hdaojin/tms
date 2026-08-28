from decimal import Decimal

from django.core.exceptions import ValidationError

from .models import (
    ConductCategory,
    ConductItem,
    ConductNature,
    ConductSeverity,
    ConductSeverityRule,
)


SEVERITY_DEFAULTS = (
    ('MINOR', '轻微'),
    ('MODERATE', '一般'),
    ('SEVERE', '严重'),
    ('CRITICAL', '特别严重'),
)

RULE_DEFAULTS = (
    (ConductNature.REWARD, 'MINOR', '鼓励', Decimal('0.00'), 10, False),
    (ConductNature.REWARD, 'MODERATE', '表扬', Decimal('1.00'), 20, True),
    (ConductNature.REWARD, 'SEVERE', '嘉奖', Decimal('2.00'), 30, False),
    (ConductNature.REWARD, 'CRITICAL', '特别嘉奖', Decimal('3.00'), 40, False),
    (ConductNature.PENALTY, 'MINOR', '轻微', Decimal('0.00'), 10, False),
    (ConductNature.PENALTY, 'MODERATE', '一般', Decimal('1.00'), 20, True),
    (ConductNature.PENALTY, 'SEVERE', '严重', Decimal('2.00'), 30, False),
    (ConductNature.PENALTY, 'CRITICAL', '特别严重', Decimal('3.00'), 40, False),
)

CATEGORY_DEFAULTS = (
    ('attendance', ConductNature.PENALTY, '考勤', '考勤类惩罚事项', 10),
    ('competition_award', ConductNature.REWARD, '竞赛获奖', '竞赛获奖类奖励事项', 10),
)

ITEM_DEFAULTS = (
    ('attendance', 'late', '迟到', Decimal('-1.00'), '考勤类惩罚事项：迟到。'),
    ('attendance', 'early_leave', '早退', Decimal('-1.00'), '考勤类惩罚事项：早退。'),
    ('attendance', 'absence', '旷课', Decimal('-5.00'), '考勤类惩罚事项：旷课。'),
    ('competition_award', 'municipal', '市级', Decimal('1.00'), '竞赛获奖类奖励事项：市级。'),
    ('competition_award', 'provincial', '省级', Decimal('5.00'), '竞赛获奖类奖励事项：省级。'),
    ('competition_award', 'national', '国家级', Decimal('10.00'), '竞赛获奖类奖励事项：国家级。'),
    ('competition_award', 'world', '世界级', Decimal('20.00'), '竞赛获奖类奖励事项：世界级。'),
)


def _record_stat(stats, created):
    stats['created'] += int(created)
    stats['existing'] += int(not created)


def bootstrap_defaults():
    stats = {'created': 0, 'existing': 0}
    severities = {}
    for code, name in SEVERITY_DEFAULTS:
        if ConductSeverity.objects.filter(name=name).exclude(code=code).exists():
            raise ValidationError(f'严重程度“{name}”已被其他代码占用，请先人工修正稳定代码。')
        severity, created = ConductSeverity.objects.get_or_create(
            code=code,
            defaults={'name': name},
        )
        severities[code] = severity
        _record_stat(stats, created)

    for nature, severity_code, label, multiplier, order, is_default in RULE_DEFAULTS:
        severity = severities[severity_code]
        effective_default = (
            is_default
            and severity.is_active
            and not ConductSeverityRule.objects.filter(
                nature=nature,
                is_default=True,
            ).exists()
        )
        _rule, created = ConductSeverityRule.objects.get_or_create(
            nature=nature,
            severity=severity,
            defaults={
                'label': label,
                'multiplier': multiplier,
                'order': order,
                'is_default': effective_default,
            },
        )
        _record_stat(stats, created)

    categories = {}
    for code, nature, name, description, order in CATEGORY_DEFAULTS:
        if ConductCategory.objects.filter(nature=nature, name=name).exclude(code=code).exists():
            raise ValidationError(f'奖惩分类“{name}”已被其他代码占用，请先人工修正稳定代码。')
        category, created = ConductCategory.objects.get_or_create(
            code=code,
            defaults={
                'nature': nature,
                'name': name,
                'description': description,
                'order': order,
            },
        )
        if category.nature != nature:
            raise ValidationError(f'奖惩分类代码“{code}”的性质与出厂定义冲突，请先人工修正。')
        categories[code] = category
        _record_stat(stats, created)

    for category_code, code, name, default_score, description in ITEM_DEFAULTS:
        category = categories[category_code]
        if ConductItem.objects.filter(category=category, name=name).exclude(code=code).exists():
            raise ValidationError(f'奖惩事项“{category.name} / {name}”已被其他代码占用，请先人工修正稳定代码。')
        _item, created = ConductItem.objects.get_or_create(
            category=category,
            code=code,
            defaults={
                'name': name,
                'default_score': default_score,
                'description': description,
            },
        )
        _record_stat(stats, created)

    return stats
