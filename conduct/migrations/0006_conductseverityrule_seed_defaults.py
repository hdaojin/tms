from decimal import Decimal

from django.db import migrations


DEFAULT_RULES = [
    ('REWARD', 'MINOR', Decimal('1.00'), 10),
    ('REWARD', 'MODERATE', Decimal('2.00'), 20),
    ('REWARD', 'SEVERE', Decimal('3.00'), 30),
    ('REWARD', 'CRITICAL', Decimal('5.00'), 40),
    ('PENALTY', 'MINOR', Decimal('-1.00'), 10),
    ('PENALTY', 'MODERATE', Decimal('-2.00'), 20),
    ('PENALTY', 'SEVERE', Decimal('-3.00'), 30),
    ('PENALTY', 'CRITICAL', Decimal('-5.00'), 40),
]


def seed_default_rules(apps, schema_editor):
    ConductSeverityRule = apps.get_model('conduct', 'ConductSeverityRule')

    for nature, severity, score, order in DEFAULT_RULES:
        ConductSeverityRule.objects.update_or_create(
            nature=nature,
            severity=severity,
            defaults={
                'score': score,
                'order': order,
            },
        )


def remove_default_rules(apps, schema_editor):
    ConductSeverityRule = apps.get_model('conduct', 'ConductSeverityRule')

    for nature, severity, _, _ in DEFAULT_RULES:
        ConductSeverityRule.objects.filter(
            nature=nature,
            severity=severity,
        ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('conduct', '0005_alter_conductitem_options_remove_conductitem_score_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_default_rules, remove_default_rules),
    ]
