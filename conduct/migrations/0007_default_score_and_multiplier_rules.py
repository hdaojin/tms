from decimal import Decimal

from django.db import migrations, models


DEFAULT_MULTIPLIERS = {
    'MINOR': Decimal('0.00'),
    'MODERATE': Decimal('1.00'),
    'SEVERE': Decimal('2.00'),
    'CRITICAL': Decimal('3.00'),
}


def migrate_to_default_score_and_multiplier(apps, schema_editor):
    ConductCategory = apps.get_model('conduct', 'ConductCategory')
    ConductItem = apps.get_model('conduct', 'ConductItem')
    ConductSeverityRule = apps.get_model('conduct', 'ConductSeverityRule')

    category_natures = dict(ConductCategory.objects.values_list('id', 'nature'))

    reward_baseline = ConductSeverityRule.objects.filter(
        nature='REWARD',
        severity='MODERATE',
    ).values_list('multiplier', flat=True).first()
    penalty_baseline = ConductSeverityRule.objects.filter(
        nature='PENALTY',
        severity='MODERATE',
    ).values_list('multiplier', flat=True).first()

    if reward_baseline is None or reward_baseline <= 0:
        reward_baseline = Decimal('2.00')
    if penalty_baseline is None or penalty_baseline >= 0:
        penalty_baseline = Decimal('-2.00')

    for item in ConductItem.objects.all().iterator():
        nature = category_natures.get(item.category_id)
        if nature == 'REWARD':
            item.default_score = reward_baseline
        elif nature == 'PENALTY':
            item.default_score = penalty_baseline
        else:
            item.default_score = Decimal('0.00')

        item.save(update_fields=['default_score'])

    for order, severity in enumerate(['MINOR', 'MODERATE', 'SEVERE', 'CRITICAL'], start=1):
        multiplier = DEFAULT_MULTIPLIERS[severity]
        for nature in ['REWARD', 'PENALTY']:
            ConductSeverityRule.objects.update_or_create(
                nature=nature,
                severity=severity,
                defaults={
                    'multiplier': multiplier,
                    'order': order * 10,
                },
            )


class Migration(migrations.Migration):

    dependencies = [
        ('conduct', '0006_conductseverityrule_seed_defaults'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='conductseverityrule',
            options={
                'ordering': ['nature', 'order', 'severity'],
                'verbose_name': '严重程度系数规则',
                'verbose_name_plural': '严重程度系数规则',
            },
        ),
        migrations.AddField(
            model_name='conductitem',
            name='default_score',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), help_text='一般情形下的基础分值。当前分值 = 默认分值 × 严重程度系数。', max_digits=6, verbose_name='默认分值'),
            preserve_default=False,
        ),
        migrations.RenameField(
            model_name='conductseverityrule',
            old_name='score',
            new_name='multiplier',
        ),
        migrations.AlterField(
            model_name='conductrecord',
            name='severity',
            field=models.CharField(choices=[('MINOR', '轻微'), ('MODERATE', '一般'), ('SEVERE', '严重'), ('CRITICAL', '特别严重')], default='MODERATE', help_text='当前分值 = 事项默认分值 × 严重程度系数', max_length=20, verbose_name='严重程度'),
        ),
        migrations.AlterField(
            model_name='conductseverityrule',
            name='multiplier',
            field=models.DecimalField(decimal_places=2, help_text='当前分值 = 事项默认分值 × 严重程度系数。', max_digits=4, verbose_name='系数'),
        ),
        migrations.RunPython(
            migrate_to_default_score_and_multiplier,
            migrations.RunPython.noop,
        ),
    ]
